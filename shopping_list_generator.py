#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema generador de listas de compras personalizadas
Genera listas de compras automáticas basadas en el menú semanal del usuario y sus preferencias
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

class ShoppingListGenerator:
    
    def __init__(self):
        # Base de datos de ingredientes con categorías
        self.ingredient_categories = {
            # Proteínas animales
            "proteinas_animales": {
                "pollo": {"base_amount": 200, "unit": "g", "shelf_life": 3},
                "pechuga_pollo": {"base_amount": 150, "unit": "g", "shelf_life": 3},
                "salmón": {"base_amount": 120, "unit": "g", "shelf_life": 2},
                "atún_fresco": {"base_amount": 120, "unit": "g", "shelf_life": 2},
                "huevos": {"base_amount": 2, "unit": "unidades", "shelf_life": 14},
                "ternera": {"base_amount": 120, "unit": "g", "shelf_life": 3},
                "pavo": {"base_amount": 120, "unit": "g", "shelf_life": 3}
            },
            
            # Carbohidratos complejos
            "carbohidratos": {
                "arroz_integral": {"base_amount": 80, "unit": "g", "shelf_life": 365},
                "quinoa": {"base_amount": 60, "unit": "g", "shelf_life": 365},
                "avena": {"base_amount": 50, "unit": "g", "shelf_life": 365},
                "pan_integral": {"base_amount": 60, "unit": "g", "shelf_life": 5},
                "pasta_integral": {"base_amount": 80, "unit": "g", "shelf_life": 365},
                "batata": {"base_amount": 150, "unit": "g", "shelf_life": 14}
            },
            
            # Verduras y vegetales
            "verduras": {
                "brócoli": {"base_amount": 150, "unit": "g", "shelf_life": 5},
                "espinacas": {"base_amount": 100, "unit": "g", "shelf_life": 3},
                "pimientos": {"base_amount": 100, "unit": "g", "shelf_life": 7},
                "tomates": {"base_amount": 150, "unit": "g", "shelf_life": 7},
                "cebolla": {"base_amount": 50, "unit": "g", "shelf_life": 30},
                "ajo": {"base_amount": 10, "unit": "g", "shelf_life": 30},
                "zanahoria": {"base_amount": 100, "unit": "g", "shelf_life": 14},
                "calabacín": {"base_amount": 150, "unit": "g", "shelf_life": 7}
            },
            
            # Legumbres
            "legumbres": {
                "garbanzos": {"base_amount": 80, "unit": "g", "shelf_life": 365},
                "lentejas": {"base_amount": 80, "unit": "g", "shelf_life": 365},
                "alubias": {"base_amount": 80, "unit": "g", "shelf_life": 365},
                "judías_verdes": {"base_amount": 150, "unit": "g", "shelf_life": 5}
            },
            
            # Lácteos
            "lacteos": {
                "yogur_griego": {"base_amount": 150, "unit": "g", "shelf_life": 14},
                "queso_feta": {"base_amount": 30, "unit": "g", "shelf_life": 21},
                "queso_fresco": {"base_amount": 50, "unit": "g", "shelf_life": 14}
            },
            
            # Frutos secos y semillas
            "frutos_secos": {
                "almendras": {"base_amount": 30, "unit": "g", "shelf_life": 180},
                "nueces": {"base_amount": 25, "unit": "g", "shelf_life": 180},
                "pistachos": {"base_amount": 25, "unit": "g", "shelf_life": 180},
                "semillas_chía": {"base_amount": 15, "unit": "g", "shelf_life": 365}
            },
            
            # Aceites y grasas
            "aceites": {
                "aceite_oliva": {"base_amount": 15, "unit": "ml", "shelf_life": 365},
                "aceitunas": {"base_amount": 20, "unit": "g", "shelf_life": 90}
            },
            
            # Frutas
            "frutas": {
                "plátano": {"base_amount": 100, "unit": "g", "shelf_life": 7},
                "manzana": {"base_amount": 150, "unit": "g", "shelf_life": 14},
                "naranja": {"base_amount": 150, "unit": "g", "shelf_life": 14},
                "fresas": {"base_amount": 100, "unit": "g", "shelf_life": 3}
            },
            
            # Hierbas y especias
            "hierbas_especias": {
                "orégano": {"base_amount": 2, "unit": "g", "shelf_life": 365},
                "tomillo": {"base_amount": 2, "unit": "g", "shelf_life": 365},
                "perejil": {"base_amount": 10, "unit": "g", "shelf_life": 7},
                "albahaca": {"base_amount": 10, "unit": "g", "shelf_life": 7},
                "jengibre": {"base_amount": 10, "unit": "g", "shelf_life": 21}
            },
            
            # Otros básicos
            "basicos": {
                "miel": {"base_amount": 15, "unit": "g", "shelf_life": 365},
                "limón": {"base_amount": 50, "unit": "g", "shelf_life": 21},
                "vinagre_balsámico": {"base_amount": 10, "unit": "ml", "shelf_life": 365}
            }
        }
        
        # Mapeo de preferencias del usuario a categorías de ingredientes
        self.preference_mapping = {
            "aves": ["pollo", "pechuga_pollo", "pavo"],
            "pescados": ["salmón", "atún_fresco"],
            "carnes_rojas": ["ternera"],
            "huevos": ["huevos"],
            "lacteos": ["yogur_griego", "queso_feta", "queso_fresco"],
            "frutos_secos": ["almendras", "nueces", "pistachos"],
            "legumbres": ["garbanzos", "lentejas", "alubias"],
            "cruciferas": ["brócoli"],
            "aceitunas": ["aceitunas", "aceite_oliva"]
        }
    
    def generate_shopping_list(self, user_profile: Dict, days: int = 5) -> Dict:
        """
        Generar lista de compras personalizada para X días
        """
        try:
            # Obtener preferencias del usuario
            preferences = user_profile.get("preferences", {})
            liked_foods = preferences.get("liked_foods", [])
            disliked_foods = preferences.get("disliked_foods", [])
            
            # Datos nutricionales del usuario
            macros = user_profile["macros"]
            daily_calories = macros["calories"]
            daily_protein = macros["protein_g"]
            daily_carbs = macros["carbs_g"]
            daily_fat = macros["fat_g"]
            
            # Objetivo del usuario para adaptar proporciones
            objective = user_profile["basic_data"]["objetivo"]
            
            # Generar lista base según macros y días
            base_shopping_list = self._calculate_base_quantities(
                daily_calories, daily_protein, daily_carbs, daily_fat, days
            )
            
            # Aplicar preferencias del usuario
            personalized_list = self._apply_user_preferences(
                base_shopping_list, liked_foods, disliked_foods
            )
            
            # Optimizar para meal prep (agrupación inteligente)
            optimized_list = self._optimize_for_meal_prep(personalized_list, days)
            
            # Añadir complementos mediterráneos personalizados
            mediterranean_list = self._add_mediterranean_complements(
                optimized_list, preferences, objective
            )
            
            # Formatear resultado final
            return {
                "success": True,
                "shopping_list": mediterranean_list,
                "metadata": {
                    "generated_for_days": days,
                    "daily_calories": daily_calories,
                    "user_objective": objective,
                    "liked_foods_count": len(liked_foods),
                    "disliked_foods_count": len(disliked_foods),
                    "generated_at": datetime.now().isoformat()
                },
                "meal_prep_tips": self._get_meal_prep_shopping_tips(days)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error generating shopping list: {str(e)}",
                "shopping_list": None
            }
    
    def _calculate_base_quantities(self, calories: float, protein: float, carbs: float, fat: float, days: int) -> Dict:
        """
        Calcular cantidades base de ingredientes según macros objetivo
        """
        base_list = {}
        
        # Distribución estimada de macros por categorías
        protein_distribution = {
            "proteinas_animales": 0.75,  # 75% de proteína de fuentes animales
            "lacteos": 0.15,             # 15% de lácteos
            "legumbres": 0.10            # 10% de legumbres
        }
        
        carbs_distribution = {
            "carbohidratos": 0.60,       # 60% carbohidratos complejos
            "frutas": 0.25,              # 25% frutas
            "verduras": 0.15             # 15% verduras
        }
        
        fat_distribution = {
            "aceites": 0.40,             # 40% aceites y aceitunas
            "frutos_secos": 0.35,        # 35% frutos secos
            "proteinas_animales": 0.25   # 25% grasas de proteínas
        }
        
        # Calcular proteínas por días
        for category, percentage in protein_distribution.items():
            target_protein = protein * percentage * days
            if category not in base_list:
                base_list[category] = {}
            
            # Distribuir entre ingredientes de la categoría
            ingredients = list(self.ingredient_categories[category].keys())
            protein_per_ingredient = target_protein / len(ingredients)
            
            for ingredient in ingredients:
                # Estimación: 1g proteína ≈ 4-6g ingrediente (varía por fuente)
                multiplier = 5 if category == "proteinas_animales" else 8
                quantity = int(protein_per_ingredient * multiplier)
                
                base_list[category][ingredient] = {
                    "quantity": quantity,
                    "unit": self.ingredient_categories[category][ingredient]["unit"]
                }
        
        # Calcular carbohidratos por días
        for category, percentage in carbs_distribution.items():
            target_carbs = carbs * percentage * days
            if category not in base_list:
                base_list[category] = {}
            
            ingredients = list(self.ingredient_categories[category].keys())
            carbs_per_ingredient = target_carbs / len(ingredients)
            
            for ingredient in ingredients:
                # Estimación: 1g carbos ≈ 3-4g ingrediente
                multiplier = 3.5
                quantity = int(carbs_per_ingredient * multiplier)
                
                if ingredient not in base_list[category]:
                    base_list[category][ingredient] = {
                        "quantity": quantity,
                        "unit": self.ingredient_categories[category][ingredient]["unit"]
                    }
                else:
                    base_list[category][ingredient]["quantity"] += quantity
        
        # Calcular grasas por días
        for category, percentage in fat_distribution.items():
            target_fat = fat * percentage * days
            if category not in base_list:
                base_list[category] = {}
            
            if category == "proteinas_animales":
                continue  # Ya calculado arriba
            
            ingredients = list(self.ingredient_categories[category].keys())
            fat_per_ingredient = target_fat / len(ingredients)
            
            for ingredient in ingredients:
                # Estimación: 1g grasa ≈ 2-3g ingrediente (frutos secos/aceites)
                multiplier = 2.5
                quantity = int(fat_per_ingredient * multiplier)
                
                if ingredient not in base_list[category]:
                    base_list[category][ingredient] = {
                        "quantity": quantity,
                        "unit": self.ingredient_categories[category][ingredient]["unit"]
                    }
                else:
                    base_list[category][ingredient]["quantity"] += quantity
        
        return base_list
    
    def _apply_user_preferences(self, base_list: Dict, liked_foods: List[str], disliked_foods: List[str]) -> Dict:
        """
        Aplicar preferencias del usuario a la lista base
        """
        personalized_list = {}
        
        # Mapear preferencias a ingredientes específicos
        liked_ingredients = []
        disliked_ingredients = []
        
        for preference in liked_foods:
            if preference in self.preference_mapping:
                liked_ingredients.extend(self.preference_mapping[preference])
        
        for preference in disliked_foods:
            if preference in self.preference_mapping:
                disliked_ingredients.extend(self.preference_mapping[preference])
        
        for category, ingredients in base_list.items():
            personalized_list[category] = {}
            
            for ingredient, data in ingredients.items():
                # Excluir alimentos no deseados
                if ingredient in disliked_ingredients:
                    continue
                
                # Aumentar cantidad de alimentos preferidos (150%)
                if ingredient in liked_ingredients:
                    data["quantity"] = int(data["quantity"] * 1.5)
                    data["preferred"] = True
                else:
                    data["preferred"] = False
                
                personalized_list[category][ingredient] = data
        
        return personalized_list
    
    def _optimize_for_meal_prep(self, shopping_list: Dict, days: int) -> Dict:
        """
        Optimizar lista para meal prep eficiente
        """
        optimized_list = {}
        
        for category, ingredients in shopping_list.items():
            optimized_list[category] = {}
            
            for ingredient, data in ingredients.items():
                # Ajustar cantidades según shelf life y meal prep
                shelf_life = self.ingredient_categories[category][ingredient]["shelf_life"]
                
                # Si el ingrediente dura menos que los días planificados, ajustar
                if shelf_life < days:
                    # Dividir en 2 compras (mitad de semana)
                    data["split_purchase"] = True
                    data["first_purchase"] = int(data["quantity"] * 0.6)
                    data["second_purchase"] = data["quantity"] - data["first_purchase"]
                else:
                    data["split_purchase"] = False
                
                # Redondear a cantidades prácticas
                data["quantity"] = self._round_to_practical_quantity(
                    data["quantity"], data["unit"]
                )
                
                optimized_list[category][ingredient] = data
        
        return optimized_list
    
    def _add_mediterranean_complements(self, shopping_list: Dict, preferences: Dict, objective: str) -> Dict:
        """
        Añadir complementos mediterráneos específicos según objetivo
        """
        # Complementos mediterráneos por objetivo
        objective_complements = {
            "bajar_peso": ["limón", "vinagre_balsámico", "orégano", "tomillo"],
            "subir_masa": ["aceite_oliva", "almendras", "nueces", "miel"],
            "subir_masa_lean": ["aceitunas", "yogur_griego", "queso_feta", "perejil"],
            "recomposicion": ["aceite_oliva", "aceitunas", "almendras", "orégano"],
            "mantener": ["aceite_oliva", "limón", "miel", "albahaca"]
        }
        
        complements = objective_complements.get(objective, objective_complements["mantener"])
        
        # Añadir complementos si no están en la lista
        for complement in complements:
            added = False
            for category, ingredients in self.ingredient_categories.items():
                if complement in ingredients:
                    if category not in shopping_list:
                        shopping_list[category] = {}
                    
                    if complement not in shopping_list[category]:
                        shopping_list[category][complement] = {
                            "quantity": ingredients[complement]["base_amount"] * 5,  # Para 5 días
                            "unit": ingredients[complement]["unit"],
                            "preferred": False,
                            "mediterranean_complement": True
                        }
                    added = True
                    break
        
        return shopping_list
    
    def _round_to_practical_quantity(self, quantity: int, unit: str) -> int:
        """
        Redondear cantidades a valores prácticos para comprar
        """
        if unit == "g":
            if quantity < 100:
                return ((quantity + 24) // 25) * 25  # Redondear a 25g
            elif quantity < 500:
                return ((quantity + 49) // 50) * 50   # Redondear a 50g
            else:
                return ((quantity + 99) // 100) * 100 # Redondear a 100g
        
        elif unit == "ml":
            if quantity < 100:
                return ((quantity + 24) // 25) * 25
            else:
                return ((quantity + 49) // 50) * 50
        
        elif unit == "unidades":
            if quantity < 6:
                return max(2, quantity)
            else:
                return ((quantity + 5) // 6) * 6  # Redondear a media docena
        
        return quantity
    
    def _get_meal_prep_shopping_tips(self, days: int) -> List[str]:
        """
        Obtener consejos de compra para meal prep
        """
        tips = [
            f"🛒 Lista optimizada para {days} días de meal prep",
            "📦 Compra ingredientes frescos (verduras, carnes) al inicio de semana",
            "🥜 Los frutos secos y legumbres secas duran meses - compra cantidad",
            "🧊 Congela las porciones de carne que uses después del día 3",
            "🥬 Lava y corta verduras el día de compra para ahorrar tiempo",
            "⏰ Planifica 2 sesiones: domingo (proteínas) y miércoles (verduras frescas)"
        ]
        
        return tips
    
    def format_shopping_list_for_telegram(self, shopping_data: Dict, user_profile: Dict) -> str:
        """
        Formatear lista de compras para mostrar en Telegram
        """
        if not shopping_data["success"]:
            return f"❌ **Error generando lista:** {shopping_data.get('error', 'Error desconocido')}"
        
        shopping_list = shopping_data["shopping_list"]
        metadata = shopping_data["metadata"]
        
        # Encabezado personalizado
        text = f"""
🛒 **LISTA DE COMPRAS PERSONALIZADA**

👤 **Perfil:** {user_profile['basic_data']['objetivo_descripcion']}
📅 **Para:** {metadata['generated_for_days']} días de meal prep
🔥 **Calorías diarias:** {metadata['daily_calories']} kcal
⏰ **Generada:** {datetime.fromisoformat(metadata['generated_at']).strftime('%d/%m/%Y %H:%M')}

"""
        
        # Categorías con emojis
        category_display = {
            "proteinas_animales": "🥩 **PROTEÍNAS PRINCIPALES**",
            "carbohidratos": "🌾 **CARBOHIDRATOS COMPLEJOS**", 
            "verduras": "🥬 **VERDURAS Y VEGETALES**",
            "legumbres": "🫘 **LEGUMBRES**",
            "lacteos": "🥛 **LÁCTEOS NATURALES**",
            "frutos_secos": "🥜 **FRUTOS SECOS Y SEMILLAS**",
            "aceites": "🫒 **ACEITES Y GRASAS SALUDABLES**",
            "frutas": "🍎 **FRUTAS FRESCAS**",
            "hierbas_especias": "🌿 **HIERBAS Y ESPECIAS**",
            "basicos": "🍯 **BÁSICOS MEDITERRÁNEOS**"
        }
        
        # Generar lista por categorías
        for category, display_name in category_display.items():
            if category in shopping_list and shopping_list[category]:
                text += f"\n{display_name}\n"
                
                for ingredient, data in shopping_list[category].items():
                    quantity = data["quantity"]
                    unit = data["unit"]
                    
                    # Indicadores especiales
                    indicators = []
                    if data.get("preferred", False):
                        indicators.append("✅")
                    if data.get("mediterranean_complement", False):
                        indicators.append("🌊")
                    if data.get("split_purchase", False):
                        indicators.append("📅")
                    
                    indicator_text = " ".join(indicators) + " " if indicators else "• "
                    
                    # Formatear nombre del ingrediente
                    display_name = ingredient.replace("_", " ").title()
                    
                    text += f"{indicator_text}{display_name}: {quantity}{unit}\n"
                    
                    # Mostrar información de compras divididas
                    if data.get("split_purchase", False):
                        text += f"  📅 Dividir: {data['first_purchase']}{unit} + {data['second_purchase']}{unit}\n"
        
        # Resumen y consejos
        text += f"""

📊 **RESUMEN DE COMPRA:**
• Total de categorías: {len([cat for cat in shopping_list if shopping_list[cat]])}
• Ingredientes preferidos: {sum(1 for cat in shopping_list.values() for item in cat.values() if item.get('preferred', False))}
• Complementos mediterráneos: {sum(1 for cat in shopping_list.values() for item in cat.values() if item.get('mediterranean_complement', False))}

🎯 **LEYENDA:**
✅ = Alimento preferido (cantidad aumentada)
🌊 = Complemento mediterráneo para tu objetivo
📅 = Comprar en 2 veces (por frescura)

💡 **CONSEJOS DE MEAL PREP:**
"""
        
        # Añadir consejos
        tips = shopping_data["meal_prep_tips"]
        for tip in tips:
            text += f"• {tip}\n"
        
        text += f"""

🔄 **COMANDOS ÚTILES:**
• `/menu` - Ver tu menú semanal personalizado
• `/generar` - Crear recetas específicas
• `/favoritas` - Ver tus recetas guardadas
• `/nueva_semana` - Planificar próxima semana

**¡Lista optimizada para tu perfil nutricional!**
"""
        
        return text

# Ejemplo de uso
if __name__ == "__main__":
    generator = ShoppingListGenerator()
    
    # Perfil de ejemplo
    sample_profile = {
        "basic_data": {
            "objetivo": "subir_masa",
            "objetivo_descripcion": "Ganar músculo con superávit controlado"
        },
        "macros": {
            "calories": 2800,
            "protein_g": 180,
            "carbs_g": 300,
            "fat_g": 100
        },
        "preferences": {
            "liked_foods": ["aves", "frutos_secos", "legumbres"],
            "disliked_foods": ["pescados"]
        }
    }
    
    # Generar lista
    result = generator.generate_shopping_list(sample_profile, days=5)
    
    if result["success"]:
        formatted_list = generator.format_shopping_list_for_telegram(result, sample_profile)
        print("=== LISTA DE COMPRAS GENERADA ===")
        print(formatted_list)
    else:
        print(f"Error: {result['error']}")