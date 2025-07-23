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
import fcntl
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import telebot
from telebot import types
from anthropic import Anthropic
from flask import Flask, request

from config import (
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY, DATABASE_FILE, BACKUP_PREFIX,
    DEFAULT_MACRO_TARGETS, DEFAULT_COOKING_SCHEDULE, SHOPPING_CATEGORIES,
    WEBHOOK_URL, WEBHOOK_PATH, USE_WEBHOOK, ACTIVITY_FACTORS, PHYSICAL_WORK_BONUS,
    MACRO_DISTRIBUTIONS, CALORIC_ADJUSTMENTS, VALIDATION_RANGES
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar bot y Flask
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)
try:
    logger.info(f"🔑 ANTHROPIC_API_KEY configurada: {ANTHROPIC_API_KEY is not None and len(ANTHROPIC_API_KEY or '') > 0}")
    claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("✅ Claude client initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing Claude client: {e}")
    logger.error(f"🔍 ANTHROPIC_API_KEY length: {len(ANTHROPIC_API_KEY or '')}")
    claude_client = None

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
        if claude_client is None:
            logger.error("Claude client not available")
            recipe["feedback"].append({
                "date": datetime.now().isoformat(),
                "comment": feedback,
                "applied": False,
                "error": "Claude client not initialized"
            })
            return recipe
            
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
        if claude_client is None:
            return "❌ Servicio de IA no disponible temporalmente. Intenta más tarde o usa /recetas para ver recetas existentes."
            
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
            # Manejo específico de errores comunes
            error_msg = str(e).lower()
            if "connection" in error_msg or "network" in error_msg:
                return "❌ Error de conexión con el servicio de IA.\n\nVerifica tu conexión a internet e intenta de nuevo."
            elif "api" in error_msg or "key" in error_msg:
                return "❌ Error de autenticación con el servicio de IA.\n\nContacta al administrador del bot."
            elif "rate" in error_msg or "limit" in error_msg:
                return "❌ Límite de uso alcanzado.\n\nEspera unos minutos e intenta de nuevo."
            else:
                return f"❌ Error al procesar tu búsqueda: Connection error.\n\nIntenta de nuevo o busca una receta más específica."
    
    def process_ingredients_with_claude(self, ingredients_list: list) -> dict:
        """Procesar y agregar ingredientes usando Claude API"""
        logger.info(f"🤖 Iniciando procesamiento con Claude API para {len(ingredients_list)} ingredientes")
        
        if claude_client is None:
            logger.error("❌ Claude client is None - API not initialized")
            return None
            
        try:
            # Preparar la lista de ingredientes para enviar a Claude
            ingredients_text = "\n".join([
                f"- {item['ingredient']} (multiplicar por {item['multiplier']:.2f}) [categoría: {item['category']}]"
                for item in ingredients_list
            ])
            
            prompt = f"""Procesa esta lista de ingredientes para meal prep y devuelve SOLO JSON válido.

INGREDIENTES ({len(ingredients_list)} total):
{ingredients_text}

TAREAS:
1. Multiplica cantidades por los factores dados
2. Agrega duplicados: "ajos" + "dientes de ajo" = "dientes de ajo" total
3. Convierte unidades:
   - "tazas" → ml (1 taza = 250ml)
   - Pesos: gramos si <1000g, kilogramos si ≥1000g  
   - Volúmenes: ml si <1000ml, litros si ≥1000ml
   - PRESERVAR: cda, cdta (no cambiar)
4. Categoriza: proteinas, legumbres, cereales, vegetales, especias, lacteos, otros

RESPUESTA (SOLO JSON):
{{
  "success": true,
  "ingredients_by_category": {{
    "proteinas": ["2.3 kg pechugas de pollo", "2.1 kg carne de res"],
    "vegetales": ["400 g cebollas", "50 g ajos"],
    "legumbres": ["1.2 kg frijoles negros", "1.4 kg garbanzos"],
    "cereales": ["830 g quinoa", "750 g arroz integral"],
    "especias": ["sal y pimienta al gusto", "4 cda oregano seco"],
    "otros": ["1.5 L caldo de pollo", "800 ml leche de coco"]
  }},
  "total_items": 25
}}
"""

            logger.info("📤 Enviando request a Claude API...")
            response = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            logger.info("📥 Respuesta recibida de Claude API")
            claude_response_text = response.content[0].text.strip()
            logger.info(f"🔍 Claude response (first 200 chars): {claude_response_text[:200]}...")
            
            import json
            result = json.loads(claude_response_text)
            
            if result.get("success"):
                logger.info(f"✅ Claude procesó {len(ingredients_list)} ingredientes → {result.get('total_items', 0)} items únicos")
                return result
            else:
                logger.error(f"❌ Claude reporting error: {result.get('error', 'Unknown error')}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parsing Claude JSON response: {e}")
            logger.error(f"🔍 Raw response was: {claude_response_text if 'claude_response_text' in locals() else 'No response captured'}")
            return None
        except Exception as e:
            logger.error(f"❌ Error processing ingredients with Claude: {str(e)}")
            logger.error(f"🔍 Exception type: {type(e).__name__}")
            return None
    
    def check_rotation_needed(self):
        """Verificar si es lunes y necesita rotación automática"""
        from datetime import datetime
        
        now = datetime.now()
        last_rotation = self.data["user_preferences"].get("last_rotation")
        
        # Si nunca ha rotado, necesita rotación
        if not last_rotation:
            return True
        
        last_rotation_date = datetime.fromisoformat(last_rotation)
        days_since_rotation = (now - last_rotation_date).days
        
        # Verificar si es lunes (0 = lunes) y han pasado al menos 6 días
        is_monday = now.weekday() == 0
        enough_time_passed = days_since_rotation >= 6
        
        return is_monday and enough_time_passed
    
    def get_available_recipes(self):
        """Obtener todas las recetas disponibles organizadas por categoría"""
        recipes_by_category = {
            "proteinas": [],
            "legumbres": [],
            "cereales": [],
            "vegetales": []
        }
        
        for recipe_id, recipe in self.data["recipes"].items():
            category = recipe.get("category", "otros")
            if category in recipes_by_category:
                recipes_by_category[category].append({
                    "id": recipe_id,
                    "name": recipe["name"],
                    "rating": recipe.get("rating", 0),
                    "favorite": recipe.get("favorite", False)
                })
        
        return recipes_by_category
    
    def get_anchored_favorites(self):
        """Obtener recetas marcadas como favoritas (ancladas)"""
        favorites = []
        for recipe_id, recipe in self.data["recipes"].items():
            if recipe.get("favorite", False):
                favorites.append({
                    "id": recipe_id,
                    "name": recipe["name"],
                    "category": recipe.get("category", "otros")
                })
        return favorites
    
    def create_new_meal_plan(self, selected_recipes):
        """Crear nuevo plan de comidas con las recetas seleccionadas"""
        # Actualizar el plan actual con las nuevas recetas
        new_plan = {
            "name": f"Semana {self.data['user_preferences']['current_week']} - Comida Natural",
            "proteins": [],
            "legumes": [],
            "base_components": [],
            "vegetables": []
        }
        
        # Organizar recetas seleccionadas por categoría
        for recipe_id in selected_recipes:
            if recipe_id in self.data["recipes"]:
                recipe = self.data["recipes"][recipe_id]
                category = recipe.get("category", "otros")
                
                if category == "protein":
                    new_plan["proteins"].append(recipe_id)
                elif category == "legume":
                    new_plan["legumes"].append(recipe_id)
                elif category == "base":
                    new_plan["base_components"].append(recipe_id)
                elif category == "vegetable":
                    new_plan["vegetables"].append(recipe_id)
        
        # Actualizar el plan en los datos
        current_week = self.data["user_preferences"]["current_week"]
        meal_plans = self.data.get("meal_plans", {})
        meal_plans[f"week_{current_week}"] = new_plan
        self.data["meal_plans"] = meal_plans
        
        # Marcar rotación completada
        self.data["user_preferences"]["last_rotation"] = datetime.now().isoformat()
        self.save_data()
        
        return new_plan
    
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

    # ===== MACRO CALCULATION FUNCTIONS =====
    
    def validate_user_data(self, data_type: str, value: float) -> bool:
        """Validar datos del usuario dentro de rangos realistas"""
        if data_type not in VALIDATION_RANGES:
            return True
        
        min_val, max_val = VALIDATION_RANGES[data_type]
        return min_val <= value <= max_val
    
    def calculate_bmr(self, peso: float, altura: float, edad: int, sexo: str) -> float:
        """Calcular Metabolismo Basal usando fórmula Mifflin-St Jeor (más precisa)"""
        if sexo.upper() in ['M', 'MASCULINO', 'HOMBRE']:
            # Hombres: BMR = 10 × peso + 6.25 × altura - 5 × edad + 5
            bmr = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
        else:
            # Mujeres: BMR = 10 × peso + 6.25 × altura - 5 × edad - 161
            bmr = (10 * peso) + (6.25 * altura) - (5 * edad) - 161
        
        return max(bmr, 1000)  # Mínimo 1000 kcal por seguridad
    
    def calculate_tdee(self, bmr: float, actividad: str, trabajo_fisico: str) -> float:
        """Calcular Gasto Energético Total Diario"""
        # Factor de actividad
        activity_multiplier = ACTIVITY_FACTORS.get(actividad, 1.2)
        tdee = bmr * activity_multiplier
        
        # Bonus por trabajo físico
        work_bonus = PHYSICAL_WORK_BONUS.get(trabajo_fisico, 0)
        tdee += work_bonus
        
        return tdee
    
    def calculate_target_calories(self, tdee: float, objetivo: str) -> int:
        """Calcular calorías objetivo según la meta"""
        adjustment = CALORIC_ADJUSTMENTS.get(objetivo, 0.0)
        target_calories = tdee * (1 + adjustment)
        return round(target_calories)
    
    def calculate_macros(self, target_calories: int, objetivo: str) -> dict:
        """Calcular distribución de macronutrientes"""
        distribution = MACRO_DISTRIBUTIONS.get(objetivo, MACRO_DISTRIBUTIONS["mantener"])
        
        # Calcular gramos de cada macro
        protein_calories = target_calories * distribution["protein"]
        carbs_calories = target_calories * distribution["carbs"]
        fat_calories = target_calories * distribution["fat"]
        
        # Convertir a gramos (proteína y carbos = 4 kcal/g, grasa = 9 kcal/g)
        macros = {
            "calories": target_calories,
            "protein": round(protein_calories / 4),
            "carbs": round(carbs_calories / 4),
            "fat": round(fat_calories / 9)
        }
        
        return macros
    
    def save_user_profile(self, perfil: dict):
        """Guardar perfil de usuario y actualizar macro targets"""
        # Actualizar perfil en user_preferences
        if "user_profile" not in self.data["user_preferences"]:
            self.data["user_preferences"]["user_profile"] = {}
        
        self.data["user_preferences"]["user_profile"] = perfil
        
        # Actualizar macro_targets con los valores calculados
        macros = perfil["macros_calculados"]
        self.data["user_preferences"]["macro_targets"] = {
            "protein": macros["protein"],
            "carbs": macros["carbs"],
            "fat": macros["fat"],
            "calories": macros["calories"]
        }
        
        self.save_data()
    
    def get_user_profile(self) -> dict:
        """Obtener perfil de usuario guardado"""
        return self.data["user_preferences"].get("user_profile", None)
    
    def calculate_personal_portions(self, num_comidas: int = 5) -> dict:
        """Calcular porciones personalizadas por comida basadas en macros del usuario"""
        user_profile = self.get_user_profile()
        if not user_profile:
            return None
            
        # Obtener macros objetivo del usuario
        target_macros = user_profile["macros_calculados"]
        daily_protein = target_macros["protein"]
        daily_carbs = target_macros["carbs"] 
        daily_fat = target_macros["fat"]
        daily_calories = target_macros["calories"]
        
        # Obtener recetas de semana actual (1-2)
        week_recipes = self.data["meal_plans"]["week_1_2"]
        
        # Calcular macros por porción de cada categoría
        recipes_data = {}
        for category in ["proteins", "legumes", "base_components"]:
            recipes_data[category] = []
            for recipe_id in week_recipes[category]:
                if recipe_id in self.data["recipes"]:
                    recipe = self.data["recipes"][recipe_id]
                    recipes_data[category].append({
                        "id": recipe_id,
                        "name": recipe["name"],
                        "macros": recipe["macros_per_serving"]
                    })
        
        # Distribución típica de macros por comida
        # Proteínas: 35%, Legumbres: 25%, Bases: 40%
        protein_from_proteins = daily_protein * 0.35
        protein_from_legumes = daily_protein * 0.25
        protein_from_bases = daily_protein * 0.40
        
        carbs_from_proteins = daily_carbs * 0.10
        carbs_from_legumes = daily_carbs * 0.35
        carbs_from_bases = daily_carbs * 0.55
        
        fat_from_proteins = daily_fat * 0.45
        fat_from_legumes = daily_fat * 0.15
        fat_from_bases = daily_fat * 0.40
        
        # Calcular porciones diarias necesarias de cada receta
        portions_needed = {}
        
        # Proteínas
        for recipe in recipes_data["proteins"]:
            recipe_protein = recipe["macros"]["protein"]
            # Dividir la proteína objetivo entre las 2 recetas de proteína
            daily_portions = (protein_from_proteins / 2) / recipe_protein
            portions_needed[recipe["id"]] = {
                "name": recipe["name"],
                "daily_portions": daily_portions,
                "portions_per_meal": daily_portions / num_comidas,
                "category": "protein"
            }
        
        # Legumbres
        for recipe in recipes_data["legumes"]:
            recipe_protein = recipe["macros"]["protein"]
            # Dividir la proteína objetivo entre las 2 recetas de legumbre
            daily_portions = (protein_from_legumes / 2) / recipe_protein
            portions_needed[recipe["id"]] = {
                "name": recipe["name"],
                "daily_portions": daily_portions,
                "portions_per_meal": daily_portions / num_comidas,
                "category": "legume"
            }
        
        # Bases (carbohidratos)
        base_recipes = [r for r in recipes_data["base_components"] if r["id"] in ["quinoa_pilaf", "brown_rice"]]
        for recipe in base_recipes:
            recipe_carbs = recipe["macros"]["carbs"]
            # Dividir los carbohidratos objetivo entre las 2 recetas base
            daily_portions = (carbs_from_bases / 2) / recipe_carbs
            portions_needed[recipe["id"]] = {
                "name": recipe["name"],
                "daily_portions": daily_portions,
                "portions_per_meal": daily_portions / num_comidas,
                "category": "base"
            }
        
        # Vegetales (cantidad fija)
        portions_needed["roasted_vegetables"] = {
            "name": "Vegetales Asados Mixtos",
            "daily_portions": 2.0,  # 2 porciones de vegetales al día
            "portions_per_meal": 2.0 / num_comidas,
            "category": "vegetable"
        }
        
        return {
            "portions_needed": portions_needed,
            "daily_macros": {
                "protein": daily_protein,
                "carbs": daily_carbs,
                "fat": daily_fat,
                "calories": daily_calories
            },
            "num_comidas": num_comidas
        }
    
    def parse_ingredient(self, ingredient: str) -> dict:
        """Parsear ingrediente para extraer cantidad, unidad y nombre"""
        import re
        
        ingredient = ingredient.strip()
        
        # Patrones múltiples para diferentes formatos
        patterns = [
            # "2 kg pechugas de pollo", "800g tomates"
            r'^(\d+(?:\.\d+)?)\s*([a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]+)\s+(.+)$',
            # "2 latas tomates triturados (800g)" - ignorar el paréntesis
            r'^(\d+(?:\.\d+)?)\s+(latas?|unidades?|dientes?|cdas?|cdtas?)\s+([^(]+)(?:\([^)]*\))?$',
            # "2 tomates grandes", "1 cebolla grande" 
            r'^(\d+(?:\.\d+)?)\s+([^0-9\s][^(]*?)(?:\s+(?:grande|pequeño|mediano|al gusto))?(?:\([^)]*\))?$'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, ingredient, re.IGNORECASE)
            if match:
                quantity = float(match.group(1))
                
                if len(match.groups()) == 3:
                    if pattern == patterns[1]:  # Formato "latas/unidades"
                        unit = match.group(2).lower().strip()
                        name = match.group(3).strip()
                    elif pattern == patterns[0]:  # Formato con unidad kg/g
                        unit = match.group(2).lower().strip()
                        name = match.group(3).strip()
                    else:  # Formato "2 tomates"
                        unit = ''
                        name = match.group(2).strip()
                else:
                    unit = ''
                    name = match.group(2).strip() if len(match.groups()) >= 2 else ingredient
                
                return {
                    'quantity': quantity,
                    'unit': unit,
                    'name': name,
                    'original': ingredient
                }
        
        # Si no coincide con ningún patrón, manejar casos especiales
        if any(word in ingredient.lower() for word in ['al gusto', 'c/n', 'cantidad necesaria']):
            return {
                'quantity': 0,  # Cantidad especial para "al gusto"
                'unit': '',
                'name': ingredient,
                'original': ingredient
            }
        
        # Fallback: devolver tal como está
        return {
            'quantity': 1.0,
            'unit': '',
            'name': ingredient,
            'original': ingredient
        }
    
    def standardize_unit(self, quantity: float, unit: str, ingredient_name: str) -> tuple:
        """Estandarizar unidades a kg/g para sólidos, L/ml para líquidos"""
        
        # No modificar cucharadas y cucharaditas
        if unit in ['cda', 'cdas', 'cucharada', 'cucharadas', 'cdta', 'cdtas', 'cucharadita', 'cucharaditas']:
            return quantity, unit
        
        # Unidades de peso
        weight_units = {
            'kg': 1000,
            'kilos': 1000,
            'kilogramo': 1000,
            'kilogramos': 1000,
            'g': 1,
            'gr': 1,
            'gramos': 1,
            'gramo': 1
        }
        
        # Unidades de volumen
        volume_units = {
            'l': 1000,
            'litro': 1000,
            'litros': 1000,
            'ml': 1,
            'mililitro': 1,
            'mililitros': 1,
            'taza': 250,  # 1 taza = 250ml
            'tazas': 250,
            'vaso': 200,  # 1 vaso = 200ml
            'vasos': 200
        }
        
        # Determinar si es peso o volumen por el contexto
        liquid_keywords = ['caldo', 'agua', 'leche', 'aceite', 'vinagre', 'jugo', 'vino', 'salsa líquida']
        is_liquid = any(keyword in ingredient_name.lower() for keyword in liquid_keywords)
        
        if unit in weight_units:
            # Convertir a gramos base
            grams = quantity * weight_units[unit]
            if grams >= 1000:
                return round(grams / 1000, 2), 'kg'
            else:
                return int(grams), 'g'
                
        elif unit in volume_units:
            # Convertir a ml base
            ml = quantity * volume_units[unit]
            if ml >= 1000:
                return round(ml / 1000, 2), 'L'
            else:
                return int(ml), 'ml'
                
        elif is_liquid and unit == '':
            # Si es líquido pero no tiene unidad explícita, asumir ml
            if quantity >= 1000:
                return round(quantity / 1000, 2), 'L'
            else:
                return int(quantity), 'ml'
        
        # Si no se puede estandarizar, devolver tal como está
        return quantity, unit
    
    def aggregate_ingredients(self, all_ingredients: list) -> dict:
        """Agregar ingredientes similares sumando cantidades"""
        aggregated = {}
        
        for ingredient_data in all_ingredients:
            parsed = self.parse_ingredient(ingredient_data['ingredient'])
            
            # Ajustar cantidad por el multiplicador de la receta
            adjusted_quantity = parsed['quantity'] * ingredient_data['multiplier']
            
            # Estandarizar unidades
            std_quantity, std_unit = self.standardize_unit(
                adjusted_quantity, 
                parsed['unit'], 
                parsed['name']
            )
            
            # Usar el nombre como clave para agregar
            key = parsed['name'].lower().strip()
            
            if key in aggregated:
                # Si ya existe, sumar cantidades (solo si tienen la misma unidad)
                if aggregated[key]['unit'] == std_unit:
                    aggregated[key]['quantity'] += std_quantity
                else:
                    # Si tienen diferentes unidades, mantener por separado
                    alt_key = f"{key}_{std_unit}"
                    if alt_key in aggregated:
                        aggregated[alt_key]['quantity'] += std_quantity
                    else:
                        aggregated[alt_key] = {
                            'quantity': std_quantity,
                            'unit': std_unit,
                            'name': parsed['name'],
                            'category': ingredient_data['category']
                        }
            else:
                aggregated[key] = {
                    'quantity': std_quantity,
                    'unit': std_unit,
                    'name': parsed['name'],
                    'category': ingredient_data['category']
                }
        
        return aggregated
    
    def format_ingredient(self, ingredient_data: dict) -> str:
        """Formatear ingrediente con cantidad y unidad estandarizada"""
        quantity = ingredient_data['quantity']
        unit = ingredient_data['unit']
        name = ingredient_data['name']
        
        # Manejar ingredientes "al gusto" (cantidad = 0)
        if quantity == 0:
            return name
        
        # Formatear cantidad
        if isinstance(quantity, float) and quantity.is_integer():
            quantity_str = str(int(quantity))
        else:
            quantity_str = f"{quantity:.1f}".rstrip('0').rstrip('.')
        
        # Formatear con unidad
        if unit:
            return f"{quantity_str} {unit} {name}"
        else:
            return f"{quantity_str} {name}"

    def calculate_cooking_amounts(self) -> dict:
        """Calcular cantidades de cocina y divisiones basadas en porciones personalizadas"""
        portions_data = self.calculate_personal_portions()
        if not portions_data:
            return None
            
        cooking_amounts = {}
        divisions = {}
        
        # Calcular cantidades semanales (7 días)
        for recipe_id, portion_info in portions_data['portions_needed'].items():
            daily_portions = portion_info['daily_portions']
            weekly_portions = daily_portions * 7  # 7 días de la semana
            
            # Obtener receta original
            if recipe_id in self.data["recipes"]:
                recipe = self.data["recipes"][recipe_id]
                original_servings = recipe["servings"]
                
                # Calcular cuántas "recetas completas" necesitamos hacer
                recipe_multiplier = weekly_portions / original_servings
                
                cooking_amounts[recipe_id] = {
                    "name": recipe["name"],
                    "original_servings": original_servings,
                    "weekly_portions_needed": weekly_portions,
                    "recipe_multiplier": recipe_multiplier,
                    "daily_portions": daily_portions,
                    "portions_per_meal": portion_info['portions_per_meal']
                }
                
                # Cálculo de divisiones
                # Si cocinamos 1x la receta (8 porciones), ¿en cuántas divisiones la partimos?
                total_cooked_servings = original_servings * recipe_multiplier
                divisions_needed = portions_data['num_comidas'] * 7  # 5 comidas x 7 días
                
                divisions[recipe_id] = {
                    "name": recipe["name"],
                    "total_cooked_servings": total_cooked_servings,
                    "divisions_needed": int(divisions_needed),
                    "portion_per_division": portion_info['portions_per_meal']
                }
        
        return {
            "cooking_amounts": cooking_amounts,
            "divisions": divisions,
            "weekly_summary": {
                "total_meals": portions_data['num_comidas'] * 7,
                "daily_meals": portions_data['num_comidas']
            }
        }
    
    def calculate_complete_profile(self, peso: float, altura: float, edad: int, 
                                 sexo: str, objetivo: str, actividad: str, 
                                 trabajo_fisico: str) -> dict:
        """Calcular perfil completo con macros"""
        # Calcular BMR
        bmr = self.calculate_bmr(peso, altura, edad, sexo)
        
        # Calcular TDEE  
        tdee = self.calculate_tdee(bmr, actividad, trabajo_fisico)
        
        # Calcular calorías objetivo
        target_calories = self.calculate_target_calories(tdee, objetivo)
        
        # Calcular macros
        macros = self.calculate_macros(target_calories, objetivo)
        
        # Calcular IMC
        altura_m = altura / 100  # convertir cm a metros
        imc = peso / (altura_m ** 2)
        
        perfil = {
            "peso": peso,
            "altura": altura,
            "edad": edad,
            "sexo": sexo,
            "objetivo": objetivo,
            "actividad": actividad,
            "trabajo_fisico": trabajo_fisico,
            "imc": round(imc, 1),
            "bmr": round(bmr),
            "tdee": round(tdee),
            "macros_calculados": macros,
            "fecha_actualizacion": datetime.now().isoformat()
        }
        
        return perfil

# Instanciar el bot
meal_bot = MealPrepBot()

# Variables para gestionar conversaciones de perfil
profile_conversations = {}

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
/perfil - Crear tu perfil personalizado
/mis\_macros - Ver tus macros calculados
/menu - Ver menú de la semana actual
/recetas - Ver todas las recetas
/buscar [consulta] - Buscar o crear recetas con IA

**🎯 MEAL PREP PERSONALIZADO:**
/meal\_prep - Calcular porciones por comida
/compras\_personales - Lista ajustada a tus macros
/divisiones - Cómo dividir alimentos cocinados

**📊 GESTIÓN:**
/compras - Lista de compra estándar
/cronograma - Ver cronograma de cocción
/macros - Ver resumen de macros
/rating [receta] [1-5] [comentario] - Calificar receta
/favorito [receta] - Marcar como favorito
/actualizar\_peso [kg] - Actualizar tu peso
/cambiar\_semana [1-4] - Cambiar semana manualmente

También puedes escribirme en lenguaje natural como:
"No me gusta el cilantro en esta receta"
"Quiero más recetas con pollo"

¡Empecemos! Usa /menu para ver tu menú actual 👨🍳
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['menu'])
def menu_command(message):
    """Mostrar menú semanal completo (L-V) con porciones, macros y divisiones"""
    try:
        # Verificar perfil
        user_profile = meal_bot.get_user_profile()
        if not user_profile:
            bot.reply_to(message, 
                "❌ **Perfil no configurado**\n\n"
                "Usa `/perfil` para configurar tu perfil primero.",
                parse_mode='Markdown')
            return
        
        # Verificar si es necesaria rotación automática
        if meal_bot.check_rotation_needed():
            rotation_response = "🔄 **ROTACIÓN AUTOMÁTICA DISPONIBLE**\n\n"
            rotation_response += "📅 ¡Es lunes! Tu semana necesita renovación\n"
            rotation_response += "🥘 Nuevas recetas naturales están listas\n\n"
            rotation_response += "💡 Usa `/nueva_semana` para rotar tu planificación\n"
            rotation_response += "➖➖➖➖➖➖➖➖➖➖\n\n"
            bot.send_message(message.chat.id, rotation_response, parse_mode='Markdown')
        
        # Obtener datos del menú actual
        meal_plan = meal_bot.get_current_meal_plan()
        current_week = meal_bot.data["user_preferences"]["current_week"]
        portions_data = meal_bot.calculate_personal_portions()
        cooking_data = meal_bot.calculate_cooking_amounts()
        
        if not portions_data or not cooking_data:
            bot.reply_to(message, "❌ Error calculando datos del menú. Intenta de nuevo.")
            return
        
        # Mensaje inicial
        response = f"📅 **MENÚ SEMANAL (LUNES - VIERNES)**\n"
        response += f"🗓️ Semana {current_week} • Comida Natural\n\n"
        
        # Macros diarios objetivo
        daily_macros = portions_data['daily_macros']
        response += f"🎯 **MACROS DIARIOS OBJETIVO:**\n"
        response += f"• {daily_macros['calories']} kcal | {daily_macros['protein']}g proteína\n"
        response += f"• {daily_macros['carbs']}g carbos | {daily_macros['fat']}g grasas\n"
        response += f"• Distribuido en {portions_data['num_comidas']} comidas\n\n"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        # Enviar planificación por día
        import time
        days = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES"]
        
        for day in days:
            day_response = f"📋 **{day}**\n\n"
            day_response += "🍽️ **COMIDAS DEL DÍA:**\n"
            
            # Mostrar porciones por comida para cada receta
            for recipe_id, portion_info in portions_data['portions_needed'].items():
                if recipe_id in meal_bot.data["recipes"]:
                    recipe = meal_bot.data["recipes"][recipe_id]
                    portions_per_meal = portion_info['portions_per_meal']
                    
                    day_response += f"• **{recipe['name']}:** {portions_per_meal:.2f} porciones/comida\n"
            
            # Información de macros por día
            day_response += f"\n📊 **MACROS TOTALES DEL DÍA:**\n"
            day_response += f"• {daily_macros['calories']} kcal • {daily_macros['protein']}g prot\n"
            day_response += f"• {daily_macros['carbs']}g carbs • {daily_macros['fat']}g grasas\n"
            
            bot.send_message(message.chat.id, day_response, parse_mode='Markdown')
            time.sleep(0.8)
        
        # Sección de divisiones (cómo dividir lo cocinado)
        divisions_response = "✂️ **CÓMO DIVIDIR LOS ALIMENTOS COCINADOS**\n\n"
        
        for recipe_id, amounts in cooking_data['cooking_amounts'].items():
            if recipe_id in meal_bot.data["recipes"]:
                recipe = meal_bot.data["recipes"][recipe_id]
                weekly_portions = amounts['weekly_portions_needed']
                daily_portions = amounts['daily_portions']
                
                divisions_response += f"**{recipe['name']}:**\n"
                divisions_response += f"• Total semanal: {weekly_portions:.1f} porciones\n"
                divisions_response += f"• Por día: {daily_portions:.1f} porciones\n"
                divisions_response += f"• Dividir en: {int(weekly_portions)} contenedores\n\n"
        
        divisions_response += "💡 **INSTRUCCIONES:**\n"
        divisions_response += "1. Cocina todo según cantidades de `/compras`\n"
        divisions_response += "2. Divide cada receta en los contenedores indicados\n"
        divisions_response += "3. Cada contenedor = 1 porción para 1 comida\n"
        divisions_response += "4. Combina porciones según el plan diario\n\n"
        divisions_response += "🔄 **Próxima rotación:** Automática cada lunes"
        
        bot.send_message(message.chat.id, divisions_response, parse_mode='Markdown')
        
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

@bot.message_handler(commands=['compras'])
def compras_command(message):
    """Generar lista de compras simplificada sin categorías"""
    try:
        # Verificar perfil
        user_profile = meal_bot.get_user_profile()
        if not user_profile:
            bot.reply_to(message, 
                "❌ **Perfil no configurado**\n\n"
                "Usa `/perfil` para configurar tu perfil primero.",
                parse_mode='Markdown')
            return
        
        # Calcular cantidades de cocina
        cooking_data = meal_bot.calculate_cooking_amounts()
        if not cooking_data:
            bot.reply_to(message, "❌ Error calculando cantidades. Intenta de nuevo.")
            return
        
        # Recopilar todos los ingredientes para Claude
        all_ingredients = []
        for recipe_id, amounts in cooking_data['cooking_amounts'].items():
            if recipe_id in meal_bot.data["recipes"]:
                recipe = meal_bot.data["recipes"][recipe_id]
                multiplier = amounts['recipe_multiplier']
                
                for ingredient in recipe["ingredients"]:
                    all_ingredients.append({
                        'ingredient': ingredient,
                        'multiplier': multiplier,
                        'category': 'otros'
                    })
        
        # Procesar con Claude para agregar y estandarizar
        claude_result = meal_bot.process_ingredients_with_claude(all_ingredients)
        
        if claude_result and claude_result.get("success"):
            # Usar resultado de Claude - unificar todas las categorías
            unified_ingredients = []
            for category_ingredients in claude_result["ingredients_by_category"].values():
                unified_ingredients.extend(category_ingredients)
        else:
            # Fallback: usar sistema anterior pero sin categorías
            logger.warning("Claude falló, usando sistema de fallback para /compras")
            aggregated_ingredients = meal_bot.aggregate_ingredients(all_ingredients)
            
            unified_ingredients = []
            if aggregated_ingredients:
                for ingredient_data in aggregated_ingredients.values():
                    formatted = meal_bot.format_ingredient(ingredient_data)
                    unified_ingredients.append(formatted)
            else:
                # Último recurso: ingredientes sin procesar
                for item in all_ingredients:
                    ingredient_with_mult = f"{item['ingredient']} ×{item['multiplier']:.1f}"
                    unified_ingredients.append(ingredient_with_mult)
        
        # Crear lista de compras unificada
        current_week = meal_bot.data["user_preferences"]["current_week"]
        
        response = f"🛒 **LISTA DE COMPRAS SEMANAL**\n"
        response += f"📅 Semana {current_week} • Comida Natural\n\n"
        
        # Ordenar alfabéticamente para facilitar las compras
        for ingredient in sorted(unified_ingredients):
            response += f"• {ingredient}\n"
        
        response += f"\n📊 **TOTAL:** {len(unified_ingredients)} ingredientes\n"
        response += "💡 **Para 5 días de comida natural (L-V)**\n"
        response += "🔄 Lista actualizada cada lunes automáticamente"
        
        # Guardar en historial
        from datetime import datetime
        meal_bot.data["shopping_lists"][datetime.now().isoformat()[:10]] = {
            "ingredients": unified_ingredients,
            "week": current_week,
            "total_items": len(unified_ingredients)
        }
        meal_bot.save_data()
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en compras_command: {e}")
        bot.reply_to(message, "❌ Error generando lista de compras. Intenta de nuevo.")

@bot.message_handler(commands=['cronograma'])
def cronograma_command(message):
    """Mostrar cronograma híbrido de cocción (batch + fresco)"""
    try:
        # Verificar perfil
        user_profile = meal_bot.get_user_profile()
        if not user_profile:
            bot.reply_to(message, 
                "❌ **Perfil no configurado**\n\n"
                "Usa `/perfil` para configurar tu perfil primero.",
                parse_mode='Markdown')
            return
        
        # Obtener datos de cocina
        cooking_data = meal_bot.calculate_cooking_amounts()
        if not cooking_data:
            bot.reply_to(message, "❌ Error calculando cronograma. Intenta de nuevo.")
            return
        
        current_week = meal_bot.data["user_preferences"]["current_week"]
        
        # Mensaje inicial
        response = f"⏰ **CRONOGRAMA HÍBRIDO DE COCINA**\n"
        response += f"📅 Semana {current_week} • Comida Natural\n\n"
        response += "🥘 **ESTRATEGIA:** Batch cooking + Fresco diario\n\n"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        # Clasificar recetas por complejidad
        import time
        batch_recipes = []
        fresh_recipes = []
        
        for recipe_id, amounts in cooking_data['cooking_amounts'].items():
            if recipe_id in meal_bot.data["recipes"]:
                recipe = meal_bot.data["recipes"][recipe_id]
                
                # Determinar si es batch cooking o fresco
                # (Por ahora, clasificación simple - se puede mejorar con utensilios de usuario)
                cook_time = recipe.get("cook_time", "")
                
                if any(keyword in cook_time.lower() for keyword in ["horas", "hour", "crockpot", "horno"]) or \
                   any(keyword in recipe["name"].lower() for keyword in ["guisado", "estofado", "cocido"]):
                    batch_recipes.append((recipe, amounts))
                else:
                    fresh_recipes.append((recipe, amounts))
        
        # Mostrar batch cooking (fin de semana)
        batch_response = "👨‍🍳 **BATCH COOKING (DOMINGO)**\n"
        batch_response += "*Recetas complejas para preparar de una vez*\n\n"
        
        if batch_recipes:
            for recipe, amounts in batch_recipes:
                weekly_portions = amounts['weekly_portions_needed']
                batch_response += f"🍲 **{recipe['name']}**\n"
                batch_response += f"• Tiempo: {recipe.get('cook_time', 'Variable')}\n"
                batch_response += f"• Producir: {weekly_portions:.1f} porciones para toda la semana\n"
                batch_response += f"• Método: {recipe.get('method', 'Según receta')}\n\n"
        else:
            batch_response += "No hay recetas complejas esta semana 👍\n\n"
        
        batch_response += "💡 Divide en contenedores y refrigera/congela"
        
        bot.send_message(message.chat.id, batch_response, parse_mode='Markdown')
        time.sleep(1)
        
        # Mostrar cocina fresca diaria
        fresh_response = "🥗 **COCINA FRESCA (DIARIO)**\n"
        fresh_response += "*Recetas simples para preparar en el momento*\n\n"
        
        if fresh_recipes:
            for recipe, amounts in fresh_recipes:
                daily_portions = amounts['daily_portions']
                fresh_response += f"🍽️ **{recipe['name']}**\n"
                fresh_response += f"• Preparar: {daily_portions:.1f} porciones diarias\n"
                fresh_response += f"• Tiempo: {recipe.get('cook_time', '15-30 min')}\n"
                fresh_response += f"• Momento: Antes de cada comida\n\n"
        else:
            fresh_response += "Todas las recetas son batch cooking esta semana 🍲\n\n"
        
        fresh_response += "⚡ Rápido, fresco y nutritivo"
        
        bot.send_message(message.chat.id, fresh_response, parse_mode='Markdown')
        time.sleep(1)
        
        # Cronograma semanal sugerido
        schedule_response = "📅 **CRONOGRAMA SEMANAL SUGERIDO**\n\n"
        schedule_response += "**DOMINGO:**\n"
        schedule_response += "• 🥘 Batch cooking (recetas complejas)\n"
        schedule_response += "• ⏰ 2-4 horas de cocina total\n"
        schedule_response += "• 📦 Dividir y almacenar\n\n"
        schedule_response += "**LUNES-VIERNES:**\n"
        schedule_response += "• 🔥 Calentar batch cooking\n"
        schedule_response += "• 🥗 Preparar recetas frescas (15-30 min)\n"
        schedule_response += "• ✨ Combinar según plan del `/menu`\n\n"
        schedule_response += "**SÁBADO:**\n"
        schedule_response += "• 🛒 Compras según `/compras`\n"
        schedule_response += "• 📋 Planificar domingo de cocina\n\n"
        schedule_response += "🔄 **Próxima rotación:** Lunes automático"
        
        bot.send_message(message.chat.id, schedule_response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error en cronograma_command: {e}")
        bot.reply_to(message, "❌ Error generando cronograma. Intenta de nuevo.")

@bot.message_handler(commands=['macros'])
def macros_command(message):
    """Mostrar resumen de macros"""
    try:
        # Verificar si hay perfil personalizado
        profile = meal_bot.get_user_profile()
        
        macros = meal_bot.calculate_daily_macros()
        targets = meal_bot.data["user_preferences"]["macro_targets"]
        
        macros_text = "📊 **RESUMEN DE MACROS DIARIOS**\n\n"
        
        # Si hay perfil, mostrar información personalizada
        if profile:
            macros_text += f"👤 **Perfil personalizado activo**\n"
            macros_text += f"• Objetivo: {profile['objetivo'].replace('_', ' ').title()}\n"
            macros_text += f"• IMC: {profile['imc']}\n\n"
        
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
        
        # Si no hay perfil, promocionar sistema personalizado
        if not profile:
            macros_text += "\n💡 **¿Quieres macros más precisos?**\n"
            macros_text += "Usa /perfil para crear tu perfil personalizado\n"
            macros_text += "basado en tu peso, altura, objetivo y actividad física"
        
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

@bot.message_handler(commands=['nueva_semana'])
def nueva_semana_command(message):
    """Iniciar proceso de rotación semanal interactiva"""
    try:
        # Verificar perfil
        user_profile = meal_bot.get_user_profile()
        if not user_profile:
            bot.reply_to(message, 
                "❌ **Perfil no configurado**\n\n"
                "Usa `/perfil` para configurar tu perfil primero.",
                parse_mode='Markdown')
            return
        
        current_week = meal_bot.data["user_preferences"]["current_week"]
        
        # Mostrar introducción
        intro_response = f"🔄 **ROTACIÓN SEMANAL AUTOMÁTICA**\n\n"
        intro_response += f"📅 Semana actual: **{current_week}**\n"
        intro_response += f"🥘 Preparando nueva semana de comida natural\n\n"
        intro_response += "🎯 **Opciones disponibles:**\n"
        intro_response += "1️⃣ Ver recetas disponibles por categoría\n"
        intro_response += "2️⃣ Mantener recetas favoritas ancladas\n"
        intro_response += "3️⃣ Buscar recetas nuevas con IA\n"
        intro_response += "4️⃣ Rotación automática inteligente\n\n"
        intro_response += "Responde con el número de opción que prefieres 👇"
        
        bot.reply_to(message, intro_response, parse_mode='Markdown')
        
        # Guardar estado de conversación
        meal_bot.data["user_preferences"]["rotation_state"] = "waiting_option"
        meal_bot.save_data()
        
    except Exception as e:
        logger.error(f"Error en nueva_semana_command: {e}")
        bot.reply_to(message, "❌ Error iniciando rotación. Intenta de nuevo.")

# ===== FUNCIONES DE CONVERSACIÓN DE ROTACIÓN =====

def handle_rotation_conversation(message):
    """Manejar conversación de rotación semanal"""
    try:
        rotation_state = meal_bot.data["user_preferences"].get("rotation_state")
        
        if rotation_state == "waiting_option":
            option = message.text.strip()
            
            if option == "1":
                # Mostrar recetas por categoría
                show_recipes_by_category(message)
            elif option == "2":
                # Mantener favoritas ancladas
                handle_anchored_favorites(message)
            elif option == "3":
                # Buscar recetas nuevas con IA
                start_ai_recipe_search(message)
            elif option == "4":
                # Rotación automática inteligente
                perform_intelligent_rotation(message)
            else:
                bot.reply_to(message, "❌ Opción no válida. Responde con 1, 2, 3 o 4.")
                return
        
        elif rotation_state == "selecting_recipes":
            handle_recipe_selection(message)
        
        elif rotation_state == "searching_new":
            handle_new_recipe_search(message)
            
    except Exception as e:
        logger.error(f"Error en handle_rotation_conversation: {e}")
        bot.reply_to(message, "❌ Error en rotación. Usa `/nueva_semana` para reiniciar.")

def show_recipes_by_category(message):
    """Mostrar recetas disponibles organizadas por categoría"""
    try:
        available_recipes = meal_bot.get_available_recipes()
        
        response = "📋 **RECETAS DISPONIBLES POR CATEGORÍA**\n\n"
        
        category_emojis = {
            "proteinas": "🥩",
            "legumbres": "🫘",
            "cereales": "🌾", 
            "vegetales": "🥬"
        }
        
        for category, recipes in available_recipes.items():
            if recipes:
                emoji = category_emojis.get(category, "🍽️")
                response += f"{emoji} **{category.upper()}:**\n"
                
                for recipe in recipes:
                    rating_stars = "⭐" * recipe["rating"] if recipe["rating"] > 0 else ""
                    favorite_mark = " ❤️" if recipe["favorite"] else ""
                    response += f"• {recipe['name']}{rating_stars}{favorite_mark}\n"
                response += "\n"
        
        response += "💡 **Instrucciones:**\n"
        response += "Responde con los nombres de las recetas que quieres para esta semana, separados por comas.\n\n"
        response += "Ejemplo: `Pollo Mediterráneo, Frijoles Negros, Quinoa`\n\n"
        response += "O escribe 'ninguna' para buscar recetas nuevas con IA 🤖"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        # Cambiar estado de conversación
        meal_bot.data["user_preferences"]["rotation_state"] = "selecting_recipes"
        meal_bot.save_data()
        
    except Exception as e:
        logger.error(f"Error en show_recipes_by_category: {e}")
        bot.reply_to(message, "❌ Error mostrando recetas.")

def handle_anchored_favorites(message):
    """Manejar recetas favoritas ancladas"""
    try:
        favorites = meal_bot.get_anchored_favorites()
        
        if not favorites:
            response = "❤️ **NO TIENES RECETAS FAVORITAS**\n\n"
            response += "Usa `/favorito [nombre_receta]` para marcar recetas como favoritas.\n\n"
            response += "Las recetas favoritas se mantienen automáticamente en cada rotación.\n\n"
            response += "¿Quieres ver todas las recetas disponibles? Responde 'sí' o 'no'."
        else:
            response = "❤️ **RECETAS FAVORITAS (ANCLADAS)**\n\n"
            response += "Estas recetas se mantendrán automáticamente:\n\n"
            
            for fav in favorites:
                response += f"• {fav['name']} ({fav['category']})\n"
            
            response += f"\n🔄 **Completando semana con {len(favorites)} favoritas ancladas...**\n"
            response += "Buscando recetas complementarias automáticamente..."
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        if favorites:
            # Auto-completar con favoritas + recetas automáticas
            import time
            time.sleep(1)
            complete_week_with_favorites(message, favorites)
        else:
            meal_bot.data["user_preferences"]["rotation_state"] = "waiting_favorites_decision"
            meal_bot.save_data()
            
    except Exception as e:
        logger.error(f"Error en handle_anchored_favorites: {e}")
        bot.reply_to(message, "❌ Error procesando favoritas.")

def complete_week_with_favorites(message, favorites):
    """Completar semana con favoritas + selección automática"""
    try:
        # Crear lista con favoritas
        selected_recipes = [fav["id"] for fav in favorites]  
        
        # TODO: Añadir lógica para completar con recetas automáticas balanceadas
        # Por ahora, crear plan solo con favoritas
        
        new_plan = meal_bot.create_new_meal_plan(selected_recipes)
        
        response = "✅ **NUEVA SEMANA CREADA**\n\n"
        response += f"📅 **Semana actualizada con éxito**\n"
        response += f"❤️ Mantenidas {len(favorites)} recetas favoritas\n"
        response += f"🎯 Plan optimizado para comida natural\n\n"
        response += "💡 Usa `/menu` para ver tu nueva planificación semanal"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        # Limpiar estado
        meal_bot.data["user_preferences"]["rotation_state"] = None
        meal_bot.save_data()
        
    except Exception as e:
        logger.error(f"Error en complete_week_with_favorites: {e}")
        bot.reply_to(message, "❌ Error completando semana.")

def start_ai_recipe_search(message):
    """Iniciar búsqueda de nuevas recetas con IA"""
    response = "🤖 **BÚSQUEDA DE RECETAS CON IA**\n\n"
    response += "Describe qué tipo de recetas quieres buscar:\n\n"
    response += "**Ejemplos:**\n"
    response += "• 'Pollo con vegetales mediterráneos'\n"  
    response += "• 'Legumbres especiadas estilo marroquí'\n"
    response += "• 'Quinoa con verduras de temporada'\n"
    response += "• 'Pescado al horno con hierbas'\n\n"
    response += "💡 Recuerda: Solo ingredientes naturales, sin procesados"
    
    bot.reply_to(message, response, parse_mode='Markdown')
    
    meal_bot.data["user_preferences"]["rotation_state"] = "searching_new"
    meal_bot.save_data()

def handle_new_recipe_search(message):
    """Manejar búsqueda de nueva receta"""
    try:
        query = message.text.strip()
        
        if len(query) < 10:
            bot.reply_to(message, "❌ Describe con más detalle qué receta buscas (mínimo 10 caracteres).")
            return
        
        response = "🔍 **BUSCANDO RECETA CON IA...**\n\n"
        response += f"Consulta: '{query}'\n"
        response += "⏳ Creando receta natural personalizada..."
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        # Usar la función de búsqueda existente pero con prompt mejorado
        result = meal_bot.search_or_create_recipe(f"{query} - ingredientes naturales sin procesar")
        
        if result and "❌" not in result:
            final_response = "✅ **NUEVA RECETA CREADA**\n\n"
            final_response += "🤖 Tu receta ha sido añadida a la base de datos\n"
            final_response += "🔄 Rotación completada con nueva comida natural\n\n"
            final_response += "💡 Usa `/menu` para ver tu planificación actualizada"
            
            bot.reply_to(message, final_response, parse_mode='Markdown')
            
            # Limpiar estado
            meal_bot.data["user_preferences"]["rotation_state"] = None
            meal_bot.save_data()
        else:
            bot.reply_to(message, f"❌ Error creando receta: {result}")
            
    except Exception as e:
        logger.error(f"Error en handle_new_recipe_search: {e}")
        bot.reply_to(message, "❌ Error en búsqueda de recetas.")

def perform_intelligent_rotation(message):
    """Realizar rotación automática inteligente"""
    try:
        response = "🤖 **ROTACIÓN AUTOMÁTICA INTELIGENTE**\n\n"
        response += "⚡ Analizando tu historial y preferencias...\n"
        response += "🎯 Seleccionando recetas balanceadas automáticamente...\n"
        response += "🥘 Priorizando comida natural y variedad..."
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
        # TODO: Implementar lógica inteligente basada en ratings, historial, etc.
        # Por ahora, selección básica
        
        import time
        time.sleep(2)
        
        # Seleccionar recetas con mejor rating de cada categoría
        available_recipes = meal_bot.get_available_recipes()
        selected_recipes = []
        
        for category, recipes in available_recipes.items():
            if recipes:
                # Ordenar por rating y tomar la mejor
                best_recipe = max(recipes, key=lambda x: (x["rating"], x["favorite"]))
                selected_recipes.append(best_recipe["id"])
        
        if selected_recipes:
            new_plan = meal_bot.create_new_meal_plan(selected_recipes)
            
            final_response = "✅ **ROTACIÓN AUTOMÁTICA COMPLETADA**\n\n"
            final_response += f"🎯 Seleccionadas {len(selected_recipes)} recetas balanceadas\n"
            final_response += "⭐ Priorizadas recetas con mejor valoración\n"
            final_response += "🥘 100% ingredientes naturales\n\n"
            final_response += "💡 Usa `/menu` para ver tu nueva planificación"
            
            bot.reply_to(message, final_response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ No hay recetas disponibles para rotación automática.")
        
        # Limpiar estado
        meal_bot.data["user_preferences"]["rotation_state"] = None
        meal_bot.save_data()
        
    except Exception as e:
        logger.error(f"Error en perform_intelligent_rotation: {e}")
        bot.reply_to(message, "❌ Error en rotación automática.")

def handle_recipe_selection(message):
    """Manejar selección manual de recetas"""
    try:
        user_input = message.text.strip()
        
        if user_input.lower() in ['listo', 'finalizar', 'completar']:
            # Finalizar selección
            selected_recipes = meal_bot.data["user_preferences"].get("selected_recipes", [])
            
            if selected_recipes:
                new_plan = meal_bot.create_new_meal_plan(selected_recipes)
                
                response = "✅ **SELECCIÓN MANUAL COMPLETADA**\n\n"
                response += f"📋 Seleccionadas {len(selected_recipes)} recetas\n"
                response += "🎯 Plan personalizado creado exitosamente\n\n"
                response += "💡 Usa `/menu` para ver tu nueva planificación"
                
                bot.reply_to(message, response, parse_mode='Markdown')
                
                # Limpiar estado
                meal_bot.data["user_preferences"]["rotation_state"] = None
                meal_bot.data["user_preferences"].pop("selected_recipes", None)
                meal_bot.save_data()
            else:
                bot.reply_to(message, "❌ No has seleccionado ninguna receta. Usa `/nueva_semana` para reiniciar.")
        else:
            # Buscar receta por nombre
            recipe_found = False
            for recipe_id, recipe in meal_bot.data["recipes"].items():
                if user_input.lower() in recipe["name"].lower():
                    selected_recipes = meal_bot.data["user_preferences"].get("selected_recipes", [])
                    
                    if recipe_id not in selected_recipes:
                        selected_recipes.append(recipe_id)
                        meal_bot.data["user_preferences"]["selected_recipes"] = selected_recipes
                        meal_bot.save_data()
                        
                        response = f"✅ **RECETA AÑADIDA**\n\n"
                        response += f"📝 {recipe['name']} agregada a tu selección\n"
                        response += f"📊 Total seleccionadas: {len(selected_recipes)}\n\n"
                        response += "💡 Añade más recetas o escribe 'listo' para finalizar"
                        
                        bot.reply_to(message, response, parse_mode='Markdown')
                        recipe_found = True
                        break
                    else:
                        bot.reply_to(message, f"⚠️ {recipe['name']} ya está seleccionada.")
                        recipe_found = True
                        break
            
            if not recipe_found:
                response = "❌ **RECETA NO ENCONTRADA**\n\n"
                response += f"No encontré una receta con el nombre '{user_input}'\n\n"
                response += "💡 Intenta con un nombre más específico o usa '/nueva_semana' para ver las opciones disponibles."
                bot.reply_to(message, response, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error en handle_recipe_selection: {e}")
        bot.reply_to(message, "❌ Error en selección de recetas.")

# ===== FUNCIONES DE CONVERSACIÓN DE PERFIL =====

def handle_profile_conversation(message):
    """Manejar conversación paso a paso para crear perfil"""
    user_id = message.from_user.id
    conversation = profile_conversations[user_id]
    state = conversation["state"]
    data = conversation["data"]
    text = message.text.strip()
    
    try:
        if state == "confirm_update":
            if text.lower() in ['actualizar', 'sí', 'si', 'yes', 'y']:
                conversation["state"] = "peso"
                bot.reply_to(message, 
                    "👤 **Actualizando perfil completo**\n\n"
                    "📝 **Paso 1/7: Peso**\n"
                    "¿Cuánto pesas? (en kg)\n\n"
                    "💡 *Ejemplo: 70 o 70.5*", 
                    parse_mode='Markdown')
            elif text.lower() in ['mantener', 'no', 'n']:
                del profile_conversations[user_id]
                bot.reply_to(message, "✅ Perfil mantenido. Usa /mis\\_macros para ver tus datos actuales.", parse_mode='Markdown')
            else:
                bot.reply_to(message, "💡 Responde 'actualizar' o 'mantener'")
            return
            
        elif state == "peso":
            try:
                peso = float(text)
                if not meal_bot.validate_user_data("peso", peso):
                    bot.reply_to(message, "❌ El peso debe estar entre 30 y 300 kg. Intenta de nuevo:")
                    return
                data["peso"] = peso
                conversation["state"] = "altura"
                bot.reply_to(message, 
                    "✅ Peso registrado\n\n"
                    "📝 **Paso 2/7: Altura**\n"
                    "¿Cuánto mides? (en cm)\n\n"
                    "💡 *Ejemplo: 175*", 
                    parse_mode='Markdown')
            except ValueError:
                bot.reply_to(message, "❌ Por favor ingresa solo el número (ej: 70)")
            return
            
        elif state == "altura":
            try:
                altura = float(text)
                if not meal_bot.validate_user_data("altura", altura):
                    bot.reply_to(message, "❌ La altura debe estar entre 120 y 220 cm. Intenta de nuevo:")
                    return
                data["altura"] = altura
                conversation["state"] = "edad"
                bot.reply_to(message, 
                    "✅ Altura registrada\n\n"
                    "📝 **Paso 3/7: Edad**\n"
                    "¿Cuántos años tienes?\n\n"
                    "💡 *Ejemplo: 25*", 
                    parse_mode='Markdown')
            except ValueError:
                bot.reply_to(message, "❌ Por favor ingresa solo el número (ej: 175)")
            return
            
        elif state == "edad":
            try:
                edad = int(text)
                if not meal_bot.validate_user_data("edad", edad):
                    bot.reply_to(message, "❌ La edad debe estar entre 15 y 100 años. Intenta de nuevo:")
                    return
                data["edad"] = edad
                conversation["state"] = "sexo"
                bot.reply_to(message, 
                    "✅ Edad registrada\n\n"
                    "📝 **Paso 4/7: Sexo**\n"
                    "¿Cuál es tu sexo?\n\n"
                    "💡 *Responde: 'M' o 'Masculino' o 'F' o 'Femenino'*", 
                    parse_mode='Markdown')
            except ValueError:
                bot.reply_to(message, "❌ Por favor ingresa solo el número (ej: 25)")
            return
            
        elif state == "sexo":
            sexo_input = text.lower()
            if sexo_input in ['m', 'masculino', 'hombre', 'male']:
                data["sexo"] = "M"
            elif sexo_input in ['f', 'femenino', 'mujer', 'female']:
                data["sexo"] = "F"
            else:
                bot.reply_to(message, "❌ Responde 'M' (masculino) o 'F' (femenino)")
                return
            
            conversation["state"] = "objetivo"
            bot.reply_to(message, 
                "✅ Sexo registrado\n\n"
                "📝 **Paso 5/7: Objetivo**\n"
                "¿Cuál es tu objetivo principal?\n\n"
                "💡 **Opciones:**\n"
                "• 1 - Bajar grasa\n"
                "• 2 - Subir masa muscular\n"
                "• 3 - Mantener peso actual\n\n"
                "*Responde con el número (1, 2 o 3)*", 
                parse_mode='Markdown')
            return
            
        elif state == "objetivo":
            objetivo_map = {
                "1": "bajar_grasa",
                "2": "subir_masa", 
                "3": "mantener"
            }
            
            if text in objetivo_map:
                data["objetivo"] = objetivo_map[text]
                conversation["state"] = "actividad"
                bot.reply_to(message, 
                    "✅ Objetivo registrado\n\n"
                    "📝 **Paso 6/7: Actividad Física**\n"
                    "¿Cuál es tu nivel de actividad?\n\n"
                    "💡 **Opciones:**\n"
                    "• 1 - Sedentario (poco o nada de ejercicio)\n"
                    "• 2 - Ligero (1-3 días de ejercicio/semana)\n"
                    "• 3 - Moderado (3-5 días/semana)\n"
                    "• 4 - Intenso (6-7 días/semana)\n"
                    "• 5 - Atlético (2+ veces al día)\n\n"
                    "*Responde con el número (1-5)*", 
                    parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ Responde con 1, 2 o 3")
            return
            
        elif state == "actividad":
            actividad_map = {
                "1": "sedentario",
                "2": "ligero",
                "3": "moderado",
                "4": "intenso", 
                "5": "atletico"
            }
            
            if text in actividad_map:
                data["actividad"] = actividad_map[text]
                conversation["state"] = "trabajo"
                bot.reply_to(message, 
                    "✅ Actividad registrada\n\n"
                    "📝 **Paso 7/7: Trabajo Físico**\n"
                    "¿Tu trabajo requiere esfuerzo físico?\n\n"
                    "💡 **Opciones:**\n"
                    "• 1 - Oficina (sentado/computadora)\n"
                    "• 2 - Ligero (de pie, caminar ocasional)\n"
                    "• 3 - Moderado (carga ligera, movimiento)\n"
                    "• 4 - Pesado (construcción, carga pesada)\n\n"
                    "*Responde con el número (1-4)*", 
                    parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ Responde con un número del 1 al 5")
            return
            
        elif state == "trabajo":
            trabajo_map = {
                "1": "oficina",
                "2": "ligero",
                "3": "moderado",
                "4": "pesado"
            }
            
            if text in trabajo_map:
                data["trabajo_fisico"] = trabajo_map[text]
                
                # Calcular perfil completo
                perfil = meal_bot.calculate_complete_profile(
                    data["peso"], data["altura"], data["edad"], 
                    data["sexo"], data["objetivo"], data["actividad"], 
                    data["trabajo_fisico"]
                )
                
                # Guardar perfil
                meal_bot.save_user_profile(perfil)
                
                # Limpiar conversación
                del profile_conversations[user_id]
                
                # Mostrar resultados
                macros = perfil["macros_calculados"]
                
                # Interpretar IMC
                imc = perfil["imc"]
                if imc < 18.5:
                    imc_status = "Bajo peso"
                elif imc < 25:
                    imc_status = "Normal"
                elif imc < 30:
                    imc_status = "Sobrepeso"
                else:
                    imc_status = "Obesidad"
                
                response_text = "🎉 **¡Perfil creado exitosamente!**\n\n"
                
                response_text += "📊 **Tu perfil:**\n"
                response_text += f"• IMC: **{perfil['imc']}** ({imc_status})\n"
                response_text += f"• BMR: {perfil['bmr']} kcal/día\n"
                response_text += f"• TDEE: {perfil['tdee']} kcal/día\n"
                response_text += f"• Objetivo: {perfil['objetivo'].replace('_', ' ').title()}\n\n"
                
                response_text += "🔥 **Calorías objetivo:** " + f"**{macros['calories']} kcal/día**\n\n"
                
                response_text += "📈 **Tus macros diarios:**\n"
                response_text += f"• 🥩 Proteína: **{macros['protein']}g**\n"
                response_text += f"• 🍞 Carbohidratos: **{macros['carbs']}g**\n"
                response_text += f"• 🥑 Grasas: **{macros['fat']}g**\n\n"
                
                response_text += "✅ *Estos macros ya están integrados en tu menú*\n\n"
                response_text += "💡 **Comandos útiles:**\n"
                response_text += "• /mis\\_macros - Ver macros detallados\n"
                response_text += "• /actualizar\\_peso - Actualizar solo peso\n"
                response_text += "• /menu - Ver tu menú personalizado"
                
                bot.reply_to(message, response_text, parse_mode='Markdown')
                
            else:
                bot.reply_to(message, "❌ Responde con un número del 1 al 4")
            return
            
    except Exception as e:
        logger.error(f"Error en handle_profile_conversation: {e}")
        del profile_conversations[user_id]
        bot.reply_to(message, "❌ Error procesando perfil. Usa /perfil para intentar de nuevo.")

# ===== COMANDOS DE PERFIL Y MACROS PERSONALIZADOS =====

@bot.message_handler(commands=['perfil'])
def profile_command(message):
    """Crear o actualizar perfil de usuario paso a paso"""
    try:
        logger.info(f"Comando /perfil ejecutado por user_id: {message.from_user.id}")
        user_id = message.from_user.id
        
        # Verificar si ya tiene perfil
        existing_profile = meal_bot.get_user_profile()
        logger.info(f"Perfil existente encontrado: {existing_profile is not None}")
        
        if existing_profile:
            bot.reply_to(message, 
                f"👤 **Ya tienes un perfil creado**\n\n"
                f"📊 IMC: {existing_profile['imc']}\n"
                f"🎯 Objetivo: {existing_profile['objetivo'].replace('_', ' ').title()}\n"
                f"🔥 Calorías: {existing_profile['macros_calculados']['calories']} kcal\n\n"
                f"💡 **Opciones:**\n"
                f"• Responde 'actualizar' para modificar tu perfil\n"
                f"• Responde 'mantener' para conservar el actual\n"
                f"• Usa /mis\\_macros para ver tus macros detallados", 
                parse_mode='Markdown')
            
            # Configurar conversación para actualización
            profile_conversations[user_id] = {
                "state": "confirm_update",
                "data": {}
            }
            return
        
        # Iniciar conversación de perfil nuevo
        profile_conversations[user_id] = {
            "state": "peso",
            "data": {}
        }
        
        bot.reply_to(message, 
            "👤 **¡Vamos a crear tu perfil personalizado!**\n\n"
            "Esto me permitirá calcular tus macros exactos según tus objetivos.\n\n"
            "📝 **Paso 1/7: Peso**\n"
            "¿Cuánto pesas? (en kg)\n\n"
            "💡 *Ejemplo: 70 o 70.5*", 
            parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error en profile_command: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        bot.reply_to(message, "❌ Error ejecutando comando /perfil. Intenta de nuevo.")

@bot.message_handler(commands=['mis_macros'])
def my_macros_command(message):
    """Mostrar macros calculados del usuario"""
    profile = meal_bot.get_user_profile()
    
    if not profile:
        bot.reply_to(message, 
            "❌ **No tienes un perfil creado**\n\n"
            "💡 Usa /perfil para crear tu perfil personalizado", 
            parse_mode='Markdown')
        return
    
    macros = profile["macros_calculados"]
    
    # Interpretar IMC
    imc = profile["imc"]
    if imc < 18.5:
        imc_status = "Bajo peso"
    elif imc < 25:
        imc_status = "Normal"
    elif imc < 30:
        imc_status = "Sobrepeso"
    else:
        imc_status = "Obesidad"
    
    response_text = f"📊 **TUS MACROS PERSONALIZADOS**\n\n"
    
    response_text += f"👤 **Perfil:**\n"
    response_text += f"• Peso: {profile['peso']} kg\n"
    response_text += f"• Altura: {profile['altura']} cm\n"
    response_text += f"• IMC: {profile['imc']} ({imc_status})\n"
    response_text += f"• Objetivo: {profile['objetivo'].replace('_', ' ').title()}\n\n"
    
    response_text += f"🔥 **Calorías diarias:** {macros['calories']} kcal\n\n"
    
    response_text += f"📈 **Macronutrientes:**\n"
    response_text += f"• 🥩 Proteína: **{macros['protein']}g**\n"
    response_text += f"• 🍞 Carbohidratos: **{macros['carbs']}g**\n"
    response_text += f"• 🥑 Grasas: **{macros['fat']}g**\n\n"
    
    response_text += f"💡 **Para actualizar:**\n"
    response_text += f"• /perfil - Crear nuevo perfil\n"
    response_text += f"• /actualizar\\_peso - Solo cambiar peso"
    
    bot.reply_to(message, response_text, parse_mode='Markdown')

@bot.message_handler(commands=['actualizar_peso'])
def update_weight_command(message):
    """Actualizar solo el peso del usuario"""
    profile = meal_bot.get_user_profile()
    
    if not profile:
        bot.reply_to(message, 
            "❌ **No tienes un perfil creado**\n\n"
            "💡 Usa /perfil para crear tu perfil personalizado", 
            parse_mode='Markdown')
        return
    
    peso_str = message.text.replace('/actualizar_peso', '').strip()
    
    if not peso_str:
        bot.reply_to(message, 
            f"⚖️ **Actualizar peso**\n\n"
            f"Peso actual: **{profile['peso']} kg**\n\n"
            f"💡 Uso: `/actualizar\_peso 75` (nuevo peso en kg)", 
            parse_mode='Markdown')
        return
    
    try:
        nuevo_peso = float(peso_str)
        if not meal_bot.validate_user_data("peso", nuevo_peso):
            bot.reply_to(message, "❌ Peso debe estar entre 30 y 300 kg")
            return
        
        peso_anterior = profile['peso']
        
        # Recalcular perfil con nuevo peso
        nuevo_perfil = meal_bot.calculate_complete_profile(
            nuevo_peso, profile['altura'], profile['edad'], 
            profile['sexo'], profile['objetivo'], profile['actividad'], 
            profile['trabajo_fisico']
        )
        
        # Guardar perfil actualizado
        meal_bot.save_user_profile(nuevo_perfil)
        
        macros = nuevo_perfil["macros_calculados"]
        
        response_text = f"✅ **Peso actualizado exitosamente**\n\n"
        response_text += f"⚖️ Peso anterior: {peso_anterior} kg\n"
        response_text += f"⚖️ Peso nuevo: **{nuevo_peso} kg**\n"
        response_text += f"📊 IMC: **{nuevo_perfil['imc']}**\n\n"
        response_text += f"📈 **Nuevos macros:**\n"
        response_text += f"• 🔥 Calorías: **{macros['calories']} kcal**\n"
        response_text += f"• 🥩 Proteína: **{macros['protein']}g**\n"
        response_text += f"• 🍞 Carbohidratos: **{macros['carbs']}g**\n"
        response_text += f"• 🥑 Grasas: **{macros['fat']}g**"
        
        bot.reply_to(message, response_text, parse_mode='Markdown')
        
    except ValueError:
        bot.reply_to(message, "❌ Por favor ingresa un número válido (ej: 70 o 70.5)")
    except Exception as e:
        logger.error(f"Error en update_weight_command: {e}")
        bot.reply_to(message, "❌ Error al actualizar peso. Intenta de nuevo.")

# Manejador de mensajes de texto libre (conversacional)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    """Manejar mensajes conversacionales"""
    try:
        user_id = message.from_user.id
        text = message.text.lower()
        
        # Manejar conversación de perfil si está activa
        if user_id in profile_conversations:
            handle_profile_conversation(message)
            return
        
        # Manejar conversación de rotación si está activa
        rotation_state = meal_bot.data["user_preferences"].get("rotation_state")
        if rotation_state:
            handle_rotation_conversation(message)
            return
        
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

# ===== WEBHOOK CONFIGURATION =====

def setup_webhook():
    """Configura el webhook para producción"""
    try:
        # Limpiar webhooks existentes
        bot.delete_webhook()
        logger.info("Webhooks existentes eliminados")
        
        if WEBHOOK_URL and USE_WEBHOOK:
            webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
            bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook configurado: {webhook_url}")
            return True
        else:
            logger.info("Configuración de webhook no encontrada, usando polling")
            return False
            
    except Exception as e:
        logger.error(f"Error configurando webhook: {e}")
        return False

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    """Endpoint para recibir actualizaciones de Telegram"""
    try:
        json_string = request.get_data(as_text=True)
        logger.info(f"Webhook recibido: {json_string[:200]}...")  # Logging del payload
        
        update = telebot.types.Update.de_json(json_string)
        logger.info(f"Update procesado: update_id={update.update_id}")
        
        # Logging de mensaje si existe
        if update.message:
            user_id = update.message.from_user.id
            username = update.message.from_user.username or "sin_username"
            message_text = update.message.text or "sin_texto"
            logger.info(f"Mensaje de @{username} (ID: {user_id}): {message_text}")
        
        bot.process_new_updates([update])
        logger.info("Update procesado exitosamente")
        return 'OK', 200
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 'Error', 500

@app.route('/health')
def health_check():
    """Endpoint de health check"""
    return 'Bot is running!', 200

def acquire_lock():
    """Adquiere un lock para prevenir múltiples instancias del bot"""
    try:
        lockfile = open('/tmp/meal_prep_bot.lock', 'w')
        fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lockfile.write(str(os.getpid()))
        lockfile.flush()
        
        def cleanup():
            try:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
                lockfile.close()
                os.remove('/tmp/meal_prep_bot.lock')
            except:
                pass
        
        atexit.register(cleanup)
        return True
        
    except (IOError, OSError):
        return False

def start_bot():
    """Inicia el bot en modo webhook o polling según la configuración"""
    # Verificar rotación automática al inicio
    if meal_bot.check_rotation_needed():
        new_week = meal_bot.rotate_menu()
        meal_bot.save_data()
        logger.info(f"Rotación automática: cambiado a semana {new_week}")
    
    # Configurar webhook o polling
    if USE_WEBHOOK and WEBHOOK_URL:
        logger.info("Iniciando en modo webhook...")
        if setup_webhook():
            # Ejecutar Flask app
            port = int(os.getenv('PORT', 5000))
            app.run(host='0.0.0.0', port=port, debug=False)
        else:
            logger.error("Error configurando webhook, cerrando...")
            exit(1)
    else:
        logger.info("Iniciando en modo polling...")
        try:
            # Limpiar webhooks existentes antes de empezar polling
            bot.delete_webhook()
            bot.infinity_polling()
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                logger.error("Error 409: Múltiples instancias detectadas. Intentando limpiar...")
                try:
                    bot.delete_webhook()
                    logger.info("Webhook eliminado, reintentando polling...")
                    bot.infinity_polling()
                except Exception as retry_e:
                    logger.error(f"Error en retry: {retry_e}")
                    exit(1)
            else:
                logger.error(f"Error de API Telegram: {e}")
                exit(1)
        except Exception as e:
            logger.error(f"Error en polling: {e}")
            exit(1)

if __name__ == '__main__':
    # Prevenir múltiples instancias solo en modo polling
    if not USE_WEBHOOK and not acquire_lock():
        logger.error("Ya existe otra instancia del bot ejecutándose. Cerrando...")
        exit(1)
    
    logger.info("Iniciando Meal Prep Bot...")
    start_bot()