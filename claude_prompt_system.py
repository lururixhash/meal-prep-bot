"""
Sistema de prompts fijos estructurados para Claude API
Evita errores de parseo y garantiza consistencia en las respuestas
"""

import json
from typing import Dict, List, Optional

class ClaudePromptSystem:
    
    def __init__(self):
        self.base_system_prompt = """
        Eres un chef nutricional especializado en alimentación natural y evidencia científica.
        Tu función es generar recetas que cumplan criterios específicos de nutrición deportiva.
        
        REGLAS OBLIGATORIAS:
        1. Solo usar ingredientes naturales (no procesados, sin conservantes artificiales)
        2. Calcular macronutrientes con precisión (±5% de margen)
        3. Respetar las preferencias alimentarias del usuario
        4. Generar recetas meal-prep friendly cuando se requiera
        5. Incluir tiempos de preparación realistas
        6. Verificar disponibilidad de ingredientes en España
        
        FORMATO DE RESPUESTA OBLIGATORIO:
        Responde SIEMPRE en formato JSON válido sin texto adicional.
        """
    
    def create_recipe_generation_prompt(self, user_profile: Dict, request_data: Dict) -> Dict:
        """
        Crear prompt estructurado para generación de recetas
        """
        
        prompt_data = {
            "system_prompt": self.base_system_prompt,
            "user_context": {
                "perfil_usuario": {
                    "objetivo": user_profile["basic_data"]["objetivo"],
                    "objetivo_descripcion": user_profile["basic_data"]["objetivo_descripcion"],
                    "macros_diarios": user_profile["macros"],
                    "available_energy": user_profile["energy_data"]["available_energy"],
                    "ea_status": user_profile["energy_data"]["ea_status"]["description"],
                    "timing_recomendado": user_profile["exercise_profile"]["recommended_timing"]
                },
                "preferencias": {
                    "alimentos_favoritos": user_profile["preferences"].get("liked_foods", []),
                    "alimentos_rechazados": user_profile["preferences"].get("disliked_foods", []),
                    "metodos_coccion": user_profile["preferences"].get("cooking_methods", []),
                    "tiempo_maximo_prep": user_profile["settings"]["max_prep_time"],
                    "nivel_variedad": user_profile["settings"]["variety_level"]
                }
            },
            "solicitud_especifica": {
                "categoria_timing": request_data["timing_category"],
                "categoria_funcion": request_data["function_category"],
                "macros_objetivo": request_data["target_macros"],
                "porciones_requeridas": request_data.get("servings", 1),
                "meal_prep_friendly": request_data.get("meal_prep_friendly", True),
                "complejidad_maxima": request_data.get("max_complexity", 3)
            },
            "criterios_validacion": {
                "ingredientes_naturales": {
                    "permitidos": [
                        "carnes_frescas", "pescados_frescos", "huevos_frescos",
                        "vegetales_frescos", "frutas_frescas", "legumbres_secas",
                        "cereales_integrales", "frutos_secos_crudos", 
                        "lacteos_naturales", "aceites_prensado_frio",
                        "especias_naturales", "hierbas_frescas", "vinagres_naturales"
                    ],
                    "prohibidos": [
                        "conservantes_artificiales", "colorantes_artificiales",
                        "saborizantes_artificiales", "edulcorantes_artificiales",
                        "harinas_refinadas", "azucares_añadidos", "grasas_trans",
                        "productos_ultraprocesados", "embutidos_procesados"
                    ]
                },
                "tolerancia_macros": {
                    "proteina": "±10%",
                    "carbohidratos": "±15%", 
                    "grasas": "±10%",
                    "calorias": "±50 kcal"
                },
                "disponibilidad_regional": "España y Europa",
                "realismo_preparacion": {
                    "tiempo_minimo": 15,
                    "tiempo_maximo": user_profile["settings"]["max_prep_time"],
                    "verificar_utensilios": True
                }
            },
            "formato_respuesta_requerido": {
                "estructura_json": {
                    "receta": {
                        "id": "string_único",
                        "name": "string",
                        "description": "string_breve",
                        "timing_category": "pre_entreno|post_entreno|comida_principal|snack_complemento",
                        "function_category": "string",
                        "servings": "number",
                        "prep_time_minutes": "number",
                        "complexity": "1-4",
                        "ingredients": [
                            {
                                "item": "string",
                                "amount": "number",
                                "unit": "string",
                                "notes": "string_opcional"
                            }
                        ],
                        "steps": ["string_paso_1", "string_paso_2"],
                        "macros_per_serving": {
                            "protein": "number",
                            "carbs": "number", 
                            "fat": "number",
                            "calories": "number"
                        },
                        "meal_prep_notes": "string",
                        "storage_instructions": "string",
                        "reheating_instructions": "string_opcional",
                        "nutritional_benefits": ["string_beneficio_1"],
                        "tags": ["string_tag_1"],
                        "validation_passed": "boolean"
                    }
                }
            }
        }
        
        return prompt_data
    
    def create_recipe_search_prompt(self, user_profile: Dict, search_query: str) -> Dict:
        """
        Crear prompt para búsqueda/adaptación de recetas existentes
        """
        
        prompt_data = {
            "system_prompt": self.base_system_prompt,
            "user_context": {
                "perfil_usuario": {
                    "objetivo": user_profile["basic_data"]["objetivo"],
                    "macros_diarios": user_profile["macros"],
                    "available_energy": user_profile["energy_data"]["available_energy"]
                },
                "preferencias": user_profile["preferences"]
            },
            "consulta_busqueda": {
                "termino_busqueda": search_query,
                "adaptacion_requerida": True,
                "macros_usuario": user_profile["macros"],
                "restricciones": user_profile["preferences"].get("disliked_foods", [])
            },
            "criterios_adaptacion": {
                "mantener_esencia": True,
                "ajustar_porciones": True,
                "sustituir_ingredientes_no_naturales": True,
                "optimizar_macros": True
            },
            "formato_respuesta": {
                "recetas_encontradas": [
                    {
                        "receta_original": "string_descripcion",
                        "adaptacion_propuesta": "objeto_receta_formato_completo",
                        "cambios_realizados": ["string_cambio_1"],
                        "justificacion_nutricional": "string"
                    }
                ],
                "numero_opciones": "1-5"
            }
        }
        
        return prompt_data
    
    def create_complement_suggestion_prompt(self, user_profile: Dict, daily_macros_current: Dict) -> Dict:
        """
        Crear prompt para sugerir complementos que completen macros faltantes
        """
        
        # Calcular macros faltantes
        target_macros = user_profile["macros"]
        remaining_macros = {
            "protein": max(0, target_macros["protein_g"] - daily_macros_current.get("protein", 0)),
            "carbs": max(0, target_macros["carbs_g"] - daily_macros_current.get("carbs", 0)),
            "fat": max(0, target_macros["fat_g"] - daily_macros_current.get("fat", 0)),
            "calories": max(0, target_macros["calories"] - daily_macros_current.get("calories", 0))
        }
        
        prompt_data = {
            "system_prompt": self.base_system_prompt,
            "user_context": {
                "perfil_usuario": user_profile["basic_data"],
                "macros_objetivo": target_macros,
                "macros_actuales": daily_macros_current,
                "macros_faltantes": remaining_macros
            },
            "solicitud_complementos": {
                "objetivo": "completar_macros_diarios",
                "distribucion_temporal": {
                    "media_manana": "20-30% del total faltante",
                    "media_tarde": "40-50% del total faltante", 
                    "noche": "20-30% del total faltante"
                },
                "preferencias_timing": user_profile["exercise_profile"]["recommended_timing"],
                "variedad_requerida": user_profile["settings"]["variety_level"]
            },
            "complementos_disponibles": {
                "frutos_secos": ["almendras", "nueces", "pistachos", "avellanas"],
                "frutas_frescas": ["manzana", "pera", "uvas", "higos", "platano"],
                "frutas_secas": ["datiles", "higos_secos", "pasas"],
                "lacteos_naturales": ["yogur_griego", "queso_feta", "queso_manchego"],
                "aceitunas_encurtidos": ["aceitunas_kalamata", "aceitunas_verdes"],
                "otros_naturales": ["miel_cruda", "aceite_oliva_virgen"]
            },
            "formato_respuesta": {
                "distribucion_diaria": {
                    "media_manana": {
                        "complementos": ["objeto_complemento_1"],
                        "macros_aportados": "objeto_macros",
                        "timing_optimo": "string"
                    },
                    "media_tarde": {
                        "complementos": ["objeto_complemento_1"],
                        "macros_aportados": "objeto_macros",
                        "timing_optimo": "string"
                    },
                    "noche": {
                        "complementos": ["objeto_complemento_1"],
                        "macros_aportados": "objeto_macros",
                        "timing_optimo": "string"
                    }
                },
                "resumen_total": {
                    "macros_completados": "objeto_macros",
                    "deficit_restante": "objeto_macros",
                    "recomendaciones_adicionales": "string"
                }
            }
        }
        
        return prompt_data
    
    def create_weekly_menu_prompt(self, user_profile: Dict, variety_preferences: Dict) -> Dict:
        """
        Crear prompt para generar menú semanal completo con variedad
        """
        
        prompt_data = {
            "system_prompt": self.base_system_prompt,
            "user_context": {
                "perfil_usuario": user_profile["basic_data"],
                "macros_diarios": user_profile["macros"],
                "preferencias": user_profile["preferences"],
                "cronograma_coccion": user_profile["settings"]["cooking_schedule"]
            },
            "requerimientos_variedad": {
                "nivel_variedad": user_profile["settings"]["variety_level"],
                "distribucion_semanal": variety_preferences,
                "evitar_repeticion": True,
                "optimizar_ingredientes": True
            },
            "estructura_semanal": {
                "dias": ["lunes", "martes", "miercoles", "jueves", "viernes"],
                "comidas_por_dia": {
                    "comida_principal": 1,
                    "complementos_distribuidos": "segun_macros_faltantes"
                },
                "balance_nutricional": "mantener_consistencia_semanal"
            },
            "optimizacion_meal_prep": {
                "ingredientes_compartidos": "maximizar_eficiencia",
                "cronograma_coccion": user_profile["settings"]["cooking_schedule"],
                "almacenamiento": "optimizar_frescura",
                "batch_cooking": "agrupar_preparaciones_similares"
            },
            "formato_respuesta": {
                "menu_semanal": {
                    "lunes": {
                        "comida_principal": "objeto_receta",
                        "complementos": ["objeto_complemento_1"],
                        "macros_dia_total": "objeto_macros"
                    },
                    "martes": "estructura_similar",
                    "miercoles": "estructura_similar",
                    "jueves": "estructura_similar",
                    "viernes": "estructura_similar"
                },
                "cronograma_preparacion": {
                    "sesiones_cocina": [
                        {
                            "dia": "string",
                            "duracion_estimada": "number_minutos",
                            "recetas_a_preparar": ["string_receta_1"],
                            "orden_optimizado": ["string_paso_1"]
                        }
                    ]
                },
                "lista_compras": {
                    "proteinas": ["item_cantidad"],
                    "vegetales": ["item_cantidad"],
                    "legumbres": ["item_cantidad"],
                    "frutos_secos": ["item_cantidad"],
                    "otros": ["item_cantidad"]
                },
                "resumen_nutricional": {
                    "macros_promedio_diario": "objeto_macros",
                    "variabilidad_calorica": "±X%",
                    "available_energy_promedio": "number"
                }
            }
        }
        
        return prompt_data
    
    def format_prompt_for_api(self, prompt_data: Dict) -> str:
        """
        Formatear el prompt estructurado para envío a Claude API
        """
        
        formatted_prompt = f"""
{prompt_data['system_prompt']}

CONTEXTO DEL USUARIO:
{json.dumps(prompt_data['user_context'], indent=2, ensure_ascii=False)}

SOLICITUD ESPECÍFICA:
{json.dumps(prompt_data.get('solicitud_especifica', prompt_data.get('consulta_busqueda', prompt_data.get('solicitud_complementos', {}))), indent=2, ensure_ascii=False)}

CRITERIOS DE VALIDACIÓN:
{json.dumps(prompt_data.get('criterios_validacion', {}), indent=2, ensure_ascii=False)}

FORMATO DE RESPUESTA REQUERIDO:
{json.dumps(prompt_data['formato_respuesta_requerido'] if 'formato_respuesta_requerido' in prompt_data else prompt_data['formato_respuesta'], indent=2, ensure_ascii=False)}

INSTRUCCIONES FINALES:
1. Responde ÚNICAMENTE en formato JSON válido
2. No incluyas texto explicativo fuera del JSON
3. Verifica que todos los campos requeridos están presentes
4. Asegúrate de que los macronutrientes suman correctamente
5. Confirma que todos los ingredientes son naturales y disponibles en España
"""
        
        return formatted_prompt

# Ejemplo de uso
if __name__ == "__main__":
    prompt_system = ClaudePromptSystem()
    
    # Datos de ejemplo
    sample_user_profile = {
        "basic_data": {
            "objetivo": "subir_masa",
            "objetivo_descripcion": "Ganar músculo minimizando grasa"
        },
        "macros": {
            "protein_g": 150,
            "carbs_g": 300, 
            "fat_g": 80,
            "calories": 2400
        },
        "energy_data": {
            "available_energy": 47.5,
            "ea_status": {"description": "Óptima para rendimiento"}
        },
        "exercise_profile": {
            "recommended_timing": ["pre_entreno", "post_entreno", "comida_principal"]
        },
        "preferences": {
            "liked_foods": ["pollo", "quinoa", "almendras"],
            "disliked_foods": ["pescado"],
            "cooking_methods": ["horno", "sarten"]
        },
        "settings": {
            "max_prep_time": 60,
            "variety_level": 4,
            "cooking_schedule": "dos_sesiones"
        }
    }
    
    sample_request = {
        "timing_category": "post_entreno",
        "function_category": "sintesis_proteica",
        "target_macros": {"protein": 35, "carbs": 40, "fat": 12, "calories": 380},
        "servings": 4,
        "meal_prep_friendly": True,
        "max_complexity": 3
    }
    
    # Generar prompt
    prompt_data = prompt_system.create_recipe_generation_prompt(sample_user_profile, sample_request)
    formatted_prompt = prompt_system.format_prompt_for_api(prompt_data)
    
    print("=== PROMPT GENERADO PARA CLAUDE API ===")
    print(formatted_prompt[:1000] + "..." if len(formatted_prompt) > 1000 else formatted_prompt)