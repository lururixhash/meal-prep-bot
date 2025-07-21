#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meal Prep Bot - Bot de Telegram para gestión de meal prep con rotación de recetas
Autor: Claude Code
"""

import json
import os
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import telebot
from telebot import types
from anthropic import Anthropic

from config import (
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY, DATABASE_FILE, BACKUP_PREFIX,
    DEFAULT_MACRO_TARGETS, DEFAULT_COOKING_SCHEDULE, SHOPPING_CATEGORIES
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar bot y Claude
bot = telebot.TeleBot(TELEGRAM_TOKEN)
claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)

class MealPrepBot:
    def __init__(self):
        self.data = self.load_data()
        
    def load_data(self) -> Dict:
        """Cargar datos del archivo JSON"""
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"No se encontró {DATABASE_FILE}")
            return self.create_default_data()
        except json.JSONDecodeError:
            logger.error(f"Error al leer {DATABASE_FILE}")
            return self.create_default_data()
    
    def create_default_data(self) -> Dict:
        """Crear estructura de datos por defecto"""
        return {
            "recipes": {},
            "meal_plans": {},
            "user_preferences": {
                "dislikes": [],
                "allergies": [],
                "macro_targets": DEFAULT_MACRO_TARGETS,
                "current_week": 1,
                "cooking_schedule": DEFAULT_COOKING_SCHEDULE,
                "last_rotation": None
            },
            "shopping_lists": {},
            "cooking_history": []
        }
    
    def save_data(self) -> bool:
        """Guardar datos con backup automático"""
        try:
            # Crear backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{BACKUP_PREFIX}{timestamp}.json"
            
            if os.path.exists(DATABASE_FILE):
                with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # Guardar datos actuales
            with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error al guardar datos: {e}")
            return False
    
    def get_current_meal_plan(self) -> Dict:
        """Obtener el plan de comidas actual"""
        current_week = self.data["user_preferences"]["current_week"]
        if current_week in [1, 2]:
            return self.data["meal_plans"]["week_1_2"]
        else:
            return self.data["meal_plans"]["week_3_4"]
    
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Dict]:
        """Obtener receta por ID"""
        return self.data["recipes"].get(recipe_id)
    
    def calculate_daily_macros(self) -> Dict:
        """Calcular macros diarios del menú actual"""
        meal_plan = self.get_current_meal_plan()
        total_macros = {"protein": 0, "carbs": 0, "fat": 0, "calories": 0}
        
        # Calcular macros de proteínas (2 porciones por día)
        for protein_id in meal_plan["proteins"]:
            recipe = self.get_recipe_by_id(protein_id)
            if recipe:
                for macro in total_macros:
                    total_macros[macro] += recipe["macros_per_serving"][macro] * 2
        
        # Calcular macros de legumbres (1.5 porciones por día)
        for legume_id in meal_plan["legumes"]:
            recipe = self.get_recipe_by_id(legume_id)
            if recipe:
                for macro in total_macros:
                    total_macros[macro] += recipe["macros_per_serving"][macro] * 1.5
        
        # Calcular macros de componentes base (1 porción cada uno)
        for base_id in meal_plan["base_components"]:
            recipe = self.get_recipe_by_id(base_id)
            if recipe:
                for macro in total_macros:
                    total_macros[macro] += recipe["macros_per_serving"][macro]
        
        return total_macros
    
    def generate_shopping_list(self) -> Dict[str, List[str]]:
        """Generar lista de compra categorizada"""
        meal_plan = self.get_current_meal_plan()
        shopping_list = {category: [] for category in SHOPPING_CATEGORIES}
        
        # Recolectar ingredientes de todas las recetas del plan
        all_recipe_ids = (meal_plan["proteins"] + 
                         meal_plan["legumes"] + 
                         meal_plan["base_components"])
        
        all_ingredients = []
        for recipe_id in all_recipe_ids:
            recipe = self.get_recipe_by_id(recipe_id)
            if recipe:
                all_ingredients.extend(recipe["ingredients"])
        
        # Categorizar ingredientes
        for ingredient in all_ingredients:
            categorized = False
            ingredient_lower = ingredient.lower()
            
            for category, keywords in SHOPPING_CATEGORIES.items():
                if any(keyword in ingredient_lower for keyword in keywords):
                    shopping_list[category].append(ingredient)
                    categorized = True
                    break
            
            if not categorized:
                shopping_list["otros"].append(ingredient)
        
        # Remover duplicados y ordenar
        for category in shopping_list:
            shopping_list[category] = sorted(list(set(shopping_list[category])))
        
        return shopping_list
    
    def generate_cooking_schedule(self) -> Dict[str, List[Dict]]:
        """Generar cronograma de cocción optimizado"""
        meal_plan = self.get_current_meal_plan()
        schedule = {"saturday": [], "sunday": []}
        
        # Sábado: Legumbres y una proteína
        saturday_recipes = []
        for legume_id in meal_plan["legumes"]:
            recipe = self.get_recipe_by_id(legume_id)
            if recipe:
                saturday_recipes.append({
                    "name": recipe["name"],
                    "cook_time": recipe["cook_time"],
                    "order": 1 if "lentils" in recipe["id"] else 2  # Lentejas primero (más rápidas)
                })
        
        # Una proteína el sábado
        if meal_plan["proteins"]:
            protein_recipe = self.get_recipe_by_id(meal_plan["proteins"][1])
            if protein_recipe:
                saturday_recipes.append({
                    "name": protein_recipe["name"],
                    "cook_time": protein_recipe["cook_time"],
                    "order": 3
                })
        
        schedule["saturday"] = sorted(saturday_recipes, key=lambda x: x["order"])
        
        # Domingo: Segunda proteína y componentes base
        sunday_recipes = []
        if meal_plan["proteins"]:
            protein_recipe = self.get_recipe_by_id(meal_plan["proteins"][0])
            if protein_recipe:
                sunday_recipes.append({
                    "name": protein_recipe["name"],
                    "cook_time": protein_recipe["cook_time"],
                    "order": 1
                })
        
        # Componentes base que requieren Crockpot
        crockpot_bases = ["quinoa_pilaf", "brown_rice"]
        for base_id in meal_plan["base_components"]:
            if base_id in crockpot_bases:
                recipe = self.get_recipe_by_id(base_id)
                if recipe:
                    sunday_recipes.append({
                        "name": recipe["name"],
                        "cook_time": recipe["cook_time"],
                        "order": 2
                    })
        
        # Preparaciones rápidas (horno/estufa)
        quick_prep = []
        if "roasted_vegetables" in meal_plan["base_components"]:
            recipe = self.get_recipe_by_id("roasted_vegetables")
            if recipe:
                quick_prep.append({
                    "name": recipe["name"],
                    "cook_time": recipe["cook_time"],
                    "order": 3,
                    "method": "horno"
                })
        
        if "hard_boiled_eggs" in meal_plan["base_components"]:
            recipe = self.get_recipe_by_id("hard_boiled_eggs")
            if recipe:
                quick_prep.append({
                    "name": recipe["name"],
                    "cook_time": recipe["cook_time"],
                    "order": 4,
                    "method": "estufa"
                })
        
        sunday_recipes.extend(quick_prep)
        schedule["sunday"] = sorted(sunday_recipes, key=lambda x: x["order"])
        
        return schedule
    
    def modify_recipe_with_claude(self, recipe: Dict, feedback: str) -> Dict:
        """Modificar receta usando Claude basado en feedback"""
        try:
            prompt = f"""
            Receta actual: {json.dumps(recipe, ensure_ascii=False)}
            Feedback del usuario: {feedback}
            Preferencias del usuario - No le gusta: {self.data['user_preferences']['dislikes']}
            Alergias: {self.data['user_preferences']['allergies']}
            
            Modifica la receta para incorporar el feedback del usuario manteniendo:
            - Macros similares (±10%)
            - Método de cocción en Crockpot
            - Número de porciones
            
            Devuelve ÚNICAMENTE el JSON de la receta modificada, sin texto adicional.
            """
            
            response = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parsear la respuesta JSON
            modified_recipe = json.loads(response.content[0].text)
            
            # Agregar feedback al historial
            if "feedback" not in modified_recipe:
                modified_recipe["feedback"] = []
            modified_recipe["feedback"].append({
                "date": datetime.now().isoformat(),
                "comment": feedback,
                "applied": True
            })
            
            return modified_recipe
            
        except Exception as e:
            logger.error(f"Error al modificar receta con Claude: {e}")
            # Agregar feedback sin modificar la receta
            recipe["feedback"].append({
                "date": datetime.now().isoformat(),
                "comment": feedback,
                "applied": False,
                "error": str(e)
            })
            return recipe
    
    def search_or_create_recipe(self, query: str) -> str:
        """Buscar o crear receta usando Claude"""
        try:
            prompt = f"""
            El usuario busca: {query}
            
            Preferencias del usuario:
            - No le gusta: {self.data['user_preferences']['dislikes']}
            - Alergias: {self.data['user_preferences']['allergies']}
            - Objetivos de macros: {self.data['user_preferences']['macro_targets']}
            
            Crea una receta que:
            1. Se pueda hacer en Crockpot de 12L
            2. Sirva para 8 porciones
            3. Sea adecuada para meal prep
            4. Incluya macros por porción
            5. Tenga instrucciones claras
            
            Responde en español con el formato:
            
            **[NOMBRE DE LA RECETA]**
            
            **Tiempo de cocción:** [tiempo]
            **Porciones:** 8
            
            **Ingredientes:**
            - [lista de ingredientes]
            
            **Instrucciones:**
            1. [pasos numerados]
            
            **Macros por porción:**
            - Proteína: [x]g
            - Carbohidratos: [x]g  
            - Grasa: [x]g
            - Calorías: [x]
            
            **¿Te gustaría guardar esta receta?**
            """
            
            response = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error al buscar/crear receta: {e}")
            return f"❌ Error al procesar tu búsqueda: {str(e)}\n\nIntenta de nuevo o busca una receta más específica."
    
    def check_rotation_needed(self):
        """Verificar si es necesario rotar el menú"""
        last_rotation = self.data["user_preferences"].get("last_rotation")
        if not last_rotation:
            return False
        
        last_rotation_date = datetime.fromisoformat(last_rotation)
        days_since_rotation = (datetime.now() - last_rotation_date).days
        
        return days_since_rotation >= 14
    
    def rotate_menu(self):
        """Rotar el menú automáticamente"""
        current_week = self.data["user_preferences"]["current_week"]
        
        if current_week in [1, 2]:
            new_week = 3 if current_week == 2 else 1
        else:
            new_week = 1 if current_week == 4 else current_week + 1
        
        self.data["user_preferences"]["current_week"] = new_week
        self.data["user_preferences"]["last_rotation"] = datetime.now().isoformat()
        
        return new_week

# Instanciar el bot
meal_bot = MealPrepBot()

# Manejadores de comandos
@bot.message_handler(commands=['start'])
def start_command(message):
    """Comando de inicio"""
    welcome_text = """
🍽️ **¡Bienvenido al Meal Prep Bot!**

Soy tu asistente personal para meal prep con batch cooking. Te ayudo a:

📅 Gestionar menús con rotación automática cada 2 semanas
🧮 Calcular macros (objetivo: 145g proteína, 380g carbos, 100g grasa)
🛒 Generar listas de compra categorizadas
⏰ Crear cronogramas de cocción optimizados para Crockpot 12L
🤖 Modificar recetas basado en tu feedback

**Comandos disponibles:**
/menu - Ver menú de la semana actual
/recetas - Ver todas las recetas
/buscar [consulta] - Buscar o crear recetas con IA
/compras - Generar lista de compra
/cronograma - Ver cronograma de cocción
/macros - Ver resumen de macros
/rating [receta] [1-5] [comentario] - Calificar receta
/favorito [receta] - Marcar como favorito
/cambiar_semana [1-4] - Cambiar semana manualmente

También puedes escribirme en lenguaje natural como:
"No me gusta el cilantro en esta receta"
"Quiero más recetas con pollo"

¡Empecemos! Usa /menu para ver tu menú actual 👨‍🍳
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['menu', 'menu_semana'])
def menu_command(message):
    """Mostrar menú de la semana actual"""
    try:
        meal_plan = meal_bot.get_current_meal_plan()
        current_week = meal_bot.data["user_preferences"]["current_week"]
        macros = meal_bot.calculate_daily_macros()
        targets = meal_bot.data["user_preferences"]["macro_targets"]
        
        menu_text = f"🍽️ **MENÚ SEMANA {current_week}-{current_week+1 if current_week in [1,3] else current_week-1}**\n"
        menu_text += f"*{meal_plan['name']}*\n\n"
        
        menu_text += "**🥩 PROTEÍNAS:**\n"
        for protein_id in meal_plan["proteins"]:
            recipe = meal_bot.get_recipe_by_id(protein_id)
            if recipe:
                menu_text += f"• {recipe['name']}\n"
        
        menu_text += "\n**🫘 LEGUMBRES:**\n"
        for legume_id in meal_plan["legumes"]:
            recipe = meal_bot.get_recipe_by_id(legume_id)
            if recipe:
                menu_text += f"• {recipe['name']}\n"
        
        menu_text += "\n**🌾 COMPONENTES BASE:**\n"
        for base_id in meal_plan["base_components"]:
            recipe = meal_bot.get_recipe_by_id(base_id)
            if recipe:
                menu_text += f"• {recipe['name']}\n"
        
        menu_text += f"\n**📊 MACROS DIARIOS:**\n"
        menu_text += f"• Proteína: {macros['protein']:.0f}g (objetivo: {targets['protein']}g)\n"
        menu_text += f"• Carbohidratos: {macros['carbs']:.0f}g (objetivo: {targets['carbs']}g)\n"
        menu_text += f"• Grasas: {macros['fat']:.0f}g (objetivo: {targets['fat']}g)\n"
        menu_text += f"• Calorías: {macros['calories']:.0f} (objetivo: {targets['calories']})\n"
        
        # Verificar si necesita rotación
        if meal_bot.check_rotation_needed():
            menu_text += "\n🔄 *Es momento de rotar el menú. Usa /cambiar_semana para cambiar.*"
        
        bot.reply_to(message, menu_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en menu_command: {e}")
        bot.reply_to(message, "❌ Error al mostrar el menú. Intenta de nuevo.")

@bot.message_handler(commands=['recetas'])
def recipes_command(message):
    """Listar todas las recetas"""
    try:
        recipes = meal_bot.data["recipes"]
        if not recipes:
            bot.reply_to(message, "📝 No hay recetas guardadas aún.")
            return
        
        recipes_text = "📚 **TODAS LAS RECETAS:**\n\n"
        
        categories = {
            "protein": "🥩 PROTEÍNAS",
            "legume": "🫘 LEGUMBRES", 
            "base": "🌾 BASES",
            "vegetable": "🥬 VEGETALES"
        }
        
        for category, title in categories.items():
            category_recipes = [r for r in recipes.values() if r.get("category") == category]
            if category_recipes:
                recipes_text += f"**{title}:**\n"
                for recipe in sorted(category_recipes, key=lambda x: x["name"]):
                    star = "⭐" if recipe.get("favorite") else ""
                    rating = "★" * int(recipe.get("rating", 0)) if recipe.get("rating", 0) > 0 else ""
                    recipes_text += f"• {recipe['name']} {star} {rating}\n"
                recipes_text += "\n"
        
        recipes_text += "💡 *Usa `/buscar [nombre]` para ver detalles de una receta*"
        
        bot.reply_to(message, recipes_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en recipes_command: {e}")
        bot.reply_to(message, "❌ Error al mostrar recetas. Intenta de nuevo.")

@bot.message_handler(commands=['buscar'])
def search_command(message):
    """Buscar o crear recetas con IA"""
    try:
        query = message.text.replace('/buscar', '').strip()
        if not query:
            bot.reply_to(message, "🔍 Uso: `/buscar [tu consulta]`\n\nEjemplos:\n• `/buscar pollo mediterráneo`\n• `/buscar desayuno proteico sin huevos`\n• `/buscar receta vegana alta en proteína`")
            return
        
        # Mostrar mensaje de "escribiendo..."
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Buscar primero en recetas existentes
        recipes = meal_bot.data["recipes"]
        matching_recipes = []
        
        query_lower = query.lower()
        for recipe in recipes.values():
            if (query_lower in recipe["name"].lower() or 
                any(query_lower in tag for tag in recipe.get("tags", []))):
                matching_recipes.append(recipe)
        
        if matching_recipes:
            # Mostrar recetas existentes que coincidan
            result_text = f"🔍 **Encontré estas recetas para '{query}':**\n\n"
            for recipe in matching_recipes[:3]:  # Máximo 3 resultados
                result_text += f"**{recipe['name']}**\n"
                result_text += f"⏱️ {recipe['cook_time']}\n"
                result_text += f"🍽️ {recipe['servings']} porciones\n"
                result_text += f"📊 P: {recipe['macros_per_serving']['protein']}g | "
                result_text += f"C: {recipe['macros_per_serving']['carbs']}g | "
                result_text += f"G: {recipe['macros_per_serving']['fat']}g\n\n"
            
            result_text += "💡 *¿Quieres que cree una receta nueva? Escribe algo más específico.*"
        else:
            # Crear nueva receta con Claude
            result_text = "🤖 Creando una receta personalizada...\n\n"
            result_text += meal_bot.search_or_create_recipe(query)
        
        bot.reply_to(message, result_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en search_command: {e}")
        bot.reply_to(message, f"❌ Error al buscar recetas: {str(e)}")

@bot.message_handler(commands=['compras', 'lista_compras'])
def shopping_command(message):
    """Generar lista de compra"""
    try:
        shopping_list = meal_bot.generate_shopping_list()
        current_week = meal_bot.data["user_preferences"]["current_week"]
        
        shopping_text = f"🛒 **LISTA DE COMPRAS - SEMANA {current_week}**\n\n"
        
        category_icons = {
            "proteinas": "🥩",
            "legumbres": "🫘", 
            "cereales": "🌾",
            "vegetales": "🥬",
            "especias": "🧂",
            "lacteos": "🥛",
            "otros": "📦"
        }
        
        for category, items in shopping_list.items():
            if items:
                icon = category_icons.get(category, "•")
                shopping_text += f"**{icon} {category.upper()}:**\n"
                for item in items:
                    shopping_text += f"☐ {item}\n"
                shopping_text += "\n"
        
        shopping_text += "💡 *Lista generada para toda la semana de meal prep*"
        
        # Guardar lista en historial
        meal_bot.data["shopping_lists"][datetime.now().isoformat()[:10]] = shopping_list
        meal_bot.save_data()
        
        bot.reply_to(message, shopping_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en shopping_command: {e}")
        bot.reply_to(message, "❌ Error al generar lista de compras. Intenta de nuevo.")

@bot.message_handler(commands=['cronograma'])
def schedule_command(message):
    """Mostrar cronograma de cocción"""
    try:
        schedule = meal_bot.generate_cooking_schedule()
        
        schedule_text = "⏰ **CRONOGRAMA DE COCCIÓN**\n\n"
        
        schedule_text += "**🍳 SÁBADO:**\n"
        for i, item in enumerate(schedule["saturday"], 1):
            schedule_text += f"{i}. **{item['name']}**\n"
            schedule_text += f"   ⏱️ {item['cook_time']}\n\n"
        
        schedule_text += "**👨‍🍳 DOMINGO:**\n"
        for i, item in enumerate(schedule["sunday"], 1):
            schedule_text += f"{i}. **{item['name']}**\n"
            schedule_text += f"   ⏱️ {item['cook_time']}\n"
            if item.get("method"):
                schedule_text += f"   🔥 Método: {item['method']}\n"
            schedule_text += "\n"
        
        schedule_text += "💡 *Optimizado para una Crockpot de 12L*\n"
        schedule_text += "📝 *Lava la Crockpot entre tandas para mejores resultados*"
        
        bot.reply_to(message, schedule_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en schedule_command: {e}")
        bot.reply_to(message, "❌ Error al generar cronograma. Intenta de nuevo.")

@bot.message_handler(commands=['macros'])
def macros_command(message):
    """Mostrar resumen de macros"""
    try:
        macros = meal_bot.calculate_daily_macros()
        targets = meal_bot.data["user_preferences"]["macro_targets"]
        
        macros_text = "📊 **RESUMEN DE MACROS DIARIOS**\n\n"
        
        # Calcular porcentajes
        protein_pct = (macros["protein"] / targets["protein"]) * 100
        carbs_pct = (macros["carbs"] / targets["carbs"]) * 100  
        fat_pct = (macros["fat"] / targets["fat"]) * 100
        cal_pct = (macros["calories"] / targets["calories"]) * 100
        
        def get_status_icon(pct):
            if 90 <= pct <= 110:
                return "✅"
            elif 80 <= pct < 90 or 110 < pct <= 120:
                return "⚠️"
            else:
                return "❌"
        
        macros_text += f"**🥩 PROTEÍNA:**\n"
        macros_text += f"{get_status_icon(protein_pct)} {macros['protein']:.0f}g / {targets['protein']}g ({protein_pct:.0f}%)\n\n"
        
        macros_text += f"**🌾 CARBOHIDRATOS:**\n"
        macros_text += f"{get_status_icon(carbs_pct)} {macros['carbs']:.0f}g / {targets['carbs']}g ({carbs_pct:.0f}%)\n\n"
        
        macros_text += f"**🥑 GRASAS:**\n"
        macros_text += f"{get_status_icon(fat_pct)} {macros['fat']:.0f}g / {targets['fat']}g ({fat_pct:.0f}%)\n\n"
        
        macros_text += f"**⚡ CALORÍAS:**\n"
        macros_text += f"{get_status_icon(cal_pct)} {macros['calories']:.0f} / {targets['calories']} ({cal_pct:.0f}%)\n\n"
        
        macros_text += "**Leyenda:**\n"
        macros_text += "✅ Objetivo alcanzado (90-110%)\n"
        macros_text += "⚠️ Cerca del objetivo (80-89%, 111-120%)\n" 
        macros_text += "❌ Lejos del objetivo (<80%, >120%)\n"
        
        bot.reply_to(message, macros_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en macros_command: {e}")
        bot.reply_to(message, "❌ Error al calcular macros. Intenta de nuevo.")

@bot.message_handler(commands=['rating'])
def rating_command(message):
    """Calificar una receta"""
    try:
        parts = message.text.split(' ', 3)
        if len(parts) < 3:
            bot.reply_to(message, "📝 Uso: `/rating [nombre_receta] [1-5] [comentario opcional]`\n\nEjemplo: `/rating pollo_mediterraneo 4 muy bueno pero menos aceitunas`")
            return
        
        recipe_name = parts[1].lower().replace(' ', '_')
        try:
            rating = int(parts[2])
            if not 1 <= rating <= 5:
                raise ValueError()
        except ValueError:
            bot.reply_to(message, "⭐ La calificación debe ser un número del 1 al 5")
            return
        
        feedback = parts[3] if len(parts) > 3 else ""
        
        # Buscar receta
        recipe = None
        recipe_id = None
        for rid, r in meal_bot.data["recipes"].items():
            if (recipe_name in rid.lower() or 
                recipe_name in r["name"].lower().replace(' ', '_')):
                recipe = r
                recipe_id = rid
                break
        
        if not recipe:
            bot.reply_to(message, f"❌ No encontré una receta llamada '{recipe_name}'. Usa /recetas para ver todas las recetas disponibles.")
            return
        
        # Actualizar rating
        recipe["rating"] = rating
        
        # Si hay feedback y rating < 4, modificar con Claude
        if feedback and rating < 4:
            bot.send_chat_action(message.chat.id, 'typing')
            modified_recipe = meal_bot.modify_recipe_with_claude(recipe, feedback)
            meal_bot.data["recipes"][recipe_id] = modified_recipe
            
            response_text = f"⭐ **Calificación guardada: {rating}/5**\n\n"
            response_text += f"🤖 **Receta modificada basada en tu feedback:**\n"
            response_text += f"*{feedback}*\n\n"
            response_text += f"✅ La receta **{recipe['name']}** ha sido actualizada automáticamente."
        else:
            if feedback:
                recipe["feedback"].append({
                    "date": datetime.now().isoformat(),
                    "comment": feedback,
                    "rating": rating,
                    "applied": False
                })
            
            response_text = f"⭐ **Calificación guardada: {rating}/5**\n"
            response_text += f"📝 **Receta:** {recipe['name']}\n"
            if feedback:
                response_text += f"💬 **Comentario:** {feedback}\n"
            response_text += "\n✅ ¡Gracias por tu feedback!"
        
        meal_bot.save_data()
        bot.reply_to(message, response_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en rating_command: {e}")
        bot.reply_to(message, f"❌ Error al guardar calificación: {str(e)}")

@bot.message_handler(commands=['favorito'])
def favorite_command(message):
    """Marcar/desmarcar receta como favorita"""
    try:
        recipe_name = message.text.replace('/favorito', '').strip().lower().replace(' ', '_')
        if not recipe_name:
            bot.reply_to(message, "⭐ Uso: `/favorito [nombre_receta]`\n\nEjemplo: `/favorito pollo_mediterraneo`")
            return
        
        # Buscar receta
        recipe = None
        recipe_id = None
        for rid, r in meal_bot.data["recipes"].items():
            if (recipe_name in rid.lower() or 
                recipe_name in r["name"].lower().replace(' ', '_')):
                recipe = r
                recipe_id = rid
                break
        
        if not recipe:
            bot.reply_to(message, f"❌ No encontré una receta llamada '{recipe_name}'. Usa /recetas para ver todas las recetas.")
            return
        
        # Toggle favorito
        recipe["favorite"] = not recipe.get("favorite", False)
        meal_bot.save_data()
        
        action = "agregada a" if recipe["favorite"] else "removida de"
        icon = "⭐" if recipe["favorite"] else "☆"
        
        bot.reply_to(message, f"{icon} **{recipe['name']}** {action} tus favoritos!")
        
    except Exception as e:
        logger.error(f"Error en favorite_command: {e}")
        bot.reply_to(message, "❌ Error al actualizar favoritos. Intenta de nuevo.")

@bot.message_handler(commands=['cambiar_semana'])
def change_week_command(message):
    """Cambiar semana de rotación manualmente"""
    try:
        week_str = message.text.replace('/cambiar_semana', '').strip()
        if not week_str:
            current_week = meal_bot.data["user_preferences"]["current_week"]
            bot.reply_to(message, f"📅 Semana actual: **{current_week}**\n\nUso: `/cambiar_semana [1-4]`\n\nSemanas disponibles:\n• 1-2: Mediterráneo/Mexicano\n• 3-4: Asiático/Marroquí")
            return
        
        try:
            new_week = int(week_str)
            if not 1 <= new_week <= 4:
                raise ValueError()
        except ValueError:
            bot.reply_to(message, "❌ La semana debe ser un número del 1 al 4")
            return
        
        old_week = meal_bot.data["user_preferences"]["current_week"]
        meal_bot.data["user_preferences"]["current_week"] = new_week
        meal_bot.data["user_preferences"]["last_rotation"] = datetime.now().isoformat()
        meal_bot.save_data()
        
        meal_plan = meal_bot.get_current_meal_plan()
        
        response_text = f"🔄 **Menú cambiado exitosamente**\n\n"
        response_text += f"📅 Semana anterior: {old_week}\n"
        response_text += f"📅 Semana actual: **{new_week}**\n"
        response_text += f"🍽️ Menú: **{meal_plan['name']}**\n\n"
        response_text += "💡 *Usa /menu para ver el nuevo menú completo*"
        
        bot.reply_to(message, response_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en change_week_command: {e}")
        bot.reply_to(message, "❌ Error al cambiar semana. Intenta de nuevo.")

# Manejador de mensajes de texto libre (conversacional)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    """Manejar mensajes conversacionales"""
    try:
        text = message.text.lower()
        
        # Frases comunes de feedback
        if any(phrase in text for phrase in ["no me gusta", "muy salado", "muy seco", "quedó", "sabe"]):
            bot.reply_to(message, "💬 ¡Entendido! Para mejorar una receta específica, usa:\n\n`/rating [nombre_receta] [1-5] [tu comentario]`\n\nEjemplo: `/rating pollo_mediterraneo 3 quedó muy seco, menos tiempo de cocción`\n\n🤖 Mi IA modificará automáticamente la receta basada en tu feedback.")
            
        elif any(phrase in text for phrase in ["quiero", "busco", "receta", "cómo hacer"]):
            bot.reply_to(message, "🔍 ¡Te ayudo a encontrar recetas! Usa:\n\n`/buscar [tu consulta]`\n\nEjemplos:\n• `/buscar pollo con especias`\n• `/buscar desayuno proteico`\n• `/buscar receta vegana`\n\n🤖 Puedo buscar en tus recetas existentes o crear nuevas con IA.")
            
        elif any(phrase in text for phrase in ["menú", "menu", "qué cocinar", "que cocinar"]):
            menu_command(message)
            
        elif any(phrase in text for phrase in ["compra", "lista", "supermercado"]):
            shopping_command(message)
            
        elif any(phrase in text for phrase in ["cronograma", "cuándo cocinar", "cuando cocinar", "horario"]):
            schedule_command(message)
            
        else:
            # Respuesta genérica amigable
            bot.reply_to(message, "👋 ¡Hola! Soy tu asistente de meal prep.\n\n💡 **Comandos útiles:**\n• `/menu` - Ver menú actual\n• `/buscar [consulta]` - Buscar recetas\n• `/compras` - Lista de compras\n• `/cronograma` - Horario de cocción\n\n❓ Escribe `/start` para ver todos los comandos disponibles.")
    
    except Exception as e:
        logger.error(f"Error en handle_text: {e}")
        bot.reply_to(message, "❌ Disculpa, ocurrió un error. Intenta usar un comando específico como /menu o /recetas.")

if __name__ == '__main__':
    logger.info("Iniciando Meal Prep Bot...")
    
    # Verificar rotación automática al inicio
    if meal_bot.check_rotation_needed():
        new_week = meal_bot.rotate_menu()
        meal_bot.save_data()
        logger.info(f"Rotación automática: cambiado a semana {new_week}")
    
    # Iniciar bot
    bot.infinity_polling()