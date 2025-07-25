"""
Sistema de display de menús con timing nutricional
Formatea menús divididos por desayuno, pre/post entreno, almuerzo, cena
"""

from typing import Dict, List
from datetime import datetime

class MenuDisplaySystem:
    
    def __init__(self):
        # Mapeo de timing a comidas del día
        self.timing_to_meals = {
            "desayuno": {
                "timing_categories": ["pre_entreno", "snack_complemento"],
                "emoji": "🌅",
                "description": "Desayuno y pre-entreno"
            },
            "media_manana": {
                "timing_categories": ["snack_complemento"],
                "emoji": "☀️", 
                "description": "Media mañana"
            },
            "almuerzo": {
                "timing_categories": ["comida_principal", "post_entreno"],
                "emoji": "🍽️",
                "description": "Almuerzo y post-entreno"
            },
            "media_tarde": {
                "timing_categories": ["snack_complemento"],
                "emoji": "🌞",
                "description": "Media tarde"
            },
            "cena": {
                "timing_categories": ["comida_principal"],
                "emoji": "🌙",
                "description": "Cena"
            }
        }
        
        # Días de la semana
        self.days = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES"]
    
    def create_weekly_menu_display(self, user_profile: Dict, weekly_recipes: Dict = None, weekly_complements: Dict = None) -> str:
        """
        Crear display del menú semanal con timing nutricional
        """
        
        if not weekly_recipes:
            # Si no hay menú generado, crear uno básico con las recetas actuales
            weekly_recipes = self._create_default_weekly_menu(user_profile)
        
        if not weekly_complements:
            weekly_complements = self._create_default_complements(user_profile)
        
        # Header del menú
        menu_text = self._create_menu_header(user_profile)
        
        # Menú día por día
        for day in self.days:
            day_menu = self._create_daily_menu(
                day, 
                weekly_recipes.get(day.lower(), {}),
                weekly_complements.get(day.lower(), {}),
                user_profile
            )
            menu_text += day_menu
        
        # Footer con instrucciones
        menu_text += self._create_menu_footer()
        
        return menu_text
    
    def _create_menu_header(self, user_profile: Dict) -> str:
        """Crear header del menú con información del usuario"""
        
        basic_data = user_profile.get("basic_data", {})
        macros = user_profile.get("macros", {})
        energy_data = user_profile.get("energy_data", {})
        
        current_week = datetime.now().isocalendar()[1] % 4 + 1  # Rotación cada 4 semanas
        
        header = f"""
📅 **MENÚ SEMANAL (LUNES - VIERNES)**
🗓️ Semana {current_week} • Comida Natural

🎯 **MACROS DIARIOS TOTALES:**
• {macros.get('calories', 0)} kcal | {macros.get('protein_g', 0)}g proteína
• {macros.get('carbs_g', 0)}g carbos | {macros.get('fat_g', 0)}g grasas
• Available Energy: {energy_data.get('available_energy', 0)} kcal/kg FFM/día
• Distribuido en timing nutricional óptimo

"""
        return header
    
    def _create_daily_menu(self, day: str, day_recipes: Dict, day_complements: Dict, user_profile: Dict) -> str:
        """Crear menú de un día específico con timing"""
        
        day_text = f"📋 **{day}**\n\n"
        
        # Iterar por cada momento del día
        for meal_time, meal_info in self.timing_to_meals.items():
            emoji = meal_info["emoji"]
            description = meal_info["description"]
            
            day_text += f"{emoji} **{description.upper()}:**\n"
            
            # Buscar recetas para este timing
            meal_recipes = []
            meal_complements = []
            
            for timing_category in meal_info["timing_categories"]:
                # Buscar recetas de este timing
                if timing_category in day_recipes:
                    meal_recipes.extend(day_recipes[timing_category])
                
                # Buscar complementos de este timing
                if timing_category in day_complements:
                    meal_complements.extend(day_complements[timing_category])
            
            # Mostrar recetas principales
            if meal_recipes:
                for recipe in meal_recipes:
                    recipe_name = recipe.get("name", "Receta")
                    portion = recipe.get("portion", 1.0)
                    macros = recipe.get("macros_per_serving", {})
                    
                    day_text += f"• {recipe_name}: {portion:.1f} porción\n"
                    day_text += f"  ({macros.get('calories', 0)} kcal, {macros.get('protein', 0)}P/{macros.get('carbs', 0)}C/{macros.get('fat', 0)}G)\n"
            
            # Mostrar complementos
            if meal_complements:
                day_text += "🥜 **Complementos:**\n"
                for complement in meal_complements:
                    comp_name = complement.get("name", "Complemento")
                    amount = complement.get("amount", 30)
                    unit = complement.get("unit", "g")
                    macros = complement.get("macros_per_portion", {})
                    
                    day_text += f"• {comp_name}: {amount}{unit}\n"
                    day_text += f"  ({macros.get('calories', 0)} kcal, {macros.get('protein', 0)}P/{macros.get('carbs', 0)}C/{macros.get('fat', 0)}G)\n"
            
            day_text += "\n"
        
        # Resumen de macros del día
        daily_macros = self._calculate_daily_macros(day_recipes, day_complements)
        day_text += f"📊 **MACROS TOTALES DEL DÍA:**\n"
        day_text += f"• {daily_macros['calories']} kcal • {daily_macros['protein']}g prot\n"
        day_text += f"• {daily_macros['carbs']}g carbs • {daily_macros['fat']}g grasas\n\n"
        
        return day_text
    
    def _create_default_weekly_menu(self, user_profile: Dict) -> Dict:
        """Crear menú por defecto basado en el perfil del usuario"""
        
        # Por ahora crear estructura básica - se mejorará con IA
        default_menu = {}
        
        for day in ["lunes", "martes", "miercoles", "jueves", "viernes"]:
            default_menu[day] = {
                "pre_entreno": [
                    {
                        "name": "Plátano con Miel",
                        "portion": 1.0,
                        "macros_per_serving": {"protein": 2, "carbs": 35, "fat": 1, "calories": 160}
                    }
                ],
                "post_entreno": [
                    {
                        "name": "Batido Proteína + Avena",
                        "portion": 1.0,
                        "macros_per_serving": {"protein": 35, "carbs": 30, "fat": 8, "calories": 320}
                    }
                ],
                "comida_principal": [
                    {
                        "name": "Pollo con Quinoa y Verduras",
                        "portion": 2.0,
                        "macros_per_serving": {"protein": 40, "carbs": 45, "fat": 15, "calories": 450}
                    },
                    {
                        "name": "Legumbres Mediterráneas", 
                        "portion": 1.5,
                        "macros_per_serving": {"protein": 15, "carbs": 35, "fat": 3, "calories": 225}
                    }
                ]
            }
        
        return default_menu
    
    def _create_default_complements(self, user_profile: Dict) -> Dict:
        """Crear complementos por defecto"""
        
        default_complements = {}
        
        for day in ["lunes", "martes", "miercoles", "jueves", "viernes"]:
            default_complements[day] = {
                "snack_complemento": [
                    {
                        "name": "Almendras Crudas",
                        "amount": 30,
                        "unit": "g",
                        "macros_per_portion": {"protein": 6, "carbs": 3, "fat": 15, "calories": 174}
                    },
                    {
                        "name": "Yogur Griego Natural",
                        "amount": 150,
                        "unit": "g", 
                        "macros_per_portion": {"protein": 15, "carbs": 6, "fat": 10, "calories": 130}
                    },
                    {
                        "name": "Manzana Verde",
                        "amount": 150,
                        "unit": "g",
                        "macros_per_portion": {"protein": 0, "carbs": 19, "fat": 0, "calories": 78}
                    }
                ]
            }
        
        return default_complements
    
    def _calculate_daily_macros(self, day_recipes: Dict, day_complements: Dict) -> Dict:
        """Calcular macros totales del día"""
        
        total_macros = {"protein": 0, "carbs": 0, "fat": 0, "calories": 0}
        
        # Sumar macros de recetas
        for timing_recipes in day_recipes.values():
            for recipe in timing_recipes:
                macros = recipe.get("macros_per_serving", {})
                portion = recipe.get("portion", 1.0)
                
                total_macros["protein"] += macros.get("protein", 0) * portion
                total_macros["carbs"] += macros.get("carbs", 0) * portion
                total_macros["fat"] += macros.get("fat", 0) * portion
                total_macros["calories"] += macros.get("calories", 0) * portion
        
        # Sumar macros de complementos
        for timing_complements in day_complements.values():
            for complement in timing_complements:
                macros = complement.get("macros_per_portion", {})
                
                total_macros["protein"] += macros.get("protein", 0)
                total_macros["carbs"] += macros.get("carbs", 0)
                total_macros["fat"] += macros.get("fat", 0)
                total_macros["calories"] += macros.get("calories", 0)
        
        # Redondear valores
        for key in total_macros:
            total_macros[key] = round(total_macros[key])
        
        return total_macros
    
    def _create_menu_footer(self) -> str:
        """Crear footer con instrucciones"""
        
        footer = """
💡 **INSTRUCCIONES DE USO:**
1. Sigue el timing nutricional para optimizar tu rendimiento
2. Los complementos completan tus macros diarios
3. Usa /generar para crear recetas específicas por timing
4. Usa /buscar para encontrar alternativas
5. Configura variedad con /nueva_semana

🔄 **Próxima rotación:** Automática cada lunes
🤖 **Personalización:** Usa /generar para recetas específicas
"""
        
        return footer

# Función de utilidad para integración
def format_menu_for_telegram(user_profile: Dict) -> str:
    """Función principal para formatear menú para Telegram"""
    
    display_system = MenuDisplaySystem()
    return display_system.create_weekly_menu_display(user_profile)

# Testing
if __name__ == "__main__":
    # Test del sistema de display
    sample_profile = {
        "basic_data": {
            "objetivo": "subir_masa",
            "objetivo_descripcion": "Ganar músculo minimizando grasa"
        },
        "macros": {
            "protein_g": 258,
            "carbs_g": 388, 
            "fat_g": 96,
            "calories": 3446
        },
        "energy_data": {
            "available_energy": 45.2
        }
    }
    
    display_system = MenuDisplaySystem()
    menu_text = display_system.create_weekly_menu_display(sample_profile)
    
    print("🧪 TESTING MENU DISPLAY SYSTEM...")
    print(f"✅ Menu generated: {len(menu_text)} characters")
    print(f"✅ Contains timing structure: {'DESAYUNO' in menu_text.upper()}")
    print(f"✅ Contains complements: {'Complementos' in menu_text}")
    print("🎉 Menu display system ready!")