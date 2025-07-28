#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Inteligencia de Recetas y Aprendizaje
Aprende de las valoraciones del usuario para mejorar recomendaciones automáticamente
"""

import json
import math
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter

class RecipeIntelligence:
    
    def __init__(self):
        # Pesos para diferentes características en el aprendizaje
        self.learning_weights = {
            "ingredient_preference": 0.35,    # Preferencias por ingredientes
            "cooking_method_preference": 0.25, # Preferencias por métodos de cocción
            "macro_preference": 0.20,         # Preferencias por distribución de macros
            "timing_preference": 0.15,        # Preferencias por timing nutricional
            "complexity_preference": 0.05     # Preferencias por complejidad
        }
        
        # Factores de decay para valoraciones antiguas
        self.temporal_decay = {
            "days_1": 1.0,      # Última semana - peso completo
            "days_7": 0.8,      # Última semana - 80%
            "days_30": 0.6,     # Último mes - 60%
            "days_90": 0.4,     # Últimos 3 meses - 40%
            "days_365": 0.2     # Último año - 20%
        }
        
        # Mapeo de valoraciones a scores numéricos
        self.rating_scores = {
            1: -2.0,  # Muy malo - penalización fuerte
            2: -1.0,  # Malo - penalización moderada
            3: 0.0,   # Neutro - sin cambio
            4: 1.0,   # Bueno - bonus moderado
            5: 2.0    # Excelente - bonus fuerte
        }
    
    def learn_from_rating(self, user_profile: Dict, recipe_data: Dict, rating: int, feedback: str = "") -> Dict:
        """
        Aprender de una valoración específica y actualizar preferencias del usuario
        """
        try:
            # Inicializar sistema de aprendizaje si no existe
            if "recipe_intelligence" not in user_profile:
                user_profile["recipe_intelligence"] = self._initialize_intelligence_profile()
            
            intelligence_profile = user_profile["recipe_intelligence"]
            
            # Registrar valoración
            rating_record = {
                "recipe_id": recipe_data.get("recipe_id", f"recipe_{datetime.now().timestamp()}"),
                "recipe_name": recipe_data.get("nombre", "Receta sin nombre"),
                "rating": rating,
                "feedback": feedback,
                "timestamp": datetime.now().isoformat(),
                "recipe_data": recipe_data
            }
            
            intelligence_profile["ratings_history"].append(rating_record)
            
            # Mantener solo las últimas 100 valoraciones
            if len(intelligence_profile["ratings_history"]) > 100:
                intelligence_profile["ratings_history"] = intelligence_profile["ratings_history"][-100:]
            
            # Actualizar estadísticas básicas
            self._update_basic_statistics(intelligence_profile, rating)
            
            # Aprender patrones de ingredientes
            ingredient_learning = self._learn_ingredient_preferences(recipe_data, rating, intelligence_profile)
            
            # Aprender patrones de métodos de cocción
            method_learning = self._learn_cooking_method_preferences(recipe_data, rating, intelligence_profile)
            
            # Aprender patrones de macros
            macro_learning = self._learn_macro_preferences(recipe_data, rating, intelligence_profile)
            
            # Aprender patrones de timing
            timing_learning = self._learn_timing_preferences(recipe_data, rating, intelligence_profile)
            
            # Aprender preferencias de complejidad
            complexity_learning = self._learn_complexity_preferences(recipe_data, rating, intelligence_profile)
            
            # Actualizar perfil base del usuario con aprendizajes
            self._update_user_base_preferences(user_profile, intelligence_profile)
            
            # Generar recomendaciones mejoradas
            updated_recommendations = self._generate_intelligent_recommendations(intelligence_profile)
            
            return {
                "success": True,
                "learning_results": {
                    "ingredient_insights": ingredient_learning,
                    "method_insights": method_learning,
                    "macro_insights": macro_learning,
                    "timing_insights": timing_learning,
                    "complexity_insights": complexity_learning
                },
                "updated_recommendations": updated_recommendations,
                "intelligence_score": self._calculate_intelligence_score(intelligence_profile)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error learning from rating: {str(e)}"
            }
    
    def _initialize_intelligence_profile(self) -> Dict:
        """
        Inicializar perfil de inteligencia para un usuario nuevo
        """
        return {
            "ratings_history": [],
            "basic_statistics": {
                "total_ratings": 0,
                "average_rating": 0.0,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            },
            "learned_preferences": {
                "ingredients": defaultdict(float),      # ingredient -> preference_score
                "cooking_methods": defaultdict(float),  # method -> preference_score
                "macro_patterns": {                     # patterns in macro distribution
                    "high_protein": 0.0,
                    "high_carbs": 0.0,
                    "high_fat": 0.0,
                    "balanced": 0.0
                },
                "timing_patterns": {                    # timing preferences
                    "pre_entreno": 0.0,
                    "post_entreno": 0.0,
                    "comida_principal": 0.0,
                    "snack_complemento": 0.0
                },
                "complexity_preference": 0.0           # -1 (simple) to 1 (complex)
            },
            "confidence_scores": {
                "ingredients": 0.0,
                "methods": 0.0,
                "macros": 0.0,
                "timing": 0.0,
                "overall": 0.0
            },
            "last_updated": datetime.now().isoformat()
        }
    
    def _update_basic_statistics(self, intelligence_profile: Dict, rating: int) -> None:
        """
        Actualizar estadísticas básicas de valoraciones
        """
        stats = intelligence_profile["basic_statistics"]
        
        # Actualizar contador total
        stats["total_ratings"] += 1
        
        # Actualizar distribución
        stats["rating_distribution"][rating] += 1
        
        # Calcular nueva media
        total_points = sum(rating * count for rating, count in stats["rating_distribution"].items())
        stats["average_rating"] = total_points / stats["total_ratings"]
    
    def _learn_ingredient_preferences(self, recipe_data: Dict, rating: int, intelligence_profile: Dict) -> Dict:
        """
        Aprender preferencias de ingredientes basándose en la valoración
        """
        ingredients = recipe_data.get("ingredientes", [])
        rating_impact = self.rating_scores[rating]
        
        learned_ingredients = {}
        
        for ingredient_data in ingredients:
            ingredient_name = ingredient_data.get("nombre", "").lower()
            if ingredient_name:
                # Aplicar learning rate decreciente
                current_score = intelligence_profile["learned_preferences"]["ingredients"][ingredient_name]
                learning_rate = 0.1  # 10% de impacto por valoración
                
                new_score = current_score + (rating_impact * learning_rate)
                # Limitar entre -2 y 2
                new_score = max(-2.0, min(2.0, new_score))
                
                intelligence_profile["learned_preferences"]["ingredients"][ingredient_name] = new_score
                learned_ingredients[ingredient_name] = new_score
        
        return {
            "ingredients_affected": len(learned_ingredients),
            "top_positive": dict(sorted(learned_ingredients.items(), key=lambda x: x[1], reverse=True)[:3]),
            "top_negative": dict(sorted(learned_ingredients.items(), key=lambda x: x[1])[:3])
        }
    
    def _learn_cooking_method_preferences(self, recipe_data: Dict, rating: int, intelligence_profile: Dict) -> Dict:
        """
        Aprender preferencias de métodos de cocción
        """
        # Inferir método de cocción del nombre o preparación
        preparation = " ".join(recipe_data.get("preparacion", []))
        recipe_name = recipe_data.get("nombre", "").lower()
        
        methods_keywords = {
            "horno": ["horno", "horneado", "hornear"],
            "sarten": ["sartén", "sarten", "freir", "saltear"],
            "plancha": ["plancha", "planchado", "a la plancha"],
            "vapor": ["vapor", "al vapor", "vaporizado"],
            "crudo": ["crudo", "sin cocinar", "fresco"],
            "cocido": ["cocido", "hervido", "cocción"]
        }
        
        detected_methods = []
        full_text = f"{recipe_name} {preparation}".lower()
        
        for method, keywords in methods_keywords.items():
            if any(keyword in full_text for keyword in keywords):
                detected_methods.append(method)
        
        # Si no se detecta método, asumir sartén como default
        if not detected_methods:
            detected_methods = ["sarten"]
        
        rating_impact = self.rating_scores[rating]
        learned_methods = {}
        
        for method in detected_methods:
            current_score = intelligence_profile["learned_preferences"]["cooking_methods"][method]
            learning_rate = 0.15  # 15% de impacto para métodos
            
            new_score = current_score + (rating_impact * learning_rate)
            new_score = max(-2.0, min(2.0, new_score))
            
            intelligence_profile["learned_preferences"]["cooking_methods"][method] = new_score
            learned_methods[method] = new_score
        
        return {
            "methods_detected": detected_methods,
            "methods_learned": learned_methods
        }
    
    def _learn_macro_preferences(self, recipe_data: Dict, rating: int, intelligence_profile: Dict) -> Dict:
        """
        Aprender preferencias de distribución de macronutrientes
        """
        macros = recipe_data.get("macros_por_porcion", {})
        calories = macros.get("calorias", 1)
        
        if calories == 0:
            return {"error": "No macro data available"}
        
        # Calcular porcentajes de macros
        protein_cal = macros.get("proteinas", 0) * 4
        carbs_cal = macros.get("carbohidratos", 0) * 4
        fat_cal = macros.get("grasas", 0) * 9
        
        protein_pct = protein_cal / calories
        carbs_pct = carbs_cal / calories
        fat_pct = fat_cal / calories
        
        # Determinar patrón dominante
        macro_pattern = None
        if protein_pct > 0.35:
            macro_pattern = "high_protein"
        elif carbs_pct > 0.55:
            macro_pattern = "high_carbs"
        elif fat_pct > 0.40:
            macro_pattern = "high_fat"
        else:
            macro_pattern = "balanced"
        
        # Actualizar preferencia
        rating_impact = self.rating_scores[rating]
        current_score = intelligence_profile["learned_preferences"]["macro_patterns"][macro_pattern]
        learning_rate = 0.12  # 12% de impacto para macros
        
        new_score = current_score + (rating_impact * learning_rate)
        new_score = max(-2.0, min(2.0, new_score))
        
        intelligence_profile["learned_preferences"]["macro_patterns"][macro_pattern] = new_score
        
        return {
            "pattern_detected": macro_pattern,
            "macro_percentages": {
                "protein": round(protein_pct * 100, 1),
                "carbs": round(carbs_pct * 100, 1), 
                "fat": round(fat_pct * 100, 1)
            },
            "updated_score": new_score
        }
    
    def _learn_timing_preferences(self, recipe_data: Dict, rating: int, intelligence_profile: Dict) -> Dict:
        """
        Aprender preferencias de timing nutricional
        """
        timing_category = recipe_data.get("categoria_timing", "comida_principal")
        
        rating_impact = self.rating_scores[rating]
        current_score = intelligence_profile["learned_preferences"]["timing_patterns"][timing_category]
        learning_rate = 0.18  # 18% de impacto para timing
        
        new_score = current_score + (rating_impact * learning_rate)
        new_score = max(-2.0, min(2.0, new_score))
        
        intelligence_profile["learned_preferences"]["timing_patterns"][timing_category] = new_score
        
        return {
            "timing_category": timing_category,
            "updated_score": new_score
        }
    
    def _learn_complexity_preferences(self, recipe_data: Dict, rating: int, intelligence_profile: Dict) -> Dict:
        """
        Aprender preferencias de complejidad de recetas
        """
        # Calcular complejidad basándose en varios factores
        prep_time = recipe_data.get("tiempo_prep", 30)
        num_ingredients = len(recipe_data.get("ingredientes", []))
        num_steps = len(recipe_data.get("preparacion", []))
        difficulty = recipe_data.get("dificultad", "⭐⭐")
        
        # Calcular score de complejidad (-1 simple, 1 complejo)
        complexity_score = 0.0
        
        # Factor tiempo (más de 45 min = complejo)
        if prep_time > 45:
            complexity_score += 0.3
        elif prep_time < 20:
            complexity_score -= 0.3
        
        # Factor ingredientes
        if num_ingredients > 8:
            complexity_score += 0.3
        elif num_ingredients < 5:
            complexity_score -= 0.3
        
        # Factor pasos
        if num_steps > 6:
            complexity_score += 0.2
        elif num_steps < 4:
            complexity_score -= 0.2
        
        # Factor dificultad
        difficulty_stars = difficulty.count("⭐")
        if difficulty_stars > 3:
            complexity_score += 0.2
        elif difficulty_stars == 1:
            complexity_score -= 0.2
        
        complexity_score = max(-1.0, min(1.0, complexity_score))
        
        # Aprender preferencia
        rating_impact = self.rating_scores[rating]
        current_preference = intelligence_profile["learned_preferences"]["complexity_preference"]
        learning_rate = 0.1
        
        # Si al usuario le gustó una receta compleja, incrementar preferencia por complejidad
        preference_update = rating_impact * complexity_score * learning_rate
        new_preference = current_preference + preference_update
        new_preference = max(-1.0, min(1.0, new_preference))
        
        intelligence_profile["learned_preferences"]["complexity_preference"] = new_preference
        
        return {
            "recipe_complexity": complexity_score,
            "complexity_factors": {
                "prep_time": prep_time,
                "ingredients": num_ingredients,
                "steps": num_steps,
                "difficulty": difficulty_stars
            },
            "updated_preference": new_preference
        }
    
    def _update_user_base_preferences(self, user_profile: Dict, intelligence_profile: Dict) -> None:
        """
        Actualizar las preferencias base del usuario basándose en el aprendizaje
        """
        learned_prefs = intelligence_profile["learned_preferences"]
        
        # Actualizar alimentos preferidos basándose en ingredientes con score positivo
        positive_ingredients = {
            ingredient: score for ingredient, score in learned_prefs["ingredients"].items()
            if score > 0.5  # Umbral para considerarlo preferido
        }
        
        # Mapear ingredientes específicos a categorías de alimentos
        ingredient_to_category = {
            "pollo": "aves", "pavo": "aves",
            "salmón": "pescados", "atún": "pescados", "lubina": "pescados",
            "huevos": "huevos",
            "almendras": "frutos_secos", "nueces": "frutos_secos", "pistachos": "frutos_secos",
            "yogur": "lacteos", "queso": "lacteos",
            "garbanzos": "legumbres", "lentejas": "legumbres",
            "brócoli": "cruciferas", "coliflor": "cruciferas",
            "aceitunas": "aceitunas", "aceite": "aceitunas"
        }
        
        # Actualizar preferencias del usuario
        if "preferences" not in user_profile:
            user_profile["preferences"] = {"liked_foods": [], "disliked_foods": []}
        
        current_liked = set(user_profile["preferences"]["liked_foods"])
        
        # Añadir nuevas preferencias aprendidas
        for ingredient, score in positive_ingredients.items():
            for ingredient_key, category in ingredient_to_category.items():
                if ingredient_key in ingredient.lower() and category not in current_liked:
                    if score > 1.0:  # Solo añadir si el score es fuerte
                        user_profile["preferences"]["liked_foods"].append(category)
                        current_liked.add(category)
                    break
        
        # Actualizar métodos de cocción preferidos
        positive_methods = [
            method for method, score in learned_prefs["cooking_methods"].items()
            if score > 0.3
        ]
        
        if positive_methods:
            user_profile["preferences"]["cooking_methods"] = list(set(
                user_profile["preferences"].get("cooking_methods", []) + positive_methods
            ))
    
    def _generate_intelligent_recommendations(self, intelligence_profile: Dict) -> Dict:
        """
        Generar recomendaciones inteligentes basadas en aprendizaje
        """
        learned_prefs = intelligence_profile["learned_preferences"]
        
        # Top ingredientes recomendados
        top_ingredients = sorted(
            learned_prefs["ingredients"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Top métodos recomendados
        top_methods = sorted(
            learned_prefs["cooking_methods"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        # Patrón de macros favorito
        favorite_macro_pattern = max(
            learned_prefs["macro_patterns"].items(),
            key=lambda x: x[1]
        )[0]
        
        # Timing favorito
        favorite_timing = max(
            learned_prefs["timing_patterns"].items(),
            key=lambda x: x[1]
        )[0]
        
        return {
            "recommended_ingredients": [item[0] for item in top_ingredients if item[1] > 0],
            "avoid_ingredients": [item[0] for item in top_ingredients if item[1] < -0.5][-3:],
            "preferred_methods": [item[0] for item in top_methods if item[1] > 0],
            "favorite_macro_pattern": favorite_macro_pattern,
            "favorite_timing": favorite_timing,
            "complexity_preference": "complex" if learned_prefs["complexity_preference"] > 0.2 else "simple" if learned_prefs["complexity_preference"] < -0.2 else "moderate"
        }
    
    def _calculate_intelligence_score(self, intelligence_profile: Dict) -> float:
        """
        Calcular puntuación de inteligencia del sistema (0-100)
        """
        stats = intelligence_profile["basic_statistics"]
        total_ratings = stats["total_ratings"]
        
        if total_ratings == 0:
            return 0.0
        
        # Componentes del score
        data_volume_score = min(total_ratings / 20.0, 1.0) * 30  # Hasta 30 puntos por volumen de datos
        
        # Diversidad de ratings (mejor si hay variedad)
        rating_dist = list(stats["rating_distribution"].values())
        non_zero_ratings = sum(1 for count in rating_dist if count > 0)
        diversity_score = (non_zero_ratings / 5.0) * 25  # Hasta 25 puntos por diversidad
        
        # Consistencia (valoraciones no extremas)
        avg_rating = stats["average_rating"]
        consistency_score = (1.0 - abs(avg_rating - 3.0) / 2.0) * 20  # Hasta 20 puntos por consistencia
        
        # Recencia (valoraciones recientes)
        recent_ratings = sum(1 for record in intelligence_profile["ratings_history"][-10:] 
                           if (datetime.now() - datetime.fromisoformat(record["timestamp"])).days < 7)
        recency_score = min(recent_ratings / 5.0, 1.0) * 25  # Hasta 25 puntos por recencia
        
        total_score = data_volume_score + diversity_score + consistency_score + recency_score
        return round(min(total_score, 100.0), 1)
    
    def get_personalized_recipe_score(self, recipe_data: Dict, intelligence_profile: Dict) -> float:
        """
        Calcular score de personalización para una receta específica
        """
        if not intelligence_profile or intelligence_profile["basic_statistics"]["total_ratings"] == 0:
            return 0.5  # Score neutro si no hay datos
        
        learned_prefs = intelligence_profile["learned_preferences"]
        score = 0.0
        
        # Score por ingredientes
        ingredients = recipe_data.get("ingredientes", [])
        ingredient_scores = []
        
        for ingredient_data in ingredients:
            ingredient_name = ingredient_data.get("nombre", "").lower()
            ingredient_score = learned_prefs["ingredients"].get(ingredient_name, 0.0)
            ingredient_scores.append(ingredient_score)
        
        if ingredient_scores:
            avg_ingredient_score = sum(ingredient_scores) / len(ingredient_scores)
            score += avg_ingredient_score * self.learning_weights["ingredient_preference"]
        
        # Score por método de cocción (simplificado)
        method_score = learned_prefs["cooking_methods"].get("sarten", 0.0)  # Default
        score += method_score * self.learning_weights["cooking_method_preference"]
        
        # Score por timing
        timing_category = recipe_data.get("categoria_timing", "comida_principal")
        timing_score = learned_prefs["timing_patterns"].get(timing_category, 0.0)
        score += timing_score * self.learning_weights["timing_preference"]
        
        # Normalizar score a 0-1
        normalized_score = (score + 2.0) / 4.0  # score está entre -2 y 2
        return max(0.0, min(1.0, normalized_score))
    
    def format_intelligence_report_for_telegram(self, intelligence_profile: Dict, user_profile: Dict) -> str:
        """
        Formatear reporte de inteligencia para mostrar en Telegram
        """
        if not intelligence_profile:
            return "📊 **Sistema de aprendizje no inicializado**\n\nComienza valorando recetas con `/valorar_receta` para activar el aprendizaje inteligente."
        
        stats = intelligence_profile["basic_statistics"]
        learned_prefs = intelligence_profile["learned_preferences"]
        recommendations = self._generate_intelligent_recommendations(intelligence_profile)
        intelligence_score = self._calculate_intelligence_score(intelligence_profile)
        
        # Encabezado
        text = f"""
🧠 **REPORTE DE INTELIGENCIA NUTRICIONAL**

👤 **Usuario:** {user_profile['basic_data']['objetivo_descripcion']}
📊 **Puntuación IA:** {intelligence_score}/100
⭐ **Valoración promedio:** {stats['average_rating']:.1f}/5.0
📈 **Total valoraciones:** {stats['total_ratings']}

"""
        
        # Distribución de valoraciones
        text += "📈 **DISTRIBUCIÓN DE VALORACIONES:**\n"
        for rating in range(1, 6):
            count = stats['rating_distribution'][rating]
            percentage = (count / stats['total_ratings'] * 100) if stats['total_ratings'] > 0 else 0
            stars = "⭐" * rating
            bar = "█" * int(percentage / 10)
            text += f"{stars} {count} ({percentage:.1f}%) {bar}\n"
        
        text += "\n"
        
        # Ingredientes aprendidos
        if recommendations["recommended_ingredients"]:
            text += "✅ **INGREDIENTES QUE PREFIERES:**\n"
            for ingredient in recommendations["recommended_ingredients"][:5]:
                score = learned_prefs["ingredients"][ingredient]
                text += f"• {ingredient.title()} ({score:+.1f})\n"
            text += "\n"
        
        if recommendations["avoid_ingredients"]:
            text += "❌ **INGREDIENTES QUE EVITAS:**\n"
            for ingredient in recommendations["avoid_ingredients"]:
                score = learned_prefs["ingredients"][ingredient]
                text += f"• {ingredient.title()} ({score:+.1f})\n"
            text += "\n"
        
        # Métodos de cocción preferidos
        if recommendations["preferred_methods"]:
            text += "👨‍🍳 **MÉTODOS DE COCCIÓN FAVORITOS:**\n"
            for method in recommendations["preferred_methods"]:
                score = learned_prefs["cooking_methods"][method]
                text += f"• {method.title()} ({score:+.1f})\n"
            text += "\n"
        
        # Patrones nutricionales
        text += f"""
🎯 **PATRONES NUTRICIONALES APRENDIDOS:**
• Distribución de macros favorita: {recommendations['favorite_macro_pattern'].replace('_', ' ').title()}
• Timing preferido: {recommendations['favorite_timing'].replace('_', ' ').title()}
• Complejidad: {recommendations['complexity_preference'].title()}

"""
        
        # Nivel de confianza
        confidence_level = "Alta" if intelligence_score > 70 else "Media" if intelligence_score > 40 else "Baja"
        confidence_emoji = "🟢" if intelligence_score > 70 else "🟡" if intelligence_score > 40 else "🔴"
        
        text += f"""
{confidence_emoji} **CONFIANZA DEL SISTEMA:** {confidence_level}

💡 **PRÓXIMOS PASOS PARA MEJORAR IA:**
"""
        
        # Recomendaciones para mejorar
        if stats['total_ratings'] < 10:
            text += "• Valora más recetas para obtener mejores recomendaciones\n"
        
        if len(set(stats['rating_distribution'].values())) < 3:
            text += "• Usa toda la escala de valoración (1-5 estrellas)\n"
        
        recent_ratings = sum(1 for record in intelligence_profile["ratings_history"][-5:] 
                           if (datetime.now() - datetime.fromisoformat(record["timestamp"])).days < 30)
        if recent_ratings < 3:
            text += "• Valora recetas más frecuentemente para mantener la IA actualizada\n"
        
        text += f"""

🤖 **COMANDOS IA:**
• `/valorar_receta` - Valorar receta actual
• `/generar` - Crear recetas con IA personalizada
• `/nueva_semana` - Plans semanales inteligentes

**¡La IA mejora automáticamente con cada valoración!**
"""
        
        return text

# Ejemplo de uso
if __name__ == "__main__":
    intelligence = RecipeIntelligence()
    
    # Perfil de usuario de ejemplo
    sample_profile = {
        "basic_data": {"objetivo_descripcion": "Recomposición corporal"},
        "preferences": {"liked_foods": ["pescados"], "disliked_foods": []}
    }
    
    # Receta de ejemplo
    sample_recipe = {
        "nombre": "Salmón a la plancha con brócoli",
        "ingredientes": [
            {"nombre": "Salmón fresco", "cantidad": 150, "unidad": "g"},
            {"nombre": "Brócoli", "cantidad": 200, "unidad": "g"}
        ],
        "macros_por_porcion": {
            "calorias": 350,
            "proteinas": 30,
            "carbohidratos": 15,
            "grasas": 20
        },
        "categoria_timing": "comida_principal",
        "tiempo_prep": 25,
        "dificultad": "⭐⭐"
    }
    
    # Simular aprendizaje
    result = intelligence.learn_from_rating(sample_profile, sample_recipe, 5, "¡Delicioso y saludable!")
    
    print("=== RESULTADO DEL APRENDIZAJE ===")
    print(f"Éxito: {result['success']}")
    if result["success"]:
        print(f"Puntuación IA: {result['intelligence_score']}")
        print("Recomendaciones actualizadas:", result['updated_recommendations'])