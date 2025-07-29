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
from shopping_list_generator import ShoppingListGenerator
from weekly_planner import WeeklyPlanner
from recipe_intelligence import RecipeIntelligence
from progress_tracker import ProgressTracker
from meal_prep_scheduler import MealPrepScheduler
from nutrition_analytics import NutritionAnalytics
from weekly_menu_system import WeeklyMenuSystem

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
        self.shopping_generator = ShoppingListGenerator()
        self.weekly_planner = WeeklyPlanner()
        self.recipe_intelligence = RecipeIntelligence()
        self.progress_tracker = ProgressTracker()
        self.meal_prep_scheduler = MealPrepScheduler()
        self.nutrition_analytics = NutritionAnalytics()
        self.weekly_menu_system = WeeklyMenuSystem(self.database_file)
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
            
            # También guardar en recent_generated_recipes para sistema de valoración
            if "recent_generated_recipes" not in user_profile:
                user_profile["recent_generated_recipes"] = []
            
            # Agregar receta con ID único para valoración
            recipe_for_rating = recipe.copy()
            recipe_for_rating["recipe_id"] = recipe_entry["id"]
            recipe_for_rating["generated_at"] = recipe_entry["generated_date"]
            
            user_profile["recent_generated_recipes"].append(recipe_for_rating)
            
            # Mantener solo las últimas 10 recetas para valoración
            if len(user_profile["recent_generated_recipes"]) > 10:
                user_profile["recent_generated_recipes"] = user_profile["recent_generated_recipes"][-10:]
            
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
    """Comando de inicio con personalización visual"""
    telegram_id = str(message.from_user.id)
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    if user_profile:
        # Usuario existente - bienvenida personalizada
        preferences = user_profile.get("preferences", {})
        liked_count = len(preferences.get("liked_foods", []))
        disliked_count = len(preferences.get("disliked_foods", []))
        
        welcome_text = f"""
✨ **¡Bienvenido de vuelta!** Meal Prep Bot V2.0

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🎯 **Personalización:** {liked_count} preferencias, {disliked_count} exclusiones
🔥 **Calorías objetivo:** {user_profile['macros']['calories']} kcal/día
⚡ **Available Energy:** {user_profile['energy_data']['available_energy']} kcal/kg FFM/día

🚀 **SISTEMA COMPLETAMENTE PERSONALIZADO:**

✅ **Menús:** Adaptados a tus gustos y objetivo
✅ **Recetas IA:** Generadas específicamente para ti  
✅ **Listas de compra:** Optimizadas para tu perfil
✅ **Complementos:** Filtrados según preferencias
✅ **Favoritas:** Sistema de recetas guardadas

**COMANDOS PRINCIPALES:**
🎯 /mis_macros - Tus macros personalizados
📅 /menu - Menú semanal con tus preferencias
🛒 /lista_compras - Lista optimizada para ti
⭐ /favoritas - Tus recetas guardadas
🤖 /generar - Crear recetas para tu objetivo
🌟 /valorar - Valorar recetas con 1-5 estrellas
🌟 /valorar_receta - Entrenar IA con ratings

**CONFIGURACIÓN:**
⚙️ /editar_perfil - Modificar preferencias
📅 /nueva_semana - Configurar cronograma

💡 **Todo se adapta automáticamente a tu perfil nutricional**
"""
    else:
        # Nuevo usuario
        welcome_text = """
🍽️ **¡Bienvenido al Meal Prep Bot V2.0!**

🤖 **Sistema de meal prep con IA completamente personalizado**

**¿Qué puedo hacer por ti?**
📊 Calcular macros según tu objetivo específico
🍽️ Crear menús adaptados a tus preferencias
🤖 Generar recetas con IA para tu perfil
🛒 Listas de compra optimizadas automáticamente
⭐ Sistema de recetas favoritas personalizado

⚠️ **IMPORTANTE:** Para experiencia 100% personalizada:

🆕 **Paso 1:** Usa `/perfil` para configurar tu perfil
🎯 **Paso 2:** El sistema se adaptará automáticamente a ti
✨ **Resultado:** Menús, recetas y listas personalizadas

**COMANDOS BÁSICOS (sin personalizar):**
/perfil - ¡Empieza aquí para personalización completa!
/menu - Menú genérico
/recetas - Ver recetas básicas
/buscar [consulta] - Buscar recetas con IA

💡 **¡Configura tu perfil para experiencia personalizada al 100%!**
"""
    
    meal_bot.send_long_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['perfil'])
def perfil_command(message):
    """Comando para configurar perfil de usuario"""
    telegram_id = str(message.from_user.id)
    
    # Iniciar proceso de configuración de perfil
    meal_bot.user_states[telegram_id] = {
        "state": "profile_setup",
        "step": "enfoque_dietetico",
        "data": {}
    }
    
    # Crear teclado para enfoque dietético
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("🇪🇸 Tradicional Español - Platos equilibrados, ingredientes mediterráneos", callback_data="approach_tradicional"),
        types.InlineKeyboardButton("💪 Fitness Orientado - Optimización nutricional, macros precisos", callback_data="approach_fitness")
    )
    
    bot.send_message(
        message.chat.id,
        "👤 **CONFIGURACIÓN DE PERFIL NUTRICIONAL**\n\n"
        "Antes de calcular tus macros personalizados, necesito conocer tu enfoque preferido:\n\n"
        "🍽️ **¿Qué enfoque nutricional prefieres?**\n\n"
        "**🇪🇸 Tradicional Español:**\n"
        "• Platos mediterráneos equilibrados\n"
        "• Ingredientes locales y de temporada\n"
        "• Recetas familiares y culturales\n"
        "• Enfoque en sabor y tradición\n\n"
        "**💪 Fitness Orientado:**\n"
        "• Optimización de macronutrientes\n"
        "• Timing nutricional preciso\n"
        "• Maximización de resultados deportivos\n"
        "• Enfoque científico y medible\n\n"
        "📍 _Esta elección influirá en el tipo de recetas y recomendaciones que recibirás_",
        parse_mode='Markdown',
        reply_markup=keyboard
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
    preferences = user_profile.get("preferences", {})
    exercise_profile = user_profile.get("exercise_profile", {})
    
    # Formatear preferencias alimentarias
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    cooking_methods = preferences.get("cooking_methods", [])
    
    # Formatear listas de preferencias con emojis
    def format_food_list(food_list):
        if not food_list:
            return "Ninguna especificada"
        
        food_emojis = {
            "carnes_rojas": "🥩", "aves": "🐔", "pescados": "🐟", "huevos": "🥚",
            "lacteos": "🥛", "frutos_secos": "🥜", "legumbres": "🫘", "hojas_verdes": "🥬",
            "cruciferas": "🥦", "solanaceas": "🍅", "aromaticas": "🌿", "raices": "🥕",
            "pimientos": "🌶️", "pepinaceas": "🥒", "aceitunas": "🫒", "aguacate": "🥑"
        }
        
        formatted = []
        for food in food_list:
            emoji = food_emojis.get(food, "🍽️")
            name = food.replace("_", " ").title()
            formatted.append(f"{emoji} {name}")
        
        return ", ".join(formatted)
    
    def format_cooking_methods(methods_list):
        if not methods_list:
            return "Ninguno especificado"
            
        method_emojis = {
            "horno": "🔥", "sarten": "🍳", "plancha": "🥘", "vapor": "🫕",
            "crudo": "🥗", "guisado": "🍲", "parrilla": "🔥", "hervido": "🥄"
        }
        
        formatted = []
        for method in methods_list:
            emoji = method_emojis.get(method, "👨‍🍳")
            name = method.replace("_", " ").title()
            formatted.append(f"{emoji} {name}")
        
        return ", ".join(formatted)
    
    response_text = f"""
👤 **TU PERFIL NUTRICIONAL COMPLETO**

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

**TUS PREFERENCIAS PERSONALES:**
🍽️ **Alimentos preferidos:**
{format_food_list(liked_foods)}

🚫 **Alimentos a evitar:**
{format_food_list(disliked_foods)}

👨‍🍳 **Métodos de cocción preferidos:**
{format_cooking_methods(cooking_methods)}

⏰ **Horario de entrenamiento:**
{exercise_profile.get('training_schedule_desc', 'No especificado')}

**RECOMENDACIÓN PERSONALIZADA:**
{energy_data['ea_status']['recommendation']}

💡 **Personalización activa:**
✅ Tus preferencias se aplican en `/buscar` y `/generar`
✅ Usa `/editar_perfil` para modificar tus preferencias
✅ Comandos personalizados: `/menu`, `/complementos`
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['editar_perfil'])
def editar_perfil_command(message):
    """Comando para editar preferencias del perfil existente"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    if not user_profile:
        bot.send_message(
            message.chat.id,
            "❌ No tienes un perfil configurado.\n\n"
            "Usa `/perfil` para crear tu perfil primero.",
            parse_mode='Markdown'
        )
        return
    
    # Crear teclado de opciones de edición
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Botones para cada sección editable
    markup.add(
        types.InlineKeyboardButton("🍽️ Alimentos Preferidos", callback_data="edit_liked_foods"),
        types.InlineKeyboardButton("🚫 Alimentos a Evitar", callback_data="edit_disliked_foods"),
        types.InlineKeyboardButton("👨‍🍳 Métodos de Cocción", callback_data="edit_cooking_methods"),
        types.InlineKeyboardButton("⏰ Horario de Entrenamiento", callback_data="edit_training_schedule"),
        types.InlineKeyboardButton("❌ Cancelar", callback_data="cancel_edit")
    )
    
    # Obtener preferencias actuales
    preferences = user_profile.get("preferences", {})
    exercise_profile = user_profile.get("exercise_profile", {})
    
    current_preferences = f"""
📝 **TUS PREFERENCIAS ACTUALES:**

🍽️ **Alimentos preferidos:**
{', '.join(preferences.get('liked_foods', [])) if preferences.get('liked_foods') else 'Ninguno seleccionado'}

🚫 **Alimentos a evitar:**
{', '.join(preferences.get('disliked_foods', [])) if preferences.get('disliked_foods') else 'Ninguno seleccionado'}

👨‍🍳 **Métodos de cocción:**
{', '.join(preferences.get('cooking_methods', [])) if preferences.get('cooking_methods') else 'Ninguno seleccionado'}

⏰ **Horario de entrenamiento:**
{exercise_profile.get('training_schedule_desc', 'No especificado')}

**¿Qué quieres modificar?**
"""
    
    bot.send_message(
        message.chat.id,
        current_preferences,
        parse_mode='Markdown',
        reply_markup=markup
    )

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
• /valorar - Valorar recetas con 1-5 estrellas  
• /valorar_receta - Entrenar IA con tus preferencias
"""
        
        meal_bot.send_long_message(message.chat.id, fallback_text, parse_mode='Markdown')

@bot.message_handler(commands=['configurar_menu'])
def configurar_menu_command(message):
    """Configurar menú semanal personalizado con recetas guardadas"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Obtener recetas guardadas por categoría
    recipes_by_category = meal_bot.weekly_menu_system.get_user_saved_recipes(user_profile)
    
    # Verificar si tiene recetas guardadas
    total_recipes = sum(len(recipes) for recipes in recipes_by_category.values())
    
    if total_recipes == 0:
        bot.send_message(
            message.chat.id,
            "🤖 **CONFIGURAR MENÚ SEMANAL**\n\n"
            "❌ **No tienes recetas guardadas aún.**\n\n"
            "Para configurar tu menú semanal necesitas generar y guardar recetas primero:\n\n"
            "📝 **Pasos para empezar:**\n"
            "1. Usa `/generar` para crear recetas por categoría\n"
            "2. Selecciona y guarda las recetas que te gusten\n"
            "3. Regresa a `/configurar_menu` para armar tu semana\n\n"
            "💡 **Tip:** Con al menos 1-2 recetas por comida podrás crear tu menú personalizado.",
            parse_mode='Markdown'
        )
        return
    
    # Inicializar estado de configuración de menú
    meal_bot.user_states[telegram_id] = {
        "state": "menu_configuration",
        "step": "category_selection",
        "data": {
            "selected_recipes": {"desayuno": [], "almuerzo": [], "merienda": [], "cena": []},
            "current_category": "desayuno"
        }
    }
    
    # Mostrar resumen de recetas disponibles
    summary_text = f"""
🤖 **CONFIGURAR MENÚ SEMANAL PERSONALIZADO**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🎯 **Enfoque:** {user_profile['basic_data'].get('enfoque_dietetico', 'fitness').title()}

📊 **Recetas disponibles:**
🌅 **Desayuno:** {len(recipes_by_category['desayuno'])} recetas
🍽️ **Almuerzo:** {len(recipes_by_category['almuerzo'])} recetas  
🥜 **Merienda:** {len(recipes_by_category['merienda'])} recetas
🌙 **Cena:** {len(recipes_by_category['cena'])} recetas

**Total:** {total_recipes} recetas guardadas

🔄 **Proceso de configuración:**
1. **Seleccionar recetas** por cada categoría de comida
2. **Preview del menú** semanal generado automáticamente
3. **Confirmar o editar** antes de aplicar

➡️ **Comenzaremos con el DESAYUNO**
"""
    
    bot.send_message(message.chat.id, summary_text, parse_mode='Markdown')
    
    # Mostrar recetas de desayuno para selección
    show_category_recipe_selection(telegram_id, "desayuno", user_profile)

def show_category_recipe_selection(telegram_id: str, category: str, user_profile: Dict):
    """Mostrar interface de selección de recetas para una categoría"""
    recipes_by_category = meal_bot.weekly_menu_system.get_user_saved_recipes(user_profile)
    recipes = recipes_by_category.get(category, [])
    
    if not recipes:
        # Si no hay recetas para esta categoría, saltar a la siguiente
        next_category = get_next_category(category)
        if next_category:
            meal_bot.user_states[telegram_id]["data"]["current_category"] = next_category
            show_category_recipe_selection(telegram_id, next_category, user_profile)
        else:
            # Todas las categorías procesadas, generar preview
            generate_menu_preview_step(telegram_id, user_profile)
        return
    
    # Crear keyboard con recetas disponibles
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Botones para cada receta
    for recipe in recipes[:7]:  # Máximo 7 recetas por categoría
        # Verificar si ya está seleccionada
        is_selected = recipe["id"] in meal_bot.user_states[telegram_id]["data"]["selected_recipes"][category]
        checkbox = "✅" if is_selected else "☐"
        
        # Mostrar nombre y calorías
        display_name = recipe["name"] if len(recipe["name"]) <= 30 else f"{recipe['name'][:27]}..."
        button_text = f"{checkbox} {display_name} ({recipe['calories']} kcal)"
        
        keyboard.add(
            types.InlineKeyboardButton(
                button_text,
                callback_data=f"menu_select_{category}_{recipe['id']}"
            )
        )
    
    # Botones de navegación
    keyboard.add(
        types.InlineKeyboardButton("➡️ Continuar con siguiente categoría", callback_data=f"menu_next_{category}")
    )
    
    # Mapear categorías a emojis
    category_icons = {
        "desayuno": "🌅",
        "almuerzo": "🍽️", 
        "merienda": "🥜",
        "cena": "🌙"
    }
    
    selected_count = len(meal_bot.user_states[telegram_id]["data"]["selected_recipes"][category])
    
    category_text = f"""
{category_icons.get(category, "🍽️")} **SELECCIONAR RECETAS DE {category.upper()}**

**Recetas seleccionadas:** {selected_count}/{len(recipes)}

📝 **Instrucciones:**
• Selecciona las recetas que quieres incluir en tu menú semanal
• Puedes elegir de 1 a 7 recetas por categoría
• **Más recetas = más variedad** durante la semana
• **Menos recetas = se repetirán** más días

✅ = Receta seleccionada
☐ = Receta disponible

👆 **Toca las recetas que quieres incluir:**
"""
    
    bot.send_message(
        telegram_id, 
        category_text, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

def get_next_category(current_category: str) -> Optional[str]:
    """Obtener la siguiente categoría en el flujo"""
    categories = ["desayuno", "almuerzo", "merienda", "cena"]
    try:
        current_index = categories.index(current_category)
        if current_index < len(categories) - 1:
            return categories[current_index + 1]
    except ValueError:
        pass
    return None

def generate_menu_preview_step(telegram_id: str, user_profile: Dict):
    """Generar preview del menú y mostrar opciones finales"""
    user_state = meal_bot.user_states[telegram_id]
    selected_recipes = user_state["data"]["selected_recipes"]
    
    # Crear distribución semanal
    weekly_menu = meal_bot.weekly_menu_system.create_weekly_distribution(selected_recipes, user_profile)
    
    # Generar preview
    preview_text = meal_bot.weekly_menu_system.generate_menu_preview(weekly_menu, user_profile)
    
    # Guardar en estado temporal
    user_state["data"]["weekly_menu"] = weekly_menu
    user_state["step"] = "preview_confirmation"
    
    # Botones de confirmación
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("✅ Confirmar menú", callback_data="menu_confirm"),
        types.InlineKeyboardButton("✏️ Editar recetas", callback_data="menu_edit")
    )
    keyboard.add(
        types.InlineKeyboardButton("💾 Guardar configuración", callback_data="menu_save_config")
    )
    
    # Enviar preview
    meal_bot.send_long_message(
        telegram_id, 
        preview_text, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

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
🌅 **DESAYUNO** - Primera comida del día
🍽️ **ALMUERZO** - Comida principal del mediodía
🥜 **MERIENDA** - Snack de la tarde
🌙 **CENA** - Última comida del día

¡Genera tu primera receta con /generar!
"""
    else:
        response_text = "📚 **TUS RECETAS GENERADAS**\n\n"
        
        # Agrupar por categoría de timing
        categories = {
            "pre_entreno": "⚡ **PRE-ENTRENO**",
            "post_entreno": "💪 **POST-ENTRENO**", 
            "desayuno": "🌅 **DESAYUNO**",
            "almuerzo": "🍽️ **ALMUERZO**",
            "merienda": "🥜 **MERIENDA**",
            "cena": "🌙 **CENA**"
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
                    name = recipe_data.get("nombre", "Receta sin nombre")
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
    """Mostrar complementos mediterráneos personalizados según preferencias"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    preferences = user_profile.get("preferences", {})
    exercise_profile = user_profile.get("exercise_profile", {})
    
    # Obtener preferencias del usuario
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    training_schedule = exercise_profile.get("training_schedule", "variable")
    objetivo = user_profile["basic_data"]["objetivo"]
    
    # Mostrar complementos de la base de datos
    complements = meal_bot.data.get("global_complements", {})
    
    response_text = f"🥜 **COMPLEMENTOS MEDITERRÁNEOS PERSONALIZADOS**\n\n"
    response_text += f"👤 **Adaptado a tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}\n"
    response_text += f"⏰ **Timing:** {exercise_profile.get('training_schedule_desc', 'Variable')}\n\n"
    
    def is_food_preferred(item_name_lower, category_name_lower):
        """Verificar si un complemento coincide con preferencias del usuario"""
        
        # Mapeo de complementos a categorías de alimentos
        food_mappings = {
            # Frutos secos
            "almendras": "frutos_secos", "nueces": "frutos_secos", "pistachos": "frutos_secos",
            "avellanas": "frutos_secos", "anacardos": "frutos_secos",
            
            # Lácteos
            "yogur": "lacteos", "queso": "lacteos", "feta": "lacteos",
            
            # Aceitunas y derivados
            "aceitunas": "aceitunas", "aceite": "aceitunas",
            
            # Frutas
            "higos": "frutas", "dátiles": "frutas", "pasas": "frutas",
            
            # Otros
            "miel": "endulzantes_naturales"
        }
        
        for word, food_category in food_mappings.items():
            if word in item_name_lower:
                return food_category in liked_foods, food_category in disliked_foods
        
        return False, False
    
    total_shown = 0
    preferred_items = []
    neutral_items = []
    avoided_items = []
    
    for category, items in complements.items():
        category_name = category.replace("_", " ").title()
        
        for item_id, item_data in items.items():
            name = item_data["name"]
            portion = item_data["portion_size"]
            unit = item_data["unit"]
            macros = item_data["macros_per_portion"]
            
            # Verificar preferencias
            is_preferred, is_disliked = is_food_preferred(name.lower(), category.lower())
            
            item_text = f"• {name} ({portion}{unit})\n"
            item_text += f"  {macros['protein']}P / {macros['carbs']}C / {macros['fat']}G = {macros['calories']} kcal"
            
            if is_preferred:
                preferred_items.append((category_name, f"✅ {item_text}"))
            elif is_disliked:
                avoided_items.append((category_name, f"⚠️ {item_text}"))
            else:
                neutral_items.append((category_name, item_text))
    
    # Mostrar complementos preferidos primero
    if preferred_items:
        response_text += "⭐ **RECOMENDADOS PARA TI:**\n"
        current_category = ""
        for category_name, item_text in preferred_items:
            if category_name != current_category:
                response_text += f"\n**{category_name.upper()}:**\n"
                current_category = category_name
            response_text += f"{item_text}\n"
        response_text += "\n"
    
    # Mostrar complementos neutrales
    if neutral_items:
        response_text += "🍽️ **OTROS COMPLEMENTOS DISPONIBLES:**\n"
        current_category = ""
        for category_name, item_text in neutral_items[:8]:  # Limitar para no sobrecargar
            if category_name != current_category:
                response_text += f"\n**{category_name.upper()}:**\n"
                current_category = category_name
            response_text += f"{item_text}\n"
        response_text += "\n"
    
    # Mostrar complementos a evitar (si los hay)
    if avoided_items:
        response_text += "🚫 **COMPLEMENTOS QUE EVITAS:**\n"
        current_category = ""
        for category_name, item_text in avoided_items:
            if category_name != current_category:
                response_text += f"\n**{category_name.upper()}:**\n"
                current_category = category_name
            response_text += f"{item_text}\n"
        response_text += "\n"
    
    # Timing personalizado según horario de entrenamiento
    timing_recommendations = {
        "mañana": {
            "pre": "🌅 **Pre-entreno (6:00-6:30):** Miel + almendras",
            "post": "☀️ **Post-entreno (8:00-9:00):** Yogur griego + nueces",
            "tarde": "🌆 **Tarde:** Aceitunas + queso feta"
        },
        "mediodia": {
            "pre": "☀️ **Pre-entreno (11:30-12:00):** Dátiles + pistachos",
            "post": "🌞 **Post-entreno (14:00-15:00):** Yogur + miel",
            "tarde": "🌆 **Tarde:** Frutos secos mixtos"
        },
        "tarde": {
            "pre": "🌆 **Pre-entreno (15:30-16:00):** Miel + frutos secos",
            "post": "🌙 **Post-entreno (20:30-21:00):** Yogur + aceitunas",
            "noche": "🌃 **Noche:** Complementos según macros faltantes"
        },
        "noche": {
            "pre": "🌙 **Pre-entreno (19:30-20:00):** Almendras + miel (ligero)",
            "post": "🌃 **Post-entreno (22:00-22:30):** Yogur (evitar exceso)",
            "descanso": "😴 **Antes de dormir:** Solo si faltan macros"
        },
        "variable": {
            "general": "🔄 **Timing flexible:** Adapta según tu horario de entrenamiento",
            "regla": "📋 **Regla general:** Pre-entreno ligero, post-entreno proteico"
        }
    }
    
    schedule_recommendations = timing_recommendations.get(training_schedule, timing_recommendations["variable"])
    
    response_text += "⏰ **TIMING PERSONALIZADO PARA TI:**\n"
    for timing_name, recommendation in schedule_recommendations.items():
        response_text += f"{recommendation}\n"
    
    response_text += f"""

🎯 **RECOMENDACIONES PARA {objetivo.upper().replace('_', ' ')}:**
"""
    
    # Recomendaciones específicas por objetivo
    objective_recommendations = {
        "bajar_peso": [
            "• Prioriza complementos altos en proteína (yogur griego)",
            "• Controla porciones de frutos secos (máximo 30g/día)",
            "• Evita miel en exceso (máximo 15g/día)"
        ],
        "subir_masa": [
            "• Aumenta frecuencia de frutos secos y aceitunas",
            "• Combina complementos para maximizar calorías",
            "• Miel post-entreno para reponer glucógeno"
        ],
        "recomposicion": [
            "• Timing preciso: proteínas post-entreno",
            "• Carbohidratos (miel, frutas) solo peri-entreno",
            "• Grasas saludables en comidas principales"
        ],
        "mantener": [
            "• Distribución equilibrada durante el día",
            "• Usa complementos para completar macros faltantes",
            "• Flexibilidad según apetito y actividad"
        ]
    }
    
    recs = objective_recommendations.get(objetivo, objective_recommendations["mantener"])
    for rec in recs:
        response_text += f"{rec}\n"
    
    response_text += f"""

💡 **PERSONALIZACIÓN ACTIVA:**
✅ Complementos filtrados según tus preferencias
✅ Timing adaptado a tu horario de entrenamiento
✅ Recomendaciones específicas para tu objetivo
✅ Usa `/editar_perfil` para modificar preferencias
"""
    
    meal_bot.send_long_message(message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['favoritas'])
def favoritas_command(message):
    """Mostrar recetas favoritas del usuario"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    favorite_ids = meal_bot.profile_system.get_user_favorites(user_profile)
    
    if not favorite_ids:
        response_text = """
⭐ **TUS RECETAS FAVORITAS**

❌ **No tienes recetas favoritas aún**

Para añadir recetas a favoritos:
• Genera recetas con `/generar`
• Busca recetas con `/buscar [consulta]`
• Marca las que te gusten con ⭐

**¡Empieza a generar recetas personalizadas!**
"""
        bot.send_message(message.chat.id, response_text, parse_mode='Markdown')
        return
    
    # Obtener recetas favoritas de la base de datos
    generated_recipes = meal_bot.data.get("generated_recipes", [])
    favorite_recipes = []
    
    for recipe_entry in generated_recipes:
        recipe_id = recipe_entry.get("recipe_id")
        if recipe_id in favorite_ids:
            favorite_recipes.append(recipe_entry)
    
    if not favorite_recipes:
        response_text = """
⭐ **TUS RECETAS FAVORITAS**

⚠️ **Recetas favoritas no encontradas**

Puede que algunas recetas favoritas ya no estén disponibles.
Genera nuevas recetas con `/generar` y márcalas como favoritas.
"""
        bot.send_message(message.chat.id, response_text, parse_mode='Markdown')
        return
    
    # Mostrar recetas favoritas
    response_text = f"⭐ **TUS RECETAS FAVORITAS**\n\n"
    response_text += f"📚 **Total:** {len(favorite_recipes)} recetas\n\n"
    
    # Agrupar por categoría de timing
    categories = {
        "pre_entreno": "⚡ **PRE-ENTRENO**",
        "post_entreno": "💪 **POST-ENTRENO**", 
        "comida_principal": "🍽️ **COMIDA PRINCIPAL**",
        "snack_complemento": "🥜 **SNACK/COMPLEMENTO**"
    }
    
    recipes_by_category = {}
    for recipe in favorite_recipes:
        category = recipe.get("timing_category", "comida_principal")
        if category not in recipes_by_category:
            recipes_by_category[category] = []
        recipes_by_category[category].append(recipe)
    
    for category, category_name in categories.items():
        if category in recipes_by_category:
            response_text += f"\n{category_name}\n"
            for i, recipe in enumerate(recipes_by_category[category], 1):
                recipe_data = recipe.get("recipe_data", {})
                name = recipe_data.get("nombre", "Receta sin nombre")
                macros = recipe_data.get("macros_per_portion", recipe_data.get("macros_por_porcion", {}))
                calories = macros.get("calories", macros.get("calorias", "N/A"))
                score = recipe.get("validation_score", 0)
                date = recipe.get("generated_date", "")[:10] if recipe.get("generated_date") else "N/A"
                
                response_text += f"⭐ **{name}**\n"
                response_text += f"   {calories} kcal • ⭐{score}/100 • {date}\n\n"
    
    response_text += """
💡 **GESTIÓN DE FAVORITAS:**
• Usa 🚫 para quitar de favoritos
• `/generar` para crear más recetas
• `/buscar [consulta]` para encontrar específicas

**¡Tus favoritas se guardan automáticamente!**
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

def determine_optimal_theme(user_profile: Dict) -> str:
    """
    Determinar tema óptimo basándose en el perfil del usuario
    """
    objetivo = user_profile["basic_data"]["objetivo"]
    available_energy = user_profile["energy_data"]["available_energy"]
    preferences = user_profile.get("preferences", {})
    liked_foods = preferences.get("liked_foods", [])
    
    # Scoring por objetivo
    if objetivo == "subir_masa":
        if available_energy > 50:
            return "alta_proteina"
        else:
            return "energia_sostenida"
    elif objetivo == "bajar_peso":
        if "pescados" in liked_foods or "verduras" in liked_foods:
            return "mediterranea"
        else:
            return "detox_natural"
    elif objetivo == "recomposicion":
        return "variedad_maxima"  # Balance perfecto
    else:  # mantener
        if "frutos_secos" in liked_foods or "aceitunas" in liked_foods:
            return "mediterranea"
        else:
            return "variedad_maxima"

def determine_optimal_cooking_schedule(user_profile: Dict) -> str:
    """
    Determinar cronograma óptimo basándose en Available Energy
    """
    available_energy = user_profile["energy_data"]["available_energy"]
    
    if available_energy >= 60:
        return "sesion_unica_domingo"  # Máxima eficiencia
    elif available_energy >= 45:
        return "dos_sesiones"  # Balance
    elif available_energy >= 35:
        return "tres_sesiones"  # Distribuida
    else:
        return "preparacion_diaria"  # Mínimo esfuerzo

def generate_intelligent_week(message, user_profile: Dict, theme: str):
    """
    Generar plan semanal inteligente con tema específico
    """
    try:
        telegram_id = str(message.from_user.id)
        
        # Mostrar mensaje de generación
        processing_msg = bot.send_message(
            message.chat.id,
            "🤖 **Generando plan semanal inteligente...**\n\n"
            "⚡ Analizando tu perfil nutricional\n"
            "🎯 Aplicando algoritmos de variedad\n"
            "🌊 Integrando ingredientes estacionales\n"
            "📊 Calculando métricas de calidad\n\n"
            "*Esto puede tomar unos segundos...*",
            parse_mode='Markdown'
        )
        
        # Preparar preferencias de semana
        if theme == "auto":
            # Auto-selección inteligente basada en el perfil del usuario
            auto_theme = determine_optimal_theme(user_profile)
            week_preferences = {
                "theme": auto_theme,
                "variety_level": 5,  # Máximo nivel de variedad
                "cooking_schedule": determine_optimal_cooking_schedule(user_profile),
                "auto_generated": True
            }
        else:
            week_preferences = {
                "theme": theme,
                "variety_level": 4,  # Alto nivel de variedad
                "cooking_schedule": "dos_sesiones"
            }
        
        # Generar plan semanal
        result = meal_bot.weekly_planner.generate_intelligent_week(
            user_profile, week_preferences
        )
        
        # Eliminar mensaje de procesamiento
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            # Formatear y enviar resultado
            formatted_plan = meal_bot.weekly_planner.format_weekly_plan_for_telegram(
                result, user_profile
            )
            
            # Crear botones de acción
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton("🛒 Lista de Compras", callback_data="week_shopping_list"),
                types.InlineKeyboardButton("🔄 Regenerar Semana", callback_data="week_regenerate")
            )
            keyboard.add(
                types.InlineKeyboardButton("⭐ Guardar Plan", callback_data="week_save"),
                types.InlineKeyboardButton("📊 Ver Métricas", callback_data="week_metrics")
            )
            
            meal_bot.send_long_message(
                message.chat.id, 
                formatted_plan, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            # Guardar plan en el perfil del usuario
            if "current_week_plan" not in user_profile:
                user_profile["current_week_plan"] = {}
            
            user_profile["current_week_plan"] = {
                "plan_data": result,
                "generated_at": datetime.now().isoformat(),
                "theme_used": theme
            }
            meal_bot.database.save_user_profile(telegram_id, user_profile)
            
        else:
            error_message = f"""
❌ **Error generando plan semanal**

**Error:** {result.get('error', 'Error desconocido')}

🔄 **Soluciones:**
• Intenta con otro tema semanal
• Verifica que tu perfil esté completo
• Usa `/help` si el problema persiste

**Puedes intentar de nuevo con `/nueva_semana`**
"""
            bot.send_message(message.chat.id, error_message, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error generating intelligent week: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ **Error interno:** {str(e)}\n\nIntenta de nuevo con `/nueva_semana`",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['nueva_semana'])
def nueva_semana_command(message):
    """Generar plan semanal inteligente"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Extraer argumentos del comando (tema opcional)
    command_parts = message.text.split()
    requested_theme = command_parts[1] if len(command_parts) > 1 else None
    
    # Crear teclado inline para selección de tema
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Botones de temas disponibles
    keyboard.add(
        types.InlineKeyboardButton("🌊 Mediterránea", callback_data="theme_mediterranea"),
        types.InlineKeyboardButton("💪 Alta Proteína", callback_data="theme_alta_proteina")
    )
    keyboard.add(
        types.InlineKeyboardButton("🌿 Detox Natural", callback_data="theme_detox_natural"),
        types.InlineKeyboardButton("⚡ Energía Sostenida", callback_data="theme_energia_sostenida")
    )
    keyboard.add(
        types.InlineKeyboardButton("🌈 Variedad Máxima", callback_data="theme_variedad_maxima")
    )
    keyboard.add(
        types.InlineKeyboardButton("🎯 Auto-selección IA", callback_data="theme_auto")
    )
    
    # Si se especificó tema, generar directamente
    if requested_theme and requested_theme in ['mediterranea', 'alta_proteina', 'detox_natural', 'energia_sostenida', 'variedad_maxima']:
        generate_intelligent_week(message, user_profile, requested_theme)
        return
    
    # Mostrar opciones de tema
    response_text = f"""
🗓️ **PLANIFICACIÓN SEMANAL INTELIGENTE**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Calorías diarias:** {user_profile['macros']['calories']} kcal
⚡ **Available Energy:** {user_profile['energy_data']['available_energy']} kcal/kg FFM

🎨 **TEMAS SEMANALES DISPONIBLES:**

🌊 **Mediterránea** - Ingredientes tradicionales mediterráneos
💪 **Alta Proteína** - Maximizar síntesis proteica y recuperación  
🌿 **Detox Natural** - Alimentos depurativos y antioxidantes
⚡ **Energía Sostenida** - Carbohidratos complejos y grasas saludables
🌈 **Variedad Máxima** - Máxima diversidad de ingredientes

🎯 **Auto-selección IA** - Deja que la IA elija el tema óptimo para ti

**Selecciona un tema para generar tu plan semanal inteligente:**
"""
    
    bot.send_message(
        message.chat.id,
        response_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['lista_compras'])
def lista_compras_command(message):
    """Generar lista de compras personalizada automática"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Mostrar opciones de duración
    response_text = f"""
🛒 **LISTA DE COMPRAS PERSONALIZADA**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Calorías diarias:** {user_profile['macros']['calories']} kcal

📅 **¿Para cuántos días quieres la lista?**

🅰️ **3 días** - Lista compacta para meal prep corto
🅱️ **5 días** - Lista estándar para semana laboral
🅲️ **7 días** - Lista completa para toda la semana
🅳️ **10 días** - Lista extendida para compra quincenal

**Responde con la letra de tu opción (A, B, C, D)**

✨ **La lista se adapta automáticamente a:**
• Tus alimentos preferidos (cantidades aumentadas)
• Alimentos que evitas (excluidos automáticamente)
• Tu objetivo nutricional específico
• Complementos mediterráneos optimizados
• Distribución inteligente por frescura
"""
    
    meal_bot.user_states[telegram_id] = {
        "state": "shopping_list_setup",
        "step": "choose_days"
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
    
    # Botones por timing (ocultando pre/post entreno según solicitud)
    keyboard.add(
        types.InlineKeyboardButton("🌅 Desayuno", callback_data="gen_desayuno"),
        types.InlineKeyboardButton("🍽️ Almuerzo", callback_data="gen_almuerzo")
    )
    keyboard.add(
        types.InlineKeyboardButton("🥜 Merienda", callback_data="gen_merienda"),
        types.InlineKeyboardButton("🌙 Cena", callback_data="gen_cena")
    )
    
    bot.send_message(
        message.chat.id,
        "🤖 **GENERACIÓN ESPECÍFICA DE RECETAS**\n\n"
        "Selecciona el tipo de receta que quieres generar según tu comida del día:\n\n"
        "🌅 **Desayuno:** Primera comida del día - energética y nutritiva\n"
        "🍽️ **Almuerzo:** Comida principal del mediodía - completa y saciante\n"
        "🥜 **Merienda:** Snack de la tarde - rico en micronutrientes\n"
        "🌙 **Cena:** Última comida del día - ligera y digestiva\n\n"
        "**Cada receta se adaptará automáticamente a tu perfil nutricional y enfoque dietético.**",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.message_handler(commands=['valorar'])
def valorar_command(message):
    """Valorar recetas específicas con escala 1-5 estrellas"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Verificar si hay recetas recientes generadas
    recent_recipes = user_profile.get("recent_generated_recipes", [])
    
    if not recent_recipes:
        no_recipes_text = """
⭐ **SISTEMA DE VALORACIÓN 1-5 ESTRELLAS**

❌ **No hay recetas para valorar**

Para valorar recetas necesitas:
1. 🤖 Generar recetas con `/generar`
2. 🔍 Buscar recetas con `/buscar [consulta]`
3. ✅ Seleccionar recetas de las opciones

💡 **¿Para qué sirven las valoraciones?**
• Mejorar recomendaciones futuras personalizadas
• Entrenar la IA con tus preferencias específicas
• Optimizar el algoritmo según tu feedback

🎯 **Genera algunas recetas primero y luego regresa aquí**
"""
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("🤖 Generar Recetas", callback_data="gen_comida_principal")
        )
        
        bot.send_message(
            message.chat.id,
            no_recipes_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    
    # Mostrar recetas disponibles para valorar
    response_text = """
⭐ **VALORAR RECETAS - ESCALA 1-5 ESTRELLAS**

📋 **Selecciona la receta que quieres valorar:**

"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Mostrar últimas 10 recetas
    for i, recipe_data in enumerate(recent_recipes[-10:], 1):
        recipe = recipe_data.get("recipe", {})
        recipe_name = recipe.get("nombre", f"Receta {i}")
        timing = recipe_data.get("timing_category", "")
        
        # Truncar nombre si es muy largo
        display_name = recipe_name if len(recipe_name) <= 35 else f"{recipe_name[:32]}..."
        
        # Agregar emoji según timing
        timing_emoji = {
            "desayuno": "🌅",
            "almuerzo": "🍽️",
            "merienda": "🥜",
            "cena": "🌙",
            "pre_entreno": "⚡",
            "post_entreno": "💪"
        }.get(timing, "🍽️")
        
        keyboard.add(
            types.InlineKeyboardButton(
                f"{timing_emoji} {display_name}",
                callback_data=f"rate_recipe_{i-1}"
            )
        )
    
    response_text += f"💫 **{len(recent_recipes[-10:])} recetas disponibles**\n\n"
    response_text += "🌟 **Escala de valoración:**\n"
    response_text += "⭐ = No me gustó\n"
    response_text += "⭐⭐ = Regular\n" 
    response_text += "⭐⭐⭐ = Buena\n"
    response_text += "⭐⭐⭐⭐ = Muy buena\n"
    response_text += "⭐⭐⭐⭐⭐ = Excelente\n\n"
    response_text += "🤖 **Tus valoraciones ayudan a la IA a generar mejores recomendaciones**"
    
    bot.send_message(
        message.chat.id,
        response_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.message_handler(commands=['valorar_receta'])
def valorar_receta_command(message):
    """Valorar receta para mejorar IA"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Verificar si hay recetas recientes generadas
    recent_recipes = user_profile.get("recent_generated_recipes", [])
    
    if not recent_recipes:
        no_recipes_text = """
⭐ **VALORAR RECETAS - SISTEMA DE APRENDIZAJE IA**

❌ **No hay recetas recientes para valorar**

Para poder valorar recetas necesitas:
1. 🤖 Generar recetas con `/generar`
2. 🔍 Buscar recetas con `/buscar [consulta]`
3. 📅 Crear plan semanal con `/nueva_semana`

💡 **¿Por qué valorar recetas?**
• La IA aprende tus preferencias automáticamente
• Mejoran las recomendaciones personalizadas
• El sistema se adapta a tu gusto específico
• Planes semanales más precisos

🚀 **Genera tu primera receta:**
"""
        
        # Crear botones para generar receta
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("🤖 Generar Receta", callback_data="gen_comida_principal"),
            types.InlineKeyboardButton("📅 Plan Semanal", callback_data="theme_auto")
        )
        
        bot.send_message(
            message.chat.id,
            no_recipes_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    
    # Mostrar recetas disponibles para valorar
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    response_text = f"""
⭐ **VALORAR RECETAS - APRENDER PREFERENCIAS**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🧠 **IA Score:** {meal_bot.recipe_intelligence._calculate_intelligence_score(user_profile.get('recipe_intelligence', {}))} /100

📋 **RECETAS DISPONIBLES PARA VALORAR:**

"""
    
    # Mostrar hasta 5 recetas más recientes
    for i, recipe in enumerate(recent_recipes[-5:]):
        recipe_name = recipe.get("nombre", f"Receta {i+1}")
        recipe_timing = recipe.get("categoria_timing", "general")
        calories = recipe.get("macros_por_porcion", {}).get("calorias", 0)
        
        response_text += f"**{i+1}.** {recipe_name}\n"
        response_text += f"   🎯 {recipe_timing.replace('_', ' ').title()} • {calories} kcal\n\n"
        
        # Botón para valorar esta receta específica
        keyboard.add(
            types.InlineKeyboardButton(
                f"⭐ Valorar: {recipe_name[:25]}{'...' if len(recipe_name) > 25 else ''}",
                callback_data=f"rate_recipe_{i}"
            )
        )
    
    # Botón para ver reporte de inteligencia
    keyboard.add(
        types.InlineKeyboardButton("🧠 Ver Reporte de IA", callback_data="show_intelligence_report")
    )
    
    response_text += """
💡 **ESCALA DE VALORACIÓN:**
⭐ = Muy malo (la IA evitará ingredientes/estilos similares)
⭐⭐ = Malo (reduce recomendaciones similares)  
⭐⭐⭐ = Neutro (sin cambios en preferencias)
⭐⭐⭐⭐ = Bueno (aumenta recomendaciones similares)
⭐⭐⭐⭐⭐ = Excelente (prioriza ingredientes/estilos similares)

**¡Cada valoración mejora automáticamente tus recomendaciones futuras!**
"""
    
    meal_bot.send_long_message(
        message.chat.id,
        response_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.message_handler(commands=['insights_ia'])
def insights_ia_command(message):
    """Ver análisis detallado de preferencias aprendidas por la IA"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Obtener insights detallados de preferencias
    insights = meal_bot.recipe_intelligence.get_user_preference_insights(user_profile)
    
    if not insights.get("insights_available"):
        not_available_text = """
🧠 **ANÁLISIS DE PREFERENCIAS IA**

❌ **Sin datos suficientes para análisis**

Para activar el análisis avanzado necesitas:
• 🤖 Generar recetas con `/generar`
• ⭐ Valorar recetas con `/valorar_receta`
• 🔄 Seleccionar opciones del sistema múltiple

💡 **¿Qué incluye el análisis IA?**
• Patrones de ingredientes preferidos/evitados
• Métodos de cocción que más te gustan
• Análisis nutricional personalizado
• Preferencias de timing (desayuno, almuerzo, etc.)
• Tendencias dietéticas identificadas
• Fuerza de las recomendaciones

🚀 **Comienza generando tu primera receta:**
"""
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("🤖 Generar Receta", callback_data="gen_comida_principal"),
            types.InlineKeyboardButton("⭐ Valorar Existentes", url="t.me/" + bot.get_me().username + "?start=valorar")
        )
        
        bot.send_message(
            message.chat.id,
            not_available_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    
    # Formatear insights detallados
    insights_text = f"""
🧠 **ANÁLISIS AVANZADO DE PREFERENCIAS IA**

👤 **Usuario:** {user_profile['basic_data']['objetivo_descripcion']}
📊 **Datos analizados:** {insights['total_data_points']} selecciones/valoraciones
🎯 **Confianza del sistema:** {insights['confidence_level']:.1f}/100
💪 **Fuerza recomendaciones:** {insights['recommendation_strength'].replace('_', ' ').title()}

"""
    
    # Análisis de ingredientes
    ingredient_insights = insights['ingredient_insights']
    if ingredient_insights.get('strong_preferences', 0) > 0:
        insights_text += "🥗 **ANÁLISIS DE INGREDIENTES:**\n"
        insights_text += f"• Preferencias fuertes: {ingredient_insights['strong_preferences']}\n"
        insights_text += f"• Rechazos identificados: {ingredient_insights['strong_dislikes']}\n"
        
        if ingredient_insights.get('preferred_proteins'):
            insights_text += f"• Proteínas favoritas: {', '.join(ingredient_insights['preferred_proteins'])}\n"
        
        if ingredient_insights.get('preferred_plants'):
            insights_text += f"• Vegetales preferidos: {', '.join(ingredient_insights['preferred_plants'])}\n"
        
        insights_text += f"• Patrón dietético: {ingredient_insights['dietary_pattern'].replace('_', ' ').title()}\n\n"
    
    # Análisis de métodos de cocción
    method_insights = insights['method_insights']
    if method_insights.get('preferred_methods'):
        insights_text += "👨‍🍳 **MÉTODOS DE COCCIÓN:**\n"
        insights_text += f"• Métodos preferidos: {', '.join(method_insights['preferred_methods'])}\n"
        insights_text += f"• Complejidad: {method_insights['complexity_preference'].title()}\n"
        insights_text += f"• Versatilidad: {method_insights['versatility_score']:.1%}\n\n"
    
    # Análisis nutricional
    nutrition_insights = insights['nutrition_insights']
    if nutrition_insights.get('preferred_macro_pattern'):
        insights_text += "🎯 **PATRONES NUTRICIONALES:**\n"
        insights_text += f"• Patrón de macros: {nutrition_insights['preferred_macro_pattern'].replace('_', ' ').title()}\n"
        insights_text += f"• Enfoque nutricional: {nutrition_insights['nutrition_focus'].replace('_', ' ').title()}\n"
        insights_text += f"• Flexibilidad: {nutrition_insights['flexibility']:.1%}\n\n"
    
    # Análisis de timing
    timing_insights = insights['timing_insights']
    if timing_insights.get('preferred_timing'):
        insights_text += "⏰ **PREFERENCIAS DE TIMING:**\n"
        insights_text += f"• Timing preferido: {timing_insights['preferred_timing'].replace('_', ' ').title()}\n"
        insights_text += f"• Flexibilidad horaria: {timing_insights['timing_flexibility']}/4\n"
        insights_text += f"• Enfoque en entreno: {'Sí' if timing_insights['training_focus'] else 'No'}\n\n"
    
    # Recomendaciones para mejorar
    insights_text += "💡 **RECOMENDACIONES PARA MEJORAR IA:**\n"
    
    if insights['total_data_points'] < 10:
        insights_text += "• Genera y valora más recetas (objetivo: 10+ valoraciones)\n"
    
    if insights['confidence_level'] < 50:
        insights_text += "• Usa toda la escala de valoración (1-5 estrellas)\n"
        insights_text += "• Selecciona opciones variadas en el sistema múltiple\n"
    
    if insights['recommendation_strength'] == 'weak':
        insights_text += "• Interactúa más frecuentemente con las recomendaciones\n"
    
    insights_text += f"""

🤖 **COMANDOS IA AVANZADOS:**
• `/valorar_receta` - Valorar para aprender
• `/generar` - Recetas personalizadas
• 🧠 Ver Reporte IA (en valorar recetas)

**¡La IA mejora automáticamente con cada interacción!**
"""
    
    meal_bot.send_long_message(
        message.chat.id,
        insights_text,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['progreso'])
def progreso_command(message):
    """Seguimiento de progreso y métricas del usuario"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Verificar si tiene datos de tracking
    tracking_data = user_profile.get("progress_tracking", {})
    has_data = tracking_data and tracking_data.get("metrics")
    
    if has_data:
        # Mostrar opciones de progreso
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("📊 Ver Reporte", callback_data="progress_report"),
            types.InlineKeyboardButton("📈 Registrar Métrica", callback_data="progress_record")
        )
        keyboard.add(
            types.InlineKeyboardButton("📅 Reporte Semanal", callback_data="progress_week"),
            types.InlineKeyboardButton("📆 Reporte Mensual", callback_data="progress_month")
        )
        keyboard.add(
            types.InlineKeyboardButton("🎯 Configurar Objetivos", callback_data="progress_goals")
        )
        
        # Obtener métricas básicas
        total_metrics = len(tracking_data.get("metrics", {}))
        total_records = sum(len(records) for records in tracking_data.get("metrics", {}).values())
        
        # Última métrica registrada
        last_record_date = "Nunca"
        for metric_records in tracking_data.get("metrics", {}).values():
            if metric_records:
                last_date = datetime.fromisoformat(metric_records[-1]["timestamp"])
                if last_record_date == "Nunca" or last_date > datetime.fromisoformat(last_record_date):
                    last_record_date = last_date.strftime("%d/%m/%Y")
        
        progress_text = f"""
📊 **SEGUIMIENTO DE PROGRESO**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🎯 **Objetivo:** {user_profile['basic_data']['objetivo'].replace('_', ' ').title()}

📈 **ESTADÍSTICAS DE TRACKING:**
• Métricas registradas: {total_metrics} tipos
• Total de registros: {total_records}
• Último registro: {last_record_date}

**¿Qué quieres hacer?**
"""
        
        bot.send_message(
            message.chat.id,
            progress_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    else:
        # Primera vez - introducir el sistema
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("📈 Registrar Primera Métrica", callback_data="progress_record"),
            types.InlineKeyboardButton("❓ ¿Cómo Funciona?", callback_data="progress_help")
        )
        
        intro_text = f"""
📊 **SISTEMA DE SEGUIMIENTO DE PROGRESO**

👤 **Tu objetivo:** {user_profile['basic_data']['objetivo_descripcion']}

🎯 **¿QUÉ PUEDES TRACKEAR?**
⚖️ Peso corporal
📊 Porcentaje de grasa
💪 Masa muscular  
📏 Circunferencia de cintura
⚡ Nivel de energía
💤 Calidad de sueño
🔄 Recuperación post-entreno
🍽️ Control del apetito

💡 **BENEFICIOS DEL TRACKING:**
• Análisis automático de tendencias
• Insights personalizados con IA
• Recomendaciones adaptativas
• Detección de patrones
• Ajustes automáticos del plan

🚀 **COMIENZA AHORA:**
**Registra tu primera métrica para activar el sistema inteligente de seguimiento.**
"""
        
        bot.send_message(
            message.chat.id,
            intro_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

@bot.message_handler(commands=['planificar_semana'])
def planificar_semana_command(message):
    """Generar cronograma optimizado de meal prep personalizado"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Extraer parámetros del comando (opcional)
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    # Configurar preferencias por defecto
    default_preferences = {
        "max_prep_time_hours": 6,
        "preferred_prep_days": ["domingo"],
        "max_session_hours": 4,
        "cooking_experience": "intermedio",
        "freshness_priority": 7,
        "time_efficiency_priority": 8,
        "storage_capacity": "medio",
        "kitchen_equipment": ["basico"]
    }
    
    # Si hay argumentos, permitir personalización rápida
    if args:
        if "rapido" in args:
            default_preferences["time_efficiency_priority"] = 10
            default_preferences["max_prep_time_hours"] = 4
        elif "fresco" in args:
            default_preferences["freshness_priority"] = 10
            default_preferences["preferred_prep_days"] = ["domingo", "miercoles"]
        elif "simple" in args:
            default_preferences["cooking_experience"] = "principiante"
            default_preferences["max_session_hours"] = 2
    
    # Mostrar mensaje de procesamiento
    processing_msg = bot.send_message(
        message.chat.id,
        "🗓️ **GENERANDO CRONOGRAMA OPTIMIZADO...**\n\n"
        "⚙️ Analizando tu perfil y restricciones\n"
        "📊 Calculando carga de trabajo total\n"
        "🎯 Optimizando distribución temporal\n"
        "📈 Aplicando algoritmos de eficiencia\n\n"
        "*Esto puede tomar unos segundos...*",
        parse_mode='Markdown'
    )
    
    try:
        # Generar cronograma optimizado
        result = meal_bot.meal_prep_scheduler.generate_optimized_schedule(
            user_profile, default_preferences
        )
        
        # Eliminar mensaje de procesamiento
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            # Formatear y enviar cronograma
            formatted_schedule = meal_bot.meal_prep_scheduler.format_schedule_for_telegram(
                result, user_profile
            )
            
            meal_bot.send_long_message(
                message.chat.id,
                formatted_schedule,
                parse_mode='Markdown'
            )
            
            # Botones de acciones rápidas
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton("📋 Lista de Compras", callback_data="generate_shopping_list"),
                types.InlineKeyboardButton("🗓️ Nuevo Cronograma", callback_data="new_schedule")
            )
            keyboard.add(
                types.InlineKeyboardButton("⚙️ Personalizar", callback_data="customize_schedule"),
                types.InlineKeyboardButton("📊 Ver Eficiencia", callback_data="schedule_metrics")
            )
            
            bot.send_message(
                message.chat.id,
                "🎯 **¿Qué quieres hacer con tu cronograma?**",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        else:
            error_msg = result.get("error", "Error desconocido")
            bot.send_message(
                message.chat.id,
                f"❌ **Error generando cronograma:**\n{error_msg}\n\n"
                "💡 **Intenta:**\n"
                "• Usar `/planificar_semana` de nuevo\n"
                "• Verificar que tu perfil esté completo con `/mis_macros`\n"
                "• Usar argumentos: `/planificar_semana rapido` o `/planificar_semana fresco`",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        # Eliminar mensaje de procesamiento si existe
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        logger.error(f"Error in planificar_semana_command: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ **Error procesando cronograma:**\n{str(e)}\n\n"
            "💡 **Soluciones:**\n"
            "• Intenta de nuevo en unos momentos\n"
            "• Verifica que tu perfil esté completo\n"
            "• Usa `/perfil` si es tu primera vez\n"
            "• Contacta soporte si persiste el error",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['analisis_nutricional'])
def analisis_nutricional_command(message):
    """Generar análisis nutricional profundo con IA avanzada"""
    telegram_id = str(message.from_user.id)
    
    if not meal_bot.create_user_if_not_exists(telegram_id, message):
        return
    
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    # Extraer período del comando (opcional)
    args = message.text.split()[1:]
    period = "month"  # Default
    
    if args:
        if "semana" in args[0].lower() or "week" in args[0].lower():
            period = "week"
        elif "trimestre" in args[0].lower() or "quarter" in args[0].lower():
            period = "quarter"
        elif "mes" in args[0].lower() or "month" in args[0].lower():
            period = "month"
    
    # Verificar datos suficientes
    progress_data = user_profile.get("progress_tracking", {})
    recipe_intelligence = user_profile.get("recipe_intelligence", {})
    
    has_progress_data = progress_data and progress_data.get("metrics")
    has_recipe_data = recipe_intelligence and recipe_intelligence.get("ratings_history")
    
    if not has_progress_data and not has_recipe_data:
        # Usuario sin datos - mostrar introducción
        intro_text = f"""
🧬 **ANÁLISIS NUTRICIONAL PROFUNDO CON IA**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}

❌ **DATOS INSUFICIENTES PARA ANÁLISIS COMPLETO**

🎯 **PARA DESBLOQUEAR ANÁLISIS PROFUNDO NECESITAS:**

📊 **DATOS DE PROGRESO:**
• Registra métricas con `/progreso`
• Mínimo: peso, energía, sueño (1 semana)
• Recomendado: 4+ métricas (2+ semanas)

⭐ **DATOS DE PREFERENCIAS:**
• Valora recetas con `/valorar_receta`
• Mínimo: 3 valoraciones
• Recomendado: 10+ valoraciones variadas

🔬 **EL ANÁLISIS INCLUIRÁ:**
• **Distribución de macronutrientes** - Adherencia vs objetivo
• **Estado de micronutrientes** - Deficiencias y fortalezas
• **Patrones de adherencia** - Consistencia y factores
• **Timing nutricional** - Optimización per objetivos
• **Variedad alimentaria** - Diversidad y monotonía
• **Correlaciones con progreso** - Qué funciona para ti
• **Puntuación nutricional global** - Score 0-100
• **Recomendaciones personalizadas** - IA adaptada

🚀 **PASOS PARA ACTIVAR:**
1. Usa `/progreso` para registrar primera métrica
2. Usa `/valorar_receta` para entrenar IA
3. Regresa en 3-7 días para análisis completo

💡 **ANÁLISIS DISPONIBLES:**
• `/analisis_nutricional semana` - Análisis semanal
• `/analisis_nutricional mes` - Análisis mensual (recomendado)
• `/analisis_nutricional trimestre` - Análisis de tendencias

**¡El análisis más avanzado se desbloquea con más datos!**
"""
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("📊 Registrar Métrica", callback_data="progress_record"),
            types.InlineKeyboardButton("⭐ Valorar Recetas", callback_data="start_rating")
        )
        keyboard.add(
            types.InlineKeyboardButton("❓ ¿Cómo Funciona?", callback_data="analytics_help")
        )
        
        meal_bot.send_long_message(
            message.chat.id,
            intro_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    
    # Usuario con datos - generar análisis
    period_names = {"week": "semanal", "month": "mensual", "quarter": "trimestral"}
    period_display = period_names.get(period, "mensual")
    
    # Mostrar mensaje de procesamiento
    processing_msg = bot.send_message(
        message.chat.id,
        f"🧬 **GENERANDO ANÁLISIS NUTRICIONAL {period_display.upper()}...**\n\n"
        "🔬 Analizando distribución de macronutrientes\n"
        "⚗️ Evaluando estado de micronutrientes\n"
        "📊 Calculando adherencia al plan\n"
        "⏰ Optimizando timing nutricional\n"
        "🌈 Analizando variedad alimentaria\n"
        "🔗 Detectando correlaciones con progreso\n"
        "🎯 Generando puntuación global\n"
        "💡 Creando recomendaciones con IA\n\n"
        "*Análisis profundo en proceso...*",
        parse_mode='Markdown'
    )
    
    try:
        # Generar análisis completo
        result = meal_bot.nutrition_analytics.generate_comprehensive_analysis(
            user_profile, period
        )
        
        # Eliminar mensaje de procesamiento
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            # Formatear y enviar análisis
            formatted_analysis = meal_bot.nutrition_analytics.format_analysis_for_telegram(
                result, user_profile
            )
            
            meal_bot.send_long_message(
                message.chat.id,
                formatted_analysis,
                parse_mode='Markdown'
            )
            
            # Botones de acciones basadas en análisis
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            
            # Acciones basadas en puntuación
            overall_score = result["nutrition_score"]["overall_score"]
            
            if overall_score < 70:
                keyboard.add(
                    types.InlineKeyboardButton("🎯 Plan de Mejora", callback_data="create_improvement_plan"),
                    types.InlineKeyboardButton("📋 Lista Optimizada", callback_data="generate_shopping_list")
                )
            else:
                keyboard.add(
                    types.InlineKeyboardButton("🔬 Análisis Avanzado", callback_data="advanced_analytics"),
                    types.InlineKeyboardButton("📊 Exportar Datos", callback_data="export_analytics")
                )
            
            keyboard.add(
                types.InlineKeyboardButton("🆕 Nuevo Análisis", callback_data="new_nutrition_analysis"),
                types.InlineKeyboardButton("📈 Ver Progreso", callback_data="progress_report")
            )
            
            bot.send_message(
                message.chat.id,
                f"🎯 **Análisis completado - Score: {overall_score:.1f}/100**\n\n"
                "**¿Qué quieres hacer con estos insights?**",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        else:
            error_msg = result.get("error", "Error desconocido")
            suggestions = result.get("suggestions", [])
            
            error_text = f"❌ **Error en análisis nutricional:**\n{error_msg}\n\n"
            
            if suggestions:
                error_text += "💡 **Sugerencias:**\n"
                for suggestion in suggestions:
                    error_text += f"• {suggestion}\n"
                error_text += "\n"
            
            error_text += "🔄 **Intenta:**\n"
            error_text += "• Registrar más métricas con `/progreso`\n"
            error_text += "• Valorar más recetas con `/valorar_receta`\n"
            error_text += "• Usar período más corto: `/analisis_nutricional semana`\n"
            error_text += "• Esperar unos días y repetir el análisis"
            
            bot.send_message(
                message.chat.id,
                error_text,
                parse_mode='Markdown'
            )
    
    except Exception as e:
        # Eliminar mensaje de procesamiento si existe
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        logger.error(f"Error in analisis_nutricional_command: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ **Error procesando análisis nutricional:**\n{str(e)}\n\n"
            "💡 **Soluciones:**\n"
            "• Verifica que tengas datos de progreso registrados\n"
            "• Intenta análisis semanal: `/analisis_nutricional semana`\n"
            "• Contacta soporte si el error persiste\n"
            "• Usa `/progreso` para registrar más datos",
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('theme_'))
def handle_theme_selection_callback(call):
    """Manejar callbacks de selección de tema semanal"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Extraer tema seleccionado
        theme_key = call.data.replace('theme_', '')
        
        user_profile = meal_bot.get_user_profile(telegram_id)
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        # Confirmar selección
        theme_names = {
            "mediterranea": "🌊 Mediterránea",
            "alta_proteina": "💪 Alta Proteína", 
            "detox_natural": "🌿 Detox Natural",
            "energia_sostenida": "⚡ Energía Sostenida",
            "variedad_maxima": "🌈 Variedad Máxima",
            "auto": "🎯 Auto-selección IA"
        }
        
        selected_theme_name = theme_names.get(theme_key, "Tema desconocido")
        
        bot.answer_callback_query(
            call.id, 
            f"✅ Generando plan {selected_theme_name}..."
        )
        
        # Crear mensaje simulado para la función helper
        class MockMessage:
            def __init__(self, chat_id):
                self.chat = type('obj', (object,), {'id': chat_id})
        
        mock_message = MockMessage(call.message.chat.id)
        
        # Generar plan semanal inteligente
        generate_intelligent_week(mock_message, user_profile, theme_key)
        
    except Exception as e:
        logger.error(f"Error in theme selection callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando selección")

@bot.callback_query_handler(func=lambda call: call.data.startswith('week_'))
def handle_week_actions_callback(call):
    """Manejar callbacks de acciones del plan semanal"""
    telegram_id = str(call.from_user.id)
    
    try:
        action = call.data.replace('week_', '')
        user_profile = meal_bot.get_user_profile(telegram_id)
        
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        current_plan = user_profile.get("current_week_plan")
        if not current_plan:
            bot.answer_callback_query(call.id, "❌ No hay plan activo")
            return
        
        if action == "shopping_list":
            # Generar lista de compras para el plan actual
            shopping_result = meal_bot.shopping_generator.generate_shopping_list(
                user_profile, days=5
            )
            
            if shopping_result["success"]:
                formatted_list = meal_bot.shopping_generator.format_shopping_list_for_telegram(
                    shopping_result, user_profile
                )
                meal_bot.send_long_message(
                    call.message.chat.id,
                    formatted_list,
                    parse_mode='Markdown'
                )
                bot.answer_callback_query(call.id, "✅ Lista generada")
            else:
                bot.answer_callback_query(call.id, "❌ Error generando lista")
        
        elif action == "regenerate":
            # Regenerar plan con el mismo tema
            theme_used = current_plan.get("theme_used", "auto")
            
            class MockMessage:
                def __init__(self, chat_id):
                    self.chat = type('obj', (object,), {'id': chat_id})
            
            mock_message = MockMessage(call.message.chat.id)
            generate_intelligent_week(mock_message, user_profile, theme_used)
            bot.answer_callback_query(call.id, "🔄 Regenerando plan...")
        
        elif action == "save":
            # Guardar plan en favoritos
            if "saved_weekly_plans" not in user_profile:
                user_profile["saved_weekly_plans"] = []
            
            # Agregar timestamp al plan guardado
            saved_plan = current_plan.copy()
            saved_plan["saved_at"] = datetime.now().isoformat() 
            saved_plan["plan_name"] = f"Plan {saved_plan['theme_used'].title()} - {datetime.now().strftime('%d/%m')}"
            
            user_profile["saved_weekly_plans"].append(saved_plan)
            
            # Mantener solo los últimos 10 planes guardados
            if len(user_profile["saved_weekly_plans"]) > 10:
                user_profile["saved_weekly_plans"] = user_profile["saved_weekly_plans"][-10:]
            
            meal_bot.database.save_user_profile(telegram_id, user_profile)
            bot.answer_callback_query(call.id, "⭐ Plan guardado en favoritos")
        
        elif action == "metrics":
            # Mostrar métricas detalladas del plan
            plan_data = current_plan["plan_data"]
            quality_metrics = plan_data["quality_metrics"]
            
            metrics_text = f"""
📊 **MÉTRICAS DETALLADAS DEL PLAN**

🎯 **Puntuación General:** {quality_metrics['overall_score']}/100

📈 **Análisis de Variedad:**
• Puntuación variedad: {quality_metrics['variety_score']}/5.0
• Diversidad ingredientes: {quality_metrics['ingredient_diversity']} tipos únicos
• Métodos de cocción: {quality_metrics['method_diversity']} diferentes

🌊 **Integración Temática:**
• Tema aplicado: {quality_metrics['theme_consistency']}
• Comidas estacionales: {quality_metrics['seasonal_integration']}

⭐ **Evaluación:**
"""
            
            # Añadir evaluación cualitativa
            if quality_metrics['overall_score'] >= 80:
                metrics_text += "✅ **Excelente** - Plan óptimo con alta variedad\n"
            elif quality_metrics['overall_score'] >= 60:
                metrics_text += "🟡 **Bueno** - Plan sólido con variedad aceptable\n"  
            else:
                metrics_text += "🔄 **Mejorable** - Considera regenerar el plan\n"
            
            metrics_text += f"\n💡 **Generado:** {datetime.fromisoformat(current_plan['generated_at']).strftime('%d/%m/%Y %H:%M')}"
            
            bot.send_message(
                call.message.chat.id,
                metrics_text,
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "📊 Métricas mostradas")
        
    except Exception as e:
        logger.error(f"Error in week actions callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando acción")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_recipe_'))
def handle_rate_recipe_callback(call):
    """Manejar callbacks de selección de receta para valorar"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Extraer índice de receta
        recipe_index = int(call.data.replace('rate_recipe_', ''))
        
        user_profile = meal_bot.get_user_profile(telegram_id)
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        recent_recipes = user_profile.get("recent_generated_recipes", [])
        if recipe_index >= len(recent_recipes):
            bot.answer_callback_query(call.id, "❌ Receta no encontrada")
            return
        
        selected_recipe = recent_recipes[-(recipe_index + 1)]  # Orden inverso
        
        # Crear teclado de valoración
        keyboard = types.InlineKeyboardMarkup(row_width=5)
        
        # Botones de estrellas
        star_buttons = []
        for rating in range(1, 6):
            stars = "⭐" * rating
            star_buttons.append(
                types.InlineKeyboardButton(stars, callback_data=f"rating_{recipe_index}_{rating}")
            )
        keyboard.add(*star_buttons)
        
        # Mostrar receta para valorar
        recipe_name = selected_recipe.get("nombre", "Receta sin nombre")
        macros = selected_recipe.get("macros_por_porcion", {})
        ingredients = selected_recipe.get("ingredientes", [])
        
        rating_text = f"""
⭐ **VALORAR RECETA ESPECÍFICA**

📋 **Receta:** {recipe_name}
🎯 **Timing:** {selected_recipe.get("categoria_timing", "general").replace("_", " ").title()}
🔥 **Calorías:** {macros.get("calorias", 0)} kcal
🥩 **Macros:** {macros.get("proteinas", 0)}P • {macros.get("carbohidratos", 0)}C • {macros.get("grasas", 0)}F

🛒 **Ingredientes principales:**
"""
        
        # Mostrar hasta 5 ingredientes principales
        for ingredient in ingredients[:5]:
            name = ingredient.get("nombre", "")
            quantity = ingredient.get("cantidad", 0)
            unit = ingredient.get("unidad", "")
            rating_text += f"• {name} ({quantity}{unit})\n"
        
        if len(ingredients) > 5:
            rating_text += f"• ... y {len(ingredients) - 5} ingredientes más\n"
        
        rating_text += f"""

💭 **¿Cómo valorarías esta receta?**

⭐ = Muy mala • ⭐⭐ = Mala • ⭐⭐⭐ = Regular • ⭐⭐⭐⭐ = Buena • ⭐⭐⭐⭐⭐ = Excelente

**Tu valoración ayuda a la IA a aprender tus preferencias automáticamente.**
"""
        
        bot.send_message(
            call.message.chat.id,
            rating_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id, f"✅ Seleccionada: {recipe_name[:20]}...")
        
    except Exception as e:
        logger.error(f"Error in rate recipe callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando selección")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rating_'))
def handle_rating_callback(call):
    """Manejar callbacks de valoración específica"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Extraer datos: rating_recipeIndex_rating
        parts = call.data.replace('rating_', '').split('_')
        recipe_index = int(parts[0])
        rating = int(parts[1])
        
        user_profile = meal_bot.get_user_profile(telegram_id)
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        recent_recipes = user_profile.get("recent_generated_recipes", [])
        if recipe_index >= len(recent_recipes):
            bot.answer_callback_query(call.id, "❌ Receta no encontrada")
            return
        
        selected_recipe = recent_recipes[-(recipe_index + 1)]
        
        # Aplicar aprendizaje con la inteligencia de recetas
        learning_result = meal_bot.recipe_intelligence.learn_from_rating(
            user_profile, selected_recipe, rating, ""
        )
        
        if learning_result["success"]:
            # Guardar perfil actualizado
            meal_bot.database.save_user_profile(telegram_id, user_profile)
            
            # Crear respuesta de confirmación
            stars = "⭐" * rating
            recipe_name = selected_recipe.get("nombre", "Receta")
            intelligence_score = learning_result["intelligence_score"]
            
            confirmation_text = f"""
✅ **VALORACIÓN REGISTRADA**

📋 **Receta:** {recipe_name}
⭐ **Tu valoración:** {stars} ({rating}/5)
🧠 **IA Score actualizado:** {intelligence_score}/100

🎯 **APRENDIZAJES DE ESTA VALORACIÓN:**
"""
            
            # Mostrar insights del aprendizaje
            learning_results = learning_result["learning_results"]
            
            if "ingredient_insights" in learning_results:
                insights = learning_results["ingredient_insights"]
                if insights.get("ingredients_affected", 0) > 0:
                    confirmation_text += f"• Ingredientes analizados: {insights['ingredients_affected']}\n"
            
            if "method_insights" in learning_results:
                insights = learning_results["method_insights"]
                if insights.get("methods_detected"):
                    methods = ", ".join(insights["methods_detected"])
                    confirmation_text += f"• Métodos detectados: {methods}\n"
            
            # Recomendaciones actualizadas
            recommendations = learning_result["updated_recommendations"]
            if recommendations.get("recommended_ingredients"):
                top_ingredients = recommendations["recommended_ingredients"][:3]
                confirmation_text += f"• Ingredientes ahora favoritos: {', '.join(top_ingredients)}\n"
            
            confirmation_text += f"""

💡 **IMPACTO EN FUTURAS RECOMENDACIONES:**
• Las recetas similares serán {'priorizadas' if rating >= 4 else 'penalizadas' if rating <= 2 else 'neutras'}
• Los ingredientes de esta receta {'suben' if rating >= 4 else 'bajan' if rating <= 2 else 'mantienen'} su puntuación
• El sistema aprende automáticamente de tu feedback

🚀 **PRÓXIMOS PASOS:**
• Genera más recetas con `/generar` para ver mejoras
• Crea plan semanal con `/nueva_semana` más personalizado
• Ve tu reporte completo con el botón de abajo
"""
            
            # Crear botón para ver reporte completo
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton("🧠 Ver Reporte Completo IA", callback_data="show_intelligence_report"),
                types.InlineKeyboardButton("⭐ Valorar Otra Receta", callback_data="back_to_rating")
            )
            
            bot.send_message(
                call.message.chat.id,
                confirmation_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            bot.answer_callback_query(call.id, f"✅ {stars} registrado - IA actualizada!")
            
        else:
            bot.answer_callback_query(call.id, "❌ Error registrando valoración")
            
    except Exception as e:
        logger.error(f"Error in rating callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando valoración")

@bot.callback_query_handler(func=lambda call: call.data == 'show_intelligence_report')
def handle_intelligence_report_callback(call):
    """Mostrar reporte completo de inteligencia"""
    telegram_id = str(call.from_user.id)
    
    try:
        user_profile = meal_bot.get_user_profile(telegram_id)
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        intelligence_profile = user_profile.get("recipe_intelligence", {})
        
        # Generar reporte completo
        report = meal_bot.recipe_intelligence.format_intelligence_report_for_telegram(
            intelligence_profile, user_profile
        )
        
        meal_bot.send_long_message(
            call.message.chat.id,
            report,
            parse_mode='Markdown'
        )
        
        bot.answer_callback_query(call.id, "📊 Reporte de IA generado")
        
    except Exception as e:
        logger.error(f"Error showing intelligence report: {e}")
        bot.answer_callback_query(call.id, "❌ Error generando reporte")

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_rating')
def handle_back_to_rating_callback(call):
    """Volver a la pantalla de valoración"""
    telegram_id = str(call.from_user.id)
    
    # Simular comando valorar_receta
    class MockMessage:
        def __init__(self, chat_id, from_user_id):
            self.chat = type('obj', (object,), {'id': chat_id})
            self.from_user = type('obj', (object,), {'id': from_user_id})
            self.text = "/valorar_receta"
    
    mock_message = MockMessage(call.message.chat.id, call.from_user.id)
    valorar_receta_command(mock_message)
    
    bot.answer_callback_query(call.id, "🔄 Volviendo a valoraciones...")

@bot.callback_query_handler(func=lambda call: call.data.startswith('progress_'))
def handle_progress_callback(call):
    """Manejar callbacks del sistema de progreso"""
    telegram_id = str(call.from_user.id)
    
    try:
        action = call.data.replace('progress_', '')
        user_profile = meal_bot.get_user_profile(telegram_id)
        
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        if action in ["report", "week", "month"]:
            # Generar reporte de progreso
            period_map = {"report": "month", "week": "week", "month": "month"}
            period = period_map[action]
            
            # Mostrar mensaje de generación
            processing_msg = bot.send_message(
                call.message.chat.id,
                "📊 **Generando reporte de progreso...**\n\n"
                "📈 Analizando tus métricas\n"
                "🎯 Calculando tendencias\n"
                "💡 Generando insights personalizados\n\n"
                "*Esto puede tomar unos segundos...*",
                parse_mode='Markdown'
            )
            
            report = meal_bot.progress_tracker.generate_progress_report(user_profile, period)
            
            # Eliminar mensaje de procesamiento
            bot.delete_message(call.message.chat.id, processing_msg.message_id)
            
            if report["success"]:
                formatted_report = meal_bot.progress_tracker.format_progress_report_for_telegram(
                    report, user_profile
                )
                
                meal_bot.send_long_message(
                    call.message.chat.id,
                    formatted_report,
                    parse_mode='Markdown'
                )
                
                bot.answer_callback_query(call.id, f"📊 Reporte {period} generado")
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"❌ **Error generando reporte:** {report.get('error', 'Error desconocido')}",
                    parse_mode='Markdown'
                )
                bot.answer_callback_query(call.id, "❌ Error generando reporte")
        
        elif action == "record":
            # Mostrar opciones de métricas para registrar
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            
            # Métricas principales
            keyboard.add(
                types.InlineKeyboardButton("⚖️ Peso", callback_data="metric_weight"),
                types.InlineKeyboardButton("📊 % Grasa", callback_data="metric_body_fat")
            )
            keyboard.add(
                types.InlineKeyboardButton("💪 Masa Muscular", callback_data="metric_muscle_mass"),
                types.InlineKeyboardButton("📏 Cintura", callback_data="metric_waist_circumference")
            )
            keyboard.add(
                types.InlineKeyboardButton("⚡ Energía", callback_data="metric_energy_level"),
                types.InlineKeyboardButton("💤 Sueño", callback_data="metric_sleep_quality")
            )
            keyboard.add(
                types.InlineKeyboardButton("🔄 Recuperación", callback_data="metric_recovery_rate"),
                types.InlineKeyboardButton("🍽️ Apetito", callback_data="metric_appetite")
            )
            
            bot.send_message(
                call.message.chat.id,
                "📈 **REGISTRAR MÉTRICA**\n\n"
                "**Selecciona la métrica que quieres registrar:**\n\n"
                "⚖️ **Peso** - Peso corporal en kg\n"
                "📊 **% Grasa** - Porcentaje de grasa corporal\n"
                "💪 **Masa Muscular** - Masa muscular en kg\n"
                "📏 **Cintura** - Circunferencia de cintura en cm\n"
                "⚡ **Energía** - Nivel de energía (1-10)\n"
                "💤 **Sueño** - Calidad de sueño (1-10)\n"
                "🔄 **Recuperación** - Recuperación post-entreno (1-10)\n"
                "🍽️ **Apetito** - Control del apetito (1-10)",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            bot.answer_callback_query(call.id, "📈 Selecciona métrica a registrar")
        
        elif action == "goals":
            # Configurar objetivos (funcionalidad futura)
            bot.send_message(
                call.message.chat.id,
                "🎯 **CONFIGURACIÓN DE OBJETIVOS**\n\n"
                "🚧 Esta funcionalidad estará disponible próximamente.\n\n"
                "**Por ahora puedes:**\n"
                "• Registrar métricas regularmente\n"
                "• Ver reportes de progreso\n"
                "• Seguir las recomendaciones automáticas\n\n"
                "El sistema aprende automáticamente de tus datos y ajusta las recomendaciones.",
                parse_mode='Markdown'
            )
            
            bot.answer_callback_query(call.id, "🚧 Próximamente disponible")
        
        elif action == "help":
            # Ayuda del sistema de progreso
            help_text = """
📊 **CÓMO FUNCIONA EL SISTEMA DE PROGRESO**

🎯 **OBJETIVO:**
Trackear automáticamente tu progreso hacia tus objetivos nutricionales y de fitness.

📈 **PROCESO:**
1️⃣ **Registras métricas** (peso, energía, etc.)
2️⃣ **El sistema analiza** tendencias automáticamente
3️⃣ **Recibes insights** personalizados con IA
4️⃣ **Se ajusta tu plan** según el progreso

💡 **BENEFICIOS:**
• **Análisis automático** de tendencias
• **Detección de patrones** en tu progreso
• **Recomendaciones adaptativas** según datos
• **Ajustes automáticos** del Available Energy
• **Insights personalizados** con IA

📊 **MÉTRICAS DISPONIBLES:**
⚖️ **Físicas:** Peso, grasa, masa muscular, cintura
⚡ **Bienestar:** Energía, sueño, recuperación, apetito

🔬 **ANÁLISIS INCLUIDO:**
• Tendencias semanales/mensuales
• Comparaciones con objetivos
• Detección de correlaciones
• Predicciones de progreso

🚀 **PRÓXIMOS PASOS:**
• Registra tu primera métrica
• Usa `/progreso` regularmente
• Sigue las recomendaciones automáticas
"""
            
            meal_bot.send_long_message(
                call.message.chat.id,
                help_text,
                parse_mode='Markdown'
            )
            
            bot.answer_callback_query(call.id, "ℹ️ Información mostrada")
        
    except Exception as e:
        logger.error(f"Error in progress callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando acción")

@bot.callback_query_handler(func=lambda call: call.data.startswith('metric_'))
def handle_metric_callback(call):
    """Manejar callbacks de selección de métrica específica"""
    telegram_id = str(call.from_user.id)
    
    try:
        metric_name = call.data.replace('metric_', '')
        user_profile = meal_bot.get_user_profile(telegram_id)
        
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Error: Perfil no encontrado")
            return
        
        # Generar ayuda para entrada de métrica
        help_text = meal_bot.progress_tracker.get_metric_entry_keyboard(metric_name)
        
        # Configurar estado para entrada de métrica
        meal_bot.user_states[telegram_id] = {
            "state": "metric_entry",
            "metric_name": metric_name,
            "step": "value"
        }
        
        bot.send_message(
            call.message.chat.id,
            help_text,
            parse_mode='Markdown'
        )
        
        metric_config = meal_bot.progress_tracker.trackable_metrics.get(metric_name, {})
        metric_display_name = metric_config.get("name", "Métrica")
        
        bot.answer_callback_query(call.id, f"📝 Registrando {metric_display_name}")
        
    except Exception as e:
        logger.error(f"Error in metric callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando métrica")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_profile_callback(call):
    """Manejar callbacks de edición de perfil"""
    telegram_id = str(call.from_user.id)
    
    if call.data == "cancel_edit":
        bot.edit_message_text(
            "❌ **Edición cancelada**\n\nTus preferencias no han sido modificadas.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "Edición cancelada")
        return
    
    # Mapear callback a sección de preferencias
    edit_sections = {
        "edit_liked_foods": {
            "section": "liked_foods",
            "title": "🍽️ ALIMENTOS PREFERIDOS",
            "step": "9C",
            "description": "Selecciona los alimentos que más te gustan. Puedes elegir múltiples opciones:"
        },
        "edit_disliked_foods": {
            "section": "disliked_foods", 
            "title": "🚫 ALIMENTOS A EVITAR",
            "step": "9D",
            "description": "Selecciona alimentos que prefieres evitar. Puedes elegir múltiples opciones:"
        },
        "edit_cooking_methods": {
            "section": "cooking_methods",
            "title": "👨‍🍳 MÉTODOS DE COCCIÓN",
            "step": "9F", 
            "description": "Selecciona tus métodos de cocción preferidos. Puedes elegir múltiples opciones:"
        },
        "edit_training_schedule": {
            "section": "training_schedule",
            "title": "⏰ HORARIO DE ENTRENAMIENTO",
            "step": "7",
            "description": "Selecciona tu horario habitual de entrenamiento:"
        }
    }
    
    section_data = edit_sections.get(call.data)
    if not section_data:
        bot.answer_callback_query(call.id, "❌ Opción no válida", show_alert=True)
        return
    
    # Configurar estado de edición
    meal_bot.user_states[telegram_id] = {
        "state": "profile_edit",
        "step": section_data["step"],
        "edit_section": section_data["section"],
        "data": {}
    }
    
    bot.answer_callback_query(call.id, f"Editando {section_data['title']}")
    
    # Redirigir al paso específico de configuración
    if section_data["step"] == "9C":
        handle_edit_liked_foods(call.message, telegram_id)
    elif section_data["step"] == "9D":
        handle_edit_disliked_foods(call.message, telegram_id)
    elif section_data["step"] == "9F":
        handle_edit_cooking_methods(call.message, telegram_id)
    elif section_data["step"] == "7":
        handle_edit_training_schedule(call.message, telegram_id)

def handle_edit_liked_foods(message, telegram_id):
    """Manejar edición de alimentos preferidos"""
    # Obtener preferencias actuales
    user_profile = meal_bot.get_user_profile(telegram_id)
    current_liked = user_profile.get("preferences", {}).get("liked_foods", [])
    
    # Reutilizar lógica del paso 9C del setup inicial
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    food_options = [
        "🥩 Carnes rojas", "🐔 Aves", "🐟 Pescados", "🥚 Huevos",
        "🥛 Lácteos", "🥜 Frutos secos", "🫘 Legumbres", "🥬 Hojas verdes",
        "🥦 Crucíferas", "🍅 Solanáceas", "🌿 Aromáticas", "🥕 Raíces",
        "🌶️ Pimientos", "🥒 Pepináceas", "🫒 Aceitunas", "🥑 Aguacate",
        "➡️ Continuar"
    ]
    
    buttons = [types.KeyboardButton(option) for option in food_options]
    markup.add(*buttons)
    
    selected_text = f"**Actualmente seleccionados:** {', '.join(current_liked) if current_liked else 'Ninguno'}"
    
    bot.edit_message_text(
        f"🍽️ **EDITANDO ALIMENTOS PREFERIDOS**\n\n"
        f"Selecciona los alimentos que más te gustan. Puedes elegir múltiples opciones.\n\n"
        f"{selected_text}\n\n"
        f"💡 Selecciona una opción o usa **➡️ Continuar** para finalizar.",
        message.chat.id,
        message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_edit_disliked_foods(message, telegram_id):
    """Manejar edición de alimentos a evitar"""
    user_profile = meal_bot.get_user_profile(telegram_id)
    current_disliked = user_profile.get("preferences", {}).get("disliked_foods", [])
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    food_options = [
        "🥩 Carnes rojas", "🐔 Aves", "🐟 Pescados", "🥚 Huevos",
        "🥛 Lácteos", "🥜 Frutos secos", "🫘 Legumbres", "🥬 Hojas verdes",
        "🥦 Crucíferas", "🍅 Solanáceas", "🌿 Aromáticas", "🥕 Raíces",
        "🌶️ Pimientos", "🥒 Pepináceas", "🫒 Aceitunas", "🥑 Aguacate",
        "➡️ Continuar"
    ]
    
    buttons = [types.KeyboardButton(option) for option in food_options]
    markup.add(*buttons)
    
    selected_text = f"**Actualmente evitados:** {', '.join(current_disliked) if current_disliked else 'Ninguno'}"
    
    bot.edit_message_text(
        f"🚫 **EDITANDO ALIMENTOS A EVITAR**\n\n"
        f"Selecciona alimentos que prefieres evitar. Puedes elegir múltiples opciones.\n\n"
        f"{selected_text}\n\n"
        f"💡 Selecciona una opción o usa **➡️ Continuar** para finalizar.",
        message.chat.id,
        message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_edit_cooking_methods(message, telegram_id):
    """Manejar edición de métodos de cocción"""
    user_profile = meal_bot.get_user_profile(telegram_id)
    current_methods = user_profile.get("preferences", {}).get("cooking_methods", [])
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    cooking_options = [
        "🔥 Horno", "🍳 Sartén", "🥘 Plancha", "🫕 Vapor",
        "🥗 Crudo/Ensaladas", "🍲 Guisado", "🔥 Parrilla", "🥄 Hervido",
        "➡️ Continuar"
    ]
    
    buttons = [types.KeyboardButton(option) for option in cooking_options]
    markup.add(*buttons)
    
    selected_text = f"**Actualmente seleccionados:** {', '.join(current_methods) if current_methods else 'Ninguno'}"
    
    bot.edit_message_text(
        f"👨‍🍳 **EDITANDO MÉTODOS DE COCCIÓN**\n\n"
        f"Selecciona tus métodos de cocción preferidos. Puedes elegir múltiples opciones.\n\n"
        f"{selected_text}\n\n"
        f"💡 Selecciona una opción o usa **➡️ Continuar** para finalizar.",
        message.chat.id,
        message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_edit_training_schedule(message, telegram_id):
    """Manejar edición de horario de entrenamiento"""
    user_profile = meal_bot.get_user_profile(telegram_id)
    current_schedule = user_profile.get("exercise_profile", {}).get("training_schedule_desc", "No especificado")
    
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    
    schedule_options = [
        "🌅 Mañana (6:00-12:00)",
        "☀️ Mediodía (12:00-16:00)", 
        "🌆 Tarde (16:00-20:00)",
        "🌙 Noche (20:00-24:00)",
        "🔄 Variable/Cambia"
    ]
    
    buttons = [types.KeyboardButton(option) for option in schedule_options]
    markup.add(*buttons)
    
    bot.edit_message_text(
        f"⏰ **EDITANDO HORARIO DE ENTRENAMIENTO**\n\n"
        f"¿Cuándo sueles entrenar habitualmente?\n\n"
        f"**Horario actual:** {current_schedule}\n\n"
        f"Selecciona tu nuevo horario:",
        message.chat.id,
        message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

def create_favorite_buttons(telegram_id: str, recipe_id: str) -> types.InlineKeyboardMarkup:
    """Crear botones de favoritos para una receta"""
    user_profile = meal_bot.get_user_profile(telegram_id)
    is_favorite = meal_bot.profile_system.is_recipe_favorite(user_profile, recipe_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if is_favorite:
        # Botón para quitar de favoritos
        markup.add(
            types.InlineKeyboardButton("🚫 Quitar de favoritos", callback_data=f"fav_remove_{recipe_id}"),
            types.InlineKeyboardButton("⭐ Ver favoritas", callback_data="fav_view_all")
        )
    else:
        # Botón para añadir a favoritos
        markup.add(
            types.InlineKeyboardButton("⭐ Añadir a favoritos", callback_data=f"fav_add_{recipe_id}"),
            types.InlineKeyboardButton("📚 Ver favoritas", callback_data="fav_view_all")
        )
    
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('fav_'))
def handle_favorite_callback(call):
    """Manejar callbacks de favoritos"""
    telegram_id = str(call.from_user.id)
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    if not user_profile:
        bot.answer_callback_query(call.id, "❌ Configura tu perfil primero", show_alert=True)
        return
    
    if call.data == "fav_view_all":
        # Mostrar todas las favoritas
        bot.answer_callback_query(call.id, "📚 Mostrando favoritas...")
        favoritas_command(call.message)
        return
    
    # Extraer acción y recipe_id
    parts = call.data.split('_', 2)
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "❌ Comando no válido", show_alert=True)
        return
    
    action = parts[1]  # 'add' o 'remove'
    recipe_id = parts[2]
    
    try:
        if action == "add":
            # Añadir a favoritos
            meal_bot.profile_system.add_to_favorites(user_profile, recipe_id)
            meal_bot.data["users"][telegram_id] = user_profile
            meal_bot.save_data()
            
            bot.answer_callback_query(call.id, "⭐ Añadido a favoritos!", show_alert=False)
            
            # Actualizar botones
            new_markup = create_favorite_buttons(telegram_id, recipe_id)
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=new_markup
                )
            except:
                pass  # Si no se puede editar, continuar
            
        elif action == "remove":
            # Quitar de favoritos
            meal_bot.profile_system.remove_from_favorites(user_profile, recipe_id)
            meal_bot.data["users"][telegram_id] = user_profile
            meal_bot.save_data()
            
            bot.answer_callback_query(call.id, "🚫 Quitado de favoritos", show_alert=False)
            
            # Actualizar botones
            new_markup = create_favorite_buttons(telegram_id, recipe_id)
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=new_markup
                )
            except:
                pass  # Si no se puede editar, continuar
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('gen_'))
def handle_generation_callback(call):
    """Manejar callbacks de generación de múltiples opciones de recetas"""
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
        "gen_desayuno": {
            "timing_category": "desayuno",
            "function_category": "equilibrio_nutricional",
            "target_macros": {"protein": 25, "carbs": 45, "fat": 15, "calories": 380}
        },
        "gen_almuerzo": {
            "timing_category": "almuerzo",
            "function_category": "equilibrio_nutricional",
            "target_macros": {"protein": 40, "carbs": 50, "fat": 20, "calories": 480}
        },
        "gen_merienda": {
            "timing_category": "merienda",
            "function_category": "micronutrientes", 
            "target_macros": {"protein": 15, "carbs": 20, "fat": 12, "calories": 220}
        },
        "gen_cena": {
            "timing_category": "cena",
            "function_category": "equilibrio_nutricional",
            "target_macros": {"protein": 35, "carbs": 25, "fat": 18, "calories": 360}
        }
    }
    
    # Limpiar callback data para manejar "_more_timestamp"
    clean_callback = call.data.split('_more_')[0]
    
    request_data = timing_map.get(clean_callback)
    if not request_data:
        bot.answer_callback_query(call.id, "❌ Opción no válida", show_alert=True)
        return
    
    # Si es una solicitud de "más opciones", agregar indicador de variabilidad
    is_more_request = '_more_' in call.data
    if is_more_request:
        # Agregar timestamp para forzar variabilidad en el prompt
        request_data = request_data.copy()
        request_data['variability_seed'] = call.data.split('_more_')[1]
        request_data['generation_type'] = 'more_options'
    
    bot.answer_callback_query(call.id, "🤖 Generando 5 opciones personalizadas...")
    
    # Mensaje de procesamiento
    timing_display = {
        "pre_entreno": "⚡ PRE-ENTRENO",
        "post_entreno": "💪 POST-ENTRENO",
        "desayuno": "🌅 DESAYUNO",
        "almuerzo": "🍽️ ALMUERZO",
        "merienda": "🥜 MERIENDA",
        "cena": "🌙 CENA"
    }.get(request_data['timing_category'], request_data['timing_category'].upper())
    
    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🤖 **GENERANDO 5 OPCIONES PARA {timing_display}**\n\n"
        f"📊 **Macros objetivo:** {request_data['target_macros']['calories']} kcal por opción\n"
        f"👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}\n\n"
        "⏳ Procesando con IA...\n"
        "🎨 Creando variedad de ingredientes...\n"
        "👨‍🍳 Variando técnicas de cocción...\n"
        "🧬 Adaptando a tus preferencias...\n"
        "✅ Validando calidad nutricional...\n\n"
        "*Esto puede tomar 10-15 segundos...*",
        parse_mode='Markdown'
    )
    
    try:
        # Generar múltiples opciones con IA
        result = meal_bot.ai_generator.generate_multiple_recipes(user_profile, request_data, num_options=5)
        
        # Borrar mensaje de procesamiento
        bot.delete_message(call.message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            # Importar la función de formateo
            from ai_integration import format_multiple_recipes_for_display
            
            # Formatear opciones para display
            options_text = format_multiple_recipes_for_display(result, request_data['timing_category'])
            
            # Crear botones de selección
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            
            # Botones para cada opción
            options = result.get("options", [])
            for i, option in enumerate(options[:5], 1):  # Máximo 5 opciones
                recipe_name = option["recipe"]["nombre"]
                # Acortar nombre si es muy largo
                display_name = recipe_name if len(recipe_name) <= 25 else f"{recipe_name[:22]}..."
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"✅ Opción {i}: {display_name}", 
                        callback_data=f"select_recipe_{i}_{request_data['timing_category']}"
                    )
                )
            
            # Botón para generar más opciones con timestamp para forzar variabilidad
            import time
            timestamp = int(time.time())
            keyboard.add(
                types.InlineKeyboardButton(
                    "🔄 Generar 5 opciones nuevas", 
                    callback_data=f"{call.data}_more_{timestamp}"
                )
            )
            
            # Enviar opciones con botones
            meal_bot.send_long_message(
                call.message.chat.id, 
                options_text, 
                parse_mode='Markdown', 
                reply_markup=keyboard
            )
            
            # Guardar las opciones temporalmente para cuando el usuario seleccione
            if "temp_recipe_options" not in user_profile:
                user_profile["temp_recipe_options"] = {}
            
            user_profile["temp_recipe_options"][request_data['timing_category']] = {
                "options": options,
                "generated_at": datetime.now().isoformat(),
                "request_data": request_data
            }
            
            # Guardar en la base de datos
            meal_bot.data["users"][telegram_id] = user_profile
            meal_bot.save_data()
            
        else:
            error_msg = result.get("error", "Error desconocido")
            bot.send_message(
                call.message.chat.id,
                f"❌ **Error generando opciones:**\n{error_msg}\n\n"
                "💡 **Intenta:**\n"
                "• Usar /generar de nuevo\n"
                "• Verificar tu conexión\n"
                "• Usar /buscar para búsqueda libre",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in multiple recipe generation: {e}")
        try:
            bot.delete_message(call.message.chat.id, processing_msg.message_id)
        except:
            pass
        bot.send_message(
            call.message.chat.id,
            "❌ **Error técnico** generando las opciones.\n"
            "Inténtalo de nuevo en unos momentos.",
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_recipe_'))
def handle_recipe_selection_callback(call):
    """Manejar la selección de una receta específica de las múltiples opciones"""
    telegram_id = str(call.from_user.id)
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    if not user_profile:
        bot.answer_callback_query(call.id, "❌ Configura tu perfil primero", show_alert=True)
        return
    
    try:
        # Parsear callback data: select_recipe_{option_number}_{timing_category}
        parts = call.data.split('_')
        if len(parts) != 4:
            bot.answer_callback_query(call.id, "❌ Formato de callback inválido", show_alert=True)
            return
        
        option_number = int(parts[2])
        timing_category = parts[3]
        
        # Obtener opciones temporales guardadas
        temp_options = user_profile.get("temp_recipe_options", {}).get(timing_category)
        if not temp_options:
            bot.answer_callback_query(call.id, "❌ Opciones expiradas. Genera nuevas opciones.", show_alert=True)
            return
        
        options = temp_options.get("options", [])
        if option_number < 1 or option_number > len(options):
            bot.answer_callback_query(call.id, "❌ Opción no válida", show_alert=True)
            return
        
        # Obtener la receta seleccionada
        selected_option = options[option_number - 1]
        recipe = selected_option["recipe"]
        validation = selected_option["validation"]
        request_data = temp_options["request_data"]
        
        bot.answer_callback_query(call.id, f"✅ Opción {option_number} seleccionada!")
        
        # Guardar receta en el perfil del usuario
        save_success = meal_bot.save_generated_recipe(telegram_id, recipe, timing_category, validation)
        
        # Formatear receta completa para mostrar
        from ai_integration import format_recipe_for_display
        recipe_text = format_recipe_for_display(recipe, validation)
        
        # Mensaje de confirmación simple con nombre de la receta
        recipe_name = recipe.get("nombre", "Receta")
        confirmation_message = f"✅ {recipe_name} guardada en tu historial"
        
        success_text = confirmation_message
        
        # Limpiar opciones temporales después de la selección
        if "temp_recipe_options" in user_profile:
            if timing_category in user_profile["temp_recipe_options"]:
                del user_profile["temp_recipe_options"][timing_category]
            
            # Guardar cambios
            meal_bot.data["users"][telegram_id] = user_profile
            meal_bot.save_data()
        
        # Enviar mensaje de confirmación simple (sin submenú)
        bot.send_message(
            call.message.chat.id, 
            success_text, 
            parse_mode='Markdown'
        )
        
        # Sistema de aprendizaje: registrar la selección y rechazos
        if hasattr(meal_bot, 'recipe_intelligence'):
            try:
                # Registrar la receta seleccionada (valoración positiva implícita)
                selection_result = meal_bot.recipe_intelligence.register_recipe_selection(
                    telegram_id, 
                    recipe, 
                    timing_category,
                    option_number,
                    len(options),
                    user_profile
                )
                
                # Registrar las opciones no seleccionadas (valoración negativa implícita)
                all_recipes = [opt["recipe"] for opt in options]
                rejection_result = meal_bot.recipe_intelligence.register_recipe_rejection(
                    telegram_id,
                    all_recipes,
                    option_number,
                    timing_category,
                    user_profile
                )
                
                logger.info(f"Learning system updated: selection={selection_result.get('success')}, rejections={rejection_result.get('success')}")
                
                # Guardar el perfil actualizado con los aprendizajes
                if selection_result.get('success'):
                    meal_bot.database.save_user_profile(telegram_id, user_profile)
                
            except Exception as e:
                logger.error(f"Error registering recipe learning: {e}")
        
    except ValueError:
        bot.answer_callback_query(call.id, "❌ Número de opción inválido", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling recipe selection: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando selección", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('schedule_'))
def handle_schedule_callback(call):
    """Manejar callbacks de selección de cronograma"""
    telegram_id = str(call.from_user.id)
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    if not user_profile:
        bot.answer_callback_query(call.id, "❌ Configura tu perfil primero", show_alert=True)
        return
    
    # Extraer el tipo de cronograma seleccionado
    schedule_type = call.data.replace('schedule_', '')
    
    # Verificar que el cronograma existe
    schedule_data = meal_bot.data['cooking_schedules'].get(schedule_type, {})
    
    if not schedule_data:
        bot.answer_callback_query(call.id, "❌ Cronograma no encontrado", show_alert=True)
        return
    
    # Guardar la selección en el perfil del usuario
    if 'settings' not in user_profile:
        user_profile['settings'] = {}
    user_profile['settings']['cooking_schedule'] = schedule_type
    meal_bot.save_data()
    
    bot.answer_callback_query(call.id, "✅ Cronograma seleccionado")
    
    # Mostrar el cronograma seleccionado
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

**Comandos relacionados:**
• /compras - Lista de compras para este cronograma
• /menu - Ver distribución nutricional semanal
• /planificar_semana - Optimización avanzada
"""
    
    bot.edit_message_text(
        text=response_text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_search_recipe_'))
def handle_search_recipe_selection_callback(call):
    """Manejar selección de receta de búsqueda"""
    telegram_id = str(call.from_user.id)
    user_profile = meal_bot.get_user_profile(telegram_id)
    
    if not user_profile:
        bot.answer_callback_query(call.id, "❌ Configura tu perfil primero", show_alert=True)
        return
    
    # Verificar estado del usuario
    user_state = meal_bot.user_states.get(telegram_id, {})
    if user_state.get("state") != "search_results":
        bot.answer_callback_query(call.id, "❌ Sesión expirada. Intenta la búsqueda de nuevo.", show_alert=True)
        return
    
    # Extraer índice de la receta seleccionada
    recipe_index = int(call.data.replace('select_search_recipe_', ''))
    results = user_state.get("results", [])
    
    if recipe_index >= len(results):
        bot.answer_callback_query(call.id, "❌ Receta no encontrada", show_alert=True)
        return
    
    # Obtener la receta seleccionada
    selected_result = results[recipe_index]
    recipe = selected_result.get("adaptacion_propuesta")
    validation = selected_result.get("validation", {})
    
    if not recipe:
        bot.answer_callback_query(call.id, "❌ Error al obtener la receta", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, f"✅ Receta {recipe_index + 1} seleccionada")
    
    # Determinar categoría de timing para guardar la receta
    timing_category = recipe.get("categoria_timing", "almuerzo")  # Default a almuerzo
    
    # Guardar la receta seleccionada
    success = meal_bot.save_generated_recipe(telegram_id, recipe, timing_category, validation)
    
    if success:
        response_text = f"""
✅ **RECETA GUARDADA EXITOSAMENTE**

📚 **"{recipe.get('nombre', 'Receta')}"** ha sido añadida a tus recetas.

**¿Qué sigue?**
• `/recetas` - Ver todas tus recetas guardadas
• `/valorar_receta` - Valorar para mejorar la IA
• `/generar` - Crear más recetas específicas
• `/nueva_semana` - Generar plan completo

💡 **La IA aprende de tus selecciones para futuras recomendaciones.**
"""
    else:
        response_text = """
❌ **Error al guardar la receta**

Intenta de nuevo o contacta soporte si el problema persiste.
"""
    
    bot.edit_message_text(
        text=response_text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode='Markdown'
    )
    
    # Limpiar estado del usuario
    if telegram_id in meal_bot.user_states:
        del meal_bot.user_states[telegram_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('more_search_options_'))
def handle_more_search_options_callback(call):
    """Manejar solicitud de más opciones de búsqueda"""
    telegram_id = str(call.from_user.id)
    query = call.data.replace('more_search_options_', '')
    
    bot.answer_callback_query(call.id, "🔄 Buscando más opciones...")
    
    # Editar mensaje para mostrar que está procesando
    bot.edit_message_text(
        text=f"🤖 **Buscando más opciones para:** '{query}'\n\n"
             "⏳ Generando nuevas recetas con IA...\n"
             "📊 Adaptando a tu perfil nutricional...",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode='Markdown'
    )
    
    # Crear mensaje simulado para reutilizar la función
    class MockMessage:
        def __init__(self, chat_id):
            self.chat = type('obj', (object,), {'id': chat_id})
    
    mock_message = MockMessage(call.message.chat.id)
    
    # Llamar a la función de búsqueda
    process_ai_search(telegram_id, query, mock_message)

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
    
    # Si no existe el cronograma específico, mostrar opciones para elegir
    if not schedule_data:
        # Crear teclado inline para selección de cronograma
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        keyboard.add(
            types.InlineKeyboardButton("🎯 Sesión única (Domingo)", callback_data="schedule_sesion_unica_domingo"),
            types.InlineKeyboardButton("⚖️ Dos sesiones (Dom + Miér)", callback_data="schedule_dos_sesiones"),
            types.InlineKeyboardButton("🔄 Tres sesiones (Dom/Mar/Vie)", callback_data="schedule_tres_sesiones"),
            types.InlineKeyboardButton("📅 Preparación diaria", callback_data="schedule_preparacion_diaria")
        )

        response_text = f"""
⏰ **SELECCIONA TU CRONOGRAMA DE COCCIÓN**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
⚡ **Available Energy:** {user_profile['energy_data']['available_energy']} kcal/kg FFM/día

**OPCIONES DISPONIBLES:**

🎯 **Sesión única** - Un día, máxima eficiencia (4-6h)
⚖️ **Dos sesiones** - Balance entre eficiencia y frescura
🔄 **Tres sesiones** - Máxima frescura distribuida
📅 **Preparación diaria** - Sin meal prep, siempre fresco

**Selecciona la opción que mejor se adapte a tu Available Energy y horarios:**

**¿Quieres más opciones?**
Usa /nueva_semana para explorar cronogramas específicos.
"""
        bot.send_message(
            message.chat.id, 
            response_text, 
            parse_mode='Markdown',
            reply_markup=keyboard
        )
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
        if step == "enfoque_dietetico":
            # Este paso se maneja por callbacks, no por texto
            bot.send_message(
                message.chat.id,
                "⚠️ Por favor, selecciona tu enfoque dietético usando los botones de arriba.\n\n"
                "Si no los ves, usa `/perfil` para empezar de nuevo.",
                parse_mode='Markdown'
            )
            return
            
        elif step == "peso":
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
            
            keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            keyboard.add("🏠 Sedentario (0 días/semana)")
            keyboard.add("🚶 Ligero (1-2 días/semana)")
            keyboard.add("🏃 Moderado (3-4 días/semana)")
            keyboard.add("💪 Intenso (5+ días/semana)")
            
            bot.send_message(
                message.chat.id,
                f"✅ Objetivo registrado: {message.text}\n\n"
                "🏃 **Paso 6/9:** ¿Cuál es tu nivel de actividad física?\n\n"
                "Selecciona la opción que mejor describa tu rutina actual:\n\n"
                "🏠 **Sedentario (0 días/semana)**\n"
                "   Trabajo de oficina, sin ejercicio regular\n\n"
                "🚶 **Ligero (1-2 días/semana)**\n"
                "   Ejercicio ocasional, caminatas, actividad ligera\n\n"
                "🏃 **Moderado (3-4 días/semana)**\n"
                "   Ejercicio regular, rutina establecida\n\n"
                "💪 **Intenso (5+ días/semana)**\n"
                "   Ejercicio frecuente, alta dedicación al fitness",
                reply_markup=keyboard
            )
            
        elif step == "actividad":
            # Procesar respuesta híbrida de actividad física
            text = message.text.lower()
            
            if "sedentario" in text or "0 días" in text:
                activity_factor = 1.2
                frecuencia_semanal = 0
                activity_level = "sedentario"
            elif "ligero" in text or "1-2 días" in text:
                activity_factor = 1.375
                frecuencia_semanal = 1.5
                activity_level = "ligero"
            elif "moderado" in text or "3-4 días" in text:
                activity_factor = 1.55
                frecuencia_semanal = 3.5
                activity_level = "moderado"
            elif "intenso" in text or "5+" in text:
                activity_factor = 1.725
                frecuencia_semanal = 5.5
                activity_level = "intenso"
            else:
                raise ValueError("Nivel de actividad no válido")
            
            data["activity_factor"] = activity_factor
            data["frecuencia_semanal"] = frecuencia_semanal
            data["activity_level"] = activity_level
            
            # Si es sedentario, saltar directamente a preferencias
            if activity_level == "sedentario":
                data["ejercicio_tipo"] = "ninguno"
                data["duracion_promedio"] = 0
                meal_bot.user_states[telegram_id]["step"] = "preferencias"
                meal_bot.user_states[telegram_id]["data"] = data
                
                keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                keyboard.add("Continuar con preferencias")
                
                bot.send_message(
                    message.chat.id,
                    f"✅ Actividad registrada: {activity_level.title()} (0 días/semana)\n\n"
                    "⏭️ **Saltando configuración de ejercicio**\n\n"
                    "🍽️ **Paso 7/9:** Configuremos tus preferencias alimentarias.\n"
                    "Presiona el botón para continuar.",
                    reply_markup=keyboard
                )
            else:
                meal_bot.user_states[telegram_id]["step"] = "ejercicio_tipo"
                meal_bot.user_states[telegram_id]["data"] = data
                
                keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
                keyboard.add("Fuerza/Pesas", "Cardio")
                keyboard.add("Deportes", "HIIT")
                keyboard.add("Mixto")
                
                bot.send_message(
                    message.chat.id,
                    f"✅ Actividad registrada: {activity_level.title()} ({frecuencia_semanal} días/semana)\n\n"
                    "🏋️ **Paso 7/9:** ¿Qué tipo de ejercicio haces principalmente?\n\n"
                    "**Fuerza/Pesas:** Entrenamiento con resistencias\n"
                    "**Cardio:** Running, ciclismo, natación\n"
                    "**Deportes:** Fútbol, tenis, baloncesto\n"
                    "**HIIT:** Entrenamientos de alta intensidad\n"
                    "**Mixto:** Combinación de varios tipos",
                    reply_markup=keyboard
                )
            
        elif step == "ejercicio_tipo":
            tipos_ejercicio = {
                "fuerza/pesas": "fuerza",
                "cardio": "cardio", 
                "deportes": "deportes",
                "hiit": "hiit",
                "mixto": "mixto"
            }
            
            tipo_ejercicio = tipos_ejercicio.get(message.text.lower())
            if not tipo_ejercicio:
                raise ValueError("Tipo de ejercicio no válido")
            
            data["ejercicio_tipo"] = tipo_ejercicio
            meal_bot.user_states[telegram_id]["step"] = "duracion"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("30-45 min", "45-60 min")
            keyboard.add("60-90 min", "90+ min")
            
            bot.send_message(
                message.chat.id,
                f"✅ Ejercicio registrado: {message.text}\n\n"
                "⏱️ **Paso 8/9:** ¿Cuánto dura cada sesión de entrenamiento?\n\n"
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
                "⏰ **Paso 9/9:** ¿A qué hora entrenas normalmente?\n\n"
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
                "🍽️ **CONFIGURACIÓN FINAL:** ¿Qué PROTEÍNAS prefieres?\n\n"
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
            # Procesar selección múltiple de verduras
            text = message.text.lower().strip()
            
            # Inicializar lista si no existe
            if "liked_vegetables" not in data:
                data["liked_vegetables"] = []
            
            # Verificar si quiere continuar
            if "continuar" in text or text == "➡️ continuar":
                # Continuar al siguiente paso
                pass
            elif "ninguna" in text or text == "⏭️ ninguna especial":
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
                    # Agregar a la lista si no está ya incluido
                    if selected not in data["liked_vegetables"]:
                        data["liked_vegetables"].append(selected)
                        
                    # Mostrar selección actual y continuar
                    selected_names = [name.replace("_", " ").title() for name in data["liked_vegetables"]]
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
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: hojas verdes, cruciferas, solanaceas, aromaticas, raices, pimientos, pepinaceas, todas, ninguna, o continuar."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "disgustos"
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Inicializar lista de alimentos a evitar
            data["disliked_foods"] = []
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🐟 Pescado", "🥛 Lácteos", "🌶️ Picante")
            keyboard.add("🧄 Ajo/Cebolla", "🥜 Frutos secos", "🍄 Hongos")
            keyboard.add("🌿 Cilantro", "⏭️ Sin restricciones", "📝 Otros")
            keyboard.add("➡️ Continuar")
            
            selected_veggies = [name.replace("_", " ").title() for name in data["liked_vegetables"]]
            veggie_text = ", ".join(selected_veggies) if selected_veggies else "Ninguna"
            
            bot.send_message(
                message.chat.id,
                f"✅ Verduras registradas: {veggie_text}\n\n"
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
                "**PUEDES SELECCIONAR MÚLTIPLES OPCIONES**\n"
                "Usa ➡️ **Continuar** cuando termines de seleccionar:",
                reply_markup=keyboard
            )
            
            
        elif step == "disgustos":
            # Procesar selección múltiple de alimentos a evitar
            text = message.text.lower().strip()
            
            # Inicializar lista si no existe
            if "disliked_foods" not in data:
                data["disliked_foods"] = []
            
            # Verificar si quiere continuar
            if "continuar" in text or text == "➡️ continuar":
                # Continuar al siguiente paso
                pass
            elif "sin restricciones" in text or "ninguna" in text:
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
                    # Agregar a la lista si no está ya incluido
                    if selected not in data["disliked_foods"]:
                        data["disliked_foods"].append(selected)
                        
                    # Mostrar selección actual y continuar
                    selected_names = [name.replace("_", " ").title() for name in data["disliked_foods"]]
                    selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
                    
                    bot.send_message(
                        message.chat.id,
                        f"✅ **{selected.replace('_', ' ').title()}** añadido a evitar\n\n"
                        f"**A evitar:** {selection_text}\n\n"
                        "Puedes seleccionar más opciones o usar ➡️ **Continuar**"
                    )
                    return  # Mantener en el mismo paso
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: pescado, lacteos, picante, ajo, cebolla, frutos secos, hongos, cilantro, sin restricciones, otros, o continuar."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "restricciones"
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Inicializar lista de restricciones especiales
            data["special_restrictions"] = []
            
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            keyboard.add("🚫 Alergias", "🌱 Vegano")
            keyboard.add("🥛 Sin lactosa", "🌾 Sin gluten")
            keyboard.add("🕌 Halal", "✡️ Kosher")
            keyboard.add("⏭️ Sin restricciones especiales")
            keyboard.add("➡️ Continuar")
            
            selected_dislikes = [name.replace("_", " ").title() for name in data["disliked_foods"]]
            dislike_text = ", ".join(selected_dislikes) if selected_dislikes else "Ninguna"
            
            bot.send_message(
                message.chat.id,
                f"✅ Alimentos a evitar registrados: {dislike_text}\n\n"
                "⚠️ **Paso 9E/10:** ¿Tienes alguna RESTRICCIÓN ESPECIAL?\n\n"
                "**Opciones disponibles:**\n"
                "• 🚫 Alergias\n"
                "• 🌱 Vegano\n"
                "• 🥛 Sin lactosa\n"
                "• 🌾 Sin gluten\n"
                "• 🕌 Halal\n"
                "• ✡️ Kosher\n"
                "• ⏭️ Sin restricciones especiales\n\n"
                "**PUEDES SELECCIONAR MÚLTIPLES OPCIONES**\n"
                "Usa ➡️ **Continuar** cuando termines de seleccionar:",
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
            # Procesar selección múltiple de restricciones especiales
            text = message.text.lower().strip()
            
            # Inicializar lista si no existe
            if "special_restrictions" not in data:
                data["special_restrictions"] = []
            
            # Verificar si quiere continuar
            if "continuar" in text or text == "➡️ continuar":
                # Continuar al siguiente paso
                pass
            elif "sin restricciones" in text or "ninguna" in text:
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
                    # Agregar a la lista si no está ya incluido
                    if selected not in data["special_restrictions"]:
                        data["special_restrictions"].append(selected)
                        
                    # Mostrar selección actual y continuar
                    selected_names = [name.replace("_", " ").title() for name in data["special_restrictions"]]
                    selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
                    
                    bot.send_message(
                        message.chat.id,
                        f"✅ **{selected.replace('_', ' ').title()}** añadido\n\n"
                        f"**Restricciones:** {selection_text}\n\n"
                        "Puedes seleccionar más opciones o usar ➡️ **Continuar**"
                    )
                    return  # Mantener en el mismo paso
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: alergias, vegano, sin lactosa, sin gluten, halal, kosher, sin restricciones, o continuar."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "metodos_coccion"
            meal_bot.user_states[telegram_id]["data"] = data
            
            # Inicializar lista de métodos de cocción
            data["cooking_methods"] = []
            
            keyboard = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            keyboard.add("🔥 Horno", "🍳 Sartén", "🍲 Plancha")
            keyboard.add("🥘 Guisos", "🍜 Vapor", "🥗 Crudo")
            keyboard.add("✅ Todos", "⏭️ Sin preferencias")
            keyboard.add("➡️ Continuar")
            
            selected_restrictions = [name.replace("_", " ").title() for name in data["special_restrictions"]]
            restriction_text = ", ".join(selected_restrictions) if selected_restrictions else "Ninguna"
            
            bot.send_message(
                message.chat.id,
                f"✅ Restricciones registradas: {restriction_text}\n\n"
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
                "**PUEDES SELECCIONAR MÚLTIPLES OPCIONES**\n"
                "Usa ➡️ **Continuar** cuando termines de seleccionar:",
                reply_markup=keyboard
            )
            
        elif step == "metodos_coccion":
            # Procesar selección múltiple de métodos de cocción
            text = message.text.lower().strip()
            
            # Inicializar lista si no existe
            if "cooking_methods" not in data:
                data["cooking_methods"] = []
            
            # Verificar si quiere continuar
            if "continuar" in text or text == "➡️ continuar":
                # Si no ha seleccionado nada, usar valores por defecto
                if not data["cooking_methods"]:
                    data["cooking_methods"] = ["horno", "sarten", "plancha"]  # Default
            elif "sin preferencias" in text or "ninguna" in text:
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
                    # Agregar a la lista si no está ya incluido
                    if selected not in data["cooking_methods"]:
                        data["cooking_methods"].append(selected)
                        
                    # Mostrar selección actual y continuar
                    selected_names = [name.replace("_", " ").title() for name in data["cooking_methods"]]
                    selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
                    
                    bot.send_message(
                        message.chat.id,
                        f"✅ **{selected.replace('_', ' ').title()}** añadido\n\n"
                        f"**Métodos seleccionados:** {selection_text}\n\n"
                        "Puedes seleccionar más opciones o usar ➡️ **Continuar**"
                    )
                    return  # Mantener en el mismo paso
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ No reconocí esa opción. Por favor usa los botones o escribe: horno, sarten, plancha, guisos, vapor, crudo, todos, sin preferencias, o continuar."
                    )
                    return
            
            meal_bot.user_states[telegram_id]["step"] = "finalizar"
            meal_bot.user_states[telegram_id]["data"] = data
            
            keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            keyboard.add("✅ Crear mi perfil nutricional")
            
            selected_methods = [name.replace("_", " ").title() for name in data["cooking_methods"]]
            methods_text = ", ".join(selected_methods) if selected_methods else "Por defecto"
            
            bot.send_message(
                message.chat.id,
                f"✅ Métodos de cocción registrados: {methods_text}\n\n"
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
                    "enfoque_dietetico": data.get("enfoque_dietetico", "fitness"),  # Default fitness
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

def process_profile_edit(telegram_id: str, message):
    """Procesar edición de preferencias del perfil"""
    user_state = meal_bot.user_states.get(telegram_id, {})
    step = user_state.get("step")
    edit_section = user_state.get("edit_section")
    data = user_state.get("data", {})
    
    text = message.text.strip()
    
    # Verificar si quiere continuar
    if "continuar" in text.lower() or text == "➡️ Continuar":
        # Finalizar edición y guardar cambios
        save_profile_edit_changes(telegram_id, edit_section, data)
        return
    
    # Procesar según sección de edición
    if step == "9C" and edit_section == "liked_foods":
        process_edit_liked_foods(telegram_id, message, data)
    elif step == "9D" and edit_section == "disliked_foods":
        process_edit_disliked_foods(telegram_id, message, data)
    elif step == "9F" and edit_section == "cooking_methods":
        process_edit_cooking_methods(telegram_id, message, data)
    elif step == "7" and edit_section == "training_schedule":
        process_edit_training_schedule(telegram_id, message, data)

def process_edit_liked_foods(telegram_id: str, message, data):
    """Procesar edición de alimentos preferidos"""
    text = message.text.strip()
    
    # Mapear opciones a IDs
    food_mapping = {
        "🥩 Carnes rojas": "carnes_rojas",
        "🐔 Aves": "aves", 
        "🐟 Pescados": "pescados",
        "🥚 Huevos": "huevos",
        "🥛 Lácteos": "lacteos",
        "🥜 Frutos secos": "frutos_secos",
        "🫘 Legumbres": "legumbres",
        "🥬 Hojas verdes": "hojas_verdes",
        "🥦 Crucíferas": "cruciferas",
        "🍅 Solanáceas": "solanaceas",
        "🌿 Aromáticas": "aromaticas",
        "🥕 Raíces": "raices",
        "🌶️ Pimientos": "pimientos",
        "🥒 Pepináceas": "pepinaceas",
        "🫒 Aceitunas": "aceitunas",
        "🥑 Aguacate": "aguacate"
    }
    
    if text in food_mapping:
        selected = food_mapping[text]
        
        # Inicializar lista si no existe
        if "liked_foods" not in data:
            data["liked_foods"] = []
        
        # Agregar si no está ya incluido
        if selected not in data["liked_foods"]:
            data["liked_foods"].append(selected)
            
        # Mostrar selección actual
        selected_names = [name.replace("_", " ").title() for name in data["liked_foods"]]
        selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
        
        bot.send_message(
            message.chat.id,
            f"✅ **{selected.replace('_', ' ').title()}** añadido\n\n"
            f"**Seleccionados:** {selection_text}\n\n"
            "Puedes seleccionar más opciones o usar **➡️ Continuar** para finalizar.",
            parse_mode='Markdown'
        )
        
        # Actualizar estado
        meal_bot.user_states[telegram_id]["data"] = data
    else:
        bot.send_message(
            message.chat.id,
            "❌ Opción no válida. Selecciona una de las opciones del teclado o usa **➡️ Continuar**.",
            parse_mode='Markdown'
        )

def process_edit_disliked_foods(telegram_id: str, message, data):
    """Procesar edición de alimentos a evitar"""
    text = message.text.strip()
    
    # Mapear opciones a IDs (mismo mapeo que liked_foods)
    food_mapping = {
        "🥩 Carnes rojas": "carnes_rojas",
        "🐔 Aves": "aves", 
        "🐟 Pescados": "pescados",
        "🥚 Huevos": "huevos",
        "🥛 Lácteos": "lacteos",
        "🥜 Frutos secos": "frutos_secos",
        "🫘 Legumbres": "legumbres",
        "🥬 Hojas verdes": "hojas_verdes",
        "🥦 Crucíferas": "cruciferas",
        "🍅 Solanáceas": "solanaceas",
        "🌿 Aromáticas": "aromaticas",
        "🥕 Raíces": "raices",
        "🌶️ Pimientos": "pimientos",
        "🥒 Pepináceas": "pepinaceas",
        "🫒 Aceitunas": "aceitunas",
        "🥑 Aguacate": "aguacate"
    }
    
    if text in food_mapping:
        selected = food_mapping[text]
        
        # Inicializar lista si no existe
        if "disliked_foods" not in data:
            data["disliked_foods"] = []
        
        # Agregar si no está ya incluido
        if selected not in data["disliked_foods"]:
            data["disliked_foods"].append(selected)
            
        # Mostrar selección actual
        selected_names = [name.replace("_", " ").title() for name in data["disliked_foods"]]
        selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
        
        bot.send_message(
            message.chat.id,
            f"✅ **{selected.replace('_', ' ').title()}** añadido a evitar\n\n"
            f"**A evitar:** {selection_text}\n\n"
            "Puedes seleccionar más opciones o usar **➡️ Continuar** para finalizar.",
            parse_mode='Markdown'
        )
        
        # Actualizar estado
        meal_bot.user_states[telegram_id]["data"] = data
    else:
        bot.send_message(
            message.chat.id,
            "❌ Opción no válida. Selecciona una de las opciones del teclado o usa **➡️ Continuar**.",
            parse_mode='Markdown'
        )

def process_edit_cooking_methods(telegram_id: str, message, data):
    """Procesar edición de métodos de cocción"""
    text = message.text.strip()
    
    # Mapear opciones a IDs
    cooking_mapping = {
        "🔥 Horno": "horno",
        "🍳 Sartén": "sarten",
        "🥘 Plancha": "plancha",
        "🫕 Vapor": "vapor",
        "🥗 Crudo/Ensaladas": "crudo",
        "🍲 Guisado": "guisado",
        "🔥 Parrilla": "parrilla",
        "🥄 Hervido": "hervido"
    }
    
    if text in cooking_mapping:
        selected = cooking_mapping[text]
        
        # Inicializar lista si no existe
        if "cooking_methods" not in data:
            data["cooking_methods"] = []
        
        # Agregar si no está ya incluido
        if selected not in data["cooking_methods"]:
            data["cooking_methods"].append(selected)
            
        # Mostrar selección actual
        selected_names = [name.replace("_", " ").title() for name in data["cooking_methods"]]
        selection_text = ", ".join(selected_names) if selected_names else "Ninguna"
        
        bot.send_message(
            message.chat.id,
            f"✅ **{selected.replace('_', ' ').title()}** añadido\n\n"
            f"**Métodos seleccionados:** {selection_text}\n\n"
            "Puedes seleccionar más opciones o usar **➡️ Continuar** para finalizar.",
            parse_mode='Markdown'
        )
        
        # Actualizar estado
        meal_bot.user_states[telegram_id]["data"] = data
    else:
        bot.send_message(
            message.chat.id,
            "❌ Opción no válida. Selecciona una de las opciones del teclado o usa **➡️ Continuar**.",
            parse_mode='Markdown'
        )

def process_edit_training_schedule(telegram_id: str, message, data):
    """Procesar edición de horario de entrenamiento"""
    text = message.text.strip()
    
    # Mapear opciones a IDs
    schedule_mapping = {
        "🌅 Mañana (6:00-12:00)": {"id": "mañana", "desc": "Mañana (6:00-12:00)"},
        "☀️ Mediodía (12:00-16:00)": {"id": "mediodia", "desc": "Mediodía (12:00-16:00)"},
        "🌆 Tarde (16:00-20:00)": {"id": "tarde", "desc": "Tarde (16:00-20:00)"},
        "🌙 Noche (20:00-24:00)": {"id": "noche", "desc": "Noche (20:00-24:00)"},
        "🔄 Variable/Cambia": {"id": "variable", "desc": "Variable/Cambia"}
    }
    
    if text in schedule_mapping:
        selected = schedule_mapping[text]
        data["training_schedule"] = selected["id"]
        data["training_schedule_desc"] = selected["desc"]
        
        # Guardar inmediatamente
        save_profile_edit_changes(telegram_id, "training_schedule", data)
    else:
        bot.send_message(
            message.chat.id,
            "❌ Opción no válida. Selecciona una de las opciones del teclado.",
            parse_mode='Markdown'
        )

def save_profile_edit_changes(telegram_id: str, edit_section: str, data):
    """Guardar cambios de edición en el perfil del usuario"""
    try:
        user_profile = meal_bot.get_user_profile(telegram_id)
        if not user_profile:
            bot.send_message(
                telegram_id,
                "❌ Error: No se pudo encontrar tu perfil."
            )
            return
        
        # Actualizar según sección editada
        if edit_section == "liked_foods":
            user_profile["preferences"]["liked_foods"] = data.get("liked_foods", [])
            updated_section = "Alimentos preferidos"
            
        elif edit_section == "disliked_foods":
            user_profile["preferences"]["disliked_foods"] = data.get("disliked_foods", [])
            updated_section = "Alimentos a evitar"
            
        elif edit_section == "cooking_methods":
            user_profile["preferences"]["cooking_methods"] = data.get("cooking_methods", [])
            updated_section = "Métodos de cocción"
            
        elif edit_section == "training_schedule":
            user_profile["exercise_profile"]["training_schedule"] = data.get("training_schedule", "variable")
            user_profile["exercise_profile"]["training_schedule_desc"] = data.get("training_schedule_desc", "Variable/Cambia")
            
            # Recalcular timing dinámico de comidas
            objetivo = user_profile["basic_data"]["objetivo"]
            new_timing = meal_bot.profile_system.get_dynamic_meal_timing(
                data["training_schedule"], 
                objetivo
            )
            user_profile["exercise_profile"]["dynamic_meal_timing"] = new_timing
            updated_section = "Horario de entrenamiento"
        
        # Guardar cambios en base de datos
        meal_bot.data["users"][telegram_id] = user_profile
        meal_bot.save_data()
        
        # Limpiar estado de edición
        meal_bot.user_states[telegram_id] = {}
        
        # Confirmar cambios
        bot.send_message(
            telegram_id,
            f"✅ **¡{updated_section} actualizado exitosamente!**\n\n"
            f"Tus preferencias han sido guardadas y se aplicarán en:\n"
            f"• Generación de recetas con IA\n"
            f"• Menús personalizados\n"
            f"• Complementos recomendados\n\n"
            f"💡 Usa `/mis_macros` para ver tu perfil actualizado.",
            parse_mode='Markdown',
            reply_markup=meal_bot.create_main_menu_keyboard()
        )
        
    except Exception as e:
        bot.send_message(
            telegram_id,
            f"❌ Error al guardar cambios: {str(e)}\n\n"
            f"Por favor, intenta de nuevo."
        )
        # Limpiar estado en caso de error
        meal_bot.user_states[telegram_id] = {}

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
            
            # Crear botones para seleccionar recetas
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            
            # Botones para cada receta encontrada
            recipe_buttons = []
            for i in range(len(results[:3])):
                recipe_buttons.append(
                    types.InlineKeyboardButton(f"✅ Receta {i+1}", callback_data=f"select_search_recipe_{i}")
                )
            
            keyboard.add(*recipe_buttons)
            keyboard.add(
                types.InlineKeyboardButton("🔄 Más opciones", callback_data=f"more_search_options_{query}"),
                types.InlineKeyboardButton("🗓️ Menú completo", callback_data="theme_auto")
            )
            
            # Guardar resultados en el estado del usuario para poder seleccionarlos
            meal_bot.user_states[telegram_id] = {
                "state": "search_results",
                "query": query,
                "results": results[:3],
                "step": "selection"
            }
            
            # Opciones de seguimiento
            followup_text = f"""
🎯 **SELECCIONA UNA RECETA:**

Puedes elegir cualquiera de las recetas mostradas arriba o buscar más opciones.

💡 **Tip:** Todas las recetas están validadas con ingredientes naturales y ajustadas a tus macros objetivo.
"""
            
            bot.send_message(
                message.chat.id, 
                followup_text, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
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
    elif user_state.get("state") == "profile_edit":
        process_profile_edit(telegram_id, message)
    elif user_state.get("state") == "schedule_setup":
        process_schedule_setup(telegram_id, message)
    elif user_state.get("state") == "shopping_list_setup":
        process_shopping_list_setup(telegram_id, message)
    elif user_state.get("state") == "ai_search":
        # Búsqueda ya procesada
        pass
    elif user_state.get("state") == "metric_entry":
        process_metric_entry(telegram_id, message)
    else:
        # Mensaje libre - responder con ayuda personalizada
        user_profile = meal_bot.get_user_profile(telegram_id)
        
        if user_profile:
            # Usuario con perfil - mostrar comandos personalizados
            preferences = user_profile.get("preferences", {})
            liked_count = len(preferences.get("liked_foods", []))
            disliked_count = len(preferences.get("disliked_foods", []))
            
            help_text = f"""
✨ **COMANDOS PERSONALIZADOS PARA TI**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🎯 **Personalización activa:** {liked_count} preferencias, {disliked_count} exclusiones

**COMANDOS PRINCIPALES:**
✅ /mis_macros - Ver tus macros personalizados
✅ /menu - Menú semanal adaptado a tus preferencias  
✅ /complementos - Complementos filtrados para ti
✅ /favoritas - Ver tus recetas guardadas
✅ /lista_compras - Lista optimizada para tu perfil

**GENERACIÓN IA:**
🤖 /generar - Recetas específicas para tu objetivo
🔍 /buscar [consulta] - Buscar con IA personalizada

**CONFIGURACIÓN:**
⚙️ /editar_perfil - Modificar preferencias
📅 /nueva_semana - Configurar cronograma

💡 **Todo se adapta automáticamente a tu perfil nutricional**
"""
        else:
            # Usuario sin perfil
            help_text = """
❓ **COMANDOS DISPONIBLES:**

⚠️ **Primero configura tu perfil para personalización completa:**
🆕 /perfil - Configurar perfil nutricional

**COMANDOS BÁSICOS:**
/menu - Menú semanal genérico
/recetas - Explorar recetas
/complementos - Ver complementos
/buscar [consulta] - Buscar recetas con IA
/generar - Generar receta específica

💡 **¡Configura tu perfil para experiencia 100% personalizada!**
"""
        
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

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

def process_shopping_list_setup(telegram_id: str, message):
    """Procesar configuración de lista de compras"""
    user_state = meal_bot.user_states.get(telegram_id, {})
    choice = message.text.upper().strip()
    
    days_mapping = {
        "A": 3,
        "B": 5,
        "C": 7,
        "D": 10
    }
    
    if choice in days_mapping:
        days = days_mapping[choice]
        
        # Mostrar mensaje de procesamiento
        bot.send_message(
            message.chat.id,
            f"🛒 **Generando lista de compras para {days} días...**\n\n"
            "⏳ Calculando cantidades según tus macros...\n"
            "🥘 Aplicando preferencias alimentarias...\n"
            "🌊 Añadiendo complementos mediterráneos...\n"
            "📦 Optimizando para meal prep...",
            parse_mode='Markdown'
        )
        
        try:
            # Obtener perfil del usuario
            user_profile = meal_bot.get_user_profile(telegram_id)
            
            # Generar lista de compras
            shopping_result = meal_bot.shopping_generator.generate_shopping_list(user_profile, days)
            
            if shopping_result["success"]:
                # Formatear y enviar lista
                shopping_text = meal_bot.shopping_generator.format_shopping_list_for_telegram(
                    shopping_result, user_profile
                )
                
                meal_bot.send_long_message(message.chat.id, shopping_text, parse_mode='Markdown')
                
                # Mensaje de confirmación
                confirmation_text = f"""
✅ **LISTA GENERADA EXITOSAMENTE**

🛒 Lista optimizada para {days} días de meal prep
📊 {shopping_result['metadata']['daily_calories']} kcal diarios
✨ Adaptada a tus preferencias alimentarias

💡 **PRÓXIMOS PASOS:**
• Guarda esta lista en tu móvil
• Ve al supermercado con la lista
• Sigue los consejos de meal prep
• Usa `/menu` para ver tu menú semanal
• Genera recetas específicas con `/generar`

**¡Lista personalizada 100% para tu perfil!**
"""
                
                bot.send_message(message.chat.id, confirmation_text, parse_mode='Markdown')
                
            else:
                bot.send_message(
                    message.chat.id,
                    f"❌ **Error generando lista:**\n{shopping_result.get('error', 'Error desconocido')}\n\n"
                    "💡 **Intenta:**\n"
                    "• Usar `/lista_compras` de nuevo\n"
                    "• Verificar que tu perfil esté completo\n"
                    "• Contactar soporte si persiste el error",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ **Error procesando solicitud:**\n{str(e)}\n\n"
                "💡 Intenta usar `/lista_compras` de nuevo",
                parse_mode='Markdown'
            )
        
        # Limpiar estado del usuario
        meal_bot.user_states[telegram_id] = {}
        
    else:
        bot.send_message(
            message.chat.id,
            "❌ **Opción no válida**\n\n"
            "Por favor responde con A, B, C o D según la duración deseada."
        )

def process_metric_entry(telegram_id: str, message):
    """Procesar entrada de métricas del usuario"""
    user_state = meal_bot.user_states.get(telegram_id, {})
    metric_name = user_state.get("metric_name")
    step = user_state.get("step", "value")
    
    if not metric_name:
        bot.send_message(message.chat.id, "❌ Error: No se encontró la métrica a registrar")
        meal_bot.user_states[telegram_id] = {}
        return
    
    if step == "value":
        try:
            # Extraer valor numérico del mensaje
            text = message.text.strip()
            
            # Separar valor de notas opcionales
            parts = text.split(' ', 1)
            value_str = parts[0]
            notes = parts[1] if len(parts) > 1 else ""
            
            # Convertir a float
            try:
                value = float(value_str.replace(',', '.'))
            except ValueError:
                raise ValueError("Valor no numérico válido")
            
            # Obtener configuración de la métrica
            metric_config = meal_bot.progress_tracker.trackable_metrics.get(metric_name, {})
            min_val = metric_config.get("min_value", 0)
            max_val = metric_config.get("max_value", 100)
            
            # Validar rango
            if not (min_val <= value <= max_val):
                bot.send_message(
                    message.chat.id,
                    f"❌ **Valor fuera de rango**\n\n"
                    f"📊 **{metric_config.get('name', 'Métrica')}** debe estar entre "
                    f"{min_val} y {max_val} {metric_config.get('unit', '')}\n\n"
                    f"💡 Envía un valor válido o usa /progreso para cancelar",
                    parse_mode='Markdown'
                )
                return
            
            # Registrar métrica
            user_profile = meal_bot.get_user_profile(telegram_id)
            if not user_profile:
                bot.send_message(message.chat.id, "❌ Error: No se encontró tu perfil")
                meal_bot.user_states[telegram_id] = {}
                return
            
            # Mostrar mensaje de procesamiento
            processing_msg = bot.send_message(
                message.chat.id,
                f"📊 **Registrando {metric_config.get('name', 'métrica')}...**\n\n"
                "📈 Guardando datos\n"
                "🎯 Calculando tendencias\n"
                "💡 Generando insights\n\n"
                "*Esto puede tomar unos segundos...*",
                parse_mode='Markdown'
            )
            
            # Registrar la métrica
            result = meal_bot.progress_tracker.record_metric(user_profile, metric_name, value, notes)
            
            # Eliminar mensaje de procesamiento
            bot.delete_message(message.chat.id, processing_msg.message_id)
            
            if result["success"]:
                # Guardar perfil actualizado
                meal_bot.database.save_user_profile(telegram_id, user_profile)
                
                # Formatear respuesta de éxito
                metric_recorded = result["metric_recorded"]
                trend_analysis = result["trend_analysis"]
                insights = result.get("insights", [])
                
                success_text = f"""
✅ **MÉTRICA REGISTRADA EXITOSAMENTE**

📊 **{metric_recorded['name']}:** {metric_recorded['value']}{metric_recorded['unit']}
📅 **Fecha:** {metric_recorded['date']}
📈 **Total registros:** {result['total_records']}

🎯 **ANÁLISIS DE TENDENCIA:**
• **Estado:** {trend_analysis['trend_description']}
• **Cambio semanal:** {trend_analysis['change_rate']:+.2f}{metric_recorded['unit']}/semana
• **Datos analizados:** {trend_analysis['data_points']} puntos en {trend_analysis['period_analyzed']}
"""
                
                # Añadir insights si existen
                if insights:
                    success_text += "\n💡 **INSIGHTS PERSONALIZADOS:**\n"
                    for insight in insights:
                        success_text += f"• {insight}\n"
                
                # Añadir próximos pasos
                success_text += f"""

🚀 **PRÓXIMOS PASOS:**
• Continúa registrando métricas regularmente
• Usa `/progreso` para ver reportes completos
• Las recomendaciones se ajustan automáticamente
• Tu Available Energy se actualiza con cambios de peso

**¡El sistema aprende continuamente de tus datos!**
"""
                
                meal_bot.send_long_message(
                    message.chat.id,
                    success_text,
                    parse_mode='Markdown'
                )
                
                # Botones de acciones rápidas
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    types.InlineKeyboardButton("📊 Ver Reporte", callback_data="progress_report"),
                    types.InlineKeyboardButton("📈 Registrar Otra", callback_data="progress_record")
                )
                
                bot.send_message(
                    message.chat.id,
                    "🎯 **¿Qué quieres hacer ahora?**",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                
            else:
                bot.send_message(
                    message.chat.id,
                    f"❌ **Error registrando métrica:**\n{result.get('error', 'Error desconocido')}\n\n"
                    "💡 Intenta de nuevo o usa `/progreso` para volver al menú principal",
                    parse_mode='Markdown'
                )
            
            # Limpiar estado
            meal_bot.user_states[telegram_id] = {}
            
        except ValueError as e:
            bot.send_message(
                message.chat.id,
                f"❌ **Formato no válido**\n\n"
                f"📝 **Envía solo el número** (ejemplo: 75.2)\n"
                f"💡 Opcionalmente puedes añadir notas después del número\n\n"
                f"**Ejemplos válidos:**\n"
                f"• `75.2`\n"
                f"• `75.2 después del entreno`\n"
                f"• `75,2 por la mañana`\n\n"
                f"Usa `/progreso` para cancelar",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error processing metric entry: {e}")
            bot.send_message(
                message.chat.id,
                f"❌ **Error procesando métrica:**\n{str(e)}\n\n"
                "💡 Intenta de nuevo o usa `/progreso` para volver al menú",
                parse_mode='Markdown'
            )
            
            # Limpiar estado en caso de error
            meal_bot.user_states[telegram_id] = {}

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

# ========================================
# CALLBACK HANDLERS - WEEKLY MENU CONFIGURATION
# ========================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_select_'))
def handle_menu_recipe_selection(call):
    """Manejar selección de recetas para el menú semanal"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Extraer datos del callback
        parts = call.data.split('_')
        category = parts[2]  # desayuno, almuerzo, merienda, cena
        recipe_id = parts[3]
        
        # Obtener perfil del usuario
        user_profile = meal_bot.database.get_user_profile(telegram_id)
        if not user_profile:
            bot.answer_callback_query(call.id, "❌ Perfil no encontrado. Usa /perfil primero.")
            return
        
        # Inicializar configuración del menú si no existe
        if "temp_menu_config" not in user_profile:
            user_profile["temp_menu_config"] = {}
        
        if "selected_recipes" not in user_profile["temp_menu_config"]:
            user_profile["temp_menu_config"]["selected_recipes"] = {
                "desayuno": [],
                "almuerzo": [],
                "merienda": [],
                "cena": []
            }
        
        # Agregar la receta seleccionada
        selected_recipes = user_profile["temp_menu_config"]["selected_recipes"]
        if recipe_id not in selected_recipes[category]:
            selected_recipes[category].append(recipe_id)
            
            # Obtener nombre de la receta para confirmación
            available_recipes = meal_bot.weekly_menu_system.get_user_saved_recipes(user_profile)
            recipe_name = "Receta seleccionada"
            for recipe in available_recipes.get(category, []):
                if recipe["id"] == recipe_id:
                    recipe_name = recipe["name"]
                    break
            
            bot.answer_callback_query(call.id, f"✅ {recipe_name} agregada a {category.title()}")
        else:
            bot.answer_callback_query(call.id, "⚠️ Esta receta ya está seleccionada para esta categoría")
        
        # Guardar cambios
        meal_bot.database.save_user_profile(telegram_id, user_profile)
        
        # Actualizar el mensaje con la nueva selección
        show_category_recipe_selection(call.message, telegram_id, category, edit_message=True)
        
    except Exception as e:
        logger.error(f"Error in menu recipe selection: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando selección")

@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_next_'))
def handle_menu_next_category(call):
    """Manejar avance a la siguiente categoría del menú"""
    telegram_id = str(call.from_user.id)
    
    try:
        current_category = call.data.split('_')[2]
        next_category = get_next_category(current_category)
        
        if next_category:
            # Mostrar la siguiente categoría
            show_category_recipe_selection(call.message, telegram_id, next_category, edit_message=True)
            bot.answer_callback_query(call.id, f"➡️ Configurando {next_category.title()}")
        else:
            # Todas las categorías completadas, mostrar preview
            generate_menu_preview_step(call.message, telegram_id, edit_message=True)
            bot.answer_callback_query(call.id, "✅ Configuración completada")
            
    except Exception as e:
        logger.error(f"Error in menu next category: {e}")
        bot.answer_callback_query(call.id, "❌ Error avanzando categoría")

@bot.callback_query_handler(func=lambda call: call.data == 'menu_confirm')
def handle_menu_confirm(call):
    """Confirmar y guardar el menú semanal configurado"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Obtener perfil del usuario
        user_profile = meal_bot.database.get_user_profile(telegram_id)
        if not user_profile or "temp_menu_config" not in user_profile:
            bot.answer_callback_query(call.id, "❌ No hay configuración de menú temporal")
            return
        
        selected_recipes = user_profile["temp_menu_config"]["selected_recipes"]
        
        # Crear distribución semanal
        weekly_menu = meal_bot.weekly_menu_system.create_weekly_distribution(selected_recipes, user_profile)
        
        # Guardar configuración del menú
        config_id = meal_bot.weekly_menu_system.save_weekly_menu_configuration(
            telegram_id, weekly_menu, selected_recipes, user_profile
        )
        
        # Limpiar configuración temporal
        del user_profile["temp_menu_config"]
        meal_bot.database.save_user_profile(telegram_id, user_profile)
        
        # Mensaje de confirmación
        bot.edit_message_text(
            f"✅ **MENÚ SEMANAL GUARDADO**\n\n"
            f"🆔 **ID de configuración:** `{config_id}`\n"
            f"📅 **Estado:** Listo para usar\n\n"
            f"🎯 **Próximos pasos:**\n"
            f"• Tu menú está distribuido inteligentemente por 7 días\n"
            f"• Recetas balanceadas según tus macros objetivo\n"
            f"• Evita repeticiones consecutivas automáticamente\n\n"
            f"💡 **Comandos útiles:**\n"
            f"• `/generar` - Crear nuevas recetas específicas\n"
            f"• `/buscar [plato]` - Encontrar recetas adicionales\n"
            f"• `/configurar_menu` - Crear otro menú diferente\n\n"
            f"**¡Tu meal prep semanal está listo!**",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='Markdown'
        )
        
        bot.answer_callback_query(call.id, "🎉 Menú guardado exitosamente")
        
    except Exception as e:
        logger.error(f"Error confirming menu: {e}")
        bot.answer_callback_query(call.id, "❌ Error guardando menú")

@bot.callback_query_handler(func=lambda call: call.data == 'menu_edit')
def handle_menu_edit(call):
    """Volver a editar la configuración del menú"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Volver al primer paso de configuración
        show_category_recipe_selection(call.message, telegram_id, "desayuno", edit_message=True)
        bot.answer_callback_query(call.id, "✏️ Editando configuración")
        
    except Exception as e:
        logger.error(f"Error editing menu: {e}")
        bot.answer_callback_query(call.id, "❌ Error editando menú")

@bot.callback_query_handler(func=lambda call: call.data == 'menu_save_config')
def handle_menu_save_config(call):
    """Guardar configuración del menú como plantilla"""
    telegram_id = str(call.from_user.id)
    
    try:
        # Obtener perfil del usuario
        user_profile = meal_bot.database.get_user_profile(telegram_id)
        if not user_profile or "temp_menu_config" not in user_profile:
            bot.answer_callback_query(call.id, "❌ No hay configuración para guardar")
            return
        
        selected_recipes = user_profile["temp_menu_config"]["selected_recipes"]
        
        # Crear distribución semanal
        weekly_menu = meal_bot.weekly_menu_system.create_weekly_distribution(selected_recipes, user_profile)
        
        # Guardar como configuración guardada (no activa)
        config_id = meal_bot.weekly_menu_system.save_weekly_menu_configuration(
            telegram_id, weekly_menu, selected_recipes, user_profile
        )
        
        # Cambiar estado a 'draft' para indicar que es una plantilla
        for config in user_profile.get("weekly_menu_configs", []):
            if config["config_id"] == config_id:
                config["status"] = "draft"
                break
        
        meal_bot.database.save_user_profile(telegram_id, user_profile)
        
        bot.answer_callback_query(call.id, "💾 Configuración guardada como plantilla")
        
        # Actualizar mensaje
        bot.edit_message_text(
            f"💾 **CONFIGURACIÓN GUARDADA COMO PLANTILLA**\n\n"
            f"🆔 **ID:** `{config_id}`\n"
            f"📋 **Estado:** Plantilla guardada\n\n"
            f"🎯 **Opciones:**\n"
            f"• Usa `/configurar_menu` para crear otra configuración\n"
            f"• Esta plantilla queda disponible para uso futuro\n"
            f"• Puedes crear múltiples configuraciones diferentes\n\n"
            f"**¡Plantilla guardada exitosamente!**",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error saving menu config: {e}")
        bot.answer_callback_query(call.id, "❌ Error guardando configuración")

@bot.callback_query_handler(func=lambda call: call.data.startswith('approach_'))
def handle_approach_callback(call):
    """Manejar la selección del enfoque dietético"""
    telegram_id = str(call.from_user.id)
    
    # Verificar que el usuario esté en el proceso de configuración
    user_state = meal_bot.user_states.get(telegram_id)
    if not user_state or user_state.get("state") != "profile_setup" or user_state.get("step") != "enfoque_dietetico":
        bot.answer_callback_query(call.id, "❌ Sesión expirada. Usa /perfil para empezar de nuevo.")
        return
    
    try:
        # Procesar la selección
        approach = call.data.split('_')[1]  # 'tradicional' o 'fitness'
        
        # Guardar el enfoque seleccionado
        user_state["data"]["enfoque_dietetico"] = approach
        
        # Avanzar al siguiente paso
        user_state["step"] = "peso"
        
        # Confirmar selección y continuar
        approach_name = "🇪🇸 Tradicional Español" if approach == "tradicional" else "💪 Fitness Orientado"
        bot.answer_callback_query(call.id, f"✅ Enfoque seleccionado: {approach_name}")
        
        # Continuar con el flujo normal del perfil
        bot.send_message(
            call.message.chat.id,
            f"✅ **Enfoque seleccionado:** {approach_name}\n\n"
            "Perfecto, ahora continuemos con tu información física para calcular tus macros personalizados.\n\n"
            "📏 **Paso 1/9:** ¿Cuál es tu peso actual en kg?\n"
            "_(Ejemplo: 70)_",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error processing approach selection: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando selección")

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