"""
Integración completa con Claude API para generación de recetas
Sistema que conecta prompts estructurados con validación automática
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from anthropic import Anthropic

logger = logging.getLogger(__name__)

class AIRecipeGenerator:
    
    def __init__(self, anthropic_api_key: str, prompt_system, validator):
        self.claude_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None
        self.prompt_system = prompt_system
        self.validator = validator
        
        # Configuración de modelos
        self.model = "claude-3-5-sonnet-20241022"
        self.max_tokens = 2000
        self.temperature = 0.3  # Baja para consistencia nutricional
        
        logger.info("🤖 AIRecipeGenerator initialized")
    
    def generate_recipe(self, user_profile: Dict, request_data: Dict) -> Dict:
        """
        Generar receta usando Claude API con validación automática
        """
        if not self.claude_client:
            return self._create_error_response("Claude API no disponible")
        
        try:
            # 1. Crear prompt estructurado
            prompt_data = self.prompt_system.create_recipe_generation_prompt(
                user_profile, request_data
            )
            formatted_prompt = self.prompt_system.format_prompt_for_api(prompt_data)
            
            logger.info(f"🔄 Generating recipe for user with {request_data.get('timing_category', 'unknown')} timing")
            
            # 2. Llamar a Claude API
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{
                    "role": "user", 
                    "content": formatted_prompt
                }]
            )
            
            # 3. Parsear respuesta JSON
            recipe_data = self._parse_claude_response(response.content[0].text)
            if not recipe_data:
                return self._create_error_response("Error parsing Claude response")
            
            # 4. Validar receta generada
            validation_result = self.validator.validate_recipe(
                recipe_data, 
                request_data.get('target_macros')
            )
            
            # 5. Si validación falla, intentar regenerar
            if not validation_result["is_valid"] and validation_result["score"] < 70:
                logger.warning(f"⚠️ Recipe validation failed (score: {validation_result['score']}), regenerating...")
                return self._regenerate_with_feedback(
                    user_profile, request_data, validation_result
                )
            
            # 6. Crear respuesta exitosa
            return {
                "success": True,
                "recipe": recipe_data,
                "validation": validation_result,
                "message": "Receta generada y validada exitosamente"
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating recipe: {e}")
            return self._create_error_response(f"Error generando receta: {str(e)}")
    
    def search_and_adapt_recipes(self, user_profile: Dict, search_query: str) -> Dict:
        """
        Buscar y adaptar recetas existentes según consulta del usuario
        """
        if not self.claude_client:
            return self._create_error_response("Claude API no disponible")
        
        try:
            # 1. Crear prompt de búsqueda
            prompt_data = self.prompt_system.create_recipe_search_prompt(
                user_profile, search_query
            )
            formatted_prompt = self.prompt_system.format_prompt_for_api(prompt_data)
            
            logger.info(f"🔍 Searching recipes for query: '{search_query}'")
            
            # 2. Llamar a Claude API
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.4,  # Slightly higher for creativity
                messages=[{
                    "role": "user",
                    "content": formatted_prompt
                }]
            )
            
            # 3. Parsear respuesta
            search_results = self._parse_search_response(response.content[0].text)
            if not search_results:
                return self._create_error_response("No se encontraron recetas relevantes")
            
            # 4. Validar cada receta encontrada
            validated_results = []
            for result in search_results.get("recetas_encontradas", []):
                recipe = result.get("adaptacion_propuesta")
                if recipe:
                    validation = self.validator.validate_recipe(recipe)
                    result["validation"] = validation
                    if validation["score"] >= 60:  # Más permisivo para búsquedas
                        validated_results.append(result)
            
            return {
                "success": True,
                "results": validated_results,
                "total_found": len(validated_results),
                "query": search_query,
                "message": f"Se encontraron {len(validated_results)} recetas válidas"
            }
            
        except Exception as e:
            logger.error(f"❌ Error searching recipes: {e}")
            return self._create_error_response(f"Error buscando recetas: {str(e)}")
    
    def generate_weekly_menu(self, user_profile: Dict, variety_preferences: Dict) -> Dict:
        """
        Generar menú semanal completo con variedad configurable
        """
        if not self.claude_client:
            return self._create_error_response("Claude API no disponible")
        
        try:
            # 1. Crear prompt de menú semanal
            prompt_data = self.prompt_system.create_weekly_menu_prompt(
                user_profile, variety_preferences
            )
            formatted_prompt = self.prompt_system.format_prompt_for_api(prompt_data)
            
            logger.info(f"📅 Generating weekly menu for user (variety level: {user_profile['settings']['variety_level']})")
            
            # 2. Llamar a Claude API con más tokens para menú completo
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=4000,  # Más tokens para menú semanal
                temperature=0.5,   # Más creatividad para variedad
                messages=[{
                    "role": "user",
                    "content": formatted_prompt
                }]
            )
            
            # 3. Parsear menú semanal
            menu_data = self._parse_menu_response(response.content[0].text)
            if not menu_data:
                return self._create_error_response("Error generando menú semanal")
            
            # 4. Validar recetas del menú
            validated_menu = self._validate_weekly_menu(menu_data)
            
            return {
                "success": True,
                "weekly_menu": validated_menu,
                "variety_level": user_profile['settings']['variety_level'],
                "cooking_schedule": user_profile['settings']['cooking_schedule'],
                "message": "Menú semanal generado exitosamente"
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating weekly menu: {e}")
            return self._create_error_response(f"Error generando menú: {str(e)}")
    
    def generate_complements_for_day(self, user_profile: Dict, daily_macros_current: Dict) -> Dict:
        """
        Generar complementos específicos para completar macros del día
        """
        if not self.claude_client:
            return self._create_error_response("Claude API no disponible")
        
        try:
            # 1. Crear prompt de complementos
            prompt_data = self.prompt_system.create_complement_suggestion_prompt(
                user_profile, daily_macros_current
            )
            formatted_prompt = self.prompt_system.format_prompt_for_api(prompt_data)
            
            logger.info("🥜 Generating complements to complete daily macros")
            
            # 2. Llamar a Claude API
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": formatted_prompt
                }]
            )
            
            # 3. Parsear complementos
            complements_data = self._parse_complements_response(response.content[0].text)
            if not complements_data:
                return self._create_error_response("Error generando complementos")
            
            return {
                "success": True,
                "complements": complements_data,
                "message": "Complementos calculados para completar macros"
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating complements: {e}")
            return self._create_error_response(f"Error generando complementos: {str(e)}")
    
    def _parse_claude_response(self, response_text: str) -> Optional[Dict]:
        """Parsear respuesta JSON de Claude"""
        try:
            # Buscar JSON en la respuesta
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error("No JSON found in Claude response")
                return None
            
            json_text = response_text[json_start:json_end]
            return json.loads(json_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing Claude response: {e}")
            return None
    
    def _parse_search_response(self, response_text: str) -> Optional[Dict]:
        """Parsear respuesta de búsqueda de recetas"""
        return self._parse_claude_response(response_text)
    
    def _parse_menu_response(self, response_text: str) -> Optional[Dict]:
        """Parsear respuesta de menú semanal"""
        return self._parse_claude_response(response_text)
    
    def _parse_complements_response(self, response_text: str) -> Optional[Dict]:
        """Parsear respuesta de complementos"""
        return self._parse_claude_response(response_text)
    
    def _regenerate_with_feedback(self, user_profile: Dict, request_data: Dict, validation_result: Dict) -> Dict:
        """Regenerar receta con feedback de validación"""
        try:
            # Agregar feedback de validación al prompt
            feedback_prompt = self._create_feedback_prompt(validation_result)
            
            # Modificar request_data con feedback
            enhanced_request = request_data.copy()
            enhanced_request["validation_feedback"] = feedback_prompt
            
            # Intentar una vez más
            prompt_data = self.prompt_system.create_recipe_generation_prompt(
                user_profile, enhanced_request
            )
            formatted_prompt = self.prompt_system.format_prompt_for_api(prompt_data)
            
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.2,  # Más conservador en regeneración
                messages=[{
                    "role": "user",
                    "content": formatted_prompt + f"\n\nCORRECCIONES NECESARIAS:\n{feedback_prompt}"
                }]
            )
            
            recipe_data = self._parse_claude_response(response.content[0].text)
            if recipe_data:
                new_validation = self.validator.validate_recipe(recipe_data, request_data.get('target_macros'))
                return {
                    "success": True,
                    "recipe": recipe_data,
                    "validation": new_validation,
                    "message": f"Receta regenerada (score: {new_validation['score']}/100)"
                }
            
        except Exception as e:
            logger.error(f"Error in regeneration: {e}")
        
        # Si falla la regeneración, devolver error
        return self._create_error_response("No se pudo generar una receta válida tras múltiples intentos")
    
    def _create_feedback_prompt(self, validation_result: Dict) -> str:
        """Crear prompt de feedback basado en errores de validación"""
        feedback = []
        
        if validation_result.get("errors"):
            feedback.append("ERRORES CRÍTICOS:")
            for error in validation_result["errors"]:
                feedback.append(f"- {error}")
        
        if validation_result.get("warnings"):
            feedback.append("WARNINGS:")
            for warning in validation_result["warnings"]:
                feedback.append(f"- {warning}")
        
        # Feedback específico por categoría
        details = validation_result.get("details", {})
        
        if not details.get("ingredients", {}).get("valid", True):
            feedback.append("- Usar solo ingredientes naturales, evitar procesados")
        
        if not details.get("macros", {}).get("valid", True):
            feedback.append("- Ajustar macronutrientes para estar dentro del rango objetivo")
        
        return "\n".join(feedback)
    
    def _validate_weekly_menu(self, menu_data: Dict) -> Dict:
        """Validar todas las recetas del menú semanal"""
        validated_menu = menu_data.copy()
        
        for day, day_data in menu_data.get("menu_semanal", {}).items():
            if "comida_principal" in day_data:
                recipe = day_data["comida_principal"]
                if isinstance(recipe, dict):
                    validation = self.validator.validate_recipe(recipe)
                    day_data["validation"] = validation
        
        return validated_menu
    
    def _create_error_response(self, error_message: str) -> Dict:
        """Crear respuesta de error estándar"""
        return {
            "success": False,
            "error": error_message,
            "message": f"❌ {error_message}"
        }

# Funciones de utilidad para integración con el bot
def format_recipe_for_display(recipe_data: Dict, validation_result: Dict) -> str:
    """Formatear receta para mostrar en Telegram"""
    recipe = recipe_data
    macros = recipe.get("macros_per_serving", {})
    
    text = f"""
🍽️ **{recipe.get('name', 'Receta')}**

📝 **Descripción:** {recipe.get('description', 'N/A')}
⭐ **Complejidad:** {recipe.get('complexity', 1)} estrellas
⏱️ **Tiempo:** {recipe.get('prep_time_minutes', 0)} minutos
🍽️ **Porciones:** {recipe.get('servings', 1)}

**MACROS POR PORCIÓN:**
🥩 Proteína: {macros.get('protein', 0)}g
🍞 Carbohidratos: {macros.get('carbs', 0)}g  
🥑 Grasas: {macros.get('fat', 0)}g
🔥 **Calorías: {macros.get('calories', 0)} kcal**

**INGREDIENTES:**
"""
    
    for i, ingredient in enumerate(recipe.get('ingredients', []), 1):
        if isinstance(ingredient, dict):
            item = ingredient.get('item', '')
            amount = ingredient.get('amount', '')
            unit = ingredient.get('unit', '')
            text += f"{i}. {item}: {amount}{unit}\n"
        else:
            text += f"{i}. {ingredient}\n"
    
    text += "\n**PREPARACIÓN:**\n"
    for i, step in enumerate(recipe.get('steps', []), 1):
        text += f"{i}. {step}\n"
    
    # Información de meal prep
    if recipe.get('meal_prep_notes'):
        text += f"\n📦 **Meal Prep:** {recipe['meal_prep_notes']}"
    
    if recipe.get('storage_instructions'):
        text += f"\n🥶 **Almacenamiento:** {recipe['storage_instructions']}"
    
    # Score de validación
    score = validation_result.get('score', 0)
    if score >= 90:
        text += f"\n✅ **Validación: {score}/100** (Excelente)"
    elif score >= 70:
        text += f"\n✅ **Validación: {score}/100** (Buena)"
    else:
        text += f"\n⚠️ **Validación: {score}/100** (Mejorable)"
    
    return text

# Ejemplo de uso para testing
if __name__ == "__main__":
    # Test sin API key real
    print("🧪 AIRecipeGenerator structure test")
    
    # Simulación de datos
    fake_profile = {
        "basic_data": {"objetivo": "subir_masa"},
        "macros": {"protein_g": 150, "carbs_g": 300, "fat_g": 80, "calories": 2400},
        "settings": {"variety_level": 3, "cooking_schedule": "dos_sesiones"}
    }
    
    fake_request = {
        "timing_category": "post_entreno",
        "function_category": "sintesis_proteica",
        "target_macros": {"protein": 35, "carbs": 40, "fat": 12, "calories": 380}
    }
    
    print("✅ AIRecipeGenerator ready for integration")
    print(f"✅ Sample profile loaded: {fake_profile['basic_data']['objetivo']}")
    print(f"✅ Sample request: {fake_request['timing_category']}")