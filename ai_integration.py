#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema completo de integración con Claude API
Maneja generación, búsqueda y adaptación de recetas con IA
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None
    logging.warning("Anthropic library not available. AI features will be disabled.")

from claude_prompt_system import ClaudePromptSystem
from recipe_validator import RecipeValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIRecipeGenerator:
    
    def __init__(self, api_key: str, prompt_system: ClaudePromptSystem, validator: RecipeValidator):
        self.api_key = api_key
        self.prompt_system = prompt_system
        self.validator = validator
        
        # Inicializar cliente Claude
        if Anthropic and api_key:
            try:
                self.client = Anthropic(api_key=api_key)
                self.available = True
                logger.info("✅ AI Recipe Generator initialized successfully")
            except Exception as e:
                logger.error(f"❌ Error initializing Claude client: {e}")
                self.client = None
                self.available = False
        else:
            self.client = None
            self.available = False
            logger.warning("⚠️ AI features disabled: No API key or Anthropic library")
        
        # Configuración de la API
        self.model = "claude-3-5-sonnet-20241022"
        self.max_tokens = 4000
        self.temperature = 0.3  # Más determinístico para recetas
        
        # Cache para optimizar llamadas
        self.recipe_cache = {}
        self.cache_max_size = 100
    
    def generate_recipe(self, user_profile: Dict, request_data: Dict) -> Dict:
        """
        Generar receta específica usando Claude API
        """
        if not self.available:
            return {
                "success": False,
                "error": "AI service not available. Check API key configuration.",
                "recipe": None,
                "validation": None
            }
        
        try:
            # Crear prompt estructurado
            prompt = self.prompt_system.create_recipe_generation_prompt(user_profile, request_data)
            
            # Verificar cache
            cache_key = self._generate_cache_key(prompt)
            if cache_key in self.recipe_cache:
                logger.info("📋 Using cached recipe")
                return self.recipe_cache[cache_key]
            
            # Llamada a Claude API
            logger.info("🤖 Generating recipe with Claude API...")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extraer contenido de la respuesta
            response_text = response.content[0].text.strip()
            
            # Validar formato de respuesta
            validation_result = self.prompt_system.validate_prompt_response(response_text)
            
            if not validation_result["valid"]:
                logger.error(f"❌ Invalid response format: {validation_result['error']}")
                
                # Intentar con prompt de fallback
                return self._generate_fallback_recipe(user_profile, request_data, validation_result["error"])
            
            recipe_data = validation_result["response"]["receta"]
            
            # Validar receta con el sistema de validación
            recipe_validation = self.validator.validate_recipe(recipe_data)
            
            # Determinar si la receta es aceptable
            is_acceptable = recipe_validation["overall_score"] >= 70
            
            result = {
                "success": is_acceptable,
                "recipe": recipe_data,
                "validation": recipe_validation,
                "generation_metadata": {
                    "model_used": self.model,
                    "generated_at": datetime.now().isoformat(),
                    "prompt_tokens": len(prompt.split()),
                    "response_tokens": len(response_text.split())
                }
            }
            
            if not is_acceptable:
                result["error"] = f"Recipe validation failed. Score: {recipe_validation['overall_score']}/100"
                
                # Intentar regenerar con feedback
                return self._regenerate_with_feedback(user_profile, request_data, recipe_validation)
            
            # Guardar en cache si es exitoso
            self._cache_result(cache_key, result)
            
            logger.info(f"✅ Recipe generated successfully. Validation score: {recipe_validation['overall_score']}/100")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating recipe: {str(e)}")
            return {
                "success": False,
                "error": f"API error: {str(e)}",
                "recipe": None,
                "validation": None
            }
    
    def search_and_adapt_recipes(self, user_profile: Dict, search_query: str) -> Dict:
        """
        Buscar y adaptar recetas existentes según consulta del usuario
        """
        if not self.available:
            return {
                "success": False,
                "error": "AI service not available",
                "results": [],
                "total_found": 0
            }
        
        try:
            # Crear prompt de búsqueda
            prompt = self.prompt_system.create_recipe_search_prompt(user_profile, search_query)
            
            # Verificar cache
            cache_key = self._generate_cache_key(f"search_{search_query}_{user_profile['telegram_id']}")
            if cache_key in self.recipe_cache:
                logger.info("📋 Using cached search results")
                return self.recipe_cache[cache_key]
            
            # Llamada a Claude API
            logger.info(f"🔍 Searching recipes for: '{search_query}'")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.4,  # Ligeramente más creativo para búsquedas
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            # Parsear respuesta JSON
            try:
                search_results = json.loads(response_text)
            except json.JSONDecodeError:
                logger.error("❌ Failed to parse search response as JSON")
                return self._fallback_search_response(search_query)
            
            # Validar cada receta encontrada
            validated_results = []
            
            for result in search_results.get("resultados", []):
                recipe = result.get("receta")
                if recipe:
                    validation = self.validator.validate_recipe(recipe)
                    
                    # Solo incluir recetas con puntuación aceptable
                    if validation["overall_score"] >= 60:  # Umbral más bajo para búsquedas
                        result["validation"] = validation
                        validated_results.append(result)
            
            final_result = {
                "success": len(validated_results) > 0,
                "results": validated_results,
                "total_found": len(validated_results),
                "query_interpretation": search_results.get("interpretacion_consulta", search_query),
                "search_metadata": {
                    "original_query": search_query,
                    "model_used": self.model,
                    "searched_at": datetime.now().isoformat()
                }
            }
            
            if len(validated_results) == 0:
                final_result["error"] = "No recipes found matching criteria and validation standards"
            
            # Guardar en cache
            self._cache_result(cache_key, final_result)
            
            logger.info(f"✅ Search completed. Found {len(validated_results)} valid recipes")
            return final_result
            
        except Exception as e:
            logger.error(f"❌ Error in recipe search: {str(e)}")
            return {
                "success": False,
                "error": f"Search error: {str(e)}",
                "results": [],
                "total_found": 0
            }
    
    def generate_weekly_menu(self, user_profile: Dict, week_preferences: Dict) -> Dict:
        """
        Generar menú semanal completo con IA
        """
        if not self.available:
            return {
                "success": False,
                "error": "AI service not available",
                "menu": None
            }
        
        try:
            # Crear prompt de menú semanal
            prompt = self.prompt_system.create_menu_generation_prompt(user_profile, week_preferences)
            
            logger.info("📅 Generating weekly menu with Claude API...")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=6000,  # Más tokens para menú completo
                temperature=0.4,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                menu_data = json.loads(response_text)
            except json.JSONDecodeError:
                logger.error("❌ Failed to parse menu response as JSON")
                return {
                    "success": False,
                    "error": "Invalid menu format received from AI",
                    "menu": None
                }
            
            # Validar menú (implementar validaciones específicas)
            menu_validation = self._validate_weekly_menu(menu_data)
            
            result = {
                "success": menu_validation["valid"],
                "menu": menu_data.get("menu_semanal"),
                "validation": menu_validation,
                "generation_metadata": {
                    "model_used": self.model,
                    "generated_at": datetime.now().isoformat(),
                    "week_preferences": week_preferences
                }
            }
            
            if not menu_validation["valid"]:
                result["error"] = f"Menu validation failed: {menu_validation['error']}"
            
            logger.info(f"✅ Weekly menu generated. Valid: {menu_validation['valid']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating weekly menu: {str(e)}")
            return {
                "success": False,
                "error": f"Menu generation error: {str(e)}",
                "menu": None
            }
    
    def _generate_fallback_recipe(self, user_profile: Dict, request_data: Dict, original_error: str) -> Dict:
        """
        Generar receta usando prompt de fallback más simple
        """
        try:
            logger.info("🔄 Attempting fallback recipe generation...")
            
            fallback_prompt = self.prompt_system.get_fallback_prompt(request_data)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": fallback_prompt
                    }
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                recipe_data = json.loads(response_text)["receta"]
                validation = self.validator.validate_recipe(recipe_data)
                
                return {
                    "success": validation["overall_score"] >= 60,  # Umbral más bajo para fallback
                    "recipe": recipe_data,
                    "validation": validation,
                    "fallback_used": True,
                    "original_error": original_error
                }
                
            except (json.JSONDecodeError, KeyError):
                logger.error("❌ Fallback recipe generation also failed")
                return self._create_emergency_recipe(request_data)
                
        except Exception as e:
            logger.error(f"❌ Fallback generation error: {str(e)}")
            return self._create_emergency_recipe(request_data)
    
    def _regenerate_with_feedback(self, user_profile: Dict, request_data: Dict, validation_result: Dict) -> Dict:
        """
        Regenerar receta incorporando feedback de validación
        """
        try:
            logger.info("🔄 Regenerating recipe with validation feedback...")
            
            # Crear prompt con feedback específico
            feedback_items = validation_result.get("recommendations", [])
            feedback_text = "\n".join(f"- {item}" for item in feedback_items[:3])
            
            original_prompt = self.prompt_system.create_recipe_generation_prompt(user_profile, request_data)
            
            feedback_prompt = f"""{original_prompt}

IMPORTANTE: La receta anterior tuvo problemas de validación. CORRIGE estos aspectos específicamente:

{feedback_text}

GENERA UNA NUEVA RECETA que resuelva estos problemas manteniendo todos los demás criterios.
"""
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.2,  # Más determinístico para correcciones
                messages=[
                    {
                        "role": "user",
                        "content": feedback_prompt
                    }
                ]
            )
            
            response_text = response.content[0].text.strip()
            validation_result = self.prompt_system.validate_prompt_response(response_text)
            
            if validation_result["valid"]:
                recipe_data = validation_result["response"]["receta"]
                new_validation = self.validator.validate_recipe(recipe_data)
                
                return {
                    "success": new_validation["overall_score"] >= 70,
                    "recipe": recipe_data,
                    "validation": new_validation,
                    "regenerated": True
                }
            else:
                return self._create_emergency_recipe(request_data)
                
        except Exception as e:
            logger.error(f"❌ Regeneration error: {str(e)}")
            return self._create_emergency_recipe(request_data)
    
    def _create_emergency_recipe(self, request_data: Dict) -> Dict:
        """
        Crear receta de emergencia predefinida cuando falla la IA
        """
        timing_category = request_data.get("timing_category", "comida_principal")
        target_macros = request_data.get("target_macros", {"calories": 400, "protein": 25, "carbs": 40, "fat": 15})
        
        emergency_recipes = {
            "pre_entreno": {
                "nombre": "Tostada con miel y plátano",
                "ingredientes": [
                    {"nombre": "Pan integral", "cantidad": 60, "unidad": "g"},
                    {"nombre": "Plátano maduro", "cantidad": 100, "unidad": "g"},
                    {"nombre": "Miel natural", "cantidad": 15, "unidad": "g"}
                ],
                "preparacion": [
                    "1. Tostar el pan integral",
                    "2. Cortar el plátano en rodajas",
                    "3. Agregar miel por encima"
                ]
            },
            "post_entreno": {
                "nombre": "Batido de proteína con avena",
                "ingredientes": [
                    {"nombre": "Yogur griego natural", "cantidad": 200, "unidad": "g"},
                    {"nombre": "Avena integral", "cantidad": 40, "unidad": "g"},
                    {"nombre": "Plátano", "cantidad": 100, "unidad": "g"},
                    {"nombre": "Almendras", "cantidad": 20, "unidad": "g"}
                ],
                "preparacion": [
                    "1. Mezclar todos los ingredientes",
                    "2. Batir hasta obtener consistencia cremosa",
                    "3. Servir inmediatamente"
                ]
            },
            "comida_principal": {
                "nombre": "Pollo con arroz integral y verduras",
                "ingredientes": [
                    {"nombre": "Pechuga de pollo", "cantidad": 150, "unidad": "g"},
                    {"nombre": "Arroz integral", "cantidad": 80, "unidad": "g"},
                    {"nombre": "Brócoli", "cantidad": 150, "unidad": "g"},
                    {"nombre": "Aceite de oliva", "cantidad": 15, "unidad": "ml"}
                ]
            }
        }
        
        base_recipe = emergency_recipes.get(timing_category, emergency_recipes["comida_principal"])
        
        emergency_recipe = {
            **base_recipe,
            "categoria_timing": timing_category,
            "categoria_funcion": "emergency_fallback",
            "dificultad": "⭐",
            "tiempo_prep": 15,
            "porciones": 1,
            "macros_por_porcion": target_macros,
            "meal_prep_tips": ["Receta de emergencia - preparar al momento"],
            "timing_consumo": "Según timing solicitado"
        }
        
        validation = {"overall_score": 60, "is_valid": True, "emergency_recipe": True}
        
        return {
            "success": True,
            "recipe": emergency_recipe,
            "validation": validation,
            "emergency_fallback": True,
            "error": "AI generation failed, using emergency recipe"
        }
    
    def _fallback_search_response(self, search_query: str) -> Dict:
        """
        Respuesta de fallback para búsquedas fallidas
        """
        return {
            "success": False,
            "results": [],
            "total_found": 0,
            "error": f"Search failed for query: '{search_query}'. Try simpler terms or check your connection.",
            "suggestions": [
                "Intenta términos más simples (ej: 'pollo' en lugar de 'pollo al curry')",
                "Especifica el timing (ej: 'post entreno')",
                "Menciona ingredientes principales"
            ]
        }
    
    def _validate_weekly_menu(self, menu_data: Dict) -> Dict:
        """
        Validar estructura y contenido del menú semanal
        """
        try:
            menu_semanal = menu_data.get("menu_semanal", {})
            
            required_fields = ["semana", "objetivo_usuario", "calorias_diarias", "distribuciones_diarias"]
            missing_fields = [field for field in required_fields if field not in menu_semanal]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            distribuciones = menu_semanal.get("distribuciones_diarias", {})
            required_days = ["lunes", "martes", "miercoles", "jueves", "viernes"]
            
            for day in required_days:
                if day not in distribuciones:
                    return {
                        "valid": False,
                        "error": f"Missing day: {day}"
                    }
            
            return {
                "valid": True,
                "days_included": len(distribuciones),
                "total_recipes": sum(len(day_data.get("desayuno", {}).get("recetas", [])) + 
                                    len(day_data.get("almuerzo", {}).get("recetas", [])) +
                                    len(day_data.get("cena", {}).get("recetas", []))
                                   for day_data in distribuciones.values())
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Menu validation error: {str(e)}"
            }
    
    def _generate_cache_key(self, content: str) -> str:
        """
        Generar clave de cache basada en el contenido
        """
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _cache_result(self, cache_key: str, result: Dict) -> None:
        """
        Guardar resultado en cache con límite de tamaño
        """
        if len(self.recipe_cache) >= self.cache_max_size:
            # Eliminar entrada más antigua
            oldest_key = next(iter(self.recipe_cache))
            del self.recipe_cache[oldest_key]
        
        self.recipe_cache[cache_key] = result
    
    def get_api_status(self) -> Dict:
        """
        Obtener estado actual de la API
        """
        return {
            "available": self.available,
            "model": self.model,
            "cache_size": len(self.recipe_cache),
            "has_api_key": bool(self.api_key),
            "anthropic_library": Anthropic is not None
        }

def format_recipe_for_display(recipe: Dict, validation: Dict) -> str:
    """
    Formatear receta para mostrar en Telegram
    """
    try:
        # Encabezado
        name = recipe.get("nombre", "Receta sin nombre")
        difficulty = recipe.get("dificultad", "⭐")
        prep_time = recipe.get("tiempo_prep", 0)
        portions = recipe.get("porciones", 1)
        
        formatted = f"**{name}**\n"
        formatted += f"🔧 {difficulty} • ⏱️ {prep_time} min • 🍽️ {portions} porciones\n\n"
        
        # Macros
        macros = recipe.get("macros_por_porcion", {})
        calories = macros.get("calorias", 0)
        protein = macros.get("proteinas", 0)
        carbs = macros.get("carbohidratos", 0)
        fat = macros.get("grasas", 0)
        
        formatted += f"📊 **MACROS POR PORCIÓN:**\n"
        formatted += f"🔥 {calories} kcal • 🥩 {protein}g prot • 🍞 {carbs}g carbs • 🥑 {fat}g grasas\n\n"
        
        # Ingredientes
        ingredients = recipe.get("ingredientes", [])
        if ingredients:
            formatted += "🛒 **INGREDIENTES:**\n"
            for ingredient in ingredients:
                name = ingredient.get("nombre", "")
                quantity = ingredient.get("cantidad", 0)
                unit = ingredient.get("unidad", "")
                formatted += f"• {quantity}{unit} {name}\n"
            formatted += "\n"
        
        # Preparación
        preparation = recipe.get("preparacion", [])
        if preparation:
            formatted += "👨🍳 **PREPARACIÓN:**\n"
            for step in preparation:
                formatted += f"{step}\n"
            formatted += "\n"
        
        # Timing de consumo
        timing = recipe.get("timing_consumo", "")
        if timing:
            formatted += f"⏰ **CUÁNDO CONSUMIR:** {timing}\n\n"
        
        # Tips de meal prep
        tips = recipe.get("meal_prep_tips", [])
        if tips:
            formatted += "📦 **MEAL PREP TIPS:**\n"
            for tip in tips:
                formatted += f"• {tip}\n"
            formatted += "\n"
        
        # Score de validación
        if validation:
            score = validation.get("overall_score", 0)
            is_valid = validation.get("is_valid", False)
            status_emoji = "✅" if is_valid else "⚠️"
            formatted += f"{status_emoji} **Puntuación de calidad:** {score}/100\n"
        
        return formatted
        
    except Exception as e:
        logger.error(f"Error formatting recipe for display: {e}")
        return f"**Error mostrando receta:** {str(e)}"

# Ejemplo de uso
if __name__ == "__main__":
    # Configuración de ejemplo
    from claude_prompt_system import ClaudePromptSystem
    from recipe_validator import RecipeValidator
    
    prompt_system = ClaudePromptSystem()
    validator = RecipeValidator()
    
    # Nota: Necesitas tu propia API key de Anthropic
    ai_generator = AIRecipeGenerator("your-api-key", prompt_system, validator)
    
    print(f"AI Generator Status: {ai_generator.get_api_status()}")