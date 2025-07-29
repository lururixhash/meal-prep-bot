#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de formateo y display de menús para Telegram
Optimizado para mostrar estructura de timing nutricional
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

def format_menu_for_telegram(user_profile: Dict) -> str:
    """
    Formatear menú semanal personalizado para Telegram
    Integra timing nutricional, preferencias del usuario y complementos mediterráneos
    """
    try:
        # Datos del usuario
        basic_data = user_profile["basic_data"]
        macros = user_profile["macros"]
        energy_data = user_profile["energy_data"]
        preferences = user_profile.get("preferences", {})
        exercise_profile = user_profile.get("exercise_profile", {})
        
        # Formatear preferencias para mostrar
        liked_foods = preferences.get("liked_foods", [])
        disliked_foods = preferences.get("disliked_foods", [])
        
        # Encabezado del menú con preferencias
        menu_text = f"""
📅 **MENÚ SEMANAL PERSONALIZADO CON PREFERENCIAS**

👤 **Tu perfil:** {basic_data['objetivo_descripcion']}
🔥 **Calorías diarias:** {macros['calories']} kcal
⚡ **Available Energy:** {energy_data['available_energy']} kcal/kg FFM/día
🎯 **Estado:** {energy_data['ea_status']['color']} {energy_data['ea_status']['description']}
⏰ **Entrenamiento:** {exercise_profile.get('training_schedule_desc', 'Variable')}

🍽️ **Priorizando:** {', '.join([f.replace('_', ' ').title() for f in liked_foods[:3]]) if liked_foods else 'Sin preferencias específicas'}
🚫 **Evitando:** {', '.join([f.replace('_', ' ').title() for f in disliked_foods[:3]]) if disliked_foods else 'Sin restricciones'}

**ESTRUCTURA DE TIMING NUTRICIONAL:**

"""
        
        # Generar distribución diaria por timing
        daily_structure = generate_daily_timing_structure(user_profile)
        
        # Formatear cada comida del día
        for meal in ["desayuno", "almuerzo", "merienda", "cena"]:
            if meal not in daily_structure:
                continue
                
            details = daily_structure[meal]
            timing_type = details.get('timing_type', 'comida_principal')
            
            # Nombre de la comida con timing dinámico
            meal_name = format_timing_name(meal)
            
            # Agregar etiqueta de timing si es pre o post entreno
            if timing_type == "pre_entreno":
                menu_text += f"**{meal_name} & PRE-ENTRENO:**\n"
            elif timing_type == "post_entreno":
                menu_text += f"**{meal_name} & POST-ENTRENO:**\n"
            else:
                menu_text += f"**{meal_name}:**\n"
            
            # Descripción del timing
            menu_text += f"_{details['description']}_\n"
            
            # Macros objetivo para este timing
            target_macros = details['target_macros']
            menu_text += f"🎯 Target: {target_macros['calories']} kcal • "
            menu_text += f"{target_macros['protein']}P • {target_macros['carbs']}C • {target_macros['fat']}F\n"
            
            # Recetas recomendadas personalizadas
            recipes = apply_user_preferences_to_recipes(details.get('recipes', []), preferences)
            if recipes:
                # Determinar si son recetas del usuario o ejemplos
                has_user_recipes = any(recipe.get('source') in ['user_generated', 'user_temp'] for recipe in recipes)
                section_title = "🍽️ **Tus recetas personalizadas:**" if has_user_recipes else "🍽️ **Opciones recomendadas:**"
                menu_text += f"{section_title}\n"
                
                for recipe in recipes[:2]:  # Máximo 2 opciones por timing
                    preference_indicator = get_preference_indicator(recipe, preferences)
                    source_indicator = ""
                    if recipe.get('source') == 'user_generated':
                        source_indicator = "👨‍🍳 "  # Chef icon for user recipes
                    elif recipe.get('source') == 'user_temp':
                        source_indicator = "⏰ "  # Clock icon for temporary recipes
                    menu_text += f"  {preference_indicator} {source_indicator}{recipe['name']} ({recipe['calories']} kcal)\n"
            
            # Complementos mediterráneos personalizados
            complements = apply_user_preferences_to_complements(details.get('complements', []), preferences)
            if complements:
                menu_text += "🥜 **Complementos:**\n"
                for complement in complements[:3]:  # Máximo 3 complementos
                    preference_indicator = get_complement_preference_indicator(complement, preferences)
                    menu_text += f"  {preference_indicator} {complement['name']} {complement['portion']}\n"
            
            menu_text += "\n"
        
        # Resumen diario
        menu_text += generate_daily_summary(user_profile)
        
        # Recomendaciones personalizadas
        menu_text += generate_personalized_recommendations(user_profile)
        
        return menu_text
        
    except Exception as e:
        return f"❌ Error generating menu: {str(e)}"

def apply_user_preferences_to_recipes(recipes: List[Dict], preferences: Dict) -> List[Dict]:
    """Aplicar preferencias del usuario a las recetas recomendadas"""
    if not recipes or not preferences:
        return recipes
    
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    
    # Separar recetas en categorías por preferencias
    preferred_recipes = []
    neutral_recipes = []
    avoided_recipes = []
    
    for recipe in recipes:
        recipe_name_lower = recipe.get('name', '').lower()
        
        # Verificar si contiene alimentos preferidos
        has_liked = any(food.replace('_', ' ') in recipe_name_lower for food in liked_foods)
        has_disliked = any(food.replace('_', ' ') in recipe_name_lower for food in disliked_foods)
        
        if has_liked and not has_disliked:
            preferred_recipes.append(recipe)
        elif has_disliked:
            avoided_recipes.append(recipe)
        else:
            neutral_recipes.append(recipe)
    
    # Priorizar recetas preferidas, luego neutrales, luego evitadas
    return preferred_recipes + neutral_recipes + avoided_recipes

def apply_user_preferences_to_complements(complements: List[Dict], preferences: Dict) -> List[Dict]:
    """Aplicar preferencias del usuario a los complementos"""
    if not complements or not preferences:
        return complements
    
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    
    # Mapeo de complementos a categorías de alimentos
    complement_mapping = {
        "almendras": "frutos_secos", "nueces": "frutos_secos", "pistachos": "frutos_secos",
        "yogur": "lacteos", "queso": "lacteos", "feta": "lacteos",
        "aceitunas": "aceitunas", "aceite": "aceitunas"
    }
    
    preferred_complements = []
    neutral_complements = []
    avoided_complements = []
    
    for complement in complements:
        complement_name_lower = complement.get('name', '').lower()
        
        # Verificar mapeo de preferencias
        is_preferred = False
        is_disliked = False
        
        for word, food_category in complement_mapping.items():
            if word in complement_name_lower:
                if food_category in liked_foods:
                    is_preferred = True
                if food_category in disliked_foods:
                    is_disliked = True
                break
        
        if is_preferred and not is_disliked:
            preferred_complements.append(complement)
        elif is_disliked:
            avoided_complements.append(complement)
        else:
            neutral_complements.append(complement)
    
    return preferred_complements + neutral_complements + avoided_complements

def get_preference_indicator(recipe: Dict, preferences: Dict) -> str:
    """Obtener indicador visual de preferencia para receta"""
    if not preferences:
        return "•"
    
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    recipe_name_lower = recipe.get('name', '').lower()
    
    has_liked = any(food.replace('_', ' ') in recipe_name_lower for food in liked_foods)
    has_disliked = any(food.replace('_', ' ') in recipe_name_lower for food in disliked_foods)
    
    if has_liked and not has_disliked:
        return "✅"  # Preferida
    elif has_disliked:
        return "⚠️"  # A evitar
    else:
        return "•"   # Neutral

def get_complement_preference_indicator(complement: Dict, preferences: Dict) -> str:
    """Obtener indicador visual de preferencia para complemento"""
    if not preferences:
        return "•"
    
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    complement_name_lower = complement.get('name', '').lower()
    
    # Mapeo específico para complementos
    complement_mapping = {
        "almendras": "frutos_secos", "nueces": "frutos_secos", "pistachos": "frutos_secos",
        "yogur": "lacteos", "queso": "lacteos", "feta": "lacteos",
        "aceitunas": "aceitunas", "aceite": "aceitunas"
    }
    
    for word, food_category in complement_mapping.items():
        if word in complement_name_lower:
            if food_category in liked_foods:
                return "✅"  # Preferido
            elif food_category in disliked_foods:
                return "⚠️"  # A evitar
            break
    
    return "•"  # Neutral

def generate_daily_timing_structure(user_profile: Dict) -> Dict:
    """
    Generar estructura de timing diario personalizada basada en el horario de entrenamiento
    """
    objective = user_profile["basic_data"]["objetivo"]
    daily_calories = user_profile["macros"]["calories"]
    
    # Obtener el timing dinámico del perfil del usuario
    exercise_profile = user_profile.get("exercise_profile", {})
    dynamic_meal_timing = exercise_profile.get("dynamic_meal_timing", {
        "desayuno": "comida_principal",
        "almuerzo": "comida_principal", 
        "merienda": "snack_complemento",
        "cena": "comida_principal"
    })
    training_schedule = exercise_profile.get("training_schedule", "variable")
    
    # Distribución de calorías equilibrada para 4 comidas
    calorie_distributions = {
        "bajar_peso": {
            "desayuno": 0.25,    # 25%
            "almuerzo": 0.35,    # 35% - Mayor comida
            "merienda": 0.15,    # 15% - Snack
            "cena": 0.25         # 25%
        },
        "subir_masa": {
            "desayuno": 0.25,
            "almuerzo": 0.30,
            "merienda": 0.15,
            "cena": 0.30
        },
        "recomposicion": {
            "desayuno": 0.25,
            "almuerzo": 0.35,
            "merienda": 0.15,
            "cena": 0.25
        },
        "mantener": {
            "desayuno": 0.25,
            "almuerzo": 0.30,
            "merienda": 0.15,
            "cena": 0.30
        }
    }
    
    distribution = calorie_distributions.get(objective, calorie_distributions["mantener"])
    
    # Obtener horarios según entrenamiento
    timing_hours = get_timing_hours_by_schedule(training_schedule)
    
    # Estructura dinámica de timing
    timing_structure = {}
    
    for meal in ["desayuno", "almuerzo", "merienda", "cena"]:
        timing_type = dynamic_meal_timing.get(meal, "comida_principal")
        
        timing_structure[meal] = {
            "description": get_meal_description(meal, timing_type, timing_hours[meal]),
            "target_macros": calculate_timing_macros(
                daily_calories * distribution[meal],
                timing_type
            ),
            "recipes": get_user_timing_recipes(user_profile, meal, timing_type),
            "complements": get_timing_complements(meal),
            "timing_type": timing_type
        }
    
    return timing_structure

def calculate_timing_macros(target_calories: float, timing_type: str) -> Dict:
    """
    Calcular distribución de macros para un timing específico
    """
    # Distribuciones por timing
    macro_ratios = {
        "pre_entreno": {"protein": 0.15, "carbs": 0.70, "fat": 0.15},
        "post_entreno": {"protein": 0.35, "carbs": 0.45, "fat": 0.20},
        "desayuno": {"protein": 0.20, "carbs": 0.50, "fat": 0.30},
        "almuerzo": {"protein": 0.25, "carbs": 0.45, "fat": 0.30},
        "merienda": {"protein": 0.20, "carbs": 0.40, "fat": 0.40},
        "cena": {"protein": 0.30, "carbs": 0.35, "fat": 0.35}
    }
    
    ratios = macro_ratios.get(timing_type, macro_ratios["almuerzo"])
    
    return {
        "calories": int(target_calories),
        "protein": int((target_calories * ratios["protein"]) / 4),
        "carbs": int((target_calories * ratios["carbs"]) / 4),
        "fat": int((target_calories * ratios["fat"]) / 9)
    }

def get_user_timing_recipes(user_profile: Dict, meal_category: str, timing_type: str) -> List[Dict]:
    """
    Obtener recetas reales del usuario para cada timing, con fallback a ejemplos
    """
    user_recipes = []
    
    # Obtener recetas recientes del usuario
    recent_recipes = user_profile.get("recent_generated_recipes", [])
    for recipe_data in recent_recipes:
        recipe = recipe_data.get("recipe", {})
        recipe_timing = recipe.get("categoria_timing", "comida_principal")
        
        # Mapear timing a categorías
        matches_timing = False
        if meal_category == "desayuno" and recipe_timing in ["desayuno", "pre_entreno"]:
            matches_timing = True
        elif meal_category == "almuerzo" and recipe_timing in ["almuerzo", "comida_principal", "post_entreno"]:
            matches_timing = True
        elif meal_category == "merienda" and recipe_timing in ["merienda", "snack_complemento"]:
            matches_timing = True
        elif meal_category == "cena" and recipe_timing in ["cena", "comida_principal"]:
            matches_timing = True
        
        if matches_timing:
            user_recipes.append({
                "name": recipe.get("nombre", "Receta sin nombre"),
                "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                "source": "user_generated"
            })
    
    # Obtener de opciones temporales también
    temp_options = user_profile.get("temp_recipe_options", {})
    if meal_category in temp_options:
        options = temp_options[meal_category].get("options", [])
        for option in options:
            recipe = option.get("recipe", {})
            user_recipes.append({
                "name": recipe.get("nombre", "Receta temporal"),
                "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                "source": "user_temp"
            })
    
    # Si hay recetas del usuario, devolverlas (máximo 3)
    if user_recipes:
        return user_recipes[:3]
    
    # Fallback a ejemplos si no hay recetas del usuario
    return get_timing_recipes_fallback(timing_type)

def get_timing_recipes_fallback(timing_type: str) -> List[Dict]:
    """
    Obtener recetas ejemplo para cada timing (fallback)
    """
    recipe_examples = {
        "pre_entreno": [
            {"name": "Tostada integral con miel y plátano", "calories": 280},
            {"name": "Smoothie de frutas con avena", "calories": 320}
        ],
        "post_entreno": [
            {"name": "Pollo con quinoa y verduras", "calories": 520},
            {"name": "Salmón con arroz integral", "calories": 480}
        ],
        "desayuno": [
            {"name": "Tortilla de vegetales mediterránea", "calories": 380},
            {"name": "Yogur griego con frutos secos", "calories": 350}
        ],
        "almuerzo": [
            {"name": "Ternera mediterránea con legumbres", "calories": 580},
            {"name": "Lubina al horno con vegetales", "calories": 450}
        ],
        "merienda": [
            {"name": "Hummus con vegetales", "calories": 220},
            {"name": "Frutos secos mixtos", "calories": 240}
        ],
        "cena": [
            {"name": "Salmón a la plancha con espárragos", "calories": 360},
            {"name": "Ensalada griega con queso feta", "calories": 340}
        ],
        "comida_principal": [
            {"name": "Pollo mediterráneo con verduras", "calories": 450},
            {"name": "Pescado al horno con quinoa", "calories": 420}
        ],
        "snack_complemento": [
            {"name": "Yogur con frutos secos", "calories": 200},
            {"name": "Hummus con vegetales", "calories": 180}
        ]
    }
    
    return recipe_examples.get(timing_type, [])

def get_timing_complements(meal_time: str) -> List[Dict]:
    """
    Obtener complementos mediterráneos para cada momento
    """
    complements_by_time = {
        "desayuno": [
            {"name": "Almendras crudas", "portion": "20g"},
            {"name": "Miel cruda", "portion": "15g"}
        ],
        "almuerzo": [
            {"name": "Yogur griego natural", "portion": "150g"},
            {"name": "Nueces", "portion": "15g"}
        ],
        "merienda": [
            {"name": "Pistachos", "portion": "25g"},
            {"name": "Higos secos", "portion": "2 unidades"}
        ],
        "cena": [
            {"name": "Aceitunas kalamata", "portion": "20g"},
            {"name": "Queso feta", "portion": "30g"}
        ],
        "snacks": [
            {"name": "Aceite oliva virgen extra", "portion": "10ml"},
            {"name": "Frutos secos mixtos", "portion": "20g"}
        ]
    }
    
    return complements_by_time.get(meal_time, [])

def get_timing_hours_by_schedule(training_schedule: str) -> Dict[str, str]:
    """
    Obtener horarios recomendados para cada comida según horario de entrenamiento
    """
    schedule_hours = {
        "mañana": {  # Entrenamiento 6:00-12:00
            "desayuno": "6:30-8:00",
            "almuerzo": "12:30-14:00", 
            "merienda": "16:00-17:00",
            "cena": "20:00-21:30"
        },
        "mediodia": {  # Entrenamiento 12:00-16:00
            "desayuno": "7:00-8:30",
            "almuerzo": "11:30-12:00",
            "merienda": "16:30-17:30",
            "cena": "20:00-21:30"
        },
        "tarde": {  # Entrenamiento 16:00-20:00
            "desayuno": "7:00-8:30",
            "almuerzo": "12:00-14:00", 
            "merienda": "15:30-16:00",
            "cena": "20:30-22:00"
        },
        "noche": {  # Entrenamiento 20:00-24:00
            "desayuno": "7:00-8:30",
            "almuerzo": "12:00-14:00",
            "merienda": "16:00-17:00",
            "cena": "19:30-20:00"
        },
        "variable": {  # Horario variable
            "desayuno": "7:00-9:00",
            "almuerzo": "12:00-14:00",
            "merienda": "16:00-17:00",
            "cena": "20:00-21:30"
        }
    }
    
    return schedule_hours.get(training_schedule, schedule_hours["variable"])

def get_meal_description(meal: str, timing_type: str, hour_range: str) -> str:
    """
    Generar descripción de comida según su función nutricional
    """
    timing_descriptions = {
        "pre_entreno": "Energía rápida pre-entreno",
        "post_entreno": "Recuperación post-entreno",
        "comida_principal": "Comida balanceada",
        "snack_complemento": "Snack complemento"
    }
    
    base_description = timing_descriptions.get(timing_type, "Comida balanceada")
    return f"{base_description} ({hour_range})"

def format_timing_name(timing_key: str) -> str:
    """
    Formatear nombres de timing para display dinámico
    """
    meal_icons = {
        "desayuno": "🌅",
        "almuerzo": "🍽️", 
        "merienda": "🥜",
        "cena": "🌙"
    }
    
    meal_names = {
        "desayuno": "DESAYUNO",
        "almuerzo": "ALMUERZO",
        "merienda": "MERIENDA", 
        "cena": "CENA"
    }
    
    # Si es una de las 4 comidas principales, usar formato dinámico
    if timing_key in meal_icons:
        return f"{meal_icons[timing_key]} {meal_names[timing_key]}"
    
    # Fallback para nombres antiguos
    timing_names = {
        "desayuno_pre": "🌅 DESAYUNO & PRE-ENTRENO",
        "almuerzo_post": "🍽️ ALMUERZO & POST-ENTRENO", 
        "cena_principal": "🌙 CENA PRINCIPAL",
        "complementos": "🥜 COMPLEMENTOS MEDITERRÁNEOS"
    }
    
    return timing_names.get(timing_key, timing_key.upper())

def generate_daily_summary(user_profile: Dict) -> str:
    """
    Generar resumen diario del menú
    """
    macros = user_profile["macros"]
    energy_data = user_profile["energy_data"]
    
    summary = f"""
📊 **RESUMEN DIARIO COMPLETO:**

🎯 **Macros objetivo totales:**
• {macros['calories']} kcal diarias
• {macros['protein_g']}g proteína ({int(macros['protein_g']*4)} kcal)
• {macros['carbs_g']}g carbohidratos ({int(macros['carbs_g']*4)} kcal)
• {macros['fat_g']}g grasas ({int(macros['fat_g']*9)} kcal)

⚡ **Análisis energético:**
• Available Energy: {energy_data['available_energy']} kcal/kg FFM/día
• TDEE: {energy_data['tdee']} kcal
• Ejercicio diario: {energy_data['daily_exercise_calories']} kcal
• Estado: {energy_data['ea_status']['description']}

"""
    
    return summary

def generate_personalized_recommendations(user_profile: Dict) -> str:
    """
    Generar recomendaciones personalizadas basadas en objetivo y preferencias
    """
    objective = user_profile["basic_data"]["objetivo"]
    ea_status = user_profile["energy_data"]["ea_status"]["status"]
    preferences = user_profile.get("preferences", {})
    exercise_profile = user_profile.get("exercise_profile", {})
    
    liked_foods = preferences.get("liked_foods", [])
    disliked_foods = preferences.get("disliked_foods", [])
    cooking_methods = preferences.get("cooking_methods", [])
    
    recommendations = f"""
💡 **RECOMENDACIONES PERSONALIZADAS:**

**Para tu objetivo ({user_profile['basic_data']['objetivo_descripcion']}):**
"""
    
    # Recomendaciones por objetivo
    objective_recommendations = {
        "bajar_peso": [
            "• Prioriza proteína en cada comida para preservar masa muscular",
            "• Consume carbohidratos principalmente pre/post entreno",
            "• Incluye grasas saludables para saciedad y hormonas"
        ],
        "subir_masa": [
            "• Asegura surplus calórico constante con alimentos densos",
            "• Maximiza ventana anabólica post-entreno",
            "• Distribuye proteína uniformemente durante el día"
        ],
        "recomposicion": [
            "• Timing nutricional preciso para maximizar partición",
            "• Carbohidratos estratégicos alrededor del entrenamiento",
            "• Mantén Available Energy en zona óptima"
        ],
        "mantener": [
            "• Equilibrio perfecto entre todos los macronutrientes",
            "• Enfoque en calidad y variedad de alimentos",
            "• Mantén rutinas consistentes"
        ]
    }
    
    for rec in objective_recommendations.get(objective, []):
        recommendations += f"{rec}\n"
    
    # Recomendaciones por Available Energy
    recommendations += "\n**Por tu Available Energy:**\n"
    ea_recommendation = user_profile["energy_data"]["ea_status"]["recommendation"]
    recommendations += f"• {ea_recommendation}\n"
    
    # Recomendaciones basadas en preferencias
    if liked_foods or disliked_foods or cooking_methods:
        recommendations += "\n**Adaptado a tus preferencias:**\n"
        
        # Recomendaciones por alimentos preferidos
        if liked_foods:
            food_recommendations = {
                "carnes_rojas": "• Incluye carnes rojas magras 2-3x/semana para hierro",
                "aves": "• Pechuga de pollo como base proteica versátil",
                "pescados": "• Incorpora pescado azul 2x/semana para omega-3",
                "huevos": "• Huevos como fuente proteica completa y económica",
                "lacteos": "• Yogur griego natural como snack post-entreno",
                "frutos_secos": "• Frutos secos para grasas saludables entre comidas",
                "legumbres": "• Legumbres como carbohidratos complejos y proteína vegetal",
                "cruciferas": "• Verduras crucíferas para micronutrientes y fibra",
                "aceitunas": "• Aceitunas y aceite de oliva como grasa principal"
            }
            
            for food in liked_foods[:3]:  # Máximo 3 recomendaciones
                if food in food_recommendations:
                    recommendations += f"{food_recommendations[food]}\n"
        
        # Avisos sobre alimentos a evitar
        if disliked_foods:
            recommendations += f"• Evitando: {', '.join([f.replace('_', ' ').title() for f in disliked_foods[:2]])} - menú adaptado\n"
        
        # Recomendaciones por métodos de cocción
        if cooking_methods:
            method_recommendations = {
                "horno": "• Horno: ideal para meal prep masivo y cocción uniforme",
                "sarten": "• Sartén: perfecto para proteínas rápidas y salteados",
                "plancha": "• Plancha: mantiene sabor natural y reduce grasas",
                "vapor": "• Vapor: preserva máximo los nutrientes de vegetales",
                "crudo": "• Crudo: maximiza enzimas y vitaminas termolábiles"
            }
            
            for method in cooking_methods[:2]:  # Máximo 2 recomendaciones
                if method in method_recommendations:
                    recommendations += f"{method_recommendations[method]}\n"
    
    # Recomendaciones por horario de entrenamiento
    training_schedule = exercise_profile.get("training_schedule", "variable")
    if training_schedule != "variable":
        recommendations += f"\n**Para tu horario de entrenamiento ({exercise_profile.get('training_schedule_desc', '')}):**\n"
        
        schedule_tips = {
            "mañana": "• Desayuno ligero pre-entreno, almuerzo abundante post-entreno",
            "mediodia": "• Almuerzo ligero pre-entreno, merienda sustanciosa post-entreno",
            "tarde": "• Merienda energética pre-entreno, cena recuperativa post-entreno",
            "noche": "• Cena ligera pre-entreno, snack post-entreno sin exceso"
        }
        
        if training_schedule in schedule_tips:
            recommendations += f"{schedule_tips[training_schedule]}\n"
    
    # Comandos disponibles
    # Verificar si el usuario tiene recetas generadas
    has_user_recipes = False
    recent_recipes = user_profile.get("recent_generated_recipes", [])
    temp_options = user_profile.get("temp_recipe_options", {})
    if recent_recipes or temp_options:
        has_user_recipes = True
    
    recipe_generation_tip = ""
    if not has_user_recipes:
        recipe_generation_tip = """
⚠️ **IMPORTANTE:** Actualmente se muestran recetas de ejemplo.
Para ver TUS recetas personalizadas en el menú:
• Usa `/generar desayuno`, `/generar almuerzo`, etc.
• O genera opciones múltiples con `/generar`

"""
    
    recommendations += f"""

🤖 **PRÓXIMOS PASOS:**
• `/generar [timing]` - Crear recetas específicas por momento del día
• `/buscar [plato]` - Encontrar recetas con IA
• `/complementos` - Ver complementos personalizados
• `/editar_perfil` - Modificar tus preferencias
• `/configurar_menu` - Configurar rotación semanal
{recipe_generation_tip}
✅ **PERSONALIZACIÓN ACTIVA:**
• Menú adaptado a tus preferencias alimentarias
• Timing optimizado para tu horario de entrenamiento
• Recomendaciones específicas para tu objetivo
• Complementos filtrados según lo que te gusta/evitas

**Tu menú se adapta automáticamente conforme generas más recetas.**
"""
    
    return recommendations

def format_shopping_list(user_profile: Dict) -> str:
    """
    Formatear lista de compras semanal
    """
    shopping_text = f"""
🛒 **LISTA DE COMPRAS SEMANAL**

👤 **Optimizada para:** {user_profile['basic_data']['objetivo_descripcion']}
🔥 **Calorías diarias:** {user_profile['macros']['calories']} kcal

**PROTEÍNAS PRINCIPALES:**
• Pechuga de pollo: 1.5 kg
• Salmón fresco: 600g
• Huevos frescos: 2 docenas
• Yogur griego natural: 1 kg

**CARBOHIDRATOS COMPLEJOS:**
• Quinoa: 400g
• Arroz integral: 800g
• Avena integral: 500g
• Pan integral: 2 barras

**VERDURAS Y VEGETALES:**
• Brócoli: 800g
• Espinacas frescas: 400g
• Tomates: 1 kg
• Pimientos mixtos: 600g

🥜 **COMPLEMENTOS MEDITERRÁNEOS:**
• Almendras crudas: 200g
• Nueces: 150g
• Aceitunas kalamata: 200g
• Queso feta: 250g
• Miel cruda: 1 bote
• Aceite oliva virgen extra: 500ml

**HIERBAS Y ESPECIAS:**
• Orégano seco
• Tomillo fresco
• Ajo fresco: 2 cabezas
• Jengibre: 1 raíz

💡 **Esta lista cubre 5 días de meal prep según tu perfil nutricional.**
"""
    
    return shopping_text

def format_cooking_schedule(user_profile: Dict) -> str:
    """
    Formatear cronograma de cocción
    """
    cooking_text = f"""
⏰ **CRONOGRAMA DE MEAL PREP**

🎯 **Optimizado para:** {user_profile['basic_data']['objetivo_descripcion']}
📅 **Modalidad:** Dos sesiones semanales

**SESIÓN 1 - DOMINGO (10:00-13:00)**
⏱️ **Duración:** 3 horas
📋 **Tareas:**
• Cocinar proteínas principales (pollo, salmón)
• Preparar quinoa y arroz integral
• Lavar y cortar todas las verduras
• Preparar complementos mediterráneos en porciones

**SESIÓN 2 - MIÉRCOLES (19:00-21:00)**
⏱️ **Duración:** 2 horas
📋 **Tareas:**
• Reabastecer verduras frescas
• Preparar recetas de media semana
• Revisar y reorganizar contenedores
• Preparar complementos restantes

**DISTRIBUCIÓN SEMANAL:**
📦 **Lunes-Martes:** Comidas de sesión domingo
📦 **Miércoles-Jueves:** Comidas frescas de sesión miércoles
📦 **Viernes:** Combinación optimizada

💡 **Ventajas de este cronograma:**
• Comidas siempre frescas (máximo 3 días)
• Carga de trabajo distribuida
• Flexibilidad para ajustes mid-week
• Óptimo para tu Available Energy
"""
    
    return cooking_text

# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo de perfil de usuario
    sample_profile = {
        "basic_data": {
            "objetivo": "subir_masa",
            "objetivo_descripcion": "Ganar músculo minimizando grasa"
        },
        "macros": {
            "calories": 2800,
            "protein_g": 180,
            "carbs_g": 300,
            "fat_g": 100
        },
        "energy_data": {
            "available_energy": 52.5,
            "tdee": 2600,
            "daily_exercise_calories": 450,
            "ea_status": {
                "status": "optimal",
                "color": "🟢",
                "description": "Óptima para rendimiento y salud",
                "recommendation": "Mantén este nivel para máximo rendimiento"
            }
        }
    }
    
    # Generar menú formateado
    menu_formatted = format_menu_for_telegram(sample_profile)
    print(menu_formatted)