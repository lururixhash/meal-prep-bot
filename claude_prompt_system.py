#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema avanzado de prompts para Claude API
Genera prompts estructurados para obtener recetas válidas y consistentes
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class ClaudePromptSystem:
    
    def __init__(self):
        # Plantillas de prompts base
        self.base_prompts = {
            "recipe_generation": self._get_recipe_generation_template(),
            "recipe_adaptation": self._get_recipe_adaptation_template(),
            "menu_creation": self._get_menu_creation_template(),
            "ingredient_validation": self._get_ingredient_validation_template()
        }
        
        # Criterios de validación nutricional
        self.validation_criteria = {
            "ingredients": {
                "natural_only": True,
                "forbidden_processed": [
                    "embutidos", "salchichas", "jamón procesado",
                    "quesos procesados", "salsas comerciales",
                    "aderezos industriales", "condimentos artificiales",
                    "conservantes", "colorantes", "saborizantes"
                ],
                "preferred_categories": [
                    "carnes_frescas", "pescados_frescos", "huevos",
                    "legumbres_secas", "cereales_integrales", "quinoa",
                    "verduras_frescas", "frutas_frescas", "frutos_secos",
                    "aceites_prensado_frio", "hierbas_frescas", "especias_naturales"
                ]
            },
            "macros": {
                "protein_min_percent": 15,
                "protein_max_percent": 35,
                "carbs_min_percent": 30,
                "carbs_max_percent": 60,
                "fat_min_percent": 20,
                "fat_max_percent": 35
            },
            "timing": {
                "pre_entreno": {
                    "carbs_target": "high",
                    "protein_target": "low",
                    "fat_target": "very_low",
                    "fiber_target": "low"
                },
                "post_entreno": {
                    "protein_target": "very_high",
                    "carbs_target": "moderate",
                    "fat_target": "low",
                    "timing_window": "30_minutes"
                },
                "comida_principal": {
                    "balance": "optimal",
                    "satiety": "high",
                    "nutrient_density": "high"
                },
                "snack_complemento": {
                    "micronutrients": "high",
                    "healthy_fats": "high",
                    "portion_control": "important"
                }
            }
        }
    
    def create_recipe_generation_prompt(self, user_profile: Dict, request_data: Dict) -> str:
        """
        Crear prompt estructurado para generación de recetas
        Evita errores de parsing usando formato fijo
        """
        
        # Extraer datos del perfil
        objective = user_profile["basic_data"]["objetivo_descripcion"]
        calories = user_profile["macros"]["calories"]
        protein_g = user_profile["macros"]["protein_g"]
        carbs_g = user_profile["macros"]["carbs_g"]
        fat_g = user_profile["macros"]["fat_g"]
        ea_value = user_profile["energy_data"]["available_energy"]
        
        # Datos de la solicitud
        timing_category = request_data.get("timing_category", "comida_principal")
        function_category = request_data.get("function_category", "equilibrio_nutricional")
        target_macros = request_data.get("target_macros", {})
        
        # Preferencias del usuario
        preferences = user_profile.get("preferences", {})
        liked_foods = preferences.get("liked_foods", [])
        disliked_foods = preferences.get("disliked_foods", [])
        cooking_methods = preferences.get("cooking_methods", [])
        
        prompt = f"""
ERES UN EXPERTO EN NUTRICIÓN DEPORTIVA Y MEAL PREP. Tu tarea es generar UNA receta específica que cumpla exactamente con estos criterios:

PERFIL DEL USUARIO:
- Objetivo: {objective}
- Available Energy: {ea_value} kcal/kg FFM/día
- Macros diarios totales: {calories} kcal ({protein_g}P/{carbs_g}C/{fat_g}F)
- Alimentos preferidos: {', '.join(liked_foods) if liked_foods else 'Ninguna preferencia específica'}
- Alimentos NO deseados: {', '.join(disliked_foods) if disliked_foods else 'Ninguna restricción'}
- Métodos de cocción preferidos: {', '.join(cooking_methods) if cooking_methods else 'Cualquier método'}

REQUERIMIENTOS DE LA RECETA:
- Categoría de timing: {timing_category.replace('_', ' ').title()}
- Función nutricional: {function_category.replace('_', ' ').title()}
- Macros objetivo para esta receta: {target_macros.get('calories', 400)} kcal
- Proteína objetivo: {target_macros.get('protein', 25)}g
- Carbohidratos objetivo: {target_macros.get('carbs', 40)}g
- Grasas objetivo: {target_macros.get('fat', 15)}g

CRITERIOS OBLIGATORIOS:
1. SOLO ingredientes naturales, frescos, no procesados
2. Sin conservantes, colorantes, saborizantes artificiales
3. Optimizada para meal prep (se conserva bien 3-5 días)
4. Tiempo de preparación máximo: 45 minutos
5. Macros dentro del ±10% del objetivo
6. Ingredientes disponibles en supermercados españoles

TIMING ESPECÍFICO - {timing_category.upper()}:
{self._get_timing_guidelines(timing_category)}

INGREDIENTES PROHIBIDOS:
Embutidos, salchichas, jamón procesado, quesos procesados, salsas comerciales, aderezos industriales, condimentos artificiales, conservantes, colorantes, saborizantes, comida precocinada.

INGREDIENTES RECOMENDADOS:
Carnes frescas, pescados frescos, huevos, legumbres secas, cereales integrales, quinoa, verduras frescas, frutas frescas, frutos secos, aceites prensado en frío, hierbas frescas, especias naturales.

DEBES RESPONDER EN ESTE FORMATO JSON EXACTO (sin texto adicional antes o después):

{{
  "receta": {{
    "nombre": "Nombre descriptivo de la receta",
    "categoria_timing": "{timing_category}",
    "categoria_funcion": "{function_category}",
    "dificultad": "⭐⭐" (1-4 estrellas),
    "tiempo_prep": 25,
    "porciones": 4,
    "ingredientes": [
      {{
        "nombre": "Ingrediente 1",
        "cantidad": 200,
        "unidad": "g",
        "categoria": "proteina_animal"
      }},
      {{
        "nombre": "Ingrediente 2", 
        "cantidad": 150,
        "unidad": "g",
        "categoria": "carbohidrato_complejo"
      }}
    ],
    "preparacion": [
      "1. Paso detallado de preparación...",
      "2. Otro paso específico...",
      "3. Paso final con detalles de cocción..."
    ],
    "macros_por_porcion": {{
      "calorias": {target_macros.get('calories', 400)},
      "proteinas": {target_macros.get('protein', 25)},
      "carbohidratos": {target_macros.get('carbs', 40)},
      "grasas": {target_macros.get('fat', 15)},
      "fibra": 8
    }},
    "meal_prep_tips": [
      "Consejo específico de conservación...",
      "Tip de almacenamiento..."
    ],
    "timing_consumo": "{self._get_consumption_timing(timing_category)}",
    "nivel_saciedad": "alto",
    "adaptaciones": [
      "Variación posible 1...",
      "Opción de sustitución..."
    ]
  }}
}}

GENERA UNA SOLA RECETA que cumpla perfectamente con todos estos criterios. La receta debe ser práctica, deliciosa y optimizada para meal prep.
"""
        
        return prompt
    
    def create_recipe_search_prompt(self, user_profile: Dict, search_query: str) -> str:
        """
        Crear prompt para búsqueda y adaptación de recetas existentes
        """
        
        objective = user_profile["basic_data"]["objetivo_descripcion"]
        calories = user_profile["macros"]["calories"]
        protein_g = user_profile["macros"]["protein_g"]
        carbs_g = user_profile["macros"]["carbs_g"]
        fat_g = user_profile["macros"]["fat_g"]
        ea_value = user_profile["energy_data"]["available_energy"]
        
        preferences = user_profile.get("preferences", {})
        liked_foods = preferences.get("liked_foods", [])
        disliked_foods = preferences.get("disliked_foods", [])
        
        prompt = f"""
ERES UN EXPERTO EN NUTRICIÓN DEPORTIVA. El usuario busca: "{search_query}"

PERFIL DEL USUARIO:
- Objetivo: {objective}
- Available Energy: {ea_value} kcal/kg FFM/día
- Macros diarios: {calories} kcal ({protein_g}P/{carbs_g}C/{fat_g}F)
- Prefiere: {', '.join(liked_foods) if liked_foods else 'Sin preferencias'}
- Evita: {', '.join(disliked_foods) if disliked_foods else 'Sin restricciones'}

TU TAREA:
1. Interpretar la consulta del usuario
2. Generar 2-3 opciones de recetas que coincidan
3. Adaptarlas al perfil nutricional específico
4. Asegurar que todos los ingredientes sean naturales

RESPONDE EN ESTE FORMATO JSON:

{{
  "interpretacion_consulta": "Qué está buscando el usuario específicamente",
  "resultados": [
    {{
      "receta": {{
        "nombre": "Nombre de la receta",
        "relevancia_consulta": "Por qué coincide con la búsqueda",
        "categoria_timing": "pre_entreno/post_entreno/comida_principal/snack_complemento",
        "dificultad": "⭐⭐",
        "tiempo_prep": 30,
        "porciones": 4,
        "ingredientes": [
          {{
            "nombre": "Ingrediente natural", 
            "cantidad": 200,
            "unidad": "g",
            "categoria": "proteina_animal/vegetal/carbohidrato_complejo/grasa_saludable"
          }}
        ],
        "preparacion": [
          "Pasos claros de preparación..."
        ],
        "macros_por_porcion": {{
          "calorias": 350,
          "proteinas": 28,
          "carbohidratos": 35,
          "grasas": 12,
          "fibra": 6
        }},
        "timing_consumo": "Cuándo consumir según objetivo",
        "meal_prep_tips": ["Consejos de conservación"]
      }},
      "adaptacion_perfil": "Cómo se adaptó al perfil del usuario",
      "cambios_realizados": ["Lista de modificaciones hechas"]
    }}
  ],
  "total_encontradas": 2
}}

CRITERIOS OBLIGATORIOS:
- Solo ingredientes naturales y frescos
- Sin procesados, conservantes o aditivos
- Optimizado para meal prep
- Macros balanceados según perfil
- Práctico para preparar en casa
"""
        
        return prompt
    
    def create_menu_generation_prompt(self, user_profile: Dict, week_preferences: Dict) -> str:
        """
        Crear prompt para generación de menú semanal completo
        """
        
        objective = user_profile["basic_data"]["objetivo_descripcion"]
        daily_calories = user_profile["macros"]["calories"]
        ea_value = user_profile["energy_data"]["available_energy"]
        recommended_timing = user_profile["exercise_profile"]["recommended_timing"]
        
        variety_level = week_preferences.get("variety_level", 3)
        cooking_schedule = week_preferences.get("cooking_schedule", "dos_sesiones")
        max_prep_time = week_preferences.get("max_prep_time", 60)
        
        prompt = f"""
ERES UN EXPERTO EN MEAL PREP NUTRICIONAL. Crea un menú semanal personalizado.

PERFIL DEL USUARIO:
- Objetivo: {objective}
- Available Energy: {ea_value} kcal/kg FFM/día
- Calorías diarias objetivo: {daily_calories} kcal
- Timing recomendado: {', '.join(recommended_timing)}

REQUERIMIENTOS DEL MENÚ:
- Nivel de variedad: {variety_level}/5 (1=muy repetitivo, 5=máxima variedad)
- Cronograma de cocción: {cooking_schedule}
- Tiempo máximo de preparación: {max_prep_time} minutos por sesión
- Distribución: Lunes a Viernes (5 días)

ESTRUCTURA DIARIA REQUERIDA:
1. DESAYUNO (6:30-8:00) - Pre/durante entrenamiento matutino
2. ALMUERZO (12:00-14:00) - Post-entrenamiento + comida principal
3. CENA (19:00-21:00) - Comida principal balanceada
4. COMPLEMENTOS - Distribuidos según necesidades

DEBES RESPONDER EN FORMATO JSON:

{{
  "menu_semanal": {{
    "semana": 1,
    "objetivo_usuario": "{objective}",
    "calorias_diarias": {daily_calories},
    "distribuciones_diarias": {{
      "lunes": {{
        "desayuno": {{
          "timing_category": "pre_entreno",
          "recetas": ["Nombre de receta 1"],
          "complementos": ["Almendras 30g", "Miel 15g"],
          "macros_totales": {{"calories": 400, "protein": 15, "carbs": 60, "fat": 12}}
        }},
        "almuerzo": {{
          "timing_category": "post_entreno", 
          "recetas": ["Receta principal"],
          "complementos": ["Yogur griego 200g"],
          "macros_totales": {{"calories": 600, "protein": 45, "carbs": 50, "fat": 18}}
        }},
        "cena": {{
          "timing_category": "comida_principal",
          "recetas": ["Receta de cena"],
          "complementos": ["Aceitunas 20g"],
          "macros_totales": {{"calories": 500, "protein": 35, "carbs": 40, "fat": 20}}
        }},
        "macros_dia": {{"calories": {daily_calories}, "protein": 95, "carbs": 150, "fat": 50}}
      }}
      // ... resto de días
    }},
    "lista_compras_semanal": {{
      "proteinas": ["Pollo 2kg", "Huevos 12 unidades"],
      "carbohidratos": ["Quinoa 500g", "Arroz integral 1kg"],
      "verduras": ["Brócoli 1kg", "Espinacas 500g"],
      "complementos_mediterraneos": ["Almendras 250g", "Yogur griego 1kg"],
      "especias_hierbas": ["Oregano", "Tomillo"]
    }},
    "cronograma_preparacion": [
      {{
        "sesion": 1,
        "dia": "domingo",
        "duracion": "3 horas",
        "tareas": ["Cocinar proteínas", "Preparar cereales", "Lavar verduras"]
      }}
    ],
    "meal_prep_tips": [
      "Consejo de conservación",
      "Tip de organización"
    ]
  }}
}}

REQUISITOS CRÍTICOS:
- Todos los ingredientes naturales y frescos
- Macros balanceados según perfil individual
- Variedad apropiada al nivel solicitado
- Optimizado para meal prep y conservación
- Complementos mediterráneos integrados
- Timing nutricional científicamente fundamentado
"""
        
        return prompt
    
    def _get_recipe_generation_template(self) -> str:
        """Template base para generación de recetas"""
        return """
GENERA UNA RECETA que cumpla estos criterios específicos:

[CRITERIOS_USUARIO]
[RESTRICCIONES_INGREDIENTES]
[OBJETIVOS_NUTRICIONALES]
[TIMING_REQUIREMENTS]

Respuesta en formato JSON estructurado...
"""
    
    def _get_recipe_adaptation_template(self) -> str:
        """Template para adaptación de recetas existentes"""
        return """
ADAPTA las siguientes recetas al perfil nutricional específico:

[PERFIL_USUARIO]
[RECETAS_BASE]
[ADAPTACIONES_REQUERIDAS]

Respuesta con modificaciones específicas...
"""
    
    def _get_menu_creation_template(self) -> str:
        """Template para creación de menús semanales"""
        return """
CREA UN MENÚ SEMANAL completo considerando:

[PERFIL_NUTRICIONAL]
[PREFERENCIAS_CRONOGRAMA]
[NIVEL_VARIEDAD]
[RESTRICCIONES_TIEMPO]

Menú estructurado por días y comidas...
"""
    
    def _get_ingredient_validation_template(self) -> str:
        """Template para validación de ingredientes"""
        return """
VALIDA estos ingredientes según criterios mediterráneos:

[LISTA_INGREDIENTES]
[CRITERIOS_NATURALES]
[CATEGORIAS_PERMITIDAS]

Validación con puntuación y recomendaciones...
"""
    
    def _get_timing_guidelines(self, timing_category: str) -> str:
        """
        Obtener guidelines específicas para cada categoría de timing
        """
        guidelines = {
            "pre_entreno": """
OBJETIVO: Proveer energía rápida sin malestar digestivo
- Carbohidratos de absorción rápida (frutas, miel, avena)
- Proteína mínima (10-15g máximo)
- Grasas muy bajas (<5g)
- Fibra baja para facilitar digestión
- Hidratación incluida
- Consumir 15-30 minutos antes del ejercicio""",
            
            "post_entreno": """
OBJETIVO: Maximizar síntesis proteica y reposición de glucógeno
- Proteína completa de alta calidad (25-40g)
- Carbohidratos para reposición (0.5-1g/kg peso)
- Ratio proteína:carbohidratos 1:2 o 1:3
- Grasas moderadas (no interferir absorción)
- Consumir dentro de 30 minutos post-ejercicio
- Incluir aminoácidos esenciales""",
            
            "comida_principal": """
OBJETIVO: Nutrición balanceada y saciedad prolongada
- Balance óptimo de macronutrientes
- Alto contenido en fibra (verduras, legumbres)
- Proteínas de alta calidad
- Carbohidratos complejos
- Grasas saludables (omega-3, monoinsaturadas)
- Micronutrientes diversos
- Saciedad mínimo 3-4 horas""",
            
            "snack_complemento": """
OBJETIVO: Complementar macros y aportar micronutrientes
- Frutos secos y semillas (grasas saludables)
- Frutas frescas (vitaminas y fibra)
- Lácteos naturales (calcio y proteína)
- Aceitunas (grasas monoinsaturadas)
- Porciones controladas (150-250 kcal)
- Fácil transporte y conservación"""
        }
        
        return guidelines.get(timing_category, "Guidelines generales de timing nutricional")
    
    def _get_consumption_timing(self, timing_category: str) -> str:
        """
        Obtener recomendaciones específicas de cuándo consumir
        """
        timing_recommendations = {
            "pre_entreno": "15-30 minutos antes del entrenamiento",
            "post_entreno": "Inmediatamente después del entrenamiento (ventana 0-30 min)",
            "comida_principal": "2-3 horas antes o después del entrenamiento",
            "snack_complemento": "Entre comidas principales o según macros faltantes"
        }
        
        return timing_recommendations.get(timing_category, "Según necesidades individuales")
    
    def validate_prompt_response(self, response_text: str) -> Dict:
        """
        Validar que la respuesta de Claude tenga el formato correcto
        Evita errores de parsing
        """
        try:
            # Intentar parsear JSON
            response_data = json.loads(response_text)
            
            # Validar estructura mínima requerida
            required_fields = ["receta"]
            missing_fields = []
            
            for field in required_fields:
                if field not in response_data:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Campos requeridos faltantes: {', '.join(missing_fields)}",
                    "response": None
                }
            
            # Validar estructura de receta
            recipe = response_data["receta"]
            recipe_required = ["nombre", "ingredientes", "preparacion", "macros_por_porcion"]
            
            for field in recipe_required:
                if field not in recipe:
                    return {
                        "valid": False,
                        "error": f"Campo de receta requerido faltante: {field}",
                        "response": None
                    }
            
            return {
                "valid": True,
                "error": None,
                "response": response_data
            }
            
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "error": f"Error de formato JSON: {str(e)}",
                "response": None
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error de validación: {str(e)}",
                "response": None
            }
    
    def get_fallback_prompt(self, original_request: Dict) -> str:
        """
        Crear prompt de fallback más simple si falla el principal
        """
        return f"""
Crea UNA receta simple que sea:
1. Natural (sin procesados)
2. Fácil de preparar (máximo 30 minutos)
3. Buena para meal prep
4. Aproximadamente 400 calorías por porción

Responde SOLO en formato JSON:
{{
  "receta": {{
    "nombre": "Nombre simple",
    "ingredientes": ["ingrediente 1", "ingrediente 2"],
    "preparacion": ["paso 1", "paso 2"],
    "macros_por_porcion": {{"calorias": 400, "proteinas": 25, "carbohidratos": 40, "grasas": 15}}
  }}
}}
"""