#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Analíticas Nutricionales Profundas
Análisis avanzado de patrones nutricionales, adherencia al plan,
balances de micronutrientes y optimizaciones basadas en datos
"""

import json
import math
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter

class NutritionAnalytics:
    
    def __init__(self):
        # Base de datos de micronutrientes por alimento (mg/100g)
        self.micronutrient_database = {
            # Proteínas
            "pollo": {"hierro": 1.3, "zinc": 2.9, "b12": 0.31, "magnesio": 25, "potasio": 256, "calcio": 15},
            "salmon": {"hierro": 0.8, "zinc": 0.6, "b12": 4.9, "magnesio": 30, "potasio": 363, "calcio": 12},
            "huevos": {"hierro": 1.2, "zinc": 1.1, "b12": 0.89, "magnesio": 12, "potasio": 126, "calcio": 50},
            "ternera": {"hierro": 2.6, "zinc": 4.5, "b12": 2.64, "magnesio": 21, "potasio": 318, "calcio": 18},
            
            # Carbohidratos
            "quinoa": {"hierro": 4.6, "zinc": 3.1, "b12": 0.0, "magnesio": 197, "potasio": 563, "calcio": 47},
            "arroz_integral": {"hierro": 1.5, "zinc": 2.0, "b12": 0.0, "magnesio": 143, "potasio": 223, "calcio": 23},
            "avena": {"hierro": 4.7, "zinc": 4.0, "b12": 0.0, "magnesio": 177, "potasio": 429, "calcio": 54},
            
            # Verduras
            "espinacas": {"hierro": 2.7, "zinc": 0.5, "b12": 0.0, "magnesio": 79, "potasio": 558, "calcio": 99},
            "brocoli": {"hierro": 0.7, "zinc": 0.4, "b12": 0.0, "magnesio": 21, "potasio": 316, "calcio": 47},
            "tomate": {"hierro": 0.3, "zinc": 0.2, "b12": 0.0, "magnesio": 11, "potasio": 237, "calcio": 10},
            
            # Frutos secos
            "almendras": {"hierro": 3.7, "zinc": 3.1, "b12": 0.0, "magnesio": 270, "potasio": 733, "calcio": 269},
            "nueces": {"hierro": 2.9, "zinc": 3.1, "b12": 0.0, "magnesio": 158, "potasio": 441, "calcio": 98},
            
            # Lácteos
            "yogur_griego": {"hierro": 0.1, "zinc": 0.6, "b12": 0.75, "magnesio": 11, "potasio": 141, "calcio": 110},
            "queso_feta": {"hierro": 0.7, "zinc": 2.9, "b12": 1.69, "magnesio": 19, "potasio": 62, "calcio": 493}
        }
        
        # Requerimientos diarios recomendados (RDA) por edad/sexo
        self.rda_requirements = {
            "masculino": {
                "18-30": {"hierro": 8, "zinc": 11, "b12": 2.4, "magnesio": 400, "potasio": 3500, "calcio": 1000},
                "31-50": {"hierro": 8, "zinc": 11, "b12": 2.4, "magnesio": 420, "potasio": 3500, "calcio": 1000},
                "51+": {"hierro": 8, "zinc": 11, "b12": 2.4, "magnesio": 420, "potasio": 3500, "calcio": 1200}
            },
            "femenino": {
                "18-30": {"hierro": 18, "zinc": 8, "b12": 2.4, "magnesio": 310, "potasio": 2600, "calcio": 1000},
                "31-50": {"hierro": 18, "zinc": 8, "b12": 2.4, "magnesio": 320, "potasio": 2600, "calcio": 1000},
                "51+": {"hierro": 8, "zinc": 8, "b12": 2.4, "magnesio": 320, "potasio": 2600, "calcio": 1200}
            }
        }
        
        # Factores de absorción por interacciones alimentarias
        self.absorption_factors = {
            "hierro": {
                "enhancers": {"vitamina_c": 1.5, "carne": 1.3, "pescado": 1.2},
                "inhibitors": {"cafe": 0.6, "te": 0.7, "calcio": 0.8, "fibra": 0.9}
            },
            "zinc": {
                "enhancers": {"proteina_animal": 1.2},
                "inhibitors": {"fibra": 0.8, "calcio": 0.7, "hierro": 0.9}
            },
            "calcio": {
                "enhancers": {"vitamina_d": 1.4, "lactosa": 1.1},
                "inhibitors": {"oxalatos": 0.7, "fitatos": 0.8, "exceso_magnesio": 0.9}
            }
        }
        
        # Patrones de adherencia al plan
        self.adherence_patterns = {
            "excellent": {"threshold": 95, "description": "Adherencia excelente"},
            "very_good": {"threshold": 85, "description": "Muy buena adherencia"},
            "good": {"threshold": 75, "description": "Buena adherencia"},
            "moderate": {"threshold": 65, "description": "Adherencia moderada"},
            "poor": {"threshold": 50, "description": "Baja adherencia"},
            "very_poor": {"threshold": 0, "description": "Adherencia muy baja"}
        }
        
        # Algoritmos de scoring nutricional
        self.nutrition_scoring = {
            "macro_balance": 0.25,      # Distribución de macronutrientes
            "micronutrient_density": 0.20,  # Densidad de micronutrientes
            "food_variety": 0.15,       # Variedad de alimentos
            "timing_optimization": 0.15, # Optimización de timing
            "adherence_consistency": 0.25  # Consistencia en la adherencia
        }
    
    def generate_comprehensive_analysis(self, user_profile: Dict, analysis_period: str = "month") -> Dict:
        """
        Generar análisis nutricional completo y profundo
        """
        try:
            # Recopilar datos del período
            period_data = self._collect_period_data(user_profile, analysis_period)
            
            if not period_data["has_sufficient_data"]:
                return {
                    "success": False,
                    "error": "Datos insuficientes para análisis completo",
                    "suggestions": [
                        "Registra al menos 7 días de datos",
                        "Usa /valorar_receta regularmente",
                        "Trackea métricas con /progreso"
                    ]
                }
            
            # Análisis de macronutrientes
            macro_analysis = self._analyze_macronutrient_patterns(period_data, user_profile)
            
            # Análisis de micronutrientes
            micro_analysis = self._analyze_micronutrient_status(period_data, user_profile)
            
            # Análisis de adherencia al plan
            adherence_analysis = self._analyze_plan_adherence(period_data, user_profile)
            
            # Análisis de timing nutricional
            timing_analysis = self._analyze_nutritional_timing(period_data, user_profile)
            
            # Análisis de variedad alimentaria
            variety_analysis = self._analyze_food_variety(period_data)
            
            # Análisis de progreso correlacional
            progress_correlation = self._analyze_progress_correlation(period_data, user_profile)
            
            # Puntuación nutricional global
            nutrition_score = self._calculate_nutrition_score(
                macro_analysis, micro_analysis, adherence_analysis, timing_analysis, variety_analysis
            )
            
            # Recomendaciones personalizadas
            personalized_recommendations = self._generate_personalized_recommendations(
                macro_analysis, micro_analysis, adherence_analysis, timing_analysis, variety_analysis, user_profile
            )
            
            return {
                "success": True,
                "analysis_period": analysis_period,
                "generated_at": datetime.now().isoformat(),
                "data_quality": period_data["data_quality"],
                "macro_analysis": macro_analysis,
                "micronutrient_analysis": micro_analysis,
                "adherence_analysis": adherence_analysis,
                "timing_analysis": timing_analysis,
                "variety_analysis": variety_analysis,
                "progress_correlation": progress_correlation,
                "nutrition_score": nutrition_score,
                "personalized_recommendations": personalized_recommendations,
                "next_steps": self._generate_next_steps(nutrition_score, user_profile)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error in comprehensive analysis: {str(e)}"
            }
    
    def _collect_period_data(self, user_profile: Dict, period: str) -> Dict:
        """
        Recopilar todos los datos relevantes del período de análisis
        """
        period_days = {"week": 7, "month": 30, "quarter": 90}.get(period, 30)
        cutoff_date = datetime.now() - timedelta(days=period_days)
        
        # Datos de progress tracking
        progress_data = user_profile.get("progress_tracking", {})
        progress_metrics = {}
        
        for metric_name, records in progress_data.get("metrics", {}).items():
            period_records = [
                record for record in records
                if datetime.fromisoformat(record["timestamp"]) >= cutoff_date
            ]
            progress_metrics[metric_name] = period_records
        
        # Datos de valoraciones de recetas
        recipe_intelligence = user_profile.get("recipe_intelligence", {})
        ratings_history = [
            rating for rating in recipe_intelligence.get("ratings_history", [])
            if datetime.fromisoformat(rating["timestamp"]) >= cutoff_date
        ]
        
        # Datos de recetas generadas/consumidas (estimación)
        generated_recipes = []  # Se populará desde la base de datos externa
        
        # Evaluar calidad de datos
        data_quality = self._assess_data_quality(progress_metrics, ratings_history, period_days)
        
        return {
            "period_days": period_days,
            "cutoff_date": cutoff_date,
            "progress_metrics": progress_metrics,
            "ratings_history": ratings_history,
            "generated_recipes": generated_recipes,
            "data_quality": data_quality,
            "has_sufficient_data": data_quality["overall_score"] >= 60
        }
    
    def _assess_data_quality(self, progress_metrics: Dict, ratings_history: List, period_days: int) -> Dict:
        """
        Evaluar la calidad y suficiencia de los datos para análisis
        """
        # Puntuación por métricas de progreso
        progress_score = 0
        if progress_metrics:
            total_records = sum(len(records) for records in progress_metrics.values())
            metrics_variety = len(progress_metrics)
            
            # Score basado en cantidad y variedad
            record_density = min(total_records / period_days, 1.0) * 50  # Hasta 50 puntos
            variety_score = min(metrics_variety / 4, 1.0) * 30  # Hasta 30 puntos (4 métricas clave)
            progress_score = record_density + variety_score
        
        # Puntuación por valoraciones de recetas
        ratings_score = 0
        if ratings_history:
            ratings_count = len(ratings_history)
            ratings_variety = len(set(r["rating"] for r in ratings_history))
            
            frequency_score = min(ratings_count / (period_days / 3), 1.0) * 15  # Hasta 15 puntos
            variety_score = min(ratings_variety / 5, 1.0) * 5  # Hasta 5 puntos
            ratings_score = frequency_score + variety_score
        
        overall_score = progress_score + ratings_score
        
        return {
            "progress_data_score": round(progress_score, 1),
            "ratings_data_score": round(ratings_score, 1),
            "overall_score": round(overall_score, 1),
            "data_completeness": "Alta" if overall_score >= 80 else "Media" if overall_score >= 60 else "Baja",
            "recommendations": self._get_data_quality_recommendations(overall_score)
        }
    
    def _get_data_quality_recommendations(self, score: float) -> List[str]:
        """
        Obtener recomendaciones para mejorar calidad de datos
        """
        recommendations = []
        
        if score < 40:
            recommendations.extend([
                "📊 Registra métricas diariamente con /progreso",
                "⭐ Valora recetas con /valorar_receta",
                "📅 Usa el bot consistentemente por al menos 1 semana"
            ])
        elif score < 70:
            recommendations.extend([
                "📈 Aumenta frecuencia de tracking de métricas",
                "🎯 Valora más variedad de recetas (escala 1-5)",
                "🔄 Mantén consistencia en el uso del bot"
            ])
        else:
            recommendations.append("✅ Calidad de datos excelente para análisis profundo")
        
        return recommendations
    
    def _analyze_macronutrient_patterns(self, period_data: Dict, user_profile: Dict) -> Dict:
        """
        Analizar patrones de distribución de macronutrientes
        """
        target_macros = user_profile["macros"]
        target_protein = target_macros["protein_g"]
        target_carbs = target_macros["carbs_g"]
        target_fat = target_macros["fat_g"]
        target_calories = target_macros["calories"]
        
        # Simular datos de macros consumidos basándose en valoraciones y progreso
        # En implementación real, esto vendría de un registro de comidas detallado
        consumed_data = self._estimate_consumed_macros_from_available_data(period_data, user_profile)
        
        analysis = {
            "target_distribution": {
                "protein_pct": round((target_protein * 4 / target_calories) * 100, 1),
                "carbs_pct": round((target_carbs * 4 / target_calories) * 100, 1),
                "fat_pct": round((target_fat * 9 / target_calories) * 100, 1)
            },
            "actual_distribution": consumed_data["distribution"],
            "adherence_score": consumed_data["adherence_score"],
            "patterns_detected": self._detect_macro_patterns(consumed_data, period_data),
            "optimization_opportunities": []
        }
        
        # Identificar oportunidades de optimización
        protein_deviation = abs(analysis["actual_distribution"]["protein_pct"] - analysis["target_distribution"]["protein_pct"])
        carbs_deviation = abs(analysis["actual_distribution"]["carbs_pct"] - analysis["target_distribution"]["carbs_pct"])
        fat_deviation = abs(analysis["actual_distribution"]["fat_pct"] - analysis["target_distribution"]["fat_pct"])
        
        if protein_deviation > 5:
            analysis["optimization_opportunities"].append({
                "type": "protein_adjustment",
                "description": f"Ajustar proteína: objetivo {analysis['target_distribution']['protein_pct']}%, actual {analysis['actual_distribution']['protein_pct']}%",
                "priority": "alta" if protein_deviation > 10 else "media"
            })
        
        if carbs_deviation > 10:
            analysis["optimization_opportunities"].append({
                "type": "carbs_adjustment", 
                "description": f"Ajustar carbohidratos: objetivo {analysis['target_distribution']['carbs_pct']}%, actual {analysis['actual_distribution']['carbs_pct']}%",
                "priority": "alta" if carbs_deviation > 15 else "media"
            })
        
        if fat_deviation > 8:
            analysis["optimization_opportunities"].append({
                "type": "fat_adjustment",
                "description": f"Ajustar grasas: objetivo {analysis['target_distribution']['fat_pct']}%, actual {analysis['actual_distribution']['fat_pct']}%",
                "priority": "media"
            })
        
        return analysis
    
    def _estimate_consumed_macros_from_available_data(self, period_data: Dict, user_profile: Dict) -> Dict:
        """
        Estimar macros consumidos basándose en datos disponibles
        """
        target_macros = user_profile["macros"]
        
        # Usar datos de progreso para inferir adherencia
        weight_trend = self._get_weight_trend_from_progress(period_data["progress_metrics"])
        energy_level = self._get_average_energy_level(period_data["progress_metrics"])
        ratings_preference = self._get_macro_preference_from_ratings(period_data["ratings_history"])
        
        # Estimar adherencia basándose en progreso
        objective = user_profile["basic_data"]["objetivo"]
        expected_weight_change = self._get_expected_weight_change(objective)
        adherence_factor = self._calculate_adherence_from_weight_trend(weight_trend, expected_weight_change)
        
        # Simular distribución de macros consumidos
        base_protein_pct = (target_macros["protein_g"] * 4 / target_macros["calories"]) * 100
        base_carbs_pct = (target_macros["carbs_g"] * 4 / target_macros["calories"]) * 100
        base_fat_pct = (target_macros["fat_g"] * 9 / target_macros["calories"]) * 100
        
        # Ajustar por preferencias inferidas de ratings
        protein_adjustment = ratings_preference.get("protein_bias", 0)
        carbs_adjustment = ratings_preference.get("carbs_bias", 0)
        fat_adjustment = ratings_preference.get("fat_bias", 0)
        
        actual_protein_pct = base_protein_pct + protein_adjustment
        actual_carbs_pct = base_carbs_pct + carbs_adjustment
        actual_fat_pct = base_fat_pct + fat_adjustment
        
        # Normalizar para que sume 100%
        total = actual_protein_pct + actual_carbs_pct + actual_fat_pct
        actual_protein_pct = round((actual_protein_pct / total) * 100, 1)
        actual_carbs_pct = round((actual_carbs_pct / total) * 100, 1)
        actual_fat_pct = round((actual_fat_pct / total) * 100, 1)
        
        return {
            "distribution": {
                "protein_pct": actual_protein_pct,
                "carbs_pct": actual_carbs_pct,
                "fat_pct": actual_fat_pct
            },
            "adherence_score": round(adherence_factor * 100, 1),
            "data_confidence": "media"  # Indicar que son estimaciones
        }
    
    def _analyze_micronutrient_status(self, period_data: Dict, user_profile: Dict) -> Dict:
        """
        Analizar estado de micronutrientes basándose en preferencias alimentarias
        """
        age = user_profile["basic_data"]["edad"]
        sex = user_profile["basic_data"]["sexo"]
        
        # Determinar grupo de edad para RDA
        age_group = "18-30" if age < 31 else "31-50" if age < 51 else "51+"
        rda = self.rda_requirements[sex][age_group]
        
        # Estimar ingesta de micronutrientes basándose en preferencias
        liked_foods = user_profile.get("preferences", {}).get("liked_foods", [])
        estimated_intake = self._estimate_micronutrient_intake(liked_foods, period_data)
        
        # Calcular ratios de cumplimiento
        micronutrient_status = {}
        for nutrient, requirement in rda.items():
            intake = estimated_intake.get(nutrient, requirement * 0.6)  # Default conservador
            ratio = intake / requirement
            
            status = "deficiente" if ratio < 0.7 else "bajo" if ratio < 0.9 else "adecuado" if ratio < 1.2 else "alto"
            
            micronutrient_status[nutrient] = {
                "requirement": requirement,
                "estimated_intake": round(intake, 2),
                "fulfillment_ratio": round(ratio, 2),
                "status": status,
                "confidence": "baja"  # Basado en estimaciones
            }
        
        # Identificar deficiencias críticas
        critical_deficiencies = [
            nutrient for nutrient, data in micronutrient_status.items()
            if data["fulfillment_ratio"] < 0.7
        ]
        
        # Identificar fortalezas nutricionales
        nutritional_strengths = [
            nutrient for nutrient, data in micronutrient_status.items()
            if data["fulfillment_ratio"] >= 1.0
        ]
        
        return {
            "user_rda_profile": {"age_group": age_group, "sex": sex},
            "micronutrient_status": micronutrient_status,
            "critical_deficiencies": critical_deficiencies,
            "nutritional_strengths": nutritional_strengths,
            "overall_micronutrient_score": self._calculate_micronutrient_score(micronutrient_status),
            "improvement_recommendations": self._generate_micronutrient_recommendations(micronutrient_status, liked_foods)
        }
    
    def _estimate_micronutrient_intake(self, liked_foods: List[str], period_data: Dict) -> Dict:
        """
        Estimar ingesta de micronutrientes basándose en preferencias alimentarias
        """
        estimated_intake = defaultdict(float)
        
        # Mapear preferencias a alimentos específicos
        food_mapping = {
            "aves": ["pollo"],
            "pescados": ["salmon"],
            "huevos": ["huevos"],
            "carnes_rojas": ["ternera"],
            "frutos_secos": ["almendras", "nueces"],
            "lacteos": ["yogur_griego", "queso_feta"],
            "cruciferas": ["brocoli"],
            "verduras_verdes": ["espinacas"]
        }
        
        # Calcular ingesta estimada
        total_weight = 0
        
        for food_category in liked_foods:
            if food_category in food_mapping:
                for food in food_mapping[food_category]:
                    if food in self.micronutrient_database:
                        # Estimar consumo semanal (gramos)
                        weekly_consumption = 200  # Estimación conservadora
                        daily_consumption = weekly_consumption / 7
                        portion_factor = daily_consumption / 100  # Convertir a factor por 100g
                        
                        for nutrient, content_per_100g in self.micronutrient_database[food].items():
                            estimated_intake[nutrient] += content_per_100g * portion_factor
                        
                        total_weight += daily_consumption
        
        # Si no se tienen preferencias específicas, usar perfil promedio
        if not liked_foods or total_weight < 50:  # Muy poco consumo estimado
            default_foods = ["pollo", "arroz_integral", "brocoli", "almendras"]
            for food in default_foods:
                daily_consumption = 75  # 75g por alimento
                portion_factor = daily_consumption / 100
                
                for nutrient, content_per_100g in self.micronutrient_database[food].items():
                    estimated_intake[nutrient] += content_per_100g * portion_factor
        
        return dict(estimated_intake)
    
    def _analyze_plan_adherence(self, period_data: Dict, user_profile: Dict) -> Dict:
        """
        Analizar adherencia al plan nutricional
        """
        # Inferir adherencia de múltiples fuentes de datos
        weight_adherence = self._calculate_weight_based_adherence(period_data, user_profile)
        energy_adherence = self._calculate_energy_based_adherence(period_data)
        rating_adherence = self._calculate_rating_based_adherence(period_data)
        
        # Combinar métricas de adherencia
        adherence_scores = [score for score in [weight_adherence, energy_adherence, rating_adherence] if score is not None]
        
        if adherence_scores:
            overall_adherence = sum(adherence_scores) / len(adherence_scores)
        else:
            overall_adherence = 70  # Default conservador
        
        # Clasificar nivel de adherencia
        adherence_level = self._classify_adherence_level(overall_adherence)
        
        # Identificar patrones de adherencia
        patterns = self._identify_adherence_patterns(period_data, overall_adherence)
        
        return {
            "overall_adherence_score": round(overall_adherence, 1),
            "adherence_level": adherence_level,
            "component_scores": {
                "weight_based": weight_adherence,
                "energy_based": energy_adherence,
                "rating_based": rating_adherence
            },
            "patterns_identified": patterns,
            "consistency_rating": self._calculate_consistency_rating(period_data),
            "improvement_areas": self._identify_improvement_areas(overall_adherence, patterns)
        }
    
    def _analyze_nutritional_timing(self, period_data: Dict, user_profile: Dict) -> Dict:
        """
        Analizar patrones de timing nutricional
        """
        exercise_profile = user_profile.get("exercise_profile", {})
        training_schedule = exercise_profile.get("training_schedule", "variable")
        
        # Analizar timing inferido de valoraciones de recetas
        timing_preferences = defaultdict(list)
        
        for rating in period_data["ratings_history"]:
            recipe_data = rating.get("recipe_data", {})
            timing_category = recipe_data.get("categoria_timing", "comida_principal")
            rating_score = rating["rating"]
            
            timing_preferences[timing_category].append(rating_score)
        
        # Calcular scores promedio por timing
        timing_analysis = {}
        for timing, ratings in timing_preferences.items():
            if ratings:
                avg_rating = sum(ratings) / len(ratings)
                timing_analysis[timing] = {
                    "average_rating": round(avg_rating, 2),
                    "sample_size": len(ratings),
                    "preference_level": "Alta" if avg_rating >= 4 else "Media" if avg_rating >= 3 else "Baja"
                }
        
        # Evaluar optimización de timing
        timing_optimization_score = self._calculate_timing_optimization_score(
            timing_analysis, training_schedule, user_profile
        )
        
        return {
            "training_schedule": training_schedule,
            "timing_preferences": timing_analysis,
            "optimization_score": timing_optimization_score,
            "recommendations": self._generate_timing_recommendations(timing_analysis, training_schedule),
            "alignment_with_goals": self._assess_timing_goal_alignment(timing_analysis, user_profile)
        }
    
    def _analyze_food_variety(self, period_data: Dict) -> Dict:
        """
        Analizar variedad alimentaria y diversidad nutricional
        """
        # Extraer alimentos/ingredientes de valoraciones
        ingredients_rated = []
        recipes_types = []
        
        for rating in period_data["ratings_history"]:
            recipe_data = rating.get("recipe_data", {})
            recipe_name = recipe_data.get("nombre", "").lower()
            
            # Inferir ingredientes principales del nombre de la receta
            detected_ingredients = self._detect_ingredients_from_recipe_name(recipe_name)
            ingredients_rated.extend(detected_ingredients)
            
            # Categorizar tipo de receta
            recipe_type = self._categorize_recipe_type(recipe_name)
            if recipe_type:
                recipes_types.append(recipe_type)
        
        # Calcular métricas de variedad
        unique_ingredients = len(set(ingredients_rated))
        unique_recipe_types = len(set(recipes_types))
        total_recipes = len(period_data["ratings_history"])
        
        variety_score = self._calculate_variety_score(unique_ingredients, unique_recipe_types, total_recipes)
        
        return {
            "unique_ingredients_count": unique_ingredients,
            "unique_recipe_types_count": unique_recipe_types,
            "total_recipes_evaluated": total_recipes,
            "variety_score": variety_score,
            "variety_level": self._classify_variety_level(variety_score),
            "most_common_ingredients": self._get_most_common_items(ingredients_rated, 5),
            "most_common_recipe_types": self._get_most_common_items(recipes_types, 3),
            "diversity_recommendations": self._generate_variety_recommendations(variety_score, ingredients_rated)
        }
    
    def _analyze_progress_correlation(self, period_data: Dict, user_profile: Dict) -> Dict:
        """
        Analizar correlaciones entre patrones nutricionales y progreso
        """
        progress_metrics = period_data["progress_metrics"]
        correlations = {}
        
        # Correlación entre valoraciones altas y energía
        if "energy_level" in progress_metrics and period_data["ratings_history"]:
            energy_correlation = self._calculate_energy_rating_correlation(
                progress_metrics["energy_level"], period_data["ratings_history"]
            )
            correlations["energy_satisfaction"] = energy_correlation
        
        # Correlación entre adherencia y progreso de peso
        if "weight" in progress_metrics:
            weight_progress_correlation = self._calculate_weight_adherence_correlation(
                progress_metrics["weight"], user_profile
            )
            correlations["weight_adherence"] = weight_progress_correlation
        
        # Correlaciones con calidad de sueño
        if "sleep_quality" in progress_metrics:
            sleep_correlation = self._calculate_sleep_nutrition_correlation(
                progress_metrics["sleep_quality"], period_data["ratings_history"]
            )
            correlations["sleep_nutrition"] = sleep_correlation
        
        return {
            "correlations_found": correlations,
            "correlation_strength": self._assess_overall_correlation_strength(correlations),
            "insights": self._generate_correlation_insights(correlations, user_profile),
            "actionable_findings": self._extract_actionable_findings(correlations)
        }
    
    def _calculate_nutrition_score(self, macro_analysis: Dict, micro_analysis: Dict, 
                                 adherence_analysis: Dict, timing_analysis: Dict, 
                                 variety_analysis: Dict) -> Dict:
        """
        Calcular puntuación nutricional global
        """
        # Scores individuales (0-100)
        macro_score = 100 - (abs(macro_analysis["adherence_score"] - 100))  # Invertir para que 100 sea mejor
        micro_score = micro_analysis["overall_micronutrient_score"]
        adherence_score = adherence_analysis["overall_adherence_score"]
        timing_score = timing_analysis["optimization_score"]
        variety_score = variety_analysis["variety_score"]
        
        # Aplicar pesos
        weighted_score = (
            macro_score * self.nutrition_scoring["macro_balance"] +
            micro_score * self.nutrition_scoring["micronutrient_density"] + 
            adherence_score * self.nutrition_scoring["adherence_consistency"] +
            timing_score * self.nutrition_scoring["timing_optimization"] +
            variety_score * self.nutrition_scoring["food_variety"]
        )
        
        # Clasificar puntuación
        if weighted_score >= 90:
            grade = "A+ Excelente"
            description = "Nutrición óptima en todos los aspectos"
        elif weighted_score >= 80:
            grade = "A Muy Bueno"
            description = "Nutrición muy buena con áreas menores de mejora"
        elif weighted_score >= 70:
            grade = "B Bueno"
            description = "Buena nutrición con oportunidades de optimización"
        elif weighted_score >= 60:
            grade = "C Regular"
            description = "Nutrición adecuada, requiere mejoras significativas"
        else:
            grade = "D Necesita Mejoras"
            description = "Nutrición subóptima, requiere intervención"
        
        return {
            "overall_score": round(weighted_score, 1),
            "grade": grade,
            "description": description,
            "component_scores": {
                "macro_balance": round(macro_score, 1),
                "micronutrient_density": round(micro_score, 1),
                "adherence_consistency": round(adherence_score, 1),
                "timing_optimization": round(timing_score, 1),
                "food_variety": round(variety_score, 1)
            },
            "strengths": self._identify_nutrition_strengths(
                macro_score, micro_score, adherence_score, timing_score, variety_score
            ),
            "improvement_priorities": self._identify_improvement_priorities(
                macro_score, micro_score, adherence_score, timing_score, variety_score
            )
        }
    
    def format_analysis_for_telegram(self, analysis_data: Dict, user_profile: Dict) -> str:
        """
        Formatear análisis nutricional completo para mostrar en Telegram
        """
        if not analysis_data["success"]:
            return f"❌ **Error en análisis nutricional:** {analysis_data.get('error', 'Error desconocido')}"
        
        # Encabezado
        text = f"""
🧬 **ANÁLISIS NUTRICIONAL PROFUNDO**

👤 **Usuario:** {user_profile['basic_data']['objetivo_descripcion']}
📅 **Período:** {analysis_data['analysis_period'].title()}
🎯 **Calidad de datos:** {analysis_data['data_quality']['data_completeness']}

📊 **PUNTUACIÓN NUTRICIONAL GLOBAL: {analysis_data['nutrition_score']['overall_score']}/100**
🏆 **Calificación:** {analysis_data['nutrition_score']['grade']}
📝 **Estado:** {analysis_data['nutrition_score']['description']}

"""
        
        # Análisis de componentes
        text += "🔬 **ANÁLISIS POR COMPONENTES:**\n\n"
        
        # Macronutrientes
        macro = analysis_data["macro_analysis"]
        text += f"**1. 🍽️ MACRONUTRIENTES** (Score: {analysis_data['nutrition_score']['component_scores']['macro_balance']}/100)\n"
        text += f"• Proteína: {macro['actual_distribution']['protein_pct']}% (objetivo: {macro['target_distribution']['protein_pct']}%)\n"
        text += f"• Carbohidratos: {macro['actual_distribution']['carbs_pct']}% (objetivo: {macro['target_distribution']['carbs_pct']}%)\n"
        text += f"• Grasas: {macro['actual_distribution']['fat_pct']}% (objetivo: {macro['target_distribution']['fat_pct']}%)\n"
        text += f"• Adherencia: {macro['adherence_score']}%\n\n"
        
        # Micronutrientes
        micro = analysis_data["micronutrient_analysis"]
        text += f"**2. ⚗️ MICRONUTRIENTES** (Score: {analysis_data['nutrition_score']['component_scores']['micronutrient_density']}/100)\n"
        if micro["critical_deficiencies"]:
            text += f"⚠️ **Deficiencias críticas:** {', '.join(micro['critical_deficiencies'])}\n"
        if micro["nutritional_strengths"]:
            text += f"✅ **Fortalezas:** {', '.join(micro['nutritional_strengths'])}\n"
        text += f"📈 **Score general:** {micro['overall_micronutrient_score']}/100\n\n"
        
        # Adherencia
        adherence = analysis_data["adherence_analysis"]
        text += f"**3. 🎯 ADHERENCIA AL PLAN** (Score: {adherence['overall_adherence_score']}/100)\n"
        text += f"• Nivel: {adherence['adherence_level']['description']}\n"
        text += f"• Consistencia: {adherence['consistency_rating']}\n\n"
        
        # Timing nutricional
        timing = analysis_data["timing_analysis"]
        text += f"**4. ⏰ TIMING NUTRICIONAL** (Score: {timing['optimization_score']}/100)\n"
        text += f"• Horario de entreno: {timing['training_schedule']}\n"
        if timing["timing_preferences"]:
            best_timing = max(timing["timing_preferences"].items(), key=lambda x: x[1]["average_rating"])
            text += f"• Timing preferido: {best_timing[0].replace('_', ' ').title()} ({best_timing[1]['average_rating']:.1f}⭐)\n"
        text += f"• Alineación con objetivos: {timing['alignment_with_goals']}\n\n"
        
        # Variedad alimentaria
        variety = analysis_data["variety_analysis"]
        text += f"**5. 🌈 VARIEDAD ALIMENTARIA** (Score: {variety['variety_score']}/100)\n"
        text += f"• Ingredientes únicos: {variety['unique_ingredients_count']}\n"
        text += f"• Tipos de receta: {variety['unique_recipe_types_count']}\n"
        text += f"• Nivel de variedad: {variety['variety_level']}\n\n"
        
        # Correlaciones con progreso
        if analysis_data["progress_correlation"]["correlations_found"]:
            text += "🔗 **CORRELACIONES DETECTADAS:**\n"
            for correlation_type, data in analysis_data["progress_correlation"]["correlations_found"].items():
                if data and data.get("strength", "baja") != "baja":
                    text += f"• {correlation_type.replace('_', ' ').title()}: {data.get('description', 'Correlación detectada')}\n"
            text += "\n"
        
        # Fortalezas identificadas
        if analysis_data["nutrition_score"]["strengths"]:
            text += "✅ **TUS FORTALEZAS NUTRICIONALES:**\n"
            for strength in analysis_data["nutrition_score"]["strengths"]:
                text += f"• {strength}\n"
            text += "\n"
        
        # Prioridades de mejora
        if analysis_data["nutrition_score"]["improvement_priorities"]:
            text += "🎯 **PRIORIDADES DE MEJORA:**\n"
            for priority in analysis_data["nutrition_score"]["improvement_priorities"]:
                text += f"• {priority}\n"
            text += "\n"
        
        # Top recomendaciones personalizadas
        recommendations = analysis_data["personalized_recommendations"]
        if recommendations:
            text += "💡 **RECOMENDACIONES PERSONALIZADAS:**\n"
            for rec in recommendations[:5]:  # Top 5 recomendaciones
                text += f"• {rec}\n"
            text += "\n"
        
        # Próximos pasos
        next_steps = analysis_data["next_steps"]
        if next_steps:
            text += "🚀 **PRÓXIMOS PASOS:**\n"
            for step in next_steps:
                text += f"• {step}\n"
            text += "\n"
        
        # Footer
        text += f"""
🤖 **COMANDOS PARA MEJORAR TU NUTRICIÓN:**
• `/generar` - Recetas optimizadas para tus deficiencias
• `/valorar_receta` - Mejorar IA con más valoraciones
• `/progreso` - Trackear métricas correlacionadas
• `/nueva_semana` - Plan semanal basado en análisis

**Análisis actualizado automáticamente con tus datos. ¡Sigue registrando para insights más precisos!**
"""
        
        return text

    # Métodos auxiliares (implementación simplificada para el ejemplo)
    def _detect_macro_patterns(self, consumed_data: Dict, period_data: Dict) -> List[str]:
        return ["Patrón detectado basado en datos disponibles"]
    
    def _get_weight_trend_from_progress(self, progress_metrics: Dict) -> Optional[float]:
        if "weight" not in progress_metrics or not progress_metrics["weight"]:
            return None
        records = progress_metrics["weight"]
        if len(records) < 2:
            return None
        return records[-1]["value"] - records[0]["value"]
    
    def _get_average_energy_level(self, progress_metrics: Dict) -> Optional[float]:
        if "energy_level" not in progress_metrics or not progress_metrics["energy_level"]:
            return None
        records = progress_metrics["energy_level"]
        return sum(r["value"] for r in records) / len(records)
    
    def _get_macro_preference_from_ratings(self, ratings_history: List) -> Dict:
        # Análisis simplificado de preferencias de macros basado en ratings
        return {"protein_bias": 0, "carbs_bias": 0, "fat_bias": 0}
    
    def _get_expected_weight_change(self, objective: str) -> float:
        mapping = {
            "bajar_peso": -0.5,  # kg por semana
            "subir_masa": 0.3,
            "subir_masa_lean": 0.2,
            "recomposicion": 0.0,
            "mantener": 0.0
        }
        return mapping.get(objective, 0.0)
    
    def _calculate_adherence_from_weight_trend(self, weight_trend: Optional[float], expected: float) -> float:
        if weight_trend is None:
            return 0.75  # Default
        
        if expected == 0:  # Mantenimiento
            return 1.0 if abs(weight_trend) < 0.5 else 0.8
        
        # Calcular qué tan cerca está del objetivo
        if expected < 0:  # Bajar peso
            if weight_trend < 0:
                adherence = min(1.0, abs(weight_trend) / abs(expected))
            else:
                adherence = 0.3  # Subió de peso cuando debía bajar
        else:  # Subir peso
            if weight_trend > 0:
                adherence = min(1.0, weight_trend / expected)
            else:
                adherence = 0.3  # Bajó peso cuando debía subir
        
        return adherence
    
    def _calculate_micronutrient_score(self, micronutrient_status: Dict) -> float:
        scores = []
        for nutrient, data in micronutrient_status.items():
            ratio = data["fulfillment_ratio"]
            # Score óptimo cuando ratio está entre 0.9 y 1.2
            if 0.9 <= ratio <= 1.2:
                score = 100
            elif 0.7 <= ratio < 0.9:
                score = 70 + (ratio - 0.7) * 150  # Escala de 70 a 100
            elif ratio < 0.7:
                score = ratio * 100  # Proporcional hasta 70
            else:  # ratio > 1.2
                score = max(60, 100 - (ratio - 1.2) * 50)  # Penalizar excesos
            
            scores.append(score)
        
        return round(sum(scores) / len(scores), 1) if scores else 50
    
    def _generate_micronutrient_recommendations(self, micronutrient_status: Dict, liked_foods: List[str]) -> List[str]:
        recommendations = []
        
        for nutrient, data in micronutrient_status.items():
            if data["fulfillment_ratio"] < 0.8:
                # Buscar alimentos ricos en este nutriente
                rich_foods = self._find_foods_rich_in_nutrient(nutrient)
                recommended_foods = [food for food in rich_foods if any(cat in liked_foods for cat in self._get_food_categories(food))]
                
                if recommended_foods:
                    recommendations.append(f"Aumenta {nutrient}: incluye {', '.join(recommended_foods[:2])}")
                else:
                    recommendations.append(f"Considera suplementación de {nutrient} (consulta profesional)")
        
        return recommendations[:3]  # Top 3 recomendaciones
    
    def _find_foods_rich_in_nutrient(self, nutrient: str) -> List[str]:
        rich_foods = []
        for food, nutrients in self.micronutrient_database.items():
            if nutrient in nutrients and nutrients[nutrient] > 0:
                rich_foods.append((food, nutrients[nutrient]))
        
        # Ordenar por contenido y devolver nombres
        rich_foods.sort(key=lambda x: x[1], reverse=True)
        return [food[0] for food in rich_foods[:5]]
    
    def _get_food_categories(self, food: str) -> List[str]:
        # Mapeo inverso de alimentos a categorías
        category_mapping = {
            "pollo": ["aves"], "salmon": ["pescados"], "huevos": ["huevos"],
            "almendras": ["frutos_secos"], "yogur_griego": ["lacteos"]
        }
        return category_mapping.get(food, [])
    
    # Implementaciones simplificadas de otros métodos auxiliares
    def _calculate_weight_based_adherence(self, period_data: Dict, user_profile: Dict) -> Optional[float]:
        return 75.0  # Placeholder
    
    def _calculate_energy_based_adherence(self, period_data: Dict) -> Optional[float]:
        return 80.0  # Placeholder
    
    def _calculate_rating_based_adherence(self, period_data: Dict) -> Optional[float]:
        ratings = period_data["ratings_history"]
        if not ratings:
            return None
        avg_rating = sum(r["rating"] for r in ratings) / len(ratings)
        return (avg_rating / 5.0) * 100
    
    def _classify_adherence_level(self, score: float) -> Dict:
        for level, data in self.adherence_patterns.items():
            if score >= data["threshold"]:
                return data
        return self.adherence_patterns["very_poor"]
    
    def _identify_adherence_patterns(self, period_data: Dict, overall_adherence: float) -> List[str]:
        return ["Adherencia variable durante fines de semana"]
    
    def _calculate_consistency_rating(self, period_data: Dict) -> str:
        return "Media"  # Placeholder
    
    def _identify_improvement_areas(self, overall_adherence: float, patterns: List[str]) -> List[str]:
        areas = []
        if overall_adherence < 70:
            areas.append("Mejorar adherencia general al plan")
        if overall_adherence < 60:
            areas.append("Establecer rutinas más consistentes")
        return areas
    
    def _calculate_timing_optimization_score(self, timing_analysis: Dict, training_schedule: str, user_profile: Dict) -> float:
        return 75.0  # Placeholder
    
    def _generate_timing_recommendations(self, timing_analysis: Dict, training_schedule: str) -> List[str]:
        return ["Optimizar timing pre-entreno con más carbohidratos"]
    
    def _assess_timing_goal_alignment(self, timing_analysis: Dict, user_profile: Dict) -> str:
        return "Buena alineación"
    
    def _detect_ingredients_from_recipe_name(self, recipe_name: str) -> List[str]:
        ingredients = []
        for food in self.micronutrient_database.keys():
            if food.lower() in recipe_name:
                ingredients.append(food)
        return ingredients
    
    def _categorize_recipe_type(self, recipe_name: str) -> Optional[str]:
        if any(word in recipe_name for word in ["ensalada", "crudo"]):
            return "crudo"
        elif any(word in recipe_name for word in ["horno", "asado"]):
            return "horno"
        elif any(word in recipe_name for word in ["plancha", "grillado"]):
            return "plancha"
        return "sarten"  # Default
    
    def _calculate_variety_score(self, unique_ingredients: int, unique_types: int, total_recipes: int) -> float:
        if total_recipes == 0:
            return 0
        
        ingredient_score = min(unique_ingredients / 15, 1.0) * 50  # Hasta 50 puntos
        type_score = min(unique_types / 8, 1.0) * 30  # Hasta 30 puntos
        frequency_score = min(total_recipes / 20, 1.0) * 20  # Hasta 20 puntos
        
        return ingredient_score + type_score + frequency_score
    
    def _classify_variety_level(self, score: float) -> str:
        if score >= 80:
            return "Excelente"
        elif score >= 60:
            return "Buena"
        elif score >= 40:
            return "Media"
        else:
            return "Base"
    
    def _get_most_common_items(self, items: List[str], limit: int) -> List[Tuple[str, int]]:
        return Counter(items).most_common(limit)
    
    def _generate_variety_recommendations(self, variety_score: float, ingredients_rated: List[str]) -> List[str]:
        recommendations = []
        if variety_score < 60:
            recommendations.append("Experimenta con nuevos ingredientes semanalmente")
            recommendations.append("Prueba diferentes métodos de cocción")
        return recommendations
    
    def _calculate_energy_rating_correlation(self, energy_records: List, ratings_history: List) -> Dict:
        return {"strength": "media", "description": "Correlación media entre satisfacción y energía"}
    
    def _calculate_weight_adherence_correlation(self, weight_records: List, user_profile: Dict) -> Dict:
        return {"strength": "alta", "description": "Buena correlación entre adherencia y progreso de peso"}
    
    def _calculate_sleep_nutrition_correlation(self, sleep_records: List, ratings_history: List) -> Dict:
        return {"strength": "baja", "description": "Correlación leve entre nutrición y sueño"}
    
    def _assess_overall_correlation_strength(self, correlations: Dict) -> str:
        return "Media"
    
    def _generate_correlation_insights(self, correlations: Dict, user_profile: Dict) -> List[str]:
        return ["Mejor adherencia correlaciona con mayor satisfacción"]
    
    def _extract_actionable_findings(self, correlations: Dict) -> List[str]:
        return ["Mantén consistencia en valoraciones altas"]
    
    def _identify_nutrition_strengths(self, macro_score: float, micro_score: float, 
                                   adherence_score: float, timing_score: float, variety_score: float) -> List[str]:
        strengths = []
        scores = {
            "Distribución de macronutrientes": macro_score,
            "Densidad de micronutrientes": micro_score,
            "Adherencia al plan": adherence_score,
            "Timing nutricional": timing_score,
            "Variedad alimentaria": variety_score
        }
        
        for area, score in scores.items():
            if score >= 80:
                strengths.append(f"{area} excelente ({score:.0f}/100)")
        
        return strengths
    
    def _identify_improvement_priorities(self, macro_score: float, micro_score: float,
                                      adherence_score: float, timing_score: float, variety_score: float) -> List[str]:
        priorities = []
        scores = {
            "Mejorar distribución de macronutrientes": macro_score,
            "Optimizar micronutrientes": micro_score,
            "Aumentar adherencia al plan": adherence_score,
            "Optimizar timing nutricional": timing_score,
            "Aumentar variedad alimentaria": variety_score
        }
        
        # Ordenar por menor score (mayor prioridad)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1])
        
        for area, score in sorted_scores:
            if score < 70:
                priorities.append(f"{area} ({score:.0f}/100)")
        
        return priorities[:3]  # Top 3 prioridades
    
    def _generate_personalized_recommendations(self, macro_analysis: Dict, micro_analysis: Dict,
                                             adherence_analysis: Dict, timing_analysis: Dict,
                                             variety_analysis: Dict, user_profile: Dict) -> List[str]:
        recommendations = []
        
        # Recomendaciones por macros
        for opportunity in macro_analysis.get("optimization_opportunities", []):
            if opportunity["priority"] == "alta":
                recommendations.append(opportunity["description"])
        
        # Recomendaciones por micronutrientes
        recommendations.extend(micro_analysis.get("improvement_recommendations", []))
        
        # Recomendaciones por adherencia
        recommendations.extend(adherence_analysis.get("improvement_areas", []))
        
        # Recomendaciones por timing
        recommendations.extend(timing_analysis.get("recommendations", []))
        
        # Recomendaciones por variedad
        recommendations.extend(variety_analysis.get("diversity_recommendations", []))
        
        return recommendations[:8]  # Top 8 recomendaciones
    
    def _generate_next_steps(self, nutrition_score: Dict, user_profile: Dict) -> List[str]:
        steps = []
        overall_score = nutrition_score["overall_score"]
        
        if overall_score < 60:
            steps.extend([
                "Enfócate en mejorar adherencia al plan base",
                "Usa /generar para recetas más alineadas",
                "Registra métricas diariamente con /progreso"
            ])
        elif overall_score < 80:
            steps.extend([
                "Optimiza timing nutricional según tu entrenamiento",
                "Incorpora más variedad de ingredientes",
                "Continúa valorando recetas para mejorar IA"
            ])
        else:
            steps.extend([
                "Mantén excelente adherencia actual",
                "Experimenta con microoptimizaciones",
                "Comparte tu éxito como referencia"
            ])
        
        return steps

# Ejemplo de uso
if __name__ == "__main__":
    analytics = NutritionAnalytics()
    
    # Perfil de usuario de ejemplo
    sample_profile = {
        "basic_data": {
            "objetivo": "recomposicion",
            "objetivo_descripcion": "Recomposición corporal",
            "edad": 28,
            "sexo": "masculino"
        },
        "macros": {
            "calories": 2400,
            "protein_g": 180,
            "carbs_g": 240,
            "fat_g": 80
        },
        "preferences": {
            "liked_foods": ["aves", "pescados", "frutos_secos"],
            "disliked_foods": []
        },
        "progress_tracking": {
            "metrics": {
                "weight": [
                    {"value": 75.2, "timestamp": "2024-01-15T10:00:00", "date": "2024-01-15"},
                    {"value": 74.8, "timestamp": "2024-01-22T10:00:00", "date": "2024-01-22"}
                ],
                "energy_level": [
                    {"value": 8, "timestamp": "2024-01-15T18:00:00", "date": "2024-01-15"},
                    {"value": 7, "timestamp": "2024-01-22T18:00:00", "date": "2024-01-22"}
                ]
            }
        },
        "recipe_intelligence": {
            "ratings_history": [
                {
                    "rating": 5,
                    "timestamp": "2024-01-16T12:00:00",
                    "recipe_data": {
                        "nombre": "Salmón a la plancha con quinoa",
                        "categoria_timing": "comida_principal"
                    }
                },
                {
                    "rating": 4,
                    "timestamp": "2024-01-20T14:00:00",
                    "recipe_data": {
                        "nombre": "Pollo al horno con brócoli",
                        "categoria_timing": "post_entreno"
                    }
                }
            ]
        }
    }
    
    # Generar análisis completo
    result = analytics.generate_comprehensive_analysis(sample_profile, "month")
    
    if result["success"]:
        formatted_analysis = analytics.format_analysis_for_telegram(result, sample_profile)
        print("=== ANÁLISIS NUTRICIONAL PROFUNDO ===")
        print(formatted_analysis)
    else:
        print(f"Error: {result['error']}")