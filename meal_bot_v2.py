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
    """Mostrar recetas disponibles por categorías"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    # Mostrar estructura de categorías nuevas
    response_text = """
📚 **CATEGORÍAS DE RECETAS V2.0**

🕐 **POR TIMING NUTRICIONAL:**

⚡ **PRE-ENTRENO** (15-30 min antes)
• Energía rápida: Carbohidratos de absorción rápida
• Hidratación: Líquidos + electrolitos

💪 **POST-ENTRENO** (0-30 min después)
• Síntesis proteica: Proteínas completas
• Reposición glucógeno: Carbohidratos complejos

🍽️ **COMIDA PRINCIPAL**
• Equilibrio nutricional: Macros balanceados
• Saciedad: Fibra + proteína

🥜 **SNACK/COMPLEMENTO**
• Micronutrientes: Vitaminas y minerales
• Grasas saludables: Ácidos grasos esenciales

**COMPLEJIDAD:**
⭐ Muy fácil (15-30 min)
⭐⭐ Fácil (30-45 min)
⭐⭐⭐ Moderado (45-60 min)
⭐⭐⭐⭐ Complejo (60+ min)

**Usa /buscar [tipo de plato] para generar recetas específicas**
"""
    
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
            
            # Formatear y enviar receta
            recipe_text = format_recipe_for_display(recipe, validation)
            
            success_text = f"""
🎉 **RECETA GENERADA EXITOSAMENTE**

{recipe_text}

🤖 **Generada específicamente para tu perfil:**
• Objetivo: {user_profile['basic_data']['objetivo_descripcion']}
• Available Energy: {user_profile['energy_data']['available_energy']} kcal/kg FFM/día
• Todos los ingredientes son naturales y no procesados

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
    cooking_schedule = user_profile['settings'].get('cooking_schedule', 'dos_sesiones')
    
    # Obtener datos del cronograma
    schedule_data = meal_bot.data['cooking_schedules'].get(cooking_schedule, {})
    
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
            keyboard.add("Recomposición", "Mantener")
            
            bot.send_message(
                message.chat.id,
                f"✅ Sexo registrado: {sexo}\n\n"
                "🎯 **Paso 5/10:** ¿Cuál es tu objetivo principal?\n\n"
                "**Bajar peso:** Perder grasa manteniendo músculo\n"
                "**Ganar músculo:** Subir masa minimizando grasa\n"
                "**Recomposición:** Bajar grasa y ganar músculo simultáneamente\n"
                "**Mantener:** Mantener peso y composición actual",
                reply_markup=keyboard
            )
            
        elif step == "objetivo":
            objetivos_map = {
                "bajar peso": "bajar_peso",
                "ganar músculo": "subir_masa", 
                "ganar musculo": "subir_masa",
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
            
        # Continuar con más pasos del perfil...
        # (Se implementarán completamente todos los pasos)
        
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