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
    Integra timing nutricional y complementos mediterráneos
    """
    try:
        # Datos del usuario
        basic_data = user_profile["basic_data"]
        macros = user_profile["macros"]
        energy_data = user_profile["energy_data"]
        
        # Encabezado del menú
        menu_text = f"""
📅 **MENÚ SEMANAL PERSONALIZADO**

👤 **Tu perfil:** {basic_data['objetivo_descripcion']}
🔥 **Calorías diarias:** {macros['calories']} kcal
⚡ **Available Energy:** {energy_data['available_energy']} kcal/kg FFM/día
🎯 **Estado:** {energy_data['ea_status']['color']} {energy_data['ea_status']['description']}

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
            
            # Recetas recomendadas
            recipes = details.get('recipes', [])
            if recipes:
                menu_text += "🍽️ **Opciones:**\n"
                for recipe in recipes[:2]:  # Máximo 2 opciones por timing
                    menu_text += f"  • {recipe['name']} ({recipe['calories']} kcal)\n"
            
            # Complementos mediterráneos
            complements = details.get('complements', [])
            if complements:
                menu_text += "🥜 **Complementos:**\n"
                for complement in complements:
                    menu_text += f"  • {complement['name']} {complement['portion']}\n"
            
            menu_text += "\n"
        
        # Resumen diario
        menu_text += generate_daily_summary(user_profile)
        
        # Recomendaciones personalizadas
        menu_text += generate_personalized_recommendations(user_profile)
        
        return menu_text
        
    except Exception as e:
        return f"❌ Error generating menu: {str(e)}"

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
            "recipes": get_timing_recipes(timing_type),
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
        "comida_principal": {"protein": 0.25, "carbs": 0.45, "fat": 0.30},
        "snack_complemento": {"protein": 0.20, "carbs": 0.40, "fat": 0.40}
    }
    
    ratios = macro_ratios.get(timing_type, macro_ratios["comida_principal"])
    
    return {
        "calories": int(target_calories),
        "protein": int((target_calories * ratios["protein"]) / 4),
        "carbs": int((target_calories * ratios["carbs"]) / 4),
        "fat": int((target_calories * ratios["fat"]) / 9)
    }

def get_timing_recipes(timing_type: str) -> List[Dict]:
    """
    Obtener recetas ejemplo para cada timing
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
        "comida_principal": [
            {"name": "Ternera mediterránea con legumbres", "calories": 580},
            {"name": "Lubina al horno con vegetales", "calories": 450}
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
    Generar recomendaciones personalizadas
    """
    objective = user_profile["basic_data"]["objetivo"]
    ea_status = user_profile["energy_data"]["ea_status"]["status"]
    
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
    
    # Comandos disponibles
    recommendations += f"""

🤖 **PRÓXIMOS PASOS:**
• `/generar` - Crear recetas específicas por timing
• `/buscar [plato]` - Encontrar recetas con IA
• `/complementos` - Ver todos los complementos mediterráneos
• `/nueva_semana` - Configurar rotación semanal

**Tu menú se adapta automáticamente a tu progreso y feedback.**
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