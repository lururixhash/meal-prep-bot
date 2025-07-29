#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de menú semanal personalizado
Permite a los usuarios crear, configurar y gestionar menús semanales
basados en sus recetas guardadas con distribución inteligente
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

class WeeklyMenuSystem:
    
    def __init__(self, database_file: str):
        self.database_file = database_file
        
        # Días de la semana
        self.days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        
        # Categorías de comidas
        self.meal_categories = ["desayuno", "almuerzo", "merienda", "cena"]
        
    def get_user_saved_recipes(self, user_profile: Dict) -> Dict[str, List[Dict]]:
        """
        Obtener recetas guardadas del usuario organizadas por categoría
        """
        # Buscar recetas en favoritos y recetas generadas recientemente
        favorites = user_profile.get("favorites", {}).get("recipe_ids", [])
        recent_recipes = user_profile.get("recent_generated_recipes", [])
        temp_options = user_profile.get("temp_recipe_options", {})
        
        # Organizar por categoría
        recipes_by_category = {
            "desayuno": [],
            "almuerzo": [],
            "merienda": [], 
            "cena": []
        }
        
        # Procesar recetas recientes
        for recipe_data in recent_recipes:
            recipe = recipe_data.get("recipe", {})
            timing = recipe.get("categoria_timing", "comida_principal")
            
            # Mapear timing a categorías principales
            if timing == "desayuno":
                recipes_by_category["desayuno"].append({
                    "id": recipe.get("recipe_id", f"recent_{len(recipes_by_category['desayuno'])}"),
                    "name": recipe.get("nombre", "Receta sin nombre"),
                    "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                    "source": "recent",
                    "recipe_data": recipe
                })
            elif timing in ["almuerzo", "comida_principal"]:
                recipes_by_category["almuerzo"].append({
                    "id": recipe.get("recipe_id", f"recent_{len(recipes_by_category['almuerzo'])}"),
                    "name": recipe.get("nombre", "Receta sin nombre"),
                    "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                    "source": "recent",
                    "recipe_data": recipe
                })
            elif timing == "merienda":
                recipes_by_category["merienda"].append({
                    "id": recipe.get("recipe_id", f"recent_{len(recipes_by_category['merienda'])}"),
                    "name": recipe.get("nombre", "Receta sin nombre"),
                    "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                    "source": "recent",
                    "recipe_data": recipe
                })
            elif timing == "cena":
                recipes_by_category["cena"].append({
                    "id": recipe.get("recipe_id", f"recent_{len(recipes_by_category['cena'])}"),
                    "name": recipe.get("nombre", "Receta sin nombre"),
                    "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                    "source": "recent",
                    "recipe_data": recipe
                })
        
        # Procesar opciones temporales (de generaciones múltiples)
        for timing, temp_data in temp_options.items():
            options = temp_data.get("options", [])
            for option in options:
                recipe = option.get("recipe", {})
                
                if timing in recipes_by_category:
                    recipes_by_category[timing].append({
                        "id": f"temp_{timing}_{len(recipes_by_category[timing])}",
                        "name": recipe.get("nombre", "Receta temporal"),
                        "calories": recipe.get("macros_por_porcion", {}).get("calorias", 0),
                        "source": "temp",
                        "recipe_data": recipe
                    })
        
        return recipes_by_category
    
    def create_weekly_distribution(self, selected_recipes: Dict[str, List[str]], 
                                 user_profile: Dict) -> Dict[str, Dict[str, str]]:
        """
        Crear distribución semanal inteligente de recetas seleccionadas
        
        Args:
            selected_recipes: {"desayuno": ["recipe_id1", "recipe_id2"], ...}
            user_profile: Perfil del usuario
            
        Returns:
            {"lunes": {"desayuno": "recipe_id", "almuerzo": "recipe_id", ...}, ...}
        """
        weekly_menu = {}
        
        # Obtener recetas disponibles
        available_recipes = self.get_user_saved_recipes(user_profile)
        
        for day in self.days:
            weekly_menu[day] = {}
            
            for meal in self.meal_categories:
                recipe_ids = selected_recipes.get(meal, [])
                
                if not recipe_ids:
                    # Si no hay recetas seleccionadas para esta comida
                    weekly_menu[day][meal] = None
                    continue
                
                if len(recipe_ids) == 1:
                    # Solo una receta: usar todos los días
                    weekly_menu[day][meal] = recipe_ids[0]
                else:
                    # Múltiples recetas: distribución inteligente
                    weekly_menu[day][meal] = self._select_recipe_for_day(
                        recipe_ids, day, meal, weekly_menu
                    )
        
        return weekly_menu
    
    def _select_recipe_for_day(self, recipe_ids: List[str], day: str, meal: str, 
                              current_menu: Dict) -> str:
        """
        Seleccionar receta para un día específico evitando repeticiones consecutivas
        """
        day_index = self.days.index(day)
        
        # Si es el primer día, seleccionar aleatoriamente
        if day_index == 0:
            return random.choice(recipe_ids)
        
        # Obtener receta del día anterior
        previous_day = self.days[day_index - 1]
        previous_recipe = current_menu.get(previous_day, {}).get(meal)
        
        # Filtrar recetas para evitar repetición consecutiva
        available_recipes = [rid for rid in recipe_ids if rid != previous_recipe]
        
        # Si todas las recetas son iguales a la anterior, usar cualquiera
        if not available_recipes:
            available_recipes = recipe_ids
        
        # Selección con distribución equilibrada
        return self._balanced_selection(available_recipes, recipe_ids, day_index)
    
    def _balanced_selection(self, available_recipes: List[str], all_recipes: List[str], 
                          day_index: int) -> str:
        """
        Selección balanceada para maximizar variedad semanal
        """
        if len(all_recipes) == 2:
            # Para 2 recetas: alternar A-B-A-B-A-B-A
            return all_recipes[day_index % 2]
        elif len(all_recipes) == 3:
            # Para 3 recetas: A-B-C-A-B-C-A
            return all_recipes[day_index % 3]
        elif len(all_recipes) >= 4:
            # Para 4+ recetas: distribución más equilibrada
            # Asegurar que todas aparezcan al menos una vez en la semana
            if day_index < len(all_recipes):
                return all_recipes[day_index]
            else:
                # Para días restantes, selección aleatoria de disponibles
                return random.choice(available_recipes)
        else:
            return random.choice(available_recipes)
    
    def generate_menu_preview(self, weekly_menu: Dict, user_profile: Dict) -> str:
        """
        Generar preview del menú semanal en formato tabla
        """
        available_recipes = self.get_user_saved_recipes(user_profile)
        
        # Crear mapeo de IDs a nombres
        recipe_name_map = {}
        for category, recipes in available_recipes.items():
            for recipe in recipes:
                recipe_name_map[recipe["id"]] = recipe["name"]
        
        preview = f"""
📅 **PREVIEW DEL MENÚ SEMANAL**

👤 **Tu perfil:** {user_profile['basic_data']['objetivo_descripcion']}
🎯 **Enfoque:** {user_profile['basic_data'].get('enfoque_dietetico', 'fitness').title()}
🔥 **Calorías diarias:** {user_profile['macros']['calories']} kcal

┌─────────────┬────────────────────┬────────────────────┬────────────────────┬────────────────────┐
│     DÍA     │     🌅 DESAYUNO    │     🍽️ ALMUERZO    │     🥜 MERIENDA    │     🌙 CENA        │
├─────────────┼────────────────────┼────────────────────┼────────────────────┼────────────────────┤"""
        
        for day in self.days:
            day_menu = weekly_menu.get(day, {})
            
            # Formatear nombres de recetas (acortar si es necesario)
            meals = []
            for meal in self.meal_categories:
                recipe_id = day_menu.get(meal)
                if recipe_id and recipe_id in recipe_name_map:
                    name = recipe_name_map[recipe_id]
                    # Acortar nombre si es muy largo
                    display_name = name if len(name) <= 18 else f"{name[:15]}..."
                    meals.append(display_name)
                else:
                    meals.append("Sin asignar")
            
            preview += f"\n│ {day.upper():^11} │ {meals[0]:^18} │ {meals[1]:^18} │ {meals[2]:^18} │ {meals[3]:^18} │"
        
        preview += "\n└─────────────┴────────────────────┴────────────────────┴────────────────────┴────────────────────┘"
        
        # Estadísticas del menú
        stats = self._calculate_menu_stats(weekly_menu, available_recipes)
        preview += f"""

📊 **ESTADÍSTICAS DEL MENÚ:**
• Total de recetas únicas: {stats['unique_recipes']}
• Variabilidad por comida:
  - 🌅 Desayuno: {stats['breakfast_variety']} recetas diferentes
  - 🍽️ Almuerzo: {stats['lunch_variety']} recetas diferentes  
  - 🥜 Merienda: {stats['snack_variety']} recetas diferentes
  - 🌙 Cena: {stats['dinner_variety']} recetas diferentes

⚡ **Available Energy estimada:** {user_profile['energy_data']['available_energy']} kcal/kg FFM/día
"""
        
        return preview
    
    def _calculate_menu_stats(self, weekly_menu: Dict, available_recipes: Dict) -> Dict:
        """
        Calcular estadísticas del menú generado
        """
        all_used_recipes = set()
        meal_varieties = {"desayuno": set(), "almuerzo": set(), "merienda": set(), "cena": set()}
        
        for day_menu in weekly_menu.values():
            for meal, recipe_id in day_menu.items():
                if recipe_id:
                    all_used_recipes.add(recipe_id)
                    if meal in meal_varieties:
                        meal_varieties[meal].add(recipe_id)
        
        return {
            "unique_recipes": len(all_used_recipes),
            "breakfast_variety": len(meal_varieties["desayuno"]),
            "lunch_variety": len(meal_varieties["almuerzo"]),
            "snack_variety": len(meal_varieties["merienda"]),
            "dinner_variety": len(meal_varieties["cena"])
        }
    
    def save_weekly_menu_configuration(self, user_id: str, weekly_menu: Dict, 
                                     selected_recipes: Dict, user_profile: Dict) -> str:
        """
        Guardar configuración de menú semanal
        """
        config_id = f"menu_{user_id}_{int(datetime.now().timestamp())}"
        config_name = f"Menú Semana {datetime.now().strftime('%W/%Y')}"
        
        config = {
            "config_id": config_id,
            "config_name": config_name,
            "created_at": datetime.now().isoformat(),
            "user_id": user_id,
            "weekly_menu": weekly_menu,
            "selected_recipes": selected_recipes,
            "user_profile_snapshot": {
                "objetivo": user_profile["basic_data"]["objetivo"],
                "enfoque_dietetico": user_profile["basic_data"].get("enfoque_dietetico", "fitness"),
                "calories": user_profile["macros"]["calories"]
            },
            "status": "draft"  # draft, confirmed, active
        }
        
        # Guardar en el perfil del usuario
        if "weekly_menu_configs" not in user_profile:
            user_profile["weekly_menu_configs"] = []
        
        user_profile["weekly_menu_configs"].append(config)
        
        # Mantener solo las últimas 5 configuraciones
        if len(user_profile["weekly_menu_configs"]) > 5:
            user_profile["weekly_menu_configs"] = user_profile["weekly_menu_configs"][-5:]
        
        return config_id
    
    def get_saved_configurations(self, user_profile: Dict) -> List[Dict]:
        """
        Obtener configuraciones guardadas del usuario
        """
        return user_profile.get("weekly_menu_configs", [])
    
    def load_configuration(self, user_profile: Dict, config_id: str) -> Optional[Dict]:
        """
        Cargar una configuración específica
        """
        configs = self.get_saved_configurations(user_profile)
        for config in configs:
            if config["config_id"] == config_id:
                return config
        return None

# Ejemplo de uso y testing
if __name__ == "__main__":
    print("🧪 Testing WeeklyMenuSystem...")
    
    # Simular perfil de usuario
    sample_profile = {
        "basic_data": {
            "objetivo_descripcion": "Ganar músculo minimizando grasa",
            "enfoque_dietetico": "fitness"
        },
        "macros": {"calories": 2800},
        "energy_data": {"available_energy": 52.5},
        "recent_generated_recipes": [
            {
                "recipe": {
                    "nombre": "Tortilla de espinacas",
                    "categoria_timing": "desayuno",
                    "macros_por_porcion": {"calorias": 380}
                }
            },
            {
                "recipe": {
                    "nombre": "Pollo con quinoa",
                    "categoria_timing": "almuerzo", 
                    "macros_por_porcion": {"calorias": 520}
                }
            }
        ]
    }
    
    menu_system = WeeklyMenuSystem("test.json")
    
    # Test obtener recetas guardadas
    recipes = menu_system.get_user_saved_recipes(sample_profile)
    print("✅ Recetas por categoría obtenidas")
    
    # Test crear distribución semanal
    selected = {
        "desayuno": ["recent_0"],
        "almuerzo": ["recent_0"], 
        "merienda": [],
        "cena": []
    }
    
    weekly_menu = menu_system.create_weekly_distribution(selected, sample_profile)
    print("✅ Distribución semanal creada")
    
    # Test preview
    preview = menu_system.generate_menu_preview(weekly_menu, sample_profile)
    print("✅ Preview generado")
    print(preview[:200] + "...")
    
    print("\n🎉 WeeklyMenuSystem funcionando correctamente")