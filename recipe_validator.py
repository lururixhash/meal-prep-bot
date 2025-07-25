#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema avanzado de validación de recetas
Valida ingredientes naturales, coherencia nutricional y timing apropiado
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

class RecipeValidator:
    
    def __init__(self):
        # Base de datos de ingredientes naturales permitidos
        self.natural_ingredients = {
            "proteina_animal": {
                "carnes_frescas": ["pollo", "pavo", "ternera", "cerdo_magro", "cordero"],
                "pescados_frescos": ["salmon", "atun", "merluza", "lubina", "sardinas", "caballa"],
                "mariscos": ["langostinos", "mejillones", "calamares", "pulpo"],
                "huevos": ["huevos_gallina", "huevos_codorniz"]
            },
            "proteina_vegetal": {
                "legumbres": ["lentejas", "garbanzos", "judias_blancas", "judias_negras", "azuki"],
                "frutos_secos": ["almendras", "nueces", "pistachos", "avellanas", "anacardos"],
                "semillas": ["chia", "lino", "sesamo", "girasol", "calabaza"]
            },
            "carbohidratos": {
                "cereales_integrales": ["arroz_integral", "quinoa", "avena", "centeno", "cebada"],
                "tubérculos": ["patata", "boniato", "yuca"],
                "frutas": ["platano", "manzana", "pera", "naranja", "fresas", "arandanos"]
            },
            "grasas_saludables": {
                "aceites_prensado_frio": ["aceite_oliva_virgen", "aceite_coco", "aceite_aguacate"],
                "frutos_grasos": ["aguacate", "aceitunas", "coco"],
                "pescados_grasos": ["salmon", "sardinas", "caballa", "anchoas"]
            },
            "verduras": {
                "hojas_verdes": ["espinacas", "acelgas", "lechuga", "rucula", "col_rizada"],
                "cruciferas": ["brocoli", "coliflor", "col", "coles_bruselas"],
                "solanaceas": ["tomate", "pimiento", "berenjena"],
                "aliáceas": ["cebolla", "ajo", "puerro", "cebollino"]
            },
            "lacteos_naturales": {
                "leches": ["leche_entera", "leche_cabra", "leche_oveja"],
                "yogures": ["yogur_natural", "yogur_griego", "kefir"],
                "quesos_frescos": ["queso_fresco", "ricotta", "mozzarella", "feta"]
            },
            "condimentos_naturales": {
                "hierbas_frescas": ["albahaca", "oregano", "tomillo", "romero", "perejil"],
                "especias": ["comino", "paprika", "curcuma", "jengibre", "canela"],
                "otros": ["limon", "vinagre_manzana", "sal_marina", "pimienta_negra"]
            }
        }
        
        # Ingredientes procesados prohibidos
        self.forbidden_ingredients = {
            "embutidos": ["chorizo", "salchichon", "mortadela", "salami", "jamon_cocido"],
            "procesados_carne": ["salchichas", "hamburguesas_congeladas", "nuggets", "bacon_procesado"],
            "lacteos_procesados": ["queso_procesado", "queso_americano", "nata_montada", "leche_condensada"],
            "salsas_comerciales": ["ketchup", "mayonesa_comercial", "salsa_barbacoa", "aderezos_embotellados"],
            "conservas_procesadas": ["atun_escabeche", "sardinas_salsa", "verduras_lata_azucar"],
            "cereales_refinados": ["arroz_blanco", "harina_refinada", "cereales_azucarados"],
            "azucares_procesados": ["azucar_blanco", "jarabe_maiz", "edulcorantes_artificiales"],
            "aceites_refinados": ["aceite_girasol_refinado", "margarina", "manteca_vegetal"],
            "aditivos": ["glutamato_monosodico", "conservantes", "colorantes", "saborizantes"]
        }
        
        # Criterios de validación nutricional
        self.macro_ranges = {
            "protein_min_percent": 15,
            "protein_max_percent": 35,
            "carbs_min_percent": 25,
            "carbs_max_percent": 65,
            "fat_min_percent": 15,
            "fat_max_percent": 35
        }
        
        # Criterios por timing nutricional
        self.timing_criteria = {
            "pre_entreno": {
                "carbs_target_percent": (50, 80),
                "protein_target_percent": (10, 20),
                "fat_target_percent": (5, 15),
                "fiber_max_g": 5,
                "calories_range": (150, 350)
            },
            "post_entreno": {
                "protein_target_percent": (30, 50),
                "carbs_target_percent": (35, 55),
                "fat_target_percent": (10, 25),
                "protein_min_g": 20,
                "calories_range": (250, 500)
            },
            "comida_principal": {
                "protein_target_percent": (20, 35),
                "carbs_target_percent": (35, 50),
                "fat_target_percent": (20, 35),
                "fiber_min_g": 8,
                "calories_range": (400, 700)
            },
            "snack_complemento": {
                "fat_target_percent": (25, 45),
                "protein_target_percent": (15, 30),
                "carbs_target_percent": (25, 60),
                "calories_range": (100, 300)
            }
        }
    
    def validate_recipe(self, recipe_data: Dict) -> Dict:
        """
        Validación completa de receta con puntuación 0-100
        """
        validation_result = {
            "overall_score": 0,
            "category_scores": {},
            "issues": [],
            "recommendations": [],
            "is_valid": False,
            "validation_details": {}
        }
        
        try:
            # 1. Validar ingredientes naturales (30 puntos)
            ingredients_score, ingredients_details = self._validate_ingredients(recipe_data)
            validation_result["category_scores"]["ingredients"] = ingredients_score
            validation_result["validation_details"]["ingredients"] = ingredients_details
            
            # 2. Validar coherencia nutricional (25 puntos)
            nutrition_score, nutrition_details = self._validate_nutrition(recipe_data)
            validation_result["category_scores"]["nutrition"] = nutrition_score
            validation_result["validation_details"]["nutrition"] = nutrition_details
            
            # 3. Validar timing apropiado (20 puntos)
            timing_score, timing_details = self._validate_timing(recipe_data)
            validation_result["category_scores"]["timing"] = timing_score
            validation_result["validation_details"]["timing"] = timing_details
            
            # 4. Validar practicidad meal prep (15 puntos)
            prep_score, prep_details = self._validate_meal_prep(recipe_data)
            validation_result["category_scores"]["meal_prep"] = prep_score
            validation_result["validation_details"]["meal_prep"] = prep_details
            
            # 5. Validar completitud de datos (10 puntos)
            completeness_score, completeness_details = self._validate_completeness(recipe_data)
            validation_result["category_scores"]["completeness"] = completeness_score
            validation_result["validation_details"]["completeness"] = completeness_details
            
            # Calcular puntuación total
            total_score = (
                ingredients_score * 0.30 +
                nutrition_score * 0.25 +
                timing_score * 0.20 +
                prep_score * 0.15 +
                completeness_score * 0.10
            )
            
            validation_result["overall_score"] = round(total_score)
            validation_result["is_valid"] = total_score >= 70  # Umbral de aprobación
            
            # Generar recomendaciones generales
            validation_result["recommendations"] = self._generate_recommendations(validation_result)
            
        except Exception as e:
            validation_result["issues"].append(f"Error en validación: {str(e)}")
            
        return validation_result
    
    def _validate_ingredients(self, recipe_data: Dict) -> Tuple[int, Dict]:
        """
        Validar que todos los ingredientes sean naturales y permitidos
        """
        score = 0
        details = {
            "natural_ingredients": [],
            "forbidden_found": [],
            "unrecognized": [],
            "categories_represented": []
        }
        
        ingredients = recipe_data.get("ingredientes", [])
        if not ingredients:
            return 0, details
        
        total_ingredients = len(ingredients)
        natural_count = 0
        forbidden_count = 0
        
        # Crear lista plana de ingredientes naturales
        all_natural = []
        for category, subcategories in self.natural_ingredients.items():
            for subcat, items in subcategories.items():
                all_natural.extend(items)
                
        # Crear lista plana de ingredientes prohibidos
        all_forbidden = []
        for category, items in self.forbidden_ingredients.items():
            all_forbidden.extend(items)
        
        for ingredient in ingredients:
            ingredient_name = ingredient.get("nombre", "").lower()
            
            # Normalizar nombre (quitar acentos, espacios, etc.)
            normalized_name = self._normalize_ingredient_name(ingredient_name)
            
            # Verificar si es natural
            if any(natural in normalized_name for natural in all_natural):
                natural_count += 1
                details["natural_ingredients"].append(ingredient_name)
                
                # Identificar categoría
                category = self._identify_ingredient_category(normalized_name)
                if category and category not in details["categories_represented"]:
                    details["categories_represented"].append(category)
            
            # Verificar si está prohibido
            elif any(forbidden in normalized_name for forbidden in all_forbidden):
                forbidden_count += 1
                details["forbidden_found"].append(ingredient_name)
            
            else:
                details["unrecognized"].append(ingredient_name)
        
        # Calcular puntuación
        if total_ingredients > 0:
            natural_ratio = natural_count / total_ingredients
            forbidden_penalty = forbidden_count * 10  # -10 puntos por ingrediente prohibido
            
            base_score = natural_ratio * 100
            final_score = max(0, base_score - forbidden_penalty)
            
            # Bonus por diversidad de categorías
            category_bonus = min(20, len(details["categories_represented"]) * 5)
            
            score = min(100, final_score + category_bonus)
        
        return int(score), details
    
    def _validate_nutrition(self, recipe_data: Dict) -> Tuple[int, Dict]:
        """
        Validar coherencia nutricional de macros
        """
        score = 0
        details = {
            "macros_analyzed": {},
            "ratios_calculated": {},
            "coherence_issues": [],
            "balance_assessment": ""
        }
        
        macros = recipe_data.get("macros_por_porcion", {})
        if not macros:
            return 0, details
        
        try:
            calories = macros.get("calorias", 0)
            protein_g = macros.get("proteinas", 0)
            carbs_g = macros.get("carbohidratos", 0)
            fat_g = macros.get("grasas", 0)
            
            if calories <= 0:
                details["coherence_issues"].append("Calorías inválidas o faltantes")
                return 0, details
            
            # Calcular calorías de macros
            calculated_calories = (protein_g * 4) + (carbs_g * 4) + (fat_g * 9)
            
            details["macros_analyzed"] = {
                "reported_calories": calories,
                "calculated_calories": calculated_calories,
                "protein_g": protein_g,
                "carbs_g": carbs_g,
                "fat_g": fat_g
            }
            
            # Verificar coherencia calórica (±10% tolerancia)
            calorie_difference = abs(calories - calculated_calories)
            calorie_tolerance = calories * 0.10
            
            if calorie_difference <= calorie_tolerance:
                coherence_score = 40
            else:
                coherence_score = max(0, 40 - (calorie_difference / calories * 100))
            
            # Calcular ratios de macronutrientes
            protein_percent = (protein_g * 4 / calories) * 100
            carbs_percent = (carbs_g * 4 / calories) * 100
            fat_percent = (fat_g * 9 / calories) * 100
            
            details["ratios_calculated"] = {
                "protein_percent": round(protein_percent, 1),
                "carbs_percent": round(carbs_percent, 1),
                "fat_percent": round(fat_percent, 1),
                "total_percent": round(protein_percent + carbs_percent + fat_percent, 1)
            }
            
            # Validar rangos de macronutrientes
            balance_score = 0
            
            # Proteína
            if self.macro_ranges["protein_min_percent"] <= protein_percent <= self.macro_ranges["protein_max_percent"]:
                balance_score += 20
            else:
                details["coherence_issues"].append(f"Proteína fuera de rango: {protein_percent:.1f}%")
            
            # Carbohidratos
            if self.macro_ranges["carbs_min_percent"] <= carbs_percent <= self.macro_ranges["carbs_max_percent"]:
                balance_score += 20
            else:
                details["coherence_issues"].append(f"Carbohidratos fuera de rango: {carbs_percent:.1f}%")
            
            # Grasas
            if self.macro_ranges["fat_min_percent"] <= fat_percent <= self.macro_ranges["fat_max_percent"]:
                balance_score += 20
            else:
                details["coherence_issues"].append(f"Grasas fuera de rango: {fat_percent:.1f}%")
            
            # Evaluación del balance
            total_percent = protein_percent + carbs_percent + fat_percent
            if 95 <= total_percent <= 105:
                balance_score += 20
                details["balance_assessment"] = "Balance nutricional excelente"
            elif 90 <= total_percent <= 110:
                balance_score += 10
                details["balance_assessment"] = "Balance nutricional bueno"
            else:
                details["balance_assessment"] = "Balance nutricional necesita ajustes"
            
            score = coherence_score + balance_score
            
        except Exception as e:
            details["coherence_issues"].append(f"Error en análisis nutricional: {str(e)}")
            score = 0
        
        return int(min(100, score)), details
    
    def _validate_timing(self, recipe_data: Dict) -> Tuple[int, Dict]:
        """
        Validar que la receta sea apropiada para su timing nutricional
        """
        score = 0
        details = {
            "declared_timing": "",
            "timing_analysis": {},
            "appropriateness_score": 0,
            "timing_recommendations": []
        }
        
        # Obtener timing declarado
        timing_category = recipe_data.get("categoria_timing", "")
        if not timing_category:
            details["timing_recommendations"].append("Categoría de timing no especificada")
            return 0, details
        
        details["declared_timing"] = timing_category
        
        # Obtener criterios para este timing
        criteria = self.timing_criteria.get(timing_category)
        if not criteria:
            details["timing_recommendations"].append(f"Timing category '{timing_category}' no reconocido")
            return 20, details  # Puntuación básica por tener timing
        
        macros = recipe_data.get("macros_por_porcion", {})
        if not macros:
            return 20, details
        
        try:
            calories = macros.get("calorias", 0)
            protein_g = macros.get("proteinas", 0)
            carbs_g = macros.get("carbohidratos", 0)
            fat_g = macros.get("grasas", 0)
            fiber_g = macros.get("fibra", 0)
            
            if calories <= 0:
                return 20, details
            
            # Calcular porcentajes de macros
            protein_percent = (protein_g * 4 / calories) * 100
            carbs_percent = (carbs_g * 4 / calories) * 100
            fat_percent = (fat_g * 9 / calories) * 100
            
            timing_score = 0
            max_timing_score = 80  # 80 puntos máximos por timing + 20 base
            
            # Validar rango calórico
            cal_min, cal_max = criteria.get("calories_range", (0, 1000))
            if cal_min <= calories <= cal_max:
                timing_score += 20
                details["timing_analysis"]["calories_appropriate"] = True
            else:
                details["timing_analysis"]["calories_appropriate"] = False
                details["timing_recommendations"].append(
                    f"Calorías ({calories}) fuera del rango recomendado para {timing_category}: {cal_min}-{cal_max}"
                )
            
            # Validar proteína
            if "protein_target_percent" in criteria:
                prot_min, prot_max = criteria["protein_target_percent"]
                if prot_min <= protein_percent <= prot_max:
                    timing_score += 20
                    details["timing_analysis"]["protein_appropriate"] = True
                else:
                    details["timing_analysis"]["protein_appropriate"] = False
                    details["timing_recommendations"].append(
                        f"Proteína ({protein_percent:.1f}%) fuera del rango para {timing_category}: {prot_min}-{prot_max}%"
                    )
            
            # Validar carbohidratos
            if "carbs_target_percent" in criteria:
                carbs_min, carbs_max = criteria["carbs_target_percent"]
                if carbs_min <= carbs_percent <= carbs_max:
                    timing_score += 20
                    details["timing_analysis"]["carbs_appropriate"] = True
                else:
                    details["timing_analysis"]["carbs_appropriate"] = False
                    details["timing_recommendations"].append(
                        f"Carbohidratos ({carbs_percent:.1f}%) fuera del rango para {timing_category}: {carbs_min}-{carbs_max}%"
                    )
            
            # Validar grasas
            if "fat_target_percent" in criteria:
                fat_min, fat_max = criteria["fat_target_percent"]
                if fat_min <= fat_percent <= fat_max:
                    timing_score += 20
                    details["timing_analysis"]["fat_appropriate"] = True
                else:
                    details["timing_analysis"]["fat_appropriate"] = False
                    details["timing_recommendations"].append(
                        f"Grasas ({fat_percent:.1f}%) fuera del rango para {timing_category}: {fat_min}-{fat_max}%"
                    )
            
            # Validaciones específicas por timing
            if timing_category == "pre_entreno" and "fiber_max_g" in criteria:
                if fiber_g <= criteria["fiber_max_g"]:
                    timing_score += 10
                else:
                    details["timing_recommendations"].append(
                        f"Fibra muy alta ({fiber_g}g) para pre-entreno. Máximo recomendado: {criteria['fiber_max_g']}g"
                    )
            
            elif timing_category == "post_entreno" and "protein_min_g" in criteria:
                if protein_g >= criteria["protein_min_g"]:
                    timing_score += 10
                else:
                    details["timing_recommendations"].append(
                        f"Proteína insuficiente ({protein_g}g) para post-entreno. Mínimo recomendado: {criteria['protein_min_g']}g"
                    )
            
            elif timing_category == "comida_principal" and "fiber_min_g" in criteria:
                if fiber_g >= criteria["fiber_min_g"]:
                    timing_score += 10
                else:
                    details["timing_recommendations"].append(
                        f"Fibra baja ({fiber_g}g) para comida principal. Mínimo recomendado: {criteria['fiber_min_g']}g"
                    )
            
            details["appropriateness_score"] = timing_score
            score = 20 + timing_score  # 20 puntos base + hasta 80 por timing apropiado
            
        except Exception as e:
            details["timing_recommendations"].append(f"Error en análisis de timing: {str(e)}")
            score = 20
        
        return int(min(100, score)), details
    
    def _validate_meal_prep(self, recipe_data: Dict) -> Tuple[int, Dict]:
        """
        Validar practicidad para meal prep
        """
        score = 0
        details = {
            "prep_time_score": 0,
            "conservation_score": 0,
            "practicality_issues": [],
            "prep_recommendations": []
        }
        
        try:
            # Validar tiempo de preparación
            prep_time = recipe_data.get("tiempo_prep", 0)
            if prep_time <= 30:
                prep_time_score = 50
            elif prep_time <= 45:
                prep_time_score = 35
            elif prep_time <= 60:
                prep_time_score = 20
            else:
                prep_time_score = 10
                details["practicality_issues"].append(f"Tiempo de preparación muy alto: {prep_time} minutos")
            
            details["prep_time_score"] = prep_time_score
            
            # Validar tips de meal prep
            meal_prep_tips = recipe_data.get("meal_prep_tips", [])
            if meal_prep_tips and len(meal_prep_tips) >= 2:
                conservation_score = 30
            elif meal_prep_tips and len(meal_prep_tips) >= 1:
                conservation_score = 20
            else:
                conservation_score = 10
                details["prep_recommendations"].append("Agregar consejos específicos de meal prep")
            
            details["conservation_score"] = conservation_score
            
            # Bonus por nivel de dificultad apropiado
            difficulty = recipe_data.get("dificultad", "")
            difficulty_stars = difficulty.count("⭐")
            
            if difficulty_stars <= 2:
                difficulty_bonus = 20
            elif difficulty_stars == 3:
                difficulty_bonus = 10
            else:
                difficulty_bonus = 0
                details["practicality_issues"].append("Dificultad muy alta para meal prep rutinario")
            
            score = prep_time_score + conservation_score + difficulty_bonus
            
        except Exception as e:
            details["practicality_issues"].append(f"Error en análisis de meal prep: {str(e)}")
            score = 20
        
        return int(min(100, score)), details
    
    def _validate_completeness(self, recipe_data: Dict) -> Tuple[int, Dict]:
        """
        Validar completitud de los datos de la receta
        """
        score = 0
        details = {
            "required_fields": [],
            "missing_fields": [],
            "completeness_percentage": 0
        }
        
        # Campos requeridos
        required_fields = [
            "nombre", "categoria_timing", "categoria_funcion", "dificultad",
            "tiempo_prep", "porciones", "ingredientes", "preparacion",
            "macros_por_porcion", "meal_prep_tips", "timing_consumo"
        ]
        
        present_fields = []
        missing_fields = []
        
        for field in required_fields:
            if field in recipe_data and recipe_data[field]:
                present_fields.append(field)
            else:
                missing_fields.append(field)
        
        details["required_fields"] = required_fields
        details["missing_fields"] = missing_fields
        
        # Calcular completitud
        completeness_percentage = (len(present_fields) / len(required_fields)) * 100
        details["completeness_percentage"] = round(completeness_percentage, 1)
        
        # Validaciones específicas
        validation_bonus = 0
        
        # Ingredientes deben tener estructura completa
        ingredients = recipe_data.get("ingredientes", [])
        if ingredients:
            complete_ingredients = 0
            for ingredient in ingredients:
                if all(key in ingredient for key in ["nombre", "cantidad", "unidad"]):
                    complete_ingredients += 1
            
            if complete_ingredients == len(ingredients):
                validation_bonus += 20
            elif complete_ingredients >= len(ingredients) * 0.8:
                validation_bonus += 10
        
        # Macros deben estar completos
        macros = recipe_data.get("macros_por_porcion", {})
        required_macros = ["calorias", "proteinas", "carbohidratos", "grasas"]
        if all(macro in macros for macro in required_macros):
            validation_bonus += 20
        
        # Preparación debe tener pasos detallados
        preparation = recipe_data.get("preparacion", [])
        if preparation and len(preparation) >= 3:
            validation_bonus += 10
        
        score = completeness_percentage + validation_bonus
        
        return int(min(100, score)), details
    
    def _normalize_ingredient_name(self, name: str) -> str:
        """
        Normalizar nombre de ingrediente para comparación
        """
        # Convertir a minúsculas
        normalized = name.lower()
        
        # Remover acentos básicos
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u'
        }
        
        for accented, normal in replacements.items():
            normalized = normalized.replace(accented, normal)
        
        # Remover espacios extra y caracteres especiales
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        normalized = re.sub(r'\s+', '_', normalized.strip())
        
        return normalized
    
    def _identify_ingredient_category(self, normalized_name: str) -> Optional[str]:
        """
        Identificar categoría de ingrediente
        """
        for main_category, subcategories in self.natural_ingredients.items():
            for subcat, ingredients in subcategories.items():
                if any(ingredient in normalized_name for ingredient in ingredients):
                    return main_category
        return None
    
    def _generate_recommendations(self, validation_result: Dict) -> List[str]:
        """
        Generar recomendaciones basadas en los resultados de validación
        """
        recommendations = []
        scores = validation_result["category_scores"]
        
        # Recomendaciones por categoría baja
        if scores.get("ingredients", 0) < 70:
            recommendations.append(
                "🥗 Reemplaza ingredientes procesados por alternativas naturales"
            )
            recommendations.append(
                "🌿 Incluye más variedad de categorías: proteínas, carbohidratos, grasas saludables"
            )
        
        if scores.get("nutrition", 0) < 70:
            recommendations.append(
                "⚖️ Ajusta las proporciones de macronutrientes para mejor balance"
            )
            recommendations.append(
                "🔢 Verifica que las calorías calculadas coincidan con los macros"
            )
        
        if scores.get("timing", 0) < 70:
            recommendations.append(
                "⏰ Ajusta la composición nutricional según el timing de consumo"
            )
            recommendations.append(
                "🎯 Considera los objetivos específicos de esta categoría de timing"
            )
        
        if scores.get("meal_prep", 0) < 70:
            recommendations.append(
                "📦 Simplifica la preparación para hacer la receta más práctica"
            )
            recommendations.append(
                "❄️ Agrega consejos específicos de conservación y almacenamiento"
            )
        
        if scores.get("completeness", 0) < 70:
            recommendations.append(
                "📝 Completa todos los campos requeridos de la receta"
            )
            recommendations.append(
                "📏 Especifica cantidades y unidades precisas para todos los ingredientes"
            )
        
        # Recomendación general
        overall_score = validation_result["overall_score"]
        if overall_score >= 90:
            recommendations.insert(0, "🏆 ¡Excelente receta! Cumple todos los estándares de calidad")
        elif overall_score >= 80:
            recommendations.insert(0, "✅ Buena receta con ajustes menores recomendados")
        elif overall_score >= 70:
            recommendations.insert(0, "⚠️ Receta aceptable que necesita mejoras importantes")
        else:
            recommendations.insert(0, "❌ Receta necesita revisión completa antes de usar")
        
        return recommendations[:6]  # Máximo 6 recomendaciones

# Ejemplo de uso
if __name__ == "__main__":
    validator = RecipeValidator()
    
    # Ejemplo de receta para validar
    sample_recipe = {
        "nombre": "Pollo mediterráneo con quinoa",
        "categoria_timing": "post_entreno",
        "categoria_funcion": "sintesis_proteica",
        "dificultad": "⭐⭐",
        "tiempo_prep": 35,
        "porciones": 4,
        "ingredientes": [
            {"nombre": "Pechuga de pollo", "cantidad": 400, "unidad": "g", "categoria": "proteina_animal"},
            {"nombre": "Quinoa", "cantidad": 200, "unidad": "g", "categoria": "carbohidrato_complejo"},
            {"nombre": "Aceite de oliva virgen", "cantidad": 30, "unidad": "ml", "categoria": "grasa_saludable"}
        ],
        "preparacion": [
            "1. Cocinar quinoa según instrucciones del paquete",
            "2. Salpimentar y cocinar pollo a la plancha",
            "3. Mezclar con aceite de oliva y servir"
        ],
        "macros_por_porcion": {
            "calorias": 380,
            "proteinas": 35,
            "carbohidratos": 28,
            "grasas": 12,
            "fibra": 4
        },
        "meal_prep_tips": [
            "Se conserva 4-5 días en refrigerador",
            "Separar salsa para mantener textura"
        ],
        "timing_consumo": "Inmediatamente después del entrenamiento"
    }
    
    # Validar receta
    result = validator.validate_recipe(sample_recipe)
    
    print("=== RESULTADO DE VALIDACIÓN ===")
    print(f"Puntuación total: {result['overall_score']}/100")
    print(f"Receta válida: {result['is_valid']}")
    print("\nPuntuaciones por categoría:")
    for category, score in result['category_scores'].items():
        print(f"  {category}: {score}/100")
    
    print("\nRecomendaciones:")
    for rec in result['recommendations']:
        print(f"  - {rec}")