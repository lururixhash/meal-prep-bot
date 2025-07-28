#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Planificación Semanal Inteligente
Genera planes semanales automáticos con rotación inteligente y variedad optimizada
"""

import json
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

class WeeklyPlanner:
    
    def __init__(self):
        # Temas semanales disponibles
        self.weekly_themes = {
            "mediterranea": {
                "name": "Semana Mediterránea",
                "description": "Enfoque en ingredientes mediterráneos tradicionales",
                "emoji": "🌊",
                "preferred_ingredients": [
                    "aceite_oliva", "aceitunas", "pescados", "yogur_griego", 
                    "queso_feta", "almendras", "tomates", "oregano"
                ],
                "cooking_methods": ["plancha", "horno", "crudo"],
                "macro_adjustment": {"fat": 1.1, "protein": 1.0, "carbs": 0.95}
            },
            "alta_proteina": {
                "name": "Semana Alta Proteína",
                "description": "Maximizar síntesis proteica y recuperación",
                "emoji": "💪",
                "preferred_ingredients": [
                    "aves", "pescados", "huevos", "yogur_griego", 
                    "legumbres", "quinoa", "almendras"
                ],
                "cooking_methods": ["plancha", "horno", "sarten"],
                "macro_adjustment": {"protein": 1.2, "fat": 0.9, "carbs": 0.9}
            },
            "detox_natural": {
                "name": "Semana Detox Natural",
                "description": "Alimentos depurativos y antioxidantes",
                "emoji": "🌿",
                "preferred_ingredients": [
                    "verduras_verdes", "cruciferas", "frutas", "jengibre",
                    "limón", "pescados", "frutos_secos"
                ],
                "cooking_methods": ["vapor", "crudo", "plancha"],
                "macro_adjustment": {"carbs": 1.1, "fat": 0.9, "protein": 1.0}
            },
            "energia_sostenida": {
                "name": "Semana Energía Sostenida",
                "description": "Carbohidratos complejos y grasas saludables",
                "emoji": "⚡",
                "preferred_ingredients": [
                    "quinoa", "arroz_integral", "avena", "batata",
                    "frutos_secos", "aceite_oliva", "pescados"
                ],
                "cooking_methods": ["horno", "vapor", "sarten"],
                "macro_adjustment": {"carbs": 1.1, "fat": 1.1, "protein": 0.95}
            },
            "variedad_maxima": {
                "name": "Semana Variedad Máxima",
                "description": "Máxima diversidad de ingredientes y preparaciones",
                "emoji": "🌈",
                "preferred_ingredients": [], # Usa todos los ingredientes
                "cooking_methods": ["horno", "sarten", "plancha", "vapor", "crudo"],
                "macro_adjustment": {"protein": 1.0, "fat": 1.0, "carbs": 1.0}
            }
        }
        
        # Ingredientes estacionales (simplificado para España)
        self.seasonal_ingredients = {
            "primavera": ["espárragos", "guisantes", "alcachofas", "fresas", "cerezas"],
            "verano": ["tomates", "pimientos", "calabacín", "berenjenas", "melocotones"],
            "otoño": ["calabaza", "setas", "manzanas", "peras", "nueces"],
            "invierno": ["brócoli", "coliflor", "naranjas", "mandarinas", "col"]
        }
        
        # Sistema de puntuación de variedad
        self.variety_weights = {
            "ingredient_repetition": 0.3,  # Penaliza repetir ingredientes
            "cooking_method_variety": 0.25, # Premia variedad en métodos
            "macro_distribution": 0.2,     # Premia distribución equilibrada
            "seasonal_bonus": 0.15,        # Bonus por ingredientes estacionales
            "theme_consistency": 0.1       # Bonus por consistencia con tema
        }
    
    def generate_intelligent_week(self, user_profile: Dict, week_preferences: Dict) -> Dict:
        """
        Generar plan semanal inteligente con rotación automática
        """
        try:
            # Obtener datos del usuario
            objective = user_profile["basic_data"]["objetivo"]
            daily_calories = user_profile["macros"]["calories"]
            preferences = user_profile.get("preferences", {})
            
            # Determinar tema semanal
            theme = self._select_weekly_theme(user_profile, week_preferences)
            
            # Obtener historial para evitar repeticiones
            week_history = user_profile.get("week_history", [])
            
            # Generar estructura base de la semana
            week_structure = self._create_week_structure(
                user_profile, theme, week_history
            )
            
            # Optimizar variedad y distribución
            optimized_week = self._optimize_week_variety(
                week_structure, user_profile, theme
            )
            
            # Añadir ingredientes estacionales
            seasonal_week = self._add_seasonal_elements(
                optimized_week, self._get_current_season()
            )
            
            # Generar métricas de calidad
            quality_metrics = self._calculate_week_quality(
                seasonal_week, user_profile, theme
            )
            
            # Crear resultado final
            result = {
                "success": True,
                "weekly_plan": seasonal_week,
                "theme": theme,
                "quality_metrics": quality_metrics,
                "generation_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "theme_applied": theme["name"],
                    "variety_score": quality_metrics["variety_score"],
                    "user_objective": objective
                },
                "next_week_suggestions": self._generate_next_week_suggestions(
                    theme, quality_metrics, user_profile
                )
            }
            
            # Actualizar historial del usuario
            self._update_user_week_history(user_profile, seasonal_week, theme)
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error generating intelligent week: {str(e)}",
                "weekly_plan": None
            }
    
    def _select_weekly_theme(self, user_profile: Dict, preferences: Dict) -> Dict:
        """
        Seleccionar tema semanal óptimo según perfil y preferencias
        """
        # Tema específico solicitado por el usuario
        requested_theme = preferences.get("theme")
        if requested_theme and requested_theme in self.weekly_themes:
            return self.weekly_themes[requested_theme]
        
        # Selección automática basada en objetivo
        objective = user_profile["basic_data"]["objetivo"]
        ea_status = user_profile["energy_data"]["ea_status"]["status"]
        
        # Mapeo objetivo -> tema recomendado
        objective_theme_mapping = {
            "bajar_peso": "detox_natural",
            "subir_masa": "alta_proteina", 
            "subir_masa_lean": "energia_sostenida",
            "recomposicion": "mediterranea",
            "mantener": "variedad_maxima"
        }
        
        # Ajuste por Available Energy
        if ea_status == "low":
            return self.weekly_themes["energia_sostenida"]
        elif ea_status == "very_high":
            return self.weekly_themes["detox_natural"]
        
        # Tema basado en objetivo
        recommended_theme = objective_theme_mapping.get(objective, "variedad_maxima")
        return self.weekly_themes[recommended_theme]
    
    def _create_week_structure(self, user_profile: Dict, theme: Dict, history: List) -> Dict:
        """
        Crear estructura base de la semana con el tema aplicado
        """
        days = ["lunes", "martes", "miercoles", "jueves", "viernes"]
        week_structure = {}
        
        # Obtener distribución calórica
        daily_calories = user_profile["macros"]["calories"]
        macro_adjustments = theme["macro_adjustment"]
        
        for day in days:
            week_structure[day] = {
                "desayuno": self._generate_meal_structure(
                    "desayuno", daily_calories * 0.25, macro_adjustments, theme, history
                ),
                "almuerzo": self._generate_meal_structure(
                    "almuerzo", daily_calories * 0.35, macro_adjustments, theme, history
                ),
                "merienda": self._generate_meal_structure(
                    "merienda", daily_calories * 0.15, macro_adjustments, theme, history
                ),
                "cena": self._generate_meal_structure(
                    "cena", daily_calories * 0.25, macro_adjustments, theme, history
                )
            }
        
        return week_structure
    
    def _generate_meal_structure(self, meal_type: str, target_calories: float, 
                               macro_adj: Dict, theme: Dict, history: List) -> Dict:
        """
        Generar estructura de una comida específica
        """
        # Calcular macros ajustados por tema
        base_protein = target_calories * 0.25 / 4  # 25% proteína base
        base_carbs = target_calories * 0.45 / 4    # 45% carbohidratos base  
        base_fat = target_calories * 0.30 / 9      # 30% grasas base
        
        adjusted_protein = base_protein * macro_adj["protein"]
        adjusted_carbs = base_carbs * macro_adj["carbs"] 
        adjusted_fat = base_fat * macro_adj["fat"]
        
        # Rebalancear calorías
        total_adjusted_calories = (adjusted_protein * 4) + (adjusted_carbs * 4) + (adjusted_fat * 9)
        calorie_factor = target_calories / total_adjusted_calories
        
        final_protein = adjusted_protein * calorie_factor
        final_carbs = adjusted_carbs * calorie_factor
        final_fat = adjusted_fat * calorie_factor
        
        return {
            "target_macros": {
                "calories": int(target_calories),
                "protein": int(final_protein),
                "carbs": int(final_carbs),
                "fat": int(final_fat)
            },
            "theme_ingredients": theme["preferred_ingredients"],
            "preferred_methods": theme["cooking_methods"],
            "meal_type": meal_type,
            "variety_score": 0  # Se calculará después
        }
    
    def _optimize_week_variety(self, week_structure: Dict, user_profile: Dict, theme: Dict) -> Dict:
        """
        Optimizar la variedad de la semana para evitar monotonía
        """
        optimized_week = week_structure.copy()
        
        # Rastrear uso de ingredientes y métodos
        ingredient_usage = defaultdict(int)
        method_usage = defaultdict(int)
        
        # Analizar uso actual
        for day_data in week_structure.values():
            for meal_data in day_data.values():
                # Simular ingredientes que se usarían
                theme_ingredients = meal_data["theme_ingredients"]
                if theme_ingredients:
                    # Seleccionar ingredientes con distribución inteligente
                    selected_ingredients = self._select_varied_ingredients(
                        theme_ingredients, ingredient_usage, 3
                    )
                    for ingredient in selected_ingredients:
                        ingredient_usage[ingredient] += 1
                
                # Método de cocción
                methods = meal_data["preferred_methods"]
                if methods:
                    selected_method = self._select_varied_method(methods, method_usage)
                    method_usage[selected_method] += 1
                    meal_data["selected_method"] = selected_method
        
        # Calcular puntuaciones de variedad
        for day, day_data in optimized_week.items():
            for meal, meal_data in day_data.items():
                variety_score = self._calculate_meal_variety_score(
                    meal_data, ingredient_usage, method_usage, theme
                )
                meal_data["variety_score"] = variety_score
        
        return optimized_week
    
    def _select_varied_ingredients(self, available_ingredients: List[str], 
                                 usage_history: Dict, count: int) -> List[str]:
        """
        Seleccionar ingredientes priorizando variedad
        """
        if not available_ingredients:
            return []
        
        # Ordenar por menor uso
        sorted_ingredients = sorted(
            available_ingredients, 
            key=lambda x: usage_history.get(x, 0)
        )
        
        # Seleccionar con algo de aleatoriedad para variedad
        selection_pool = sorted_ingredients[:min(count * 2, len(sorted_ingredients))]
        selected = random.sample(selection_pool, min(count, len(selection_pool)))
        
        return selected
    
    def _select_varied_method(self, available_methods: List[str], usage_history: Dict) -> str:
        """
        Seleccionar método de cocción priorizando variedad
        """
        if not available_methods:
            return "sarten"  # Fallback
        
        # Seleccionar el método menos usado
        return min(available_methods, key=lambda x: usage_history.get(x, 0))
    
    def _add_seasonal_elements(self, week_structure: Dict, season: str) -> Dict:
        """
        Añadir elementos estacionales a la semana
        """
        seasonal_week = week_structure.copy()
        seasonal_ingredients = self.seasonal_ingredients.get(season, [])
        
        if not seasonal_ingredients:
            return seasonal_week
        
        # Añadir 1-2 ingredientes estacionales por día
        for day, day_data in seasonal_week.items():
            daily_seasonal = random.sample(
                seasonal_ingredients, 
                min(2, len(seasonal_ingredients))
            )
            
            for meal, meal_data in day_data.items():
                # Añadir ingrediente estacional como complemento
                meal_data["seasonal_ingredients"] = daily_seasonal[:1]
                meal_data["seasonal_bonus"] = True
        
        return seasonal_week
    
    def _calculate_week_quality(self, week_structure: Dict, user_profile: Dict, theme: Dict) -> Dict:
        """
        Calcular métricas de calidad de la semana
        """
        total_variety_score = 0
        total_meals = 0
        ingredient_diversity = set()
        method_diversity = set()
        
        for day_data in week_structure.values():
            for meal_data in day_data.values():
                total_variety_score += meal_data.get("variety_score", 0)
                total_meals += 1
                
                # Diversidad de ingredientes
                theme_ingredients = meal_data.get("theme_ingredients", [])
                ingredient_diversity.update(theme_ingredients[:3])  # Simular 3 por comida
                
                # Diversidad de métodos
                selected_method = meal_data.get("selected_method")
                if selected_method:
                    method_diversity.add(selected_method)
        
        avg_variety_score = total_variety_score / total_meals if total_meals > 0 else 0
        
        # Calcular puntuación global (0-100)
        variety_component = min(avg_variety_score * 20, 30)  # Máximo 30 puntos
        diversity_component = min(len(ingredient_diversity) * 2, 40)  # Máximo 40 puntos  
        method_component = min(len(method_diversity) * 6, 30)  # Máximo 30 puntos
        
        overall_score = variety_component + diversity_component + method_component
        
        return {
            "variety_score": round(avg_variety_score, 2),
            "ingredient_diversity": len(ingredient_diversity),
            "method_diversity": len(method_diversity),
            "overall_score": round(overall_score, 1),
            "theme_consistency": theme["name"],
            "seasonal_integration": self._count_seasonal_meals(week_structure)
        }
    
    def _calculate_meal_variety_score(self, meal_data: Dict, ingredient_usage: Dict, 
                                    method_usage: Dict, theme: Dict) -> float:
        """
        Calcular puntuación de variedad para una comida específica
        """
        scores = []
        
        # Puntuación por uso de ingredientes (menos usado = mejor puntuación)
        theme_ingredients = meal_data.get("theme_ingredients", [])
        if theme_ingredients:
            avg_ingredient_usage = sum(ingredient_usage.get(ing, 0) for ing in theme_ingredients[:3]) / 3
            ingredient_score = max(0, 5 - avg_ingredient_usage)  # 5 es máximo
            scores.append(ingredient_score * self.variety_weights["ingredient_repetition"])
        
        # Puntuación por método de cocción
        selected_method = meal_data.get("selected_method")
        if selected_method:
            method_usage_count = method_usage.get(selected_method, 0)
            method_score = max(0, 3 - method_usage_count)  # 3 es máximo
            scores.append(method_score * self.variety_weights["cooking_method_variety"])
        
        # Puntuación por distribución de macros (equilibrio)
        target_macros = meal_data.get("target_macros", {})
        if target_macros:
            macro_balance = self._calculate_macro_balance_score(target_macros)
            scores.append(macro_balance * self.variety_weights["macro_distribution"])
        
        # Bonus estacional
        if meal_data.get("seasonal_bonus", False):
            scores.append(1.0 * self.variety_weights["seasonal_bonus"])
        
        # Consistencia con tema
        scores.append(1.0 * self.variety_weights["theme_consistency"])
        
        return sum(scores)
    
    def _calculate_macro_balance_score(self, macros: Dict) -> float:
        """
        Calcular puntuación de equilibrio de macronutrientes
        """
        calories = macros.get("calories", 1)
        protein_cal = macros.get("protein", 0) * 4
        carbs_cal = macros.get("carbs", 0) * 4
        fat_cal = macros.get("fat", 0) * 9
        
        protein_pct = protein_cal / calories
        carbs_pct = carbs_cal / calories
        fat_pct = fat_cal / calories
        
        # Ideal: 25% proteína, 45% carbos, 30% grasas
        ideal_protein = 0.25
        ideal_carbs = 0.45
        ideal_fat = 0.30
        
        # Calcular desviación del ideal
        protein_deviation = abs(protein_pct - ideal_protein)
        carbs_deviation = abs(carbs_pct - ideal_carbs)
        fat_deviation = abs(fat_pct - ideal_fat)
        
        avg_deviation = (protein_deviation + carbs_deviation + fat_deviation) / 3
        balance_score = max(0, 1.0 - (avg_deviation * 4))  # Penalizar desviaciones
        
        return balance_score
    
    def _get_current_season(self) -> str:
        """
        Determinar la estación actual
        """
        month = datetime.now().month
        
        if 3 <= month <= 5:
            return "primavera"
        elif 6 <= month <= 8:
            return "verano"
        elif 9 <= month <= 11:
            return "otoño"
        else:
            return "invierno"
    
    def _count_seasonal_meals(self, week_structure: Dict) -> int:
        """
        Contar comidas con ingredientes estacionales
        """
        count = 0
        for day_data in week_structure.values():
            for meal_data in day_data.values():
                if meal_data.get("seasonal_bonus", False):
                    count += 1
        return count
    
    def _generate_next_week_suggestions(self, current_theme: Dict, quality_metrics: Dict, 
                                      user_profile: Dict) -> List[str]:
        """
        Generar sugerencias para la siguiente semana
        """
        suggestions = []
        
        # Sugerencia basada en variedad actual
        if quality_metrics["variety_score"] < 3.0:
            suggestions.append("🌈 Considera 'Variedad Máxima' para la próxima semana")
        
        # Sugerencia basada en diversidad de ingredientes
        if quality_metrics["ingredient_diversity"] < 15:
            suggestions.append("🥗 Prueba ingredientes nuevos la próxima semana")
        
        # Sugerencia basada en métodos de cocción
        if quality_metrics["method_diversity"] < 4:
            suggestions.append("👨‍🍳 Experimenta con nuevos métodos de cocción")
        
        # Sugerencia de tema complementario
        current_theme_key = None
        for key, theme_data in self.weekly_themes.items():
            if theme_data["name"] == current_theme["name"]:
                current_theme_key = key
                break
        
        # Recomendar tema complementario
        theme_suggestions = {
            "mediterranea": "alta_proteina",
            "alta_proteina": "detox_natural", 
            "detox_natural": "energia_sostenida",
            "energia_sostenida": "mediterranea",
            "variedad_maxima": "mediterranea"
        }
        
        if current_theme_key and current_theme_key in theme_suggestions:
            next_theme_key = theme_suggestions[current_theme_key]
            next_theme = self.weekly_themes[next_theme_key]
            suggestions.append(f"{next_theme['emoji']} Próxima semana: {next_theme['name']}")
        
        # Sugerencia estacional
        season = self._get_current_season()
        suggestions.append(f"🍂 Aprovecha ingredientes de {season}")
        
        return suggestions[:3]  # Máximo 3 sugerencias
    
    def _update_user_week_history(self, user_profile: Dict, week_plan: Dict, theme: Dict) -> None:
        """
        Actualizar historial de semanas del usuario
        """
        if "week_history" not in user_profile:
            user_profile["week_history"] = []
        
        # Mantener solo las últimas 4 semanas
        if len(user_profile["week_history"]) >= 4:
            user_profile["week_history"].pop(0)
        
        # Añadir semana actual
        week_record = {
            "week_date": datetime.now().isoformat(),
            "theme": theme["name"],
            "quality_score": 0,  # Se calculará externamente
            "ingredients_used": []  # Se populará externamente
        }
        
        user_profile["week_history"].append(week_record)
    
    def format_weekly_plan_for_telegram(self, plan_data: Dict, user_profile: Dict) -> str:
        """
        Formatear plan semanal para mostrar en Telegram
        """
        if not plan_data["success"]:
            return f"❌ **Error generando plan semanal:** {plan_data.get('error', 'Error desconocido')}"
        
        weekly_plan = plan_data["weekly_plan"]
        theme = plan_data["theme"]
        quality_metrics = plan_data["quality_metrics"]
        
        # Encabezado del plan
        text = f"""
🗓️ **PLAN SEMANAL INTELIGENTE**

{theme['emoji']} **Tema:** {theme['name']}
📝 **Descripción:** {theme['description']}

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🎯 **Puntuación de calidad:** {quality_metrics['overall_score']}/100

📊 **MÉTRICAS DE VARIEDAD:**
• Diversidad de ingredientes: {quality_metrics['ingredient_diversity']} tipos
• Métodos de cocción: {quality_metrics['method_diversity']} diferentes
• Integración estacional: {quality_metrics['seasonal_integration']} comidas
• Puntuación variedad: {quality_metrics['variety_score']}/5.0

"""
        
        # Días de la semana
        days_display = {
            "lunes": "🌅 LUNES",
            "martes": "💫 MARTES", 
            "miercoles": "⚡ MIÉRCOLES",
            "jueves": "🌟 JUEVES",
            "viernes": "🎯 VIERNES"
        }
        
        for day, day_name in days_display.items():
            if day in weekly_plan:
                text += f"\n**{day_name}**\n"
                day_data = weekly_plan[day]
                
                # Resumen del día
                total_day_calories = sum(
                    meal_data["target_macros"]["calories"] 
                    for meal_data in day_data.values()
                )
                text += f"📈 Total diario: {total_day_calories} kcal\n"
                
                # Comidas del día
                meal_icons = {
                    "desayuno": "🌅", "almuerzo": "🍽️", 
                    "merienda": "🥜", "cena": "🌙"
                }
                
                for meal, meal_data in day_data.items():
                    icon = meal_icons.get(meal, "🍴")
                    macros = meal_data["target_macros"]
                    method = meal_data.get("selected_method", "variado")
                    variety = meal_data.get("variety_score", 0)
                    
                    text += f"  {icon} **{meal.title()}** ({method})\n"
                    text += f"    🎯 {macros['calories']} kcal • {macros['protein']}P • {macros['carbs']}C • {macros['fat']}F\n"
                    text += f"    ⭐ Variedad: {variety:.1f}/5.0\n"
                    
                    # Ingredientes estacionales
                    seasonal_ingredients = meal_data.get("seasonal_ingredients", [])
                    if seasonal_ingredients:
                        text += f"    🍂 Estacional: {', '.join(seasonal_ingredients)}\n"
                
                text += "\n"
        
        # Sugerencias para próxima semana
        next_suggestions = plan_data.get("next_week_suggestions", [])
        if next_suggestions:
            text += "💡 **SUGERENCIAS PRÓXIMA SEMANA:**\n"
            for suggestion in next_suggestions:
                text += f"• {suggestion}\n"
            text += "\n"
        
        # Comandos disponibles
        text += f"""
🤖 **COMANDOS DISPONIBLES:**
• `/generar` - Crear recetas específicas del tema
• `/lista_compras` - Lista optimizada para esta semana
• `/nueva_semana [tema]` - Generar nueva semana con tema específico
• `/valorar_receta` - Calificar recetas para mejorar IA

🎨 **TEMAS DISPONIBLES:**
🌊 mediterranea • 💪 alta_proteina • 🌿 detox_natural
⚡ energia_sostenida • 🌈 variedad_maxima

**¡Plan inteligente adaptado a tu progreso!**
"""
        
        return text

# Ejemplo de uso
if __name__ == "__main__":
    planner = WeeklyPlanner()
    
    # Perfil de ejemplo
    sample_profile = {
        "basic_data": {
            "objetivo": "recomposicion",
            "objetivo_descripcion": "Recomposición corporal"
        },
        "macros": {
            "calories": 2400,
            "protein_g": 160,
            "carbs_g": 240,
            "fat_g": 80
        },
        "energy_data": {
            "available_energy": 48.5,
            "ea_status": {"status": "optimal"}
        },
        "preferences": {
            "liked_foods": ["pescados", "frutos_secos", "aceitunas"],
            "disliked_foods": ["carnes_rojas"]
        }
    }
    
    # Generar plan semanal
    week_preferences = {"theme": "mediterranea", "variety_level": 4}
    result = planner.generate_intelligent_week(sample_profile, week_preferences)
    
    if result["success"]:
        formatted_plan = planner.format_weekly_plan_for_telegram(result, sample_profile)
        print("=== PLAN SEMANAL INTELIGENTE ===")
        print(formatted_plan)
    else:
        print(f"Error: {result['error']}")