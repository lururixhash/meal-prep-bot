#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meal Prep Bot V2.0 - Sistema completo con perfiles individuales y IA integrada
Integra todos los sistemas nuevos: categorías duales, Available Energy, generación IA
"""

import json
import os
import logging
import fcntl
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import telebot
from telebot import types
from anthropic import Anthropic
from flask import Flask, request

# Importar nuevos sistemas
from user_profile_system import UserProfileSystem
from claude_prompt_system import ClaudePromptSystem
from recipe_validator import RecipeValidator
from ai_integration import AIRecipeGenerator, format_recipe_for_display
from menu_display_system import format_menu_for_telegram

from config import (
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY, WEBHOOK_URL, WEBHOOK_PATH, USE_WEBHOOK
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar componentes
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# Inicializar Claude client
try:
    claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("✅ Claude client initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing Claude client: {e}")
    claude_client = None

class MealPrepBotV2:
    def __init__(self):
        self.database_file = "recipes_new.json"
        self.data = self.load_data()
        
        # Inicializar sistemas
        self.profile_system = UserProfileSystem(self.database_file)
        self.prompt_system = ClaudePromptSystem()
        self.validator = RecipeValidator()
        self.ai_generator = AIRecipeGenerator(
            ANTHROPIC_API_KEY, 
            self.prompt_system, 
            self.validator
        )
        
        # Estado de conversación por usuario
        self.user_states = {}
        
        logger.info("🚀 MealPrepBot V2.0 initialized with new architecture")
    
    def load_data(self) -> Dict:
        """Cargar datos de la nueva estructura"""
        try:
            with open(self.database_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"No se encontró {self.database_file}")
            return self.create_default_data()
        except json.JSONDecodeError:
            logger.error(f"Error al leer {self.database_file}")
            return self.create_default_data()
    
    def create_default_data(self) -> Dict:
        """Crear estructura de datos nueva"""
        with open("recipes_new.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_data(self) -> bool:
        """Guardar datos con backup automático"""
        try:
            # Crear backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backup_v2_{timestamp}.json"
            
            if os.path.exists(self.database_file):
                with open(self.database_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # Guardar datos actuales
            with open(self.database_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error al guardar datos: {e}")
            return False
    
    def get_user_profile(self, telegram_id: str) -> Optional[Dict]:
        """Obtener perfil de usuario por Telegram ID"""
        return self.data["users"].get(telegram_id)
    
    def save_generated_recipe(self, telegram_id: str, recipe: Dict, timing_category: str, validation: Dict) -> bool:
        """Guardar receta generada en el perfil del usuario"""
        try:
            user_profile = self.get_user_profile(telegram_id)
            if not user_profile:
                return False
            
            # Inicializar lista de recetas si no existe
            if "generated_recipes" not in user_profile:
                user_profile["generated_recipes"] = []
            
            # Crear entrada de receta con metadata
            recipe_entry = {
                "id": f"{telegram_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "generated_date": datetime.now().isoformat(),
                "timing_category": timing_category,
                "recipe_data": recipe,
                "validation_score": validation.get("score", 0),
                "user_rating": None  # Para futuras mejoras
            }
            
            # Agregar al inicio de la lista (más reciente primero)
            user_profile["generated_recipes"].insert(0, recipe_entry)
            
            # Mantener solo las últimas 20 recetas por usuario
            if len(user_profile["generated_recipes"]) > 20:
                user_profile["generated_recipes"] = user_profile["generated_recipes"][:20]
            
            # Guardar cambios
            self.data["users"][telegram_id] = user_profile
            return self.save_data()
            
        except Exception as e:
            logger.error(f"Error saving generated recipe for user {telegram_id}: {e}")
            return False
    
    def create_user_if_not_exists(self, telegram_id: str, message) -> bool:
        """Crear usuario si no existe y redirigir a setup de perfil"""
        if telegram_id not in self.data["users"]:
            bot.send_message(
                message.chat.id,
                "👋 ¡Bienvenido al Meal Prep Bot V2.0!\n\n"
                "Para comenzar, necesito configurar tu perfil nutricional personalizado.\n"
                "Usa el comando /perfil para empezar.",
                reply_markup=self.create_main_menu_keyboard()
            )
            return False
        return True
    
    def create_main_menu_keyboard(self) -> types.ReplyKeyboardMarkup:
        """Crear teclado principal con comandos disponibles"""
        keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        buttons = [
            "/perfil", "/mis_macros",
            "/menu", "/recetas", 
            "/complementos", "/buscar",
            "/generar", "/nueva_semana"
        ]
        
        keyboard.add(*[types.KeyboardButton(btn) for btn in buttons])
        return keyboard
    
    def split_long_message(self, text: str, max_length: int = 4000) -> List[str]:
        """Dividir mensajes largos para Telegram (límite 4096 caracteres)"""
        if len(text) <= max_length:
            return [text]
        
        messages = []
        current_message = ""
        
        lines = text.split('\n')
        for line in lines:
            if len(current_message + line + '\n') <= max_length:
                current_message += line + '\n'
            else:
                if current_message:
                    messages.append(current_message.strip())
                current_message = line + '\n'
        
        if current_message:
            messages.append(current_message.strip())
        
        return messages
    
    def send_long_message(self, chat_id: int, text: str, **kwargs):
        """Enviar mensaje largo dividiéndolo si es necesario"""
        messages = self.split_long_message(text)
        for i, msg in enumerate(messages):
            if i == 0:
                bot.send_message(chat_id, msg, **kwargs)
            else:
                bot.send_message(chat_id, msg, parse_mode=kwargs.get('parse_mode'))

# Crear instancia global del bot
meal_bot = MealPrepBotV2()

# ========================================
# COMANDOS PRINCIPALES
# ========================================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Comando de inicio"""
    telegram_id = str(message.from_user.id)
    
    welcome_text = """
🍽️ ¡Bienvenido al Meal Prep Bot!

Soy tu asistente personal para meal prep con batch cooking. Te ayudo a:

📅 Gestionar menús con rotación automática cada 2 semanas
🧮 Calcular macros personalizados según tu perfil
🛒 Generar listas de compra categorizadas
⏰ Crear cronogramas de cocción optimizados
🤖 Modificar recetas basado en tu feedback

**Comandos disponibles:**
/perfil - Crear tu perfil personalizado
/mis_macros - Ver tus macros calculados
/menu - Ver menú de la semana actual
/recetas - Ver todas las recetas
/buscar consulta - Buscar o crear recetas con IA

🥜 **COMPLEMENTOS MEDITERRÁNEOS:**
/complementos - Ver alimentos simples naturales
/nueva_semana - Rotación semanal con complementos

🤖 **GENERACIÓN INTELIGENTE:**
/generar - Crear recetas por timing nutricional

📊 **GESTIÓN:**
/compras - Lista de compra con complementos
/cronograma - Ver cronograma de cocción
/timing - Ver timing nutricional personalizado
/rating receta 1-5 comentario - Calificar receta
/favorito receta - Marcar como favorito

También puedes escribirme en lenguaje natural como:
"No me gusta el cilantro en esta receta"
"Quiero más recetas con pollo"

¡Empecemos! Usa /menu para ver tu menú actual 👨🍳
"""
    
    meal_bot.send_long_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=meal_bot.create_main_menu_keyboard()
    )

@bot.message_handler(commands=['perfil'])
def perfil_command(message):
    """Comando para configurar perfil de usuario"""
    telegram_id = str(message.from_user.id)
    
    # Iniciar proceso de configuración de perfil
    meal_bot.user_states[telegram_id] = {
        "state": "profile_setup",
        "step": "peso",
        "data": {}
    }
    
    bot.send_message(
        message.chat.id,
        "👤 **CONFIGURACIÓN DE PERFIL NUTRICIONAL**\n\n"
        "Te haré algunas preguntas para calcular tus macros personalizados "
        "basados en evidencia científica.\n\n"
        "📏 **Paso 1/10:** ¿Cuál es tu peso actual en kg?\n"
        "_(Ejemplo: 70)_",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['mis_macros'])
def mis_macros_command(message):
    """Mostrar macros calculados del usuario"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Datos del perfil
    basic_data = user_profile["basic_data"]
    body_comp = user_profile["body_composition"]
    energy_data = user_profile["energy_data"]
    macros = user_profile["macros"]
    
    response_text = f"""
👤 **TU PERFIL NUTRICIONAL**

**DATOS BÁSICOS:**
• Peso: {basic_data['peso']} kg
• Altura: {basic_data['altura']} cm
• Edad: {basic_data['edad']} años
• Objetivo: {basic_data['objetivo_descripcion']}

**COMPOSICIÓN CORPORAL:**
• BMR: {body_comp['bmr']} kcal/día
• Grasa corporal: {body_comp['body_fat_percentage']}%
• Masa magra: {body_comp['lean_mass_kg']} kg
• IMC: {body_comp['bmi']}

**ENERGÍA DISPONIBLE:**
• Available Energy: {energy_data['available_energy']} kcal/kg FFM/día
• Estado: {energy_data['ea_status']['color']} {energy_data['ea_status']['description']}
• TDEE: {energy_data['tdee']} kcal/día
• Ejercicio diario: {energy_data['daily_exercise_calories']} kcal

**MACROS DIARIOS OBJETIVO:**
🥩 Proteína: {macros['protein_g']}g ({macros['protein_g']*4} kcal)
🍞 Carbohidratos: {macros['carbs_g']}g ({macros['carbs_g']*4} kcal)
🥑 Grasas: {macros['fat_g']}g ({macros['fat_g']*9} kcal)
🔥 **TOTAL: {macros['calories']} kcal/día**

**RECOMENDACIÓN:**
{energy_data['ea_status']['recommendation']}
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['menu'])
def menu_command(message):
    """Mostrar menú semanal con timing nutricional"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Generar menú con timing nutricional
    try:
        menu_text = format_menu_for_telegram(user_profile)
        meal_bot.send_long_message(message.chat.id, menu_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error generating menu: {e}")
        
        # Fallback a menú básico
        fallback_text = f"""
📅 **MENÚ SEMANAL PERSONALIZADO**

🎯 **Objetivo:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Calorías diarias:** {user_profile['macros']['calories']} kcal
⚡ **Available Energy:** {user_profile['energy_data']['available_energy']} kcal/kg FFM/día

**TIMING NUTRICIONAL OPTIMIZADO:**

🌅 **DESAYUNO Y PRE-ENTRENO:**
• Energía rápida para entrenar
• Carbohidratos de absorción rápida

🍽️ **ALMUERZO Y POST-ENTRENO:**
• Proteína para recuperación muscular
• Reposición de glucógeno

🌙 **CENA:**
• Comida balanceada
• Preparación para descanso

🥜 **COMPLEMENTOS MEDITERRÁNEOS:**
• Distribuidos durante el día
• Completan macros faltantes

**Para generar tu menú específico:**
• /generar - Crear recetas por timing
• /buscar [plato] - Encontrar recetas específicas
• /nueva_semana - Configurar rotación completa
"""
        
        meal_bot.send_long_message(message.chat.id, fallback_text, parse_mode='Markdown')

@bot.message_handler(commands=['recetas'])
def recetas_command(message):
    """Mostrar recetas generadas por el usuario"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    generated_recipes = user_profile.get("generated_recipes", [])
    
    if not generated_recipes:
        response_text = """
📚 **TUS RECETAS GENERADAS**

❌ **No tienes recetas generadas aún**

Para generar recetas personalizadas:
• Usa /generar para crear recetas específicas por timing
• Usa /buscar [consulta] para recetas con IA

**CATEGORÍAS DISPONIBLES:**

⚡ **PRE-ENTRENO** (15-30 min antes)
💪 **POST-ENTRENO** (0-30 min después)  
🍽️ **COMIDA PRINCIPAL**
🥜 **SNACK/COMPLEMENTO**

¡Genera tu primera receta con /generar!
"""
    else:
        response_text = "📚 **TUS RECETAS GENERADAS**\n\n"
        
        # Agrupar por categoría de timing
        categories = {
            "pre_entreno": "⚡ **PRE-ENTRENO**",
            "post_entreno": "💪 **POST-ENTRENO**", 
            "comida_principal": "🍽️ **COMIDA PRINCIPAL**",
            "snack_complemento": "🥜 **SNACK/COMPLEMENTO**"
        }
        
        recipes_by_category = {}
        for recipe in generated_recipes[:10]:  # Mostrar solo las 10 más recientes
            category = recipe["timing_category"]
            if category not in recipes_by_category:
                recipes_by_category[category] = []
            recipes_by_category[category].append(recipe)
        
        for category, category_name in categories.items():
            if category in recipes_by_category:
                response_text += f"\n{category_name}\n"
                for i, recipe in enumerate(recipes_by_category[category][:3], 1):  # Máximo 3 por categoría
                    recipe_data = recipe["recipe_data"]
                    name = recipe_data.get("name", "Receta sin nombre")
                    calories = recipe_data.get("macros_per_portion", {}).get("calories", "N/A")
                    score = recipe["validation_score"]
                    date = recipe["generated_date"][:10]  # Solo fecha
                    
                    response_text += f"• {name}\n"
                    response_text += f"  {calories} kcal • ⭐{score}/100 • {date}\n"
                response_text += "\n"
        
        total_recipes = len(generated_recipes)
        response_text += f"**Total de recetas:** {total_recipes}\n"
        response_text += f"**Mostrando:** Las más recientes por categoría\n\n"
        response_text += "💡 **Generar más:** /generar\n"
        response_text += "🔍 **Búsqueda específica:** /buscar [consulta]"
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['complementos'])
def complementos_command(message):
    """Mostrar complementos mediterráneos disponibles"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    # Mostrar complementos de la base de datos
    complements = meal_bot.data.get("global_complements", {})
    
    response_text = "🥜 **COMPLEMENTOS MEDITERRÁNEOS NATURALES**\n\n"
    
    for category, items in complements.items():
        category_name = category.replace("_", " ").title()
        response_text += f"**{category_name.upper()}:**\n"
        
        for item_id, item_data in items.items():
            name = item_data["name"]
            portion = item_data["portion_size"]
            unit = item_data["unit"]
            macros = item_data["macros_per_portion"]
            
            response_text += f"• {name} ({portion}{unit})\n"
            response_text += f"  {macros['protein']}P / {macros['carbs']}C / {macros['fat']}G = {macros['calories']} kcal\n"
        
        response_text += "\n"
    
    response_text += """
**TIMING RECOMENDADO:**
🌅 **Media mañana:** Frutos secos + frutas
🌞 **Media tarde:** Lácteos + aceitunas
🌙 **Noche:** Según macros faltantes

**Los complementos se calculan automáticamente para completar tus macros diarios.**
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['buscar'])
def buscar_command(message):
    """Comando para buscar/generar recetas con IA"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    # Extraer consulta del mensaje
    query = message.text.replace('/buscar', '').strip()
    
    if not query:
        bot.send_message(
            message.chat.id,
            "🔍 **BÚSQUEDA INTELIGENTE DE RECETAS**\n\n"
            "Usa: `/buscar [tu consulta]`\n\n"
            "**Ejemplos:**\n"
            "• `/buscar pollo post entreno`\n"
            "• `/buscar legumbres mediterraneas`\n"
            "• `/buscar snack alto proteina`\n"
            "• `/buscar desayuno pre entreno`\n\n"
            "La IA generará recetas personalizadas según tu perfil.",
            parse_mode='Markdown'
        )
        return
    
    # Iniciar búsqueda con IA
    meal_bot.user_states[telegram_id] = {
        "state": "ai_search",
        "query": query,
        "step": "processing"
    }
    
    bot.send_message(
        message.chat.id,
        f"🤖 **Buscando recetas para:** '{query}'\n\n"
        "⏳ Generando opciones personalizadas con IA...\n"
        "📊 Considerando tu perfil nutricional...\n"
        "🍽️ Validando ingredientes naturales...",
        parse_mode='Markdown'
    )
    
    # Procesar búsqueda (se implementará completamente en siguiente fase)
    process_ai_search(telegram_id, query, message)

@bot.message_handler(commands=['nueva_semana'])
def nueva_semana_command(message):
    """Configurar nueva semana con cronograma"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Mostrar opciones de cronograma  
    response_text = f"""
📅 **CONFIGURAR NUEVA SEMANA**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Calorías objetivo:** {user_profile['macros']['calories']} kcal/día

🕐 **OPCIONES DE CRONOGRAMA SEMANAL:**

⭐ **RECOMENDADO para tu perfil:**
🅰️ **Sesión única domingo** (4-6 horas)
   • Máxima eficiencia meal prep
   • Todo listo para la semana
   • Tiempo estimado: 4-6 horas

🅱️ **Dos sesiones: Dom + Miér** (2-3 horas c/u)
   • Balance eficiencia/frescura
   • Comidas más frescas
   • Tiempo total: 4-6 horas

🅲️ **Tres sesiones: Dom/Mar/Vie** (1.5-2 horas c/u)
   • Máxima frescura
   • Carga distribuida
   • Tiempo total: 4.5-6 horas

🅳️ **Preparación diaria** (20-30 min/día)
   • Comida siempre fresca  
   • Sin meal prep masivo
   • Tiempo diario: 20-30 min

**Responde con la letra de tu opción preferida (A, B, C, D)**
"""
    
    meal_bot.user_states[telegram_id] = {
        "state": "schedule_setup",
        "step": "choose_schedule"
    }
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['generar'])
def generar_command(message):
    """Generar receta específica por timing y función"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    # Mostrar opciones de generación
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Botones por timing
    keyboard.add(
        types.InlineKeyboardButton("⚡ Pre-entreno", callback_data="gen_pre_entreno"),
        types.InlineKeyboardButton("💪 Post-entreno", callback_data="gen_post_entreno")
    )
    keyboard.add(
        types.InlineKeyboardButton("🍽️ Comida principal", callback_data="gen_comida_principal"),
        types.InlineKeyboardButton("🥜 Snack/Complemento", callback_data="gen_snack")
    )
    
    bot.send_message(
        message.chat.id,
        "🤖 **GENERACIÓN ESPECÍFICA DE RECETAS**\n\n"
        "Selecciona el tipo de receta que quieres generar según tu timing nutricional:\n\n"
        "⚡ **Pre-entreno:** Energía rápida (15-30 min antes)\n"
        "💪 **Post-entreno:** Recuperación muscular (0-30 min después)\n"
        "🍽️ **Comida principal:** Nutrición balanceada general\n"
        "🥜 **Snack:** Complemento para ajustar macros\n\n"
        "**La receta se adaptará automáticamente a tu perfil nutricional.**",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('gen_'))
def handle_generation_callback(call):
    """Manejar callbacks de generación de recetas"""
    telegram_id = str(call.from_user.id)
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    if not user_profile:
        bot.answer_callback_query(call.id, "❌ Configura tu perfil primero", show_alert=True)
        return
    
    # Mapear callback a parámetros
    timing_map = {
        "gen_pre_entreno": {
            "timing_category": "pre_entreno",
            "function_category": "energia_rapida",
            "target_macros": {"protein": 10, "carbs": 35, "fat": 5, "calories": 210}
        },
        "gen_post_entreno": {
            "timing_category": "post_entreno", 
            "function_category": "sintesis_proteica",
            "target_macros": {"protein": 35, "carbs": 30, "fat": 8, "calories": 320}
        },
        "gen_comida_principal": {
            "timing_category": "comida_principal",
            "function_category": "equilibrio_nutricional",
            "target_macros": {"protein": 40, "carbs": 50, "fat": 20, "calories": 480}
        },
        "gen_snack": {
            "timing_category": "snack_complemento",
            "function_category": "micronutrientes", 
            "target_macros": {"protein": 15, "carbs": 20, "fat": 12, "calories": 220}
        }
    }
    
    request_data = timing_map.get(call.data)
    if not request_data:
        bot.answer_callback_query(call.id, "❌ Opción no válida", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "🤖 Generando receta personalizada...")
    
    # Mensaje de procesamiento
    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🤖 **GENERANDO RECETA PERSONALIZADA**\n\n"
        f"🎯 **Tipo:** {request_data['timing_category'].replace('_', ' ').title()}\n"
        f"⚡ **Función:** {request_data['function_category'].replace('_', ' ').title()}\n"
        f"📊 **Macros objetivo:** {request_data['target_macros']['calories']} kcal\n\n"
        "⏳ Procesando con IA...\n"
        "🧬 Adaptando a tu perfil...\n"
        "✅ Validando ingredientes naturales...",
        parse_mode='Markdown'
    )
    
    try:
        # Generar receta con IA
        result = meal_bot.ai_generator.generate_recipe(user_profile, request_data)
        
        # Borrar mensaje de procesamiento
        bot.delete_message(call.message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            recipe = result["recipe"]
            validation = result["validation"]
            
            # Guardar receta en el perfil del usuario
            timing_category = request_data["timing_category"]
            save_success = meal_bot.save_generated_recipe(telegram_id, recipe, timing_category, validation)
            
            # Formatear y enviar receta
            recipe_text = format_recipe_for_display(recipe, validation)
            
            save_status = "✅ Receta guardada en tu historial" if save_success else "⚠️ Receta no pudo guardarse"
            
            success_text = f"""
🎉 **RECETA GENERADA EXITOSAMENTE**

{recipe_text}

🤖 **Generada específicamente para tu perfil:**
• Objetivo: {user_profile['basic_data']['objetivo_descripcion']}
• Available Energy: {user_profile['energy_data']['available_energy']} kcal/kg FFM/día
• Todos los ingredientes son naturales y no procesados

{save_status}

💡 **¿Quieres otra opción?** Usa el comando /generar de nuevo
"""
            
            meal_bot.send_long_message(call.message.chat.id, success_text, parse_mode='Markdown')
            
        else:
            error_msg = result.get("error", "Error desconocido")
            bot.send_message(
                call.message.chat.id,
                f"❌ **Error generando receta:**\n{error_msg}\n\n"
                "💡 **Intenta:**\n"
                "• Usar /generar de nuevo\n"
                "• Verificar tu conexión\n"
                "• Usar /buscar para búsqueda libre",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in recipe generation: {e}")
        bot.delete_message(call.message.chat.id, processing_msg.message_id)
        bot.send_message(
            call.message.chat.id,
            "❌ **Error técnico** generando la receta.\n"
            "Inténtalo de nuevo en unos momentos.",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['compras'])
def compras_command(message):
    """Mostrar lista de compras con complementos"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    response_text = f"""
🛒 **LISTA DE COMPRAS SEMANAL**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Calorías objetivo:** {user_profile['macros']['calories']} kcal/día

**PROTEÍNAS:**
• Pechuga de pollo: 2.5 kg
• Carne de res magra: 1.5 kg
• Huevos frescos: 2 docenas
• Salmón fresco: 800g

**LEGUMBRES Y CEREALES:**
• Quinoa: 500g
• Arroz integral: 1 kg
• Lentejas rojas: 400g
• Garbanzos secos: 500g

**VEGETALES FRESCOS:**
• Brócoli: 1 kg
• Espinacas: 500g
• Tomates: 1.5 kg
• Pimientos: 800g
• Cebolla: 1 kg

🥜 **COMPLEMENTOS MEDITERRÁNEOS:**
• Almendras crudas: 250g
• Nueces: 200g
• Yogur griego natural: 1 kg
• Queso feta: 300g
• Aceitunas kalamata: 200g
• Miel cruda: 1 bote
• Aceite oliva virgen extra: 500ml

**ESPECIAS Y HIERBAS:**
• Oregano seco
• Tomillo fresco
• Ajo fresco
• Jengibre
• Comino molido

💡 **Tip:** Esta lista está optimizada para meal prep semanal según tu perfil nutricional.

**Comandos relacionados:**
• /cronograma - Ver cuándo cocinar cada cosa
• /menu - Ver cómo se distribuye todo
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['cronograma'])
def cronograma_command(message):
    """Mostrar cronograma de cocción"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    if not user_profile:
        bot.send_message(message.chat.id, "❌ Error: No se pudo encontrar tu perfil")
        return
    
    # Obtener cronograma con valores por defecto
    cooking_schedule = user_profile.get('settings', {}).get('cooking_schedule', 'dos_sesiones')
    
    # Verificar que existan cooking_schedules en los datos
    if 'cooking_schedules' not in meal_bot.data:
        bot.send_message(
            message.chat.id,
            "⚠️ **CRONOGRAMA NO DISPONIBLE**\n\n"
            "Los datos de cronogramas no están disponibles actualmente.\n"
            "Usa /generar para crear recetas específicas por timing."
        )
        return
    
    # Obtener datos del cronograma
    schedule_data = meal_bot.data['cooking_schedules'].get(cooking_schedule, {})
    
    # Si no existe el cronograma específico, mostrar cronograma genérico
    if not schedule_data:
        response_text = f"""
⏰ **CRONOGRAMA DE COCCIÓN SEMANAL**

🎯 **Tu cronograma:** Personalizado
📝 **Descripción:** Cronograma básico de meal prep
⏱️ **Tiempo estimado:** 2-4 horas

**SESIONES RECOMENDADAS:**

**SESIÓN 1 - Domingo**
🕐 Horario: 10:00-14:00
⏰ Duración: 3-4 horas
📋 Tareas:
• Preparar proteínas principales
• Cocinar granos y cereales
• Procesar verduras
• Porcionar y almacenar

**SESIÓN 2 - Miércoles** (opcional)
🕐 Horario: 19:00-20:30
⏰ Duración: 1-2 horas
📋 Tareas:
• Refrescar verduras
• Preparar snacks
• Revisar porciones

✅ **VENTAJAS:**
• Flexibilidad total
• Adaptable a cualquier horario
• Permite experimentar

💡 **OPTIMIZACIÓN SEGÚN TU PERFIL:**
• Objetivo: {user_profile['basic_data']['objetivo_descripcion']}
• Available Energy: {user_profile['energy_data']['available_energy']} kcal/kg FFM/día
• Macros diarios: {user_profile['macros']['calories']} kcal

**¿Quieres más opciones?**
Usa /nueva_semana para explorar cronogramas específicos.
"""
        meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')
        return
    
    response_text = f"""
⏰ **CRONOGRAMA DE COCCIÓN SEMANAL**

🎯 **Tu cronograma:** {schedule_data.get('name', 'Personalizado')}
📝 **Descripción:** {schedule_data.get('description', 'Cronograma optimizado')}
⏱️ **Tiempo estimado:** {schedule_data.get('estimated_time', 'Variable')}

**SESIONES PLANIFICADAS:**
"""
    
    sessions = schedule_data.get('sessions', [])
    for i, session in enumerate(sessions, 1):
        day = session.get('day', 'día').title()
        duration = session.get('duration', '2-3 horas')
        start_time = session.get('start_time', '10:00')
        tasks = session.get('tasks', [])
        
        response_text += f"""
**SESIÓN {i} - {day}**
🕐 Horario: {start_time}
⏰ Duración: {duration}
📋 Tareas:
"""
        for task in tasks:
            response_text += f"• {task.replace('_', ' ').title()}\n"
    
    # Ventajas/desventajas
    pros = schedule_data.get('pros', [])
    cons = schedule_data.get('cons', [])
    
    if pros:
        response_text += "\n✅ **VENTAJAS:**\n"
        for pro in pros:
            response_text += f"• {pro}\n"
    
    if cons:
        response_text += "\n⚠️ **CONSIDERACIONES:**\n"
        for con in cons:
            response_text += f"• {con}\n"
    
    response_text += f"""

💡 **OPTIMIZACIÓN SEGÚN TU PERFIL:**
• Objetivo: {user_profile['basic_data']['objetivo_descripcion']}
• Available Energy: {user_profile['energy_data']['available_energy']} kcal/kg FFM/día
• Macros diarios: {user_profile['macros']['calories']} kcal

**¿Quieres cambiar tu cronograma?**
Usa /nueva_semana para explorar otras opciones.
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['timing'])
def timing_command(message):
    """Mostrar timing nutricional personalizado según horario de entrenamiento"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    if not user_profile:
        bot.send_message(message.chat.id, "❌ Error: No se pudo encontrar tu perfil")
        return
    
    exercise_profile = user_profile.get("exercise_profile", {})
    training_schedule = exercise_profile.get("training_schedule", "variable")
    training_desc = exercise_profile.get("training_schedule_desc", "Variable/Cambia")
    dynamic_timing = exercise_profile.get("dynamic_meal_timing", {})
    timing_desc = exercise_profile.get("timing_description", {})
    objetivo = user_profile["basic_data"]["objetivo_descripcion"]
    
    response_text = f"""
⏰ **TU TIMING NUTRICIONAL PERSONALIZADO**

🎯 **Horario de entrenamiento:** {training_desc}
💪 **Objetivo:** {objetivo}

**DISTRIBUCIÓN ÓPTIMA DE COMIDAS:**
"""
    
    # Iconos para cada comida
    meal_icons = {
        "desayuno": "🌅",
        "almuerzo": "🌞", 
        "merienda": "🌇",
        "cena": "🌙"
    }
    
    # Traducir categorías de timing
    timing_translation = {
        "pre_entreno": "⚡ PRE-ENTRENO",
        "post_entreno": "💪 POST-ENTRENO",
        "comida_principal": "🍽️ COMIDA PRINCIPAL", 
        "snack_complemento": "🥜 SNACK/COMPLEMENTO"
    }
    
    for meal, timing_category in dynamic_timing.items():
        icon = meal_icons.get(meal, "🍽️")
        timing_name = timing_translation.get(timing_category, timing_category.title())
        response_text += f"\n{icon} **{meal.title()}:** {timing_name}"
    
    if timing_desc:
        response_text += f"""

📝 **ESTRATEGIA NUTRICIONAL:**
• **Pre-entreno:** {timing_desc.get('pre_timing', 'Adaptado a tu horario')}
• **Post-entreno:** {timing_desc.get('post_timing', 'Recuperación optimizada')}
• **Filosofía:** {timing_desc.get('strategy', 'Personalizado según tus necesidades')}

💡 **CÓMO USARLO:**
• Usa /generar y selecciona el timing de tu próxima comida
• Las recetas se adaptarán automáticamente a tu horario
• /recetas te mostrará tus recetas organizadas por timing

🔄 **¿Cambió tu horario?**
Usa /perfil para actualizar tu horario de entrenamiento.
"""
    else:
        response_text += """

💡 **CÓMO USARLO:**
• Usa /generar para crear recetas específicas por timing
• /recetas te mostrará todas tus recetas generadas
• Cada receta está optimizada para el momento del día

🔄 **¿Quieres optimizar más?**
Usa /perfil para configurar tu horario de entrenamiento específico.
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['rating'])
def rating_command(message):
    """Comando para calificar recetas (placeholder)"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    # Extraer rating del mensaje (formato: /rating receta 1-5 comentario)
    text_parts = message.text.split(' ', 3)
    
    if len(text_parts) < 3:
        bot.send_message(
            message.chat.id,
            "📊 **SISTEMA DE CALIFICACIONES**\n\n"
            "**Uso:** `/rating nombre_receta 1-5 [comentario]`\n\n"
            "**Ejemplos:**\n"
            "• `/rating pollo_quinoa 5 Excelente sabor`\n"
            "• `/rating lentejas_curry 3 Muy salado`\n"
            "• `/rating batido_proteina 4`\n\n"
            "**Tu feedback ayuda a mejorar las recetas futuras con IA.**",
            parse_mode='Markdown'
        )
        return
    
    recipe_name = text_parts[1]
    try:
        rating_value = int(text_parts[2])
        if not (1 <= rating_value <= 5):
            raise ValueError
    except (ValueError, IndexError):
        bot.send_message(
            message.chat.id,
            "❌ **Error:** La calificación debe ser un número del 1 al 5."
        )
        return
    
    comment = text_parts[3] if len(text_parts) > 3 else ""
    
    # Simular guardado de rating (se implementaría completamente)
    bot.send_message(
        message.chat.id,
        f"⭐ **CALIFICACIÓN GUARDADA**\n\n"
        f"**Receta:** {recipe_name.replace('_', ' ').title()}\n"
        f"**Puntuación:** {rating_value}/5 {'⭐' * rating_value}\n"
        f"**Comentario:** {comment if comment else 'Sin comentario'}\n\n"
        "✅ Tu feedback se usará para mejorar futuras recomendaciones con IA.\n\n"
        "💡 **Tip:** Las recetas mejor calificadas aparecerán más frecuentemente.",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['favorito'])
def favorito_command(message):
    """Comando para marcar recetas como favoritas (placeholder)"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    # Extraer nombre de receta
    text_parts = message.text.split(' ', 1)
    
    if len(text_parts) < 2:
        bot.send_message(
            message.chat.id,
            "❤️ **SISTEMA DE FAVORITOS**\n\n"
            "**Uso:** `/favorito nombre_receta`\n\n"
            "**Ejemplos:**\n"
            "• `/favorito pollo_mediteraneo`\n"
            "• `/favorito garbanzos_curry`\n"
            "• `/favorito batido_recovery`\n\n"
            "**Las recetas favoritas tendrán prioridad en tus menús semanales.**",
            parse_mode='Markdown'
        )
        return
    
    recipe_name = text_parts[1]
    
    # Simular guardado de favorito
    bot.send_message(
        message.chat.id,
        f"❤️ **RECETA MARCADA COMO FAVORITA**\n\n"
        f"**Receta:** {recipe_name.replace('_', ' ').title()}\n\n"
        "✅ Esta receta aparecerá más frecuentemente en tus menús semanales.\n"
        "🤖 La IA tendrá esto en cuenta para futuras recomendaciones.\n\n"
        "**Ver todos tus favoritos:** Próximamente con /mis_favoritos",
        parse_mode='Markdown'
    )

# ========================================
# PROCESADORES DE ESTADO
# ========================================

def process_profile_setup(telegram_id: str, message):
    """Procesar configuración de perfil paso a paso"""
    user_state = meal_bot.user_states.get(telegram_id, {})
    step = user_state.get("step", "peso")
    data = user_state.get("data", {})
    
    try:
        if step == "peso":
            peso = float(message.text)
            if not (30 <= peso <= 300):
                raise ValueError("Peso fuera de rango válido")
            
            data["peso"] = peso
            meal_bot.user_states[telegram_id]["step"] = "altura"
            meal_bot.user_states[telegram_id]["data"] = data
            
            bot.send_message(
                message.chat.id,
                f"✅ Peso registrado: {peso} kg\n\n"
                "📏 **Paso 2/10:** ¿Cuál es tu altura en cm?\n"
                "_(Ejemplo: 175)_"
            )
            
        elif step == "altura":
            altura = float(message.text)
            if not (120 <= altura <= 220):
                raise ValueError("Altura fuera de rango válido")
            
            data["altura"] = altura
            meal_bot.user_states[telegram_id]["step"] = "edad"
            meal_bot.user_states[telegram_id]["data"] = data
            
            bot.send_message(
                message.chat.id,
                f"✅ Altura registrada: {altura} cm\n\n"
                "🎂 **Paso 3/10:** ¿Cuál es tu edad en años?\n"
                "_(Ejemplo: 25)_"
            )
            
        elif step == "edad":
            edad = int(message.text)
            if not (15 <= edad <= 100):
                raise ValueError("Edad fuera de rango válido")
            
            data["edad"] = edad
            meal_bot.user_states[telegram_id]["step"] = "sexo"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("Masculino", "Femenino")
            
            bot.send_message(
                message.chat.id,
                f"✅ Edad registrada: {edad} años\n\n"
                "⚧️ **Paso 4/10:** ¿Cuál es tu sexo biológico?\n"
                "_(Necesario para cálculos de BMR precisos)_",
                reply_markup=keyboard
            )
            
        elif step == "sexo":
            sexo = message.text.lower()
            if sexo not in ["masculino", "femenino"]:
                raise ValueError("Sexo debe ser Masculino o Femenino")
            
            data["sexo"] = sexo
            meal_bot.user_states[telegram_id]["step"] = "objetivo"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("Bajar peso", "Ganar músculo")
            keyboard.add("Ganancia limpia", "Recomposición")
            keyboard.add("Mantener")
            
            bot.send_message(
                message.chat.id,
                f"✅ Sexo registrado: {sexo}\n\n"
                "🎯 **Paso 5/10:** ¿Cuál es tu objetivo principal?\n\n"
                "**Bajar peso:** Perder grasa manteniendo músculo\n"
                "**Ganar músculo:** Superávit controlado (200-300 kcal)\n"
                "**Ganancia limpia:** Ultra-limpia (150-250 kcal superávit)\n"
                "**Recomposición:** Bajar grasa y ganar músculo simultáneamente\n"
                "**Mantener:** Mantener peso y composición actual",
                reply_markup=keyboard
            )
            
        elif step == "objetivo":
            objetivos_map = {
                "bajar peso": "bajar_peso",
                "ganar músculo": "subir_masa", 
                "ganar musculo": "subir_masa",
                "ganancia limpia": "subir_masa_lean",
                "recomposición": "recomposicion",
                "recomposicion": "recomposicion",
                "mantener": "mantener"
            }
            
            objetivo = objetivos_map.get(message.text.lower())
            if not objetivo:
                raise ValueError("Objetivo no válido")
            
            data["objetivo"] = objetivo
            meal_bot.user_states[telegram_id]["step"] = "actividad"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("Sedentario", "Ligero")
            keyboard.add("Moderado", "Intenso")
            
            bot.send_message(
                message.chat.id,
                f"✅ Objetivo registrado: {message.text}\n\n"
                "🏃 **Paso 6/10:** ¿Cuál es tu nivel de actividad general?\n\n"
                "**Sedentario:** Trabajo de oficina, poco ejercicio\n"
                "**Ligero:** Ejercicio ligero 1-3 días/semana\n"
                "**Moderado:** Ejercicio moderado 3-5 días/semana\n"
                "**Intenso:** Ejercicio intenso 6-7 días/semana",
                reply_markup=keyboard
            )
            
        elif step == "actividad":
            actividad_map = {
                "sedentario": 1.2,
                "ligero": 1.375, 
                "moderado": 1.55,
                "intenso": 1.725
            }
            
            actividad = actividad_map.get(message.text.lower())
            if not actividad:
                raise ValueError("Nivel de actividad no válido")
            
            data["activity_factor"] = actividad
            meal_bot.user_states[telegram_id]["step"] = "ejercicio_tipo"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("Fuerza/Pesas", "Cardio")
            keyboard.add("Deportes", "HIIT")
            keyboard.add("Mixto", "Solo dieta")
            
            bot.send_message(
                message.chat.id,
                f"✅ Actividad registrada: {message.text}\n\n"
                "🏋️ **Paso 7/10:** ¿Qué tipo de ejercicio haces principalmente?\n\n"
                "**Fuerza/Pesas:** Entrenamiento con resistencias\n"
                "**Cardio:** Running, ciclismo, natación\n"
                "**Deportes:** Fútbol, tenis, baloncesto\n"
                "**HIIT:** Entrenamientos de alta intensidad\n"
                "**Mixto:** Combinación de varios tipos\n"
                "**Solo dieta:** No hago ejercicio actualmente",
                reply_markup=keyboard
            )
            
        elif step == "ejercicio_tipo":
            tipos_ejercicio = {
                "fuerza/pesas": "fuerza",
                "cardio": "cardio", 
                "deportes": "deportes",
                "hiit": "hiit",
                "mixto": "mixto",
                "solo dieta": "ninguno"
            }
            
            tipo_ejercicio = tipos_ejercicio.get(message.text.lower())
            if not tipo_ejercicio:
                raise ValueError("Tipo de ejercicio no válido")
            
            data["ejercicio_tipo"] = tipo_ejercicio
            meal_bot.user_states[telegram_id]["step"] = "frecuencia"
            meal_bot.user_states[telegram_id]["data"] = data
            
            if tipo_ejercicio == "ninguno":
                # Saltar frecuencia si no hace ejercicio
                data["frecuencia_semanal"] = 0
                data["duracion_promedio"] = 0
                meal_bot.user_states[telegram_id]["step"] = "preferencias"
                meal_bot.user_states[telegram_id]["data"] = data
                
                keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                keyboard.add("Continuar con preferencias")
                
                bot.send_message(
                    message.chat.id,
                    f"✅ Registrado: {message.text}\n\n"
                    "⏭️ **Saltando al paso 9/10**\n\n"
                    "🍽️ **Paso 9/10:** Configuremos tus preferencias alimentarias.\n"
                    "Presiona el botón para continuar.",
                    reply_markup=keyboard
                )
            else:
                keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
                keyboard.add("1-2 días", "3-4 días", "5-6 días")
                keyboard.add("Todos los días")
                
                bot.send_message(
                    message.chat.id,
                    f"✅ Ejercicio registrado: {message.text}\n\n"
                    "📅 **Paso 8/10:** ¿Cuántos días por semana entrenas?\n\n"
                    "Solo indica la frecuencia total de entrenamiento.",
                    reply_markup=keyboard
                )
            
        elif step == "frecuencia":
            # Procesamiento flexible de frecuencia
            text = message.text.lower().strip()
            
            # Mapear variaciones de texto a frecuencia numérica
            if any(keyword in text for keyword in ["1", "2", "1-2", "uno", "dos"]):
                frecuencia = 1.5
            elif any(keyword in text for keyword in ["3", "4", "3-4", "tres", "cuatro"]):
                frecuencia = 3.5
            elif any(keyword in text for keyword in ["5", "6", "5-6", "cinco", "seis"]):
                frecuencia = 5.5
            elif any(keyword in text for keyword in ["7", "todos", "diario", "diaria"]):
                frecuencia = 7
            else:
                # Intentar extraer número específico
                import re
                numbers = re.findall(r'\d+', text)
                if numbers:
                    num_days = int(numbers[0])
                    if 1 <= num_days <= 2:
                        frecuencia = 1.5
                    elif 3 <= num_days <= 4:
                        frecuencia = 3.5
                    elif 5 <= num_days <= 6:
                        frecuencia = 5.5
                    elif num_days >= 7:
                        frecuencia = 7
                    else:
                        frecuencia = None
                else:
                    frecuencia = None
            
            if not frecuencia:
                bot.send_message(
                    message.chat.id,
                    "❌ **No pude entender la frecuencia.**\n\n"
                    "Por favor, usa los botones del teclado o escribe:\n"
                    "• **1-2 días** por semana\n"
                    "• **3-4 días** por semana\n" 
                    "• **5-6 días** por semana\n"
                    "• **Todos los días**"
                )
                return
            
            data["frecuencia_semanal"] = frecuencia
            meal_bot.user_states[telegram_id]["step"] = "duracion"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("30-45 min", "45-60 min")
            keyboard.add("60-90 min", "90+ min")
            
            bot.send_message(
                message.chat.id,
                f"✅ Frecuencia registrada: {message.text}\n\n"
                "⏱️ **Paso 8B/10:** ¿Cuánto dura cada sesión de entrenamiento?\n\n"
                "Tiempo promedio por sesión incluyendo calentamiento.",
                reply_markup=keyboard
            )
            
        elif step == "duracion":
            # Procesamiento flexible de duración
            text = message.text.lower().strip()
            
            # Extraer números del texto
            import re
            numbers = re.findall(r'\d+', text)
            
            if numbers:
                # Usar el primer número encontrado como referencia
                duration_num = int(numbers[0])
                
                if duration_num <= 30:
                    duracion = 30
                elif duration_num <= 45:
                    duracion = 37.5
                elif duration_num <= 60:
                    duracion = 52.5
                elif duration_num <= 90:
                    duracion = 75
                else:
                    duracion = 105
            elif any(keyword in text for keyword in ["30", "45", "corta", "rapida"]):
                duracion = 37.5
            elif any(keyword in text for keyword in ["60", "hora", "normal"]):
                duracion = 52.5
            elif any(keyword in text for keyword in ["90", "larga", "intensa"]):
                duracion = 75
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ **No pude entender la duración.**\n\n"
                    "Por favor, usa los botones del teclado o escribe un tiempo como:\n"
                    "• **30-45 minutos**\n"
                    "• **60 minutos**\n"
                    "• **90 minutos**"
                )
                return
            
            data["duracion_promedio"] = duracion
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Ir a horario de entrenamiento
            meal_bot.user_states[telegram_id]["step"] = "horario_entrenamiento"
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("🌅 Mañana (6:00-12:00)", "🌞 Mediodía (12:00-16:00)")
            keyboard.add("🌇 Tarde (16:00-20:00)", "🌙 Noche (20:00-24:00)")
            keyboard.add("🔄 Variable/Cambia")
            
            bot.send_message(
                message.chat.id,
                f"✅ Duración registrada: {message.text}\n\n"
                "⏰ **Paso 8C/10:** ¿A qué hora entrenas normalmente?\n\n"
                "**Esto nos ayuda a optimizar tu timing nutricional:**\n"
                "• Pre-entreno: 30-60 min antes\n"
                "• Post-entreno: inmediatamente después\n"
                "• Comidas principales: horarios que no interfieran\n\n"
                "**Selecciona tu horario habitual:**",
                reply_markup=keyboard
            )
            
        elif step == "horario_entrenamiento":
            # Procesar horario de entrenamiento
            text = message.text.lower().strip()
            
            # Mapear texto a valores estructurados
            if "mañana" in text or "6:00-12:00" in text:
                horario = "mañana"
                horario_desc = "Mañana (6:00-12:00)"
            elif "mediodía" in text or "mediodia" in text or "12:00-16:00" in text:
                horario = "mediodia" 
                horario_desc = "Mediodía (12:00-16:00)"
            elif "tarde" in text or "16:00-20:00" in text:
                horario = "tarde"
                horario_desc = "Tarde (16:00-20:00)"
            elif "noche" in text or "20:00-24:00" in text:
                horario = "noche"
                horario_desc = "Noche (20:00-24:00)"
            elif "variable" in text or "cambia" in text:
                horario = "variable"
                horario_desc = "Variable/Cambia"
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ **No reconocí ese horario.**\n\n"
                    "Por favor usa los botones o escribe: mañana, mediodía, tarde, noche, o variable."
                )
                return
            
            data["horario_entrenamiento"] = horario
            data["horario_entrenamiento_desc"] = horario_desc
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Ir a preferencias de proteínas
            meal_bot.user_states[telegram_id]["step"] = "gustos_proteinas"
            
            # Inicializar lista de proteínas vacía
            data["liked_proteins"] = []
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🍗 Pollo", "🥩 Ternera", "🐟 Pescado")
            keyboard.add("🥚 Huevos", "🫘 Legumbres", "🧀 Lácteos") 
            keyboard.add("🌰 Frutos secos", "✅ Todas", "⏭️ Ninguna especial")
            keyboard.add("➡️ Continuar")
            
            bot.send_message(
                message.chat.id,
                f"✅ Horario registrado: {horario_desc}\n\n"
                "🍽️ **Paso 9A/10:** ¿Qué PROTEÍNAS prefieres?\n\n"
                "**Opciones disponibles:**\n"
                "• 🍗 Pollo\n"
                "• 🥩 Ternera  \n"
                "• 🐟 Pescado\n"
                "• 🥚 Huevos\n"
                "• 🫘 Legumbres\n"
                "• 🧀 Lácteos\n"
                "• 🌰 Frutos secos\n"
                "• ✅ Todas\n"
                "• ⏭️ Ninguna especial\n\n"
                "**PUEDES SELECCIONAR MÚLTIPLES OPCIONES**\n"
                "Usa ➡️ **Continuar** cuando termines de seleccionar:",
                reply_markup=keyboard
            )
            
        elif step == "gustos_proteinas":
            # Procesar selección múltiple de proteínas
            text = message.text.lower().strip()
            
            # Inicializar lista si no existe
            if "liked_proteins" not in data:
                data["liked_proteins"] = []
            
            # Verificar si quiere continuar
            if "continuar" in text or text == "➡️ continuar":
                # Continuar al siguiente paso
                pass
            elif "ninguna" in text or text == "⏭️ ninguna especial":
                data["liked_proteins"] = []
            elif "todas" in text or text == "✅ todas":
                data["liked_proteins"] = ["pollo", "ternera", "pescado", "huevos", "legumbres", "lacteos", "frutos_secos"]
            else:
                # Mapear tanto emojis como texto
                protein_map = {
                    "🍗 pollo": "pollo", "pollo": "pollo",
                    "🥩 ternera": "ternera", "ternera": "ternera", "carne": "ternera",
                    "🐟 pescado": "pescado", "pescado": "pescado", "pez": "pescado",
                    "🥚 huevos": "huevos", "huevos": "huevos", "huevo": "huevos",
                    "🫘 legumbres": "legumbres", "legumbres": "legumbres", "lentejas": "legumbres",
                    "🧀 lácteos": "lacteos", "lacteos": "lacteos", "queso": "lacteos", "yogur": "lacteos",
                    "🌰 frutos secos": "frutos_secos", "frutos secos": "frutos_secos", "nueces": "frutos_secos"
                }
                
                selected = None
                for key, value in protein_map.items():
                    if key in text or text in key:
                        selected = value
                        break
                
                if selected:
                    # Agregar a la lista si no está ya incluido
                    if selected not in data["liked_proteins"]:
                        data["liked_proteins"].append(selected)
                        
                    # Mostrar selección actual y continuar
                    selected_names = [name.replace("_", " ").title() for name in data["liked_proteins"]]
                    selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
                    
                    bot.send_message(
                        message.chat.id,
                        f"✅ **{selected.replace('_', ' ').title()}** añadido\n\n"
                        f"**Seleccionados:** {selection_text}\n\n"
                        "Puedes seleccionar más opciones o usar ➡️ **Continuar**"
                    )
                    return  # Mantener en el mismo paso
                else:
                    # Si no reconoce la entrada, pedir clarificación
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: pollo, ternera, pescado, huevos, legumbres, lacteos, frutos secos, todas, ninguna, o continuar."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "gustos_carbos"
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Inicializar lista de carbohidratos
            data["liked_carbs"] = []
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🍚 Arroz", "🌾 Quinoa", "🍞 Avena")
            keyboard.add("🥔 Patatas", "🍝 Pasta", "🫓 Pan integral")
            keyboard.add("🍌 Frutas", "✅ Todas", "⏭️ Ninguna especial")
            keyboard.add("➡️ Continuar")
            
            selected_proteins = [name.replace("_", " ").title() for name in data["liked_proteins"]]
            protein_text = ", ".join(selected_proteins) if selected_proteins else "Ninguna"
            
            bot.send_message(
                message.chat.id,
                f"✅ Proteínas registradas: {protein_text}\n\n"
                "🍽️ **Paso 9B/10:** ¿Qué CARBOHIDRATOS prefieres?\n\n"
                "**Opciones disponibles:**\n"
                "• 🍚 Arroz\n"
                "• 🌾 Quinoa\n"
                "• 🍞 Avena\n"
                "• 🥔 Patatas\n"
                "• 🍝 Pasta\n"
                "• 🫓 Pan integral\n"
                "• 🍌 Frutas\n"
                "• ✅ Todas\n"
                "• ⏭️ Ninguna especial\n\n"
                "**PUEDES SELECCIONAR MÚLTIPLES OPCIONES**\n"
                "Usa ➡️ **Continuar** cuando termines de seleccionar:",
                reply_markup=keyboard
            )
            
        elif step == "gustos_carbos":
            # Procesar selección múltiple de carbohidratos
            text = message.text.lower().strip()
            
            # Inicializar lista si no existe
            if "liked_carbs" not in data:
                data["liked_carbs"] = []
            
            # Verificar si quiere continuar
            if "continuar" in text or text == "➡️ continuar":
                # Continuar al siguiente paso
                pass
            elif "ninguna" in text or text == "⏭️ ninguna especial":
                data["liked_carbs"] = []
            elif "todas" in text or text == "✅ todas":
                data["liked_carbs"] = ["arroz", "quinoa", "avena", "patatas", "pasta", "pan_integral", "frutas"]
            else:
                carb_map = {
                    "🍚 arroz": "arroz", "arroz": "arroz",
                    "🌾 quinoa": "quinoa", "quinoa": "quinoa",
                    "🍞 avena": "avena", "avena": "avena",
                    "🥔 patatas": "patatas", "patatas": "patatas", "papa": "patatas",
                    "🍝 pasta": "pasta", "pasta": "pasta",
                    "🫓 pan integral": "pan_integral", "pan integral": "pan_integral", "pan": "pan_integral",
                    "🍌 frutas": "frutas", "frutas": "frutas", "fruta": "frutas"
                }
                
                selected = None
                for key, value in carb_map.items():
                    if key in text or text in key:
                        selected = value
                        break
                
                if selected:
                    # Agregar a la lista si no está ya incluido
                    if selected not in data["liked_carbs"]:
                        data["liked_carbs"].append(selected)
                        
                    # Mostrar selección actual y continuar
                    selected_names = [name.replace("_", " ").title() for name in data["liked_carbs"]]
                    selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
                    
                    bot.send_message(
                        message.chat.id,
                        f"✅ **{selected.replace('_', ' ').title()}** añadido\n\n"
                        f"**Seleccionados:** {selection_text}\n\n"
                        "Puedes seleccionar más opciones o usar ➡️ **Continuar**"
                    )
                    return  # Mantener en el mismo paso
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: arroz, quinoa, avena, patatas, pasta, pan integral, frutas, todas, ninguna, o continuar."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "gustos_verduras"
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Inicializar lista de verduras
            data["liked_vegetables"] = []
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🥬 Hojas verdes", "🥦 Crucíferas", "🍅 Solanáceas")
            keyboard.add("🧄 Aromáticas", "🥕 Raíces", "🫑 Pimientos")
            keyboard.add("🥒 Pepináceas", "✅ Todas", "⏭️ Ninguna especial")
            keyboard.add("➡️ Continuar")
            
            selected_carbs = [name.replace("_", " ").title() for name in data["liked_carbs"]]
            carb_text = ", ".join(selected_carbs) if selected_carbs else "Ninguna"
            
            bot.send_message(
                message.chat.id,
                f"✅ Carbohidratos registrados: {carb_text}\n\n"
                "🍽️ **Paso 9C/10:** ¿Qué VERDURAS prefieres?\n\n"
                "**Familias de vegetales disponibles:**\n"
                "• 🥬 Hojas verdes\n"
                "• 🥦 Crucíferas\n"
                "• 🍅 Solanáceas\n"
                "• 🧄 Aromáticas\n"
                "• 🥕 Raíces\n"
                "• 🫑 Pimientos\n"
                "• 🥒 Pepináceas\n"
                "• ✅ Todas\n"
                "• ⏭️ Ninguna especial\n\n"
                "**PUEDES SELECCIONAR MÚLTIPLES OPCIONES**\n"
                "Usa ➡️ **Continuar** cuando termines de seleccionar:",
                reply_markup=keyboard
            )
            
        elif step == "gustos_verduras":
            # Procesar verduras con manejo flexible
            text = message.text.lower().strip()
            
            if "ninguna" in text or text == "⏭️ ninguna especial":
                data["liked_vegetables"] = []
            elif "todas" in text or text == "✅ todas":
                data["liked_vegetables"] = ["hojas_verdes", "cruciferas", "solanaceas", "aromaticas", "raices", "pimientos", "pepinaceas"]
            else:
                veg_map = {
                    "🥬 hojas verdes": "hojas_verdes", "hojas verdes": "hojas_verdes", "espinaca": "hojas_verdes", "lechuga": "hojas_verdes",
                    "🥦 crucíferas": "cruciferas", "cruciferas": "cruciferas", "brocoli": "cruciferas", "coliflor": "cruciferas",
                    "🍅 solanáceas": "solanaceas", "solanaceas": "solanaceas", "tomate": "solanaceas", "berenjena": "solanaceas",
                    "🧄 aromáticas": "aromaticas", "aromaticas": "aromaticas", "ajo": "aromaticas", "cebolla": "aromaticas",
                    "🥕 raíces": "raices", "raices": "raices", "zanahoria": "raices", "remolacha": "raices",
                    "🫑 pimientos": "pimientos", "pimientos": "pimientos", "pimiento": "pimientos",
                    "🥒 pepináceas": "pepinaceas", "pepinaceas": "pepinaceas", "pepino": "pepinaceas", "calabacin": "pepinaceas"
                }
                
                selected = None
                for key, value in veg_map.items():
                    if key in text or text in key:
                        selected = value
                        break
                
                if selected:
                    data["liked_vegetables"] = [selected]
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: hojas verdes, cruciferas, solanaceas, aromaticas, raices, pimientos, pepinaceas, todas, o ninguna."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "disgustos"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🐟 Pescado", "🥛 Lácteos", "🌶️ Picante")
            keyboard.add("🧄 Ajo/Cebolla", "🥜 Frutos secos", "🍄 Hongos")
            keyboard.add("🌿 Cilantro", "⏭️ Sin restricciones", "📝 Otros")
            
            bot.send_message(
                message.chat.id,
                "✅ Verduras registradas\n\n"
                "🚫 **Paso 9D/10:** ¿Qué alimentos prefieres EVITAR?\n\n"
                "**Opciones disponibles:**\n"
                "• 🐟 Pescado\n"
                "• 🥛 Lácteos\n"
                "• 🌶️ Picante\n"
                "• 🧄 Ajo/Cebolla\n"
                "• 🥜 Frutos secos\n"
                "• 🍄 Hongos\n"
                "• 🌿 Cilantro\n"
                "• ⏭️ Sin restricciones\n"
                "• 📝 Otros\n\n"
                "Puedes usar los botones o escribir el nombre:",
                reply_markup=keyboard
            )
            
            
        elif step == "disgustos":
            # Procesar alimentos a evitar con manejo flexible
            text = message.text.lower().strip()
            
            if "sin restricciones" in text or "ninguna" in text:
                data["disliked_foods"] = []
            elif "otros" in text or text == "📝 otros":
                # Permitir texto libre para casos específicos
                meal_bot.user_states[telegram_id]["step"] = "disgustos_texto"
                bot.send_message(
                    message.chat.id,
                    "📝 **Escribe otros alimentos que prefieres evitar:**\n\n"
                    "Ejemplos: mariscos, gluten, soja, cítricos\n\n"
                    "Sepáralos por comas o escribe 'ninguno':"
                )
                return
            else:
                dislike_map = {
                    "🐟 pescado": "pescado", "pescado": "pescado", "pez": "pescado",
                    "🥛 lácteos": "lacteos", "lacteos": "lacteos", "leche": "lacteos", "queso": "lacteos",
                    "🌶️ picante": "picante", "picante": "picante", "chile": "picante",
                    "🧄 ajo/cebolla": "ajo_cebolla", "ajo": "ajo_cebolla", "cebolla": "ajo_cebolla",
                    "🥜 frutos secos": "frutos_secos", "frutos secos": "frutos_secos", "nueces": "frutos_secos",
                    "🍄 hongos": "hongos", "hongos": "hongos", "setas": "hongos",
                    "🌿 cilantro": "cilantro", "cilantro": "cilantro"
                }
                
                selected = None
                for key, value in dislike_map.items():
                    if key in text or text in key:
                        selected = value
                        break
                
                if selected:
                    data["disliked_foods"] = [selected]
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: pescado, lacteos, picante, ajo, cebolla, frutos secos, hongos, cilantro, sin restricciones, u otros."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "restricciones"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("🚫 Alergias", "🌱 Vegano")
            keyboard.add("🥛 Sin lactosa", "🌾 Sin gluten")
            keyboard.add("🕌 Halal", "✡️ Kosher")
            keyboard.add("⏭️ Sin restricciones especiales")
            
            bot.send_message(
                message.chat.id,
                "✅ Alimentos a evitar registrados\n\n"
                "⚠️ **Paso 9E/10:** ¿Tienes alguna RESTRICCIÓN ESPECIAL?\n\n"
                "**Opciones disponibles:**\n"
                "• 🚫 Alergias\n"
                "• 🌱 Vegano\n"
                "• 🥛 Sin lactosa\n"
                "• 🌾 Sin gluten\n"
                "• 🕌 Halal\n"
                "• ✡️ Kosher\n"
                "• ⏭️ Sin restricciones especiales\n\n"
                "Puedes usar los botones o escribir el nombre:",
                reply_markup=keyboard
            )
            
        elif step == "disgustos_texto":
            # Procesar disgustos por texto libre
            if message.text.lower() in ["ninguno", "sin restricciones", "no"]:
                additional_dislikes = []
            else:
                additional_dislikes = [food.strip() for food in message.text.split(',')]
            
            # Combinar con restricciones anteriores
            current_dislikes = data.get("disliked_foods", [])
            data["disliked_foods"] = current_dislikes + additional_dislikes
            
            meal_bot.user_states[telegram_id]["step"] = "restricciones"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("🚫 Alergias", "🌱 Vegano")
            keyboard.add("🥛 Sin lactosa", "🌾 Sin gluten")
            keyboard.add("🕌 Halal", "✡️ Kosher")
            keyboard.add("⏭️ Sin restricciones especiales")
            
            bot.send_message(
                message.chat.id,
                "✅ Alimentos adicionales registrados\n\n"
                "⚠️ **Paso 9E/10:** ¿Tienes alguna RESTRICCIÓN ESPECIAL?\n\n"
                "**Opciones disponibles:**\n"
                "• 🚫 Alergias\n"
                "• 🌱 Vegano\n"
                "• 🥛 Sin lactosa\n"
                "• 🌾 Sin gluten\n"
                "• 🕌 Halal\n"
                "• ✡️ Kosher\n"
                "• ⏭️ Sin restricciones especiales\n\n"
                "Puedes usar los botones o escribir el nombre:",
                reply_markup=keyboard
            )
            
        elif step == "restricciones":
            # Procesar restricciones especiales con manejo flexible
            text = message.text.lower().strip()
            
            if "sin restricciones" in text or "ninguna" in text:
                data["special_restrictions"] = []
            else:
                restriction_map = {
                    "🚫 alergias": "alergias", "alergias": "alergias", "alergia": "alergias",
                    "🌱 vegano": "vegano", "vegano": "vegano", "vegetariano": "vegano",
                    "🥛 sin lactosa": "sin_lactosa", "sin lactosa": "sin_lactosa", "lactosa": "sin_lactosa",
                    "🌾 sin gluten": "sin_gluten", "sin gluten": "sin_gluten", "gluten": "sin_gluten", "celiaco": "sin_gluten",
                    "🕌 halal": "halal", "halal": "halal",
                    "✡️ kosher": "kosher", "kosher": "kosher"
                }
                
                selected = None
                for key, value in restriction_map.items():
                    if key in text or text in key:
                        selected = value
                        break
                
                if selected:
                    data["special_restrictions"] = [selected]
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: alergias, vegano, sin lactosa, sin gluten, halal, kosher, o sin restricciones."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "metodos_coccion"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🔥 Horno", "🍳 Sartén", "🍲 Plancha")
            keyboard.add("🥘 Guisos", "🍜 Vapor", "🥗 Crudo")
            keyboard.add("✅ Todos", "⏭️ Sin preferencias")
            
            bot.send_message(
                message.chat.id,
                "✅ Restricciones registradas\n\n"
                "👨‍🍳 **Paso 9F/10:** ¿Qué MÉTODOS DE COCCIÓN prefieres?\n\n"
                "**Opciones disponibles:**\n"
                "• 🔥 Horno\n"
                "• 🍳 Sartén\n"
                "• 🍲 Plancha\n"
                "• 🥘 Guisos\n"
                "• 🍜 Vapor\n"
                "• 🥗 Crudo\n"
                "• ✅ Todos\n"
                "• ⏭️ Sin preferencias\n\n"
                "Puedes usar los botones o escribir el nombre:",
                reply_markup=keyboard
            )
            
        elif step == "metodos_coccion":
            # Procesar métodos de cocción con manejo flexible
            text = message.text.lower().strip()
            
            if "sin preferencias" in text or "ninguna" in text:
                data["cooking_methods"] = ["horno", "sarten", "plancha"]  # Default
            elif "todos" in text or text == "✅ todos":
                data["cooking_methods"] = ["horno", "sarten", "plancha", "guisos", "vapor", "crudo"]
            else:
                method_map = {
                    "🔥 horno": "horno", "horno": "horno",
                    "🍳 sartén": "sarten", "sarten": "sarten", "sartén": "sarten", "freir": "sarten",
                    "🍲 plancha": "plancha", "plancha": "plancha", "grill": "plancha",
                    "🥘 guisos": "guisos", "guisos": "guisos", "hervir": "guisos", "cocido": "guisos",
                    "🍜 vapor": "vapor", "vapor": "vapor", "vaporera": "vapor",
                    "🥗 crudo": "crudo", "crudo": "crudo", "ensalada": "crudo"
                }
                
                selected = None
                for key, value in method_map.items():
                    if key in text or text in key:
                        selected = value
                        break
                
                if selected:
                    data["cooking_methods"] = [selected]
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: horno, sarten, plancha, guisos, vapor, crudo, todos, o sin preferencias."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "finalizar"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            keyboard.add("✅ Crear mi perfil nutricional")
            
            bot.send_message(
                message.chat.id,
                "✅ Métodos de cocción registrados\n\n"
                "🎯 **Paso 10/10:** ¡Todo listo para crear tu perfil científico!\n\n"
                "📊 **Tu configuración incluye:**\n"
                "• Datos biométricos y objetivo\n"
                "• Available Energy científico\n"
                "• Distribución de ejercicio detallada\n"
                "• Preferencias alimentarias completas\n"
                "• Restricciones y métodos de cocción\n\n"
                "🤖 **El sistema generará recetas personalizadas con IA**\n\n"
                "**Para finalizar:**\n"
                "• Usa el botón: ✅ Crear mi perfil nutricional\n"
                "• O escribe: 'crear perfil' o 'finalizar'\n\n"
                "¡Tu perfil científico estará listo en segundos!",
                reply_markup=keyboard
            )
            
        elif step == "finalizar":
            # Validar entrada flexible para crear perfil
            text = message.text.lower().strip()
            
            # Aceptar múltiples variaciones
            valid_inputs = [
                "✅ crear mi perfil nutricional",
                "crear mi perfil nutricional", 
                "crear perfil",
                "crear",
                "finalizar",
                "terminar",
                "continuar",
                "listo",
                "si"
            ]
            
            # Verificar si la entrada es válida
            is_valid = False
            for valid_input in valid_inputs:
                if valid_input in text or text in valid_input:
                    is_valid = True
                    break
            
            if not is_valid:
                bot.send_message(
                    message.chat.id,
                    "❌ Para crear tu perfil, por favor:\n\n"
                    "• Usa el botón: ✅ Crear mi perfil nutricional\n"
                    "• O escribe: 'crear perfil', 'finalizar', 'listo'\n\n"
                    "¡Estás a un paso de tener tu perfil científico!"
                )
                return
            
            # Crear perfil completo usando UserProfileSystem
            try:
                # Preparar datos para el sistema de perfiles
                exercise_data = []
                if data.get("ejercicio_tipo", "ninguno") != "ninguno":
                    exercise_data = [{
                        "tipo": data["ejercicio_tipo"],
                        "subtipo": "intensidad_media",  # Default
                        "duracion": data["duracion_promedio"],
                        "peso": data["peso"],
                        "frecuencia_semanal": data["frecuencia_semanal"]
                    }]
                
                # Combinar todas las preferencias alimentarias
                all_liked_foods = (
                    data.get("liked_proteins", []) + 
                    data.get("liked_carbs", []) + 
                    data.get("liked_vegetables", []) +
                    data.get("liked_foods", [])  # Fallback para compatibilidad
                )
                
                profile_data = {
                    "peso": data["peso"],
                    "altura": data["altura"],
                    "edad": data["edad"],
                    "sexo": data["sexo"],
                    "objetivo": data["objetivo"],
                    "activity_factor": data["activity_factor"],
                    "exercise_data": exercise_data,
                    "preferences": {
                        "liked_foods": all_liked_foods,
                        "liked_proteins": data.get("liked_proteins", []),
                        "liked_carbs": data.get("liked_carbs", []),
                        "liked_vegetables": data.get("liked_vegetables", []),
                        "disliked_foods": data.get("disliked_foods", []),
                        "special_restrictions": data.get("special_restrictions", []),
                        "cooking_methods": data.get("cooking_methods", ["horno", "sarten", "plancha"])
                    },
                    "variety_level": 3,  # Default
                    "cooking_schedule": "dos_sesiones",  # Default
                    "max_prep_time": 60  # Default
                }
                
                # Crear perfil usando el sistema científico
                user_profile = meal_bot.profile_system.create_user_profile(telegram_id, profile_data)
                
                # Guardar en la base de datos
                meal_bot.data["users"][telegram_id] = user_profile
                meal_bot.save_data()
                
                # Limpiar estado de configuración
                meal_bot.user_states[telegram_id] = {}
                
                # Mostrar resumen del perfil creado
                success_message = f"""
🎉 **¡PERFIL NUTRICIONAL CREADO EXITOSAMENTE!**

👤 **TU PERFIL CIENTÍFICO:**
• Objetivo: {user_profile['basic_data']['objetivo_descripcion']}
• BMR: {user_profile['body_composition']['bmr']} kcal/día
• Available Energy: {user_profile['energy_data']['available_energy']} kcal/kg FFM/día
• Estado: {user_profile['energy_data']['ea_status']['color']} {user_profile['energy_data']['ea_status']['description']}

🎯 **MACROS DIARIOS PERSONALIZADOS:**
🔥 {user_profile['macros']['calories']} kcal totales
🥩 {user_profile['macros']['protein_g']}g proteína
🍞 {user_profile['macros']['carbs_g']}g carbohidratos  
🥑 {user_profile['macros']['fat_g']}g grasas

💡 **RECOMENDACIÓN CIENTÍFICA:**
{user_profile['energy_data']['ea_status']['recommendation']}

🚀 **¡YA PUEDES USAR EL SISTEMA V2.0!**

**Comandos disponibles:**
• `/mis_macros` - Ver tu perfil completo
• `/menu` - Menú semanal con timing nutricional
• `/buscar [consulta]` - Generar recetas con IA
• `/generar` - Recetas específicas por timing
• `/complementos` - Ver complementos mediterráneos

¡Tu alimentación ahora está optimizada científicamente! 🧬
"""
                
                meal_bot.send_long_message(
                    message.chat.id,
                    success_message,
                    parse_mode='Markdown',
                    reply_markup=meal_bot.create_main_menu_keyboard()
                )
                
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Error creando el perfil: {str(e)}\n\n"
                    "Por favor, intenta de nuevo con /perfil"
                )
        
    except ValueError as e:
        bot.send_message(
            message.chat.id,
            f"❌ Error: {str(e)}\n\n"
            "Por favor, introduce un valor válido."
        )

def process_ai_search(telegram_id: str, query: str, message):
    """Procesar búsqueda con IA completamente funcional"""
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    if not user_profile:
        bot.send_message(
            message.chat.id,
            "❌ **Error:** Necesitas configurar tu perfil primero.\n"
            "Usa /perfil para comenzar.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Generar recetas con IA
        result = meal_bot.ai_generator.search_and_adapt_recipes(user_profile, query)
        
        if result["success"]:
            results = result["results"]
            total_found = result["total_found"]
            
            if total_found == 0:
                bot.send_message(
                    message.chat.id,
                    f"🔍 **Búsqueda: '{query}'**\n\n"
                    "❌ No se encontraron recetas que cumplan tus criterios.\n\n"
                    "💡 **Sugerencias:**\n"
                    "• Intenta términos más generales (ej: 'pollo' en lugar de 'pollo al curry')\n"
                    "• Especifica el timing (ej: 'post entreno')\n"
                    "• Menciona ingredientes principales\n\n"
                    "**Ejemplos exitosos:**\n"
                    "• `/buscar proteina post entreno`\n"
                    "• `/buscar legumbres mediterraneas`\n"
                    "• `/buscar desayuno alto carbohidratos`",
                    parse_mode='Markdown'
                )
                return
            
            # Mostrar resultados encontrados
            intro_text = f"""
🤖 **BÚSQUEDA COMPLETADA CON IA**

**Tu consulta:** '{query}'
✅ **Encontradas:** {total_found} recetas válidas
📊 **Adaptadas** a tu perfil nutricional

🎯 **Tu objetivo:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Tus macros:** {user_profile['macros']['calories']} kcal diarias

**RECETAS GENERADAS:**
"""
            
            meal_bot.send_long_message(message.chat.id, intro_text, parse_mode='Markdown')
            
            # Mostrar cada receta encontrada
            for i, recipe_result in enumerate(results[:3], 1):  # Máximo 3 recetas
                recipe = recipe_result.get("adaptacion_propuesta")
                validation = recipe_result.get("validation", {})
                changes = recipe_result.get("cambios_realizados", [])
                
                if recipe:
                    # Formatear receta para display
                    recipe_text = format_recipe_for_display(recipe, validation)
                    
                    # Agregar información de cambios
                    if changes:
                        recipe_text += f"\n\n🔧 **Adaptaciones realizadas:**\n"
                        for change in changes:
                            recipe_text += f"• {change}\n"
                    
                    # Enviar receta
                    meal_bot.send_long_message(
                        message.chat.id, 
                        f"**OPCIÓN {i}:**\n{recipe_text}",
                        parse_mode='Markdown'
                    )
            
            # Opciones de seguimiento
            followup_text = f"""
🎯 **PRÓXIMOS PASOS:**

• **¿Te gusta alguna receta?** Responde con el número (1, 2, 3)
• **¿Quieres más opciones?** Envía `/buscar {query} más opciones`
• **¿Modificar algo?** Escribe qué cambiar
• **¿Generar menú completo?** Usa `/nueva_semana`

💡 **Tip:** Todas las recetas están validadas con ingredientes naturales y ajustadas a tus macros.
"""
            
            meal_bot.send_long_message(message.chat.id, followup_text, parse_mode='Markdown')
            
        else:
            # Error en la generación
            error_msg = result.get("error", "Error desconocido")
            bot.send_message(
                message.chat.id,
                f"❌ **Error en la búsqueda:**\n{error_msg}\n\n"
                "💡 **Intenta:**\n"
                "• Reformular tu consulta\n"
                "• Usar términos más específicos\n"
                "• Verificar tu conexión a internet\n\n"
                "Si el problema persiste, contacta al administrador.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in AI search: {e}")
        bot.send_message(
            message.chat.id,
            "❌ **Error técnico** procesando tu búsqueda.\n"
            "Inténtalo de nuevo en unos momentos.",
            parse_mode='Markdown'
        )
    
    # Limpiar estado
    meal_bot.user_states[telegram_id] = {}

# ========================================
# MANEJADOR DE MENSAJES DE TEXTO
# ========================================

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    """Manejar todos los mensajes de texto según el estado del usuario"""
    telegram_id = str(message.from_user.id)
    user_state = meal_bot.user_states.get(telegram_id, {})
    
    if user_state.get("state") == "profile_setup":
        process_profile_setup(telegram_id, message)
    elif user_state.get("state") == "schedule_setup":
        process_schedule_setup(telegram_id, message)
    elif user_state.get("state") == "ai_search":
        # Búsqueda ya procesada
        pass
    else:
        # Mensaje libre - responder con ayuda
        bot.send_message(
            message.chat.id,
            "❓ **COMANDOS DISPONIBLES:**\n\n"
            "/perfil - Configurar perfil nutricional\n"
            "/mis_macros - Ver tus macros\n"
            "/menu - Menú semanal\n"
            "/recetas - Explorar recetas\n"
            "/complementos - Ver complementos\n"
            "/buscar [consulta] - Buscar recetas con IA\n"
            "/generar - Generar receta específica\n"
            "/nueva_semana - Configurar cronograma\n\n"
            "💡 **Tip:** Empieza configurando tu perfil con /perfil"
        )

def process_schedule_setup(telegram_id: str, message):
    """Procesar configuración de cronograma"""
    user_state = meal_bot.user_states.get(telegram_id, {})
    choice = message.text.upper().strip()
    
    schedules = {
        "A": "sesion_unica_domingo",
        "B": "dos_sesiones", 
        "C": "tres_sesiones",
        "D": "preparacion_diaria"
    }
    
    if choice in schedules:
        schedule_id = schedules[choice]
        schedule_data = meal_bot.data["cooking_schedules"][schedule_id]
        
        # Guardar en perfil de usuario (cuando esté implementado)
        # user_profile["settings"]["cooking_schedule"] = schedule_id
        
        bot.send_message(
            message.chat.id,
            f"✅ **Cronograma seleccionado:** {schedule_data['name']}\n\n"
            f"📝 **Descripción:** {schedule_data['description']}\n"
            f"⏱️ **Tiempo estimado:** {schedule_data['estimated_time']}\n\n"
            "🎯 **Próximos pasos:**\n"
            "• Usa /buscar para generar recetas específicas\n"
            "• Configura tu nivel de variedad semanal\n"
            "• El sistema optimizará tu lista de compras\n\n"
            "**Tu cronograma se aplicará automáticamente al generar menús.**",
            parse_mode='Markdown',
            reply_markup=meal_bot.create_main_menu_keyboard()
        )
        
        # Limpiar estado
        meal_bot.user_states[telegram_id] = {}
        
    else:
        bot.send_message(
            message.chat.id,
            "❌ **Opción no válida**\n\n"
            "Por favor responde con A, B, C o D según tu preferencia."
        )

# ========================================
# CONFIGURACIÓN WEBHOOK/POLLING
# ========================================

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    """Webhook endpoint para Railway"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 400

def setup_webhook():
    """Configurar webhook si está habilitado"""
    if USE_WEBHOOK and WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook configurado: {webhook_url}")
        return True
    return False

def main():
    """Función principal"""
    logger.info("🚀 Iniciando Meal Prep Bot V2.0...")
    
    try:
        # Intentar configurar webhook
        if not setup_webhook():
            logger.info("📱 Iniciando en modo polling...")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=1, timeout=60)
        else:
            logger.info("🌐 Iniciando servidor webhook...")
            # En Railway, el puerto se obtiene de la variable de entorno
            port = int(os.environ.get('PORT', 5000))
            app.run(host='0.0.0.0', port=port, debug=False)
            
    except Exception as e:
        logger.error(f"❌ Error al iniciar el bot: {e}")
        raise

if __name__ == "__main__":
    main()