"""
Sistema de validación automática para recetas generadas por IA
Garantiza que todas las recetas cumplan los criterios establecidos
"""

import json
import re
from typing import Dict, List, Tuple, Optional

class RecipeValidator:
    
    def __init__(self):
        # Ingredientes naturales permitidos
        self.natural_ingredients = {
            "carnes_frescas": [
                "pollo", "pavo", "ternera", "cerdo", "cordero", "conejo",
                "pechugas", "muslos", "solomillo", "lomo", "chuletas"
            ],
            "pescados_frescos": [
                "salmon", "atun", "merluza", "lubina", "dorada", "bacalao",
                "sardinas", "caballa", "trucha"
            ],
            "huevos": ["huevos", "claras", "yemas"],
            "vegetales": [
                "tomate", "cebolla", "ajo", "pimiento", "calabacin", "berenjena",
                "brocoli", "coliflor", "espinacas", "acelgas", "zanahoria", "apio",
                "pepino", "lechuga", "rúcula", "espárragos", "champiñones", "setas"
            ],
            "frutas": [
                "manzana", "pera", "platano", "naranja", "limon", "uvas", "fresas",
                "higos", "kiwi", "melon", "sandia", "melocotón", "albaricoque"
            ],
            "legumbres": [
                "lentejas", "garbanzos", "alubias", "judias", "frijoles", "habas",
                "guisantes", "soja"
            ],
            "cereales_integrales": [
                "arroz integral", "quinoa", "avena", "trigo sarraceno", "mijo",
                "amaranto", "pasta integral", "pan integral"
            ],
            "frutos_secos": [
                "almendras", "nueces", "avellanas", "pistachos", "anacardos",
                "piñones", "castañas"
            ],
            "semillas": [
                "chia", "lino", "sesamo", "girasol", "calabaza"
            ],
            "lacteos_naturales": [
                "yogur natural", "queso fresco", "feta", "manchego", "cabra",
                "leche", "nata", "mantequilla"
            ],
            "aceites_grasas": [
                "aceite oliva virgen", "aceite coco", "aguacate", "aceitunas"
            ],
            "especias_hierbas": [
                "sal", "pimienta", "oregano", "tomillo", "romero", "albahaca",
                "perejil", "cilantro", "comino", "paprika", "curcuma", "jengibre",
                "canela", "laurel", "ajo en polvo", "cebolla en polvo"
            ],
            "otros_naturales": [
                "vinagre", "limon", "caldo natural", "miel", "mostaza dijon"
            ]
        }
        
        # Ingredientes prohibidos (procesados)
        self.forbidden_ingredients = [
            # Conservantes y aditivos
            "conservante", "colorante", "saborizante", "edulcorante artificial",
            "glutamato monosódico", "nitrito", "nitrato", "BHA", "BHT",
            
            # Procesados
            "salchicha", "embutido", "bacon procesado", "jamón york",
            "nuggets", "hamburguesa procesada", "croquetas congeladas",
            
            # Harinas refinadas y azúcares
            "harina blanca", "pan blanco", "pasta blanca", "arroz blanco",
            "azúcar blanco", "azúcar moreno", "jarabe maíz", "fructosa",
            
            # Grasas trans
            "margarina", "manteca vegetal", "aceite parcialmente hidrogenado",
            
            # Ultraprocesados
            "sopa de sobre", "caldo en cubitos", "salsa preparada embotellada",
            "mayonesa industrial", "ketchup", "mostaza con aditivos"
        ]
        
        # Factores de conversión para macronutrientes (kcal/g)
        self.macro_calories = {
            "protein": 4,
            "carbs": 4,
            "fat": 9
        }
    
    def validate_recipe(self, recipe_data: Dict, target_macros: Optional[Dict] = None) -> Dict:
        """
        Validación completa de una receta
        Retorna diccionario con resultado de validación y errores encontrados
        """
        
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "score": 0,
            "details": {}
        }
        
        # 1. Validar estructura JSON
        structure_result = self._validate_structure(recipe_data)
        validation_result["details"]["structure"] = structure_result
        if not structure_result["valid"]:
            validation_result["is_valid"] = False
            validation_result["errors"].extend(structure_result["errors"])
        
        # 2. Validar ingredientes naturales
        ingredients_result = self._validate_natural_ingredients(recipe_data.get("ingredients", []))
        validation_result["details"]["ingredients"] = ingredients_result
        if not ingredients_result["valid"]:
            validation_result["is_valid"] = False
            validation_result["errors"].extend(ingredients_result["errors"])
        
        # 3. Validar macronutrientes
        if target_macros:
            macros_result = self._validate_macros(recipe_data.get("macros_per_serving", {}), target_macros)
            validation_result["details"]["macros"] = macros_result
            if not macros_result["valid"]:
                validation_result["warnings"].extend(macros_result["warnings"])
        
        # 4. Validar coherencia nutricional
        nutritional_result = self._validate_nutritional_coherence(recipe_data)
        validation_result["details"]["nutritional"] = nutritional_result
        if not nutritional_result["valid"]:
            validation_result["warnings"].extend(nutritional_result["warnings"])
        
        # 5. Validar tiempo de preparación
        time_result = self._validate_preparation_time(recipe_data)
        validation_result["details"]["time"] = time_result
        if not time_result["valid"]:
            validation_result["warnings"].extend(time_result["warnings"])
        
        # 6. Validar disponibilidad regional
        availability_result = self._validate_regional_availability(recipe_data.get("ingredients", []))
        validation_result["details"]["availability"] = availability_result
        if not availability_result["valid"]:
            validation_result["warnings"].extend(availability_result["warnings"])
        
        # Calcular score total (0-100)
        validation_result["score"] = self._calculate_score(validation_result["details"])
        
        return validation_result
    
    def _validate_structure(self, recipe_data: Dict) -> Dict:
        """Validar que la receta tenga la estructura JSON correcta"""
        
        required_fields = [
            "id", "name", "description", "timing_category", "function_category",
            "servings", "prep_time_minutes", "complexity", "ingredients",
            "steps", "macros_per_serving"
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in recipe_data:
                missing_fields.append(field)
        
        # Validar tipos de datos
        type_errors = []
        if "servings" in recipe_data and not isinstance(recipe_data["servings"], (int, float)):
            type_errors.append("servings debe ser numérico")
        
        if "prep_time_minutes" in recipe_data and not isinstance(recipe_data["prep_time_minutes"], (int, float)):
            type_errors.append("prep_time_minutes debe ser numérico")
        
        if "ingredients" in recipe_data and not isinstance(recipe_data["ingredients"], list):
            type_errors.append("ingredients debe ser una lista")
        
        if "steps" in recipe_data and not isinstance(recipe_data["steps"], list):
            type_errors.append("steps debe ser una lista")
        
        return {
            "valid": len(missing_fields) == 0 and len(type_errors) == 0,
            "errors": missing_fields + type_errors,
            "missing_fields": missing_fields,
            "type_errors": type_errors
        }
    
    def _validate_natural_ingredients(self, ingredients: List) -> Dict:
        """Validar que todos los ingredientes sean naturales"""
        
        forbidden_found = []
        natural_score = 0
        total_ingredients = len(ingredients)
        
        for ingredient in ingredients:
            ingredient_text = ""
            if isinstance(ingredient, dict):
                ingredient_text = ingredient.get("item", "").lower()
            elif isinstance(ingredient, str):
                ingredient_text = ingredient.lower()
            
            # Buscar ingredientes prohibidos
            for forbidden in self.forbidden_ingredients:
                if forbidden.lower() in ingredient_text:
                    forbidden_found.append(f"Ingrediente prohibido: {ingredient_text}")
            
            # Verificar si es natural
            is_natural = False
            for category, natural_items in self.natural_ingredients.items():
                for natural_item in natural_items:
                    if natural_item.lower() in ingredient_text:
                        is_natural = True
                        break
                if is_natural:
                    break
            
            if is_natural:
                natural_score += 1
        
        natural_percentage = (natural_score / total_ingredients * 100) if total_ingredients > 0 else 0
        
        return {
            "valid": len(forbidden_found) == 0,
            "errors": forbidden_found,
            "natural_percentage": natural_percentage,
            "natural_count": natural_score,
            "total_count": total_ingredients
        }
    
    def _validate_macros(self, recipe_macros: Dict, target_macros: Dict) -> Dict:
        """Validar que los macronutrientes estén dentro del rango aceptable"""
        
        # Tolerancias por nutriente
        tolerances = {
            "protein": 0.10,  # ±10%
            "carbs": 0.15,    # ±15%
            "fat": 0.10,      # ±10%
            "calories": 50    # ±50 kcal (absoluto)
        }
        
        warnings = []
        macro_details = {}
        
        for macro in ["protein", "carbs", "fat", "calories"]:
            if macro not in recipe_macros or macro not in target_macros:
                continue
                
            recipe_value = recipe_macros[macro]
            target_value = target_macros[macro]
            
            if macro == "calories":
                # Tolerancia absoluta para calorías
                diff = abs(recipe_value - target_value)
                tolerance = tolerances[macro]
                is_within_range = diff <= tolerance
            else:
                # Tolerancia porcentual para otros macros
                tolerance = tolerances[macro]
                min_value = target_value * (1 - tolerance)
                max_value = target_value * (1 + tolerance)
                is_within_range = min_value <= recipe_value <= max_value
                diff_percentage = abs(recipe_value - target_value) / target_value * 100
            
            macro_details[macro] = {
                "recipe_value": recipe_value,
                "target_value": target_value,
                "within_range": is_within_range,
                "difference": diff if macro == "calories" else diff_percentage
            }
            
            if not is_within_range:
                if macro == "calories":
                    warnings.append(f"{macro}: {recipe_value} vs objetivo {target_value} (diff: {diff:.0f} kcal)")
                else:
                    warnings.append(f"{macro}: {recipe_value}g vs objetivo {target_value}g (diff: {diff_percentage:.1f}%)")
        
        # Validar coherencia de calorías calculadas
        calculated_calories = (
            recipe_macros.get("protein", 0) * self.macro_calories["protein"] +
            recipe_macros.get("carbs", 0) * self.macro_calories["carbs"] +
            recipe_macros.get("fat", 0) * self.macro_calories["fat"]
        )
        
        stated_calories = recipe_macros.get("calories", 0)
        calorie_diff = abs(calculated_calories - stated_calories)
        
        if calorie_diff > 20:  # Tolerancia de 20 kcal para redondeos
            warnings.append(f"Calorías inconsistentes: calculadas {calculated_calories:.0f} vs declaradas {stated_calories}")
        
        return {
            "valid": len(warnings) < 2,  # Máximo 1 warning para ser válido
            "warnings": warnings,
            "macro_details": macro_details,
            "calorie_coherence": {
                "calculated": calculated_calories,
                "stated": stated_calories,
                "difference": calorie_diff
            }
        }
    
    def _validate_nutritional_coherence(self, recipe_data: Dict) -> Dict:
        """Validar coherencia nutricional general de la receta"""
        
        warnings = []
        
        # Validar que el timing coincida con los macros
        timing = recipe_data.get("timing_category", "")
        macros = recipe_data.get("macros_per_serving", {})
        
        if timing == "pre_entreno":
            # Pre-entreno debería ser alto en carbos, bajo en grasa
            carb_percentage = self._calculate_macro_percentage(macros, "carbs")
            fat_percentage = self._calculate_macro_percentage(macros, "fat")
            
            if carb_percentage < 50:
                warnings.append("Pre-entreno debería tener >50% carbohidratos")
            if fat_percentage > 20:
                warnings.append("Pre-entreno debería tener <20% grasas")
        
        elif timing == "post_entreno":
            # Post-entreno debería ser alto en proteína
            protein_percentage = self._calculate_macro_percentage(macros, "protein")
            
            if protein_percentage < 25:
                warnings.append("Post-entreno debería tener >25% proteína")
        
        # Validar densidad calórica razonable
        calories = macros.get("calories", 0)
        if calories < 50:
            warnings.append("Densidad calórica muy baja para una receta completa")
        elif calories > 1000:
            warnings.append("Densidad calórica muy alta para una porción")
        
        return {
            "valid": len(warnings) == 0,
            "warnings": warnings
        }
    
    def _validate_preparation_time(self, recipe_data: Dict) -> Dict:
        """Validar que el tiempo de preparación sea realista"""
        
        prep_time = recipe_data.get("prep_time_minutes", 0)
        complexity = recipe_data.get("complexity", 1)
        steps_count = len(recipe_data.get("steps", []))
        
        warnings = []
        
        # Validar coherencia tiempo-complejidad
        expected_time_ranges = {
            1: (15, 30),   # ⭐
            2: (30, 45),   # ⭐⭐
            3: (45, 60),   # ⭐⭐⭐
            4: (60, 120)   # ⭐⭐⭐⭐
        }
        
        if complexity in expected_time_ranges:
            min_time, max_time = expected_time_ranges[complexity]
            if prep_time < min_time or prep_time > max_time:
                warnings.append(f"Tiempo {prep_time}min no coherente con complejidad {complexity} estrellas")
        
        # Validar coherencia tiempo-pasos
        if steps_count > 0:
            time_per_step = prep_time / steps_count
            if time_per_step < 2:
                warnings.append("Tiempo insuficiente por paso de preparación")
            elif time_per_step > 20:
                warnings.append("Tiempo excesivo por paso de preparación")
        
        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "prep_time": prep_time,
            "complexity": complexity,
            "steps_count": steps_count
        }
    
    def _validate_regional_availability(self, ingredients: List) -> Dict:
        """Validar disponibilidad de ingredientes en España"""
        
        # Ingredientes difíciles de encontrar en España
        uncommon_ingredients = [
            "quinoa negra", "amaranto", "teff", "miso", "tahini",
            "aceite mct", "stevia líquida", "xilitol", "eritritol",
            "harina de almendra", "harina de coco", "levadura nutricional"
        ]
        
        warnings = []
        
        for ingredient in ingredients:
            ingredient_text = ""
            if isinstance(ingredient, dict):
                ingredient_text = ingredient.get("item", "").lower()
            elif isinstance(ingredient, str):
                ingredient_text = ingredient.lower()
            
            for uncommon in uncommon_ingredients:
                if uncommon in ingredient_text:
                    warnings.append(f"Ingrediente poco común en España: {ingredient_text}")
        
        return {
            "valid": len(warnings) <= 1,  # Máximo 1 ingrediente poco común
            "warnings": warnings
        }
    
    def _calculate_macro_percentage(self, macros: Dict, macro_type: str) -> float:
        """Calcular porcentaje de calorías de un macronutriente"""
        
        total_calories = macros.get("calories", 0)
        if total_calories == 0:
            return 0
        
        macro_grams = macros.get(macro_type, 0)
        macro_calories = macro_grams * self.macro_calories.get(macro_type, 4)
        
        return (macro_calories / total_calories) * 100
    
    def _calculate_score(self, validation_details: Dict) -> int:
        """Calcular puntuación total de validación (0-100)"""
        
        score = 100
        
        # Penalizaciones por errores estructurales
        if not validation_details.get("structure", {}).get("valid", True):
            score -= 30
        
        # Penalizaciones por ingredientes no naturales
        ingredients_data = validation_details.get("ingredients", {})
        natural_percentage = ingredients_data.get("natural_percentage", 100)
        if natural_percentage < 100:
            score -= (100 - natural_percentage) * 0.5
        
        # Penalizaciones por macros fuera de rango
        macros_warnings = len(validation_details.get("macros", {}).get("warnings", []))
        score -= macros_warnings * 10
        
        # Penalizaciones por incoherencias nutricionales
        nutritional_warnings = len(validation_details.get("nutritional", {}).get("warnings", []))
        score -= nutritional_warnings * 5
        
        # Penalizaciones por tiempo irealista
        time_warnings = len(validation_details.get("time", {}).get("warnings", []))
        score -= time_warnings * 5
        
        # Penalizaciones por ingredientes poco disponibles
        availability_warnings = len(validation_details.get("availability", {}).get("warnings", []))
        score -= availability_warnings * 3
        
        return max(0, min(100, score))

# Ejemplo de uso
if __name__ == "__main__":
    validator = RecipeValidator()
    
    # Receta de ejemplo para testing
    sample_recipe = {
        "id": "pollo_quinoa_test",
        "name": "Pollo con Quinoa",
        "description": "Proteína completa post-entreno",
        "timing_category": "post_entreno",
        "function_category": "sintesis_proteica",
        "servings": 4,
        "prep_time_minutes": 45,
        "complexity": 2,
        "ingredients": [
            {"item": "pechuga de pollo", "amount": 400, "unit": "g"},
            {"item": "quinoa", "amount": 200, "unit": "g"},
            {"item": "brócoli", "amount": 300, "unit": "g"},
            {"item": "aceite de oliva virgen", "amount": 20, "unit": "ml"}
        ],
        "steps": [
            "Lavar y cortar el pollo",
            "Cocinar quinoa en agua",
            "Saltear pollo en aceite de oliva",
            "Agregar brócoli al vapor",
            "Mezclar y servir"
        ],
        "macros_per_serving": {
            "protein": 35,
            "carbs": 40,
            "fat": 12,
            "calories": 380
        }
    }
    
    target_macros = {
        "protein": 35,
        "carbs": 42,
        "fat": 10,
        "calories": 375
    }
    
    # Validar receta
    result = validator.validate_recipe(sample_recipe, target_macros)
    
    print("=== RESULTADO DE VALIDACIÓN ===")
    print(f"Válida: {result['is_valid']}")
    print(f"Puntuación: {result['score']}/100")
    print(f"Errores: {result['errors']}")
    print(f"Warnings: {result['warnings']}")