"""
Sistema de perfiles multiusuario con cálculo de Available Energy
Basado en evidencia científica de la documentación nutricional
"""

import json
import math
from datetime import datetime
from typing import Dict, Optional, List, Tuple

class UserProfileSystem:
    
    def __init__(self, database_file: str):
        self.database_file = database_file
        self.exercise_met_values = {
            # MET values (Metabolic Equivalent of Task)
            "fuerza": {
                "intensidad_baja": 3.0,    # Pesas ligeras, descansos largos
                "intensidad_media": 4.5,   # Entrenamiento típico de fuerza
                "intensidad_alta": 6.0     # Powerlifting, alta intensidad
            },
            "cardio": {
                "caminar": 3.5,
                "trotar": 7.0,
                "correr": 10.0,
                "bicicleta": 8.0,
                "natacion": 9.0,
                "eliptica": 6.0
            },
            "deportes": {
                "futbol": 8.0,
                "baloncesto": 7.5,
                "tenis": 6.5,
                "padel": 6.0,
                "voley": 4.0
            },
            "hiit": {
                "intensidad_moderada": 8.0,
                "intensidad_alta": 12.0
            }
        }
    
    def calculate_bmr(self, peso: float, altura: float, edad: int, sexo: str) -> float:
        """Calcular BMR usando fórmula Mifflin-St Jeor (más precisa)"""
        if sexo.lower() == "masculino":
            bmr = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
        else:
            bmr = (10 * peso) + (6.25 * altura) - (5 * edad) - 161
        return bmr
    
    def calculate_body_fat_percentage(self, peso: float, altura: float, edad: int, sexo: str) -> float:
        """Estimación de grasa corporal usando BMI + edad + sexo"""
        bmi = peso / ((altura / 100) ** 2)
        
        if sexo.lower() == "masculino":
            body_fat = (1.20 * bmi) + (0.23 * edad) - 16.2
        else:
            body_fat = (1.20 * bmi) + (0.23 * edad) - 5.4
            
        # Limitar valores razonables
        return max(5, min(50, body_fat))
    
    def calculate_lean_body_mass(self, peso: float, body_fat_percentage: float) -> float:
        """Calcular masa libre de grasa (FFM - Fat Free Mass)"""
        fat_mass = peso * (body_fat_percentage / 100)
        lean_mass = peso - fat_mass
        return lean_mass
    
    def calculate_exercise_calories(self, exercise_data: List[Dict]) -> float:
        """
        Calcular calorías quemadas en ejercicio usando MET values
        exercise_data: [{"tipo": "fuerza", "subtipo": "intensidad_media", "duracion": 60, "peso": 70}]
        """
        total_calories = 0
        
        for exercise in exercise_data:
            tipo = exercise.get("tipo", "")
            subtipo = exercise.get("subtipo", "")
            duracion_min = exercise.get("duracion", 0)
            peso = exercise.get("peso", 70)
            
            # Obtener MET value
            met_value = 3.5  # Default
            if tipo in self.exercise_met_values and subtipo in self.exercise_met_values[tipo]:
                met_value = self.exercise_met_values[tipo][subtipo]
            
            # Fórmula: Calorías = MET × peso(kg) × tiempo(horas)
            calories = met_value * peso * (duracion_min / 60)
            total_calories += calories
            
        return total_calories
    
    def calculate_available_energy(self, daily_calories: float, exercise_calories: float, lean_mass: float) -> float:
        """
        Calcular Available Energy según IOC/ISSN guidelines
        EA = (Ingesta Energética - Gasto Energético del Ejercicio) / Masa Libre de Grasa
        """
        available_energy = (daily_calories - exercise_calories) / lean_mass
        return available_energy
    
    def get_ea_status(self, ea_value: float) -> Dict:
        """Evaluar el estado de Available Energy según umbrales científicos"""
        if ea_value >= 45:
            return {
                "status": "optimal",
                "color": "🟢",
                "description": "Óptima para rendimiento y salud",
                "recommendation": "Mantén este nivel para máximo rendimiento"
            }
        elif ea_value >= 30:
            return {
                "status": "alert",
                "color": "🟡", 
                "description": "Zona de alerta - Posibles compromisos",
                "recommendation": "Considera aumentar ingesta o reducir volumen de ejercicio"
            }
        else:
            return {
                "status": "risk",
                "color": "🔴",
                "description": "Alto riesgo de síndrome REDs",
                "recommendation": "URGENTE: Aumentar ingesta calórica o reducir ejercicio"
            }
    
    def create_user_profile(self, telegram_id: str, profile_data: Dict) -> Dict:
        """Crear perfil completo de usuario con todos los cálculos"""
        
        # Datos básicos
        peso = profile_data["peso"]
        altura = profile_data["altura"] 
        edad = profile_data["edad"]
        sexo = profile_data["sexo"]
        objetivo = profile_data["objetivo"]
        
        # Cálculos corporales
        bmr = self.calculate_bmr(peso, altura, edad, sexo)
        body_fat = self.calculate_body_fat_percentage(peso, altura, edad, sexo)
        lean_mass = self.calculate_lean_body_mass(peso, body_fat)
        
        # Actividad física y ejercicio
        activity_factor = profile_data.get("activity_factor", 1.55)  # Moderado por defecto
        tdee = bmr * activity_factor
        
        # Ejercicio específico
        exercise_data = profile_data.get("exercise_data", [])
        daily_exercise_calories = self.calculate_exercise_calories(exercise_data)
        
        # Ajuste calórico según objetivo (basado en evidencia científica)
        caloric_adjustments = {
            "bajar_peso": -0.15,           # -15% para pérdida de grasa
            "subir_masa": 0.10,            # +10% para ganancia equilibrada (200-300 kcal superávit)
            "subir_masa_lean": 0.08,       # +8% para ganancia ultra-limpia (150-250 kcal superávit)
            "recomposicion": 0.0,          # Mantenimiento para recomposición
            "mantener": 0.0                # Mantenimiento estricto
        }
        
        adjustment = caloric_adjustments.get(objetivo, 0.0)
        target_calories = tdee * (1 + adjustment)
        
        # Available Energy
        available_energy = self.calculate_available_energy(target_calories, daily_exercise_calories, lean_mass)
        ea_status = self.get_ea_status(available_energy)
        
        # Distribución de macronutrientes optimizada por objetivo
        macro_distributions = {
            "bajar_peso": {"protein": 0.35, "carbs": 0.40, "fat": 0.25},        # Alta proteína para preservar músculo
            "subir_masa": {"protein": 0.30, "carbs": 0.45, "fat": 0.25},        # Carbos para rendimiento, proteína para síntesis
            "subir_masa_lean": {"protein": 0.32, "carbs": 0.43, "fat": 0.25},   # Más proteína para ganancia ultra-limpia
            "recomposicion": {"protein": 0.35, "carbs": 0.40, "fat": 0.25},     # Alta proteína para recomposición
            "mantener": {"protein": 0.30, "carbs": 0.40, "fat": 0.30}           # Distribución equilibrada
        }
        
        distribution = macro_distributions.get(objetivo, macro_distributions["mantener"])
        
        # Macros en gramos
        protein_g = (target_calories * distribution["protein"]) / 4
        carbs_g = (target_calories * distribution["carbs"]) / 4  
        fat_g = (target_calories * distribution["fat"]) / 9
        
        # Perfil completo
        user_profile = {
            "telegram_id": telegram_id,
            "created_date": datetime.now().isoformat(),
            "basic_data": {
                "peso": peso,
                "altura": altura,
                "edad": edad,
                "sexo": sexo,
                "objetivo": objetivo,
                "objetivo_descripcion": self.get_objective_description(objetivo)
            },
            "body_composition": {
                "bmr": round(bmr),
                "body_fat_percentage": round(body_fat, 1),
                "lean_mass_kg": round(lean_mass, 1),
                "bmi": round(peso / ((altura/100)**2), 1)
            },
            "energy_data": {
                "tdee": round(tdee),
                "target_calories": round(target_calories),
                "daily_exercise_calories": round(daily_exercise_calories),
                "available_energy": round(available_energy, 1),
                "ea_status": ea_status
            },
            "macros": {
                "protein_g": round(protein_g),
                "carbs_g": round(carbs_g),
                "fat_g": round(fat_g),
                "calories": round(target_calories)
            },
            "exercise_profile": {
                "activity_factor": activity_factor,
                "exercise_data": exercise_data,
                "recommended_timing": self.get_recommended_timing(objetivo)
            },
            "preferences": profile_data.get("preferences", {}),
            "settings": {
                "variety_level": profile_data.get("variety_level", 3),
                "cooking_schedule": profile_data.get("cooking_schedule", "dos_sesiones"),
                "max_prep_time": profile_data.get("max_prep_time", 60)
            }
        }
        
        return user_profile
    
    def get_objective_description(self, objetivo: str) -> str:
        """Obtener descripción user-friendly del objetivo"""
        descriptions = {
            "bajar_peso": "Perder grasa manteniendo músculo",
            "subir_masa": "Ganar músculo con superávit controlado (200-300 kcal)", 
            "subir_masa_lean": "Ganancia muscular ultra-limpia (150-250 kcal superávit)",
            "recomposicion": "Bajar grasa y ganar músculo simultáneamente",
            "mantener": "Mantener peso y composición corporal"
        }
        return descriptions.get(objetivo, "Objetivo no especificado")
    
    def get_recommended_timing(self, objetivo: str) -> List[str]:
        """Obtener timing nutricional recomendado según objetivo"""
        timing_recommendations = {
            "bajar_peso": ["post_entreno", "comida_principal"],
            "subir_masa": ["pre_entreno", "post_entreno", "comida_principal"],
            "subir_masa_lean": ["post_entreno", "comida_principal", "snack_complemento"],  # Timing más controlado
            "recomposicion": ["post_entreno", "comida_principal", "snack_complemento"],
            "mantener": ["comida_principal", "snack_complemento"]
        }
        return timing_recommendations.get(objetivo, ["comida_principal"])
    
    def update_exercise_data(self, user_profile: Dict, new_exercise_data: List[Dict]) -> Dict:
        """Actualizar datos de ejercicio y recalcular Available Energy"""
        peso = user_profile["basic_data"]["peso"]
        lean_mass = user_profile["body_composition"]["lean_mass_kg"]
        target_calories = user_profile["energy_data"]["target_calories"]
        
        # Recalcular ejercicio
        daily_exercise_calories = self.calculate_exercise_calories(new_exercise_data)
        available_energy = self.calculate_available_energy(target_calories, daily_exercise_calories, lean_mass)
        ea_status = self.get_ea_status(available_energy)
        
        # Actualizar perfil
        user_profile["energy_data"]["daily_exercise_calories"] = round(daily_exercise_calories)
        user_profile["energy_data"]["available_energy"] = round(available_energy, 1)
        user_profile["energy_data"]["ea_status"] = ea_status
        user_profile["exercise_profile"]["exercise_data"] = new_exercise_data
        user_profile["last_updated"] = datetime.now().isoformat()
        
        return user_profile

# Ejemplo de uso para testing
if __name__ == "__main__":
    profile_system = UserProfileSystem("recipes_new.json")
    
    # Ejemplo de perfil de usuario (datos del informe)
    sample_profile_data = {
        "peso": 70.0,
        "altura": 176.0,
        "edad": 26,  # Actualizado según informe
        "sexo": "masculino",
        "objetivo": "subir_masa",  # Ahora con +10% en lugar de +15%
        "activity_factor": 1.55,
        "exercise_data": [
            {
                "tipo": "fuerza",
                "subtipo": "intensidad_media", 
                "duracion": 60,  # minutos
                "peso": 70,
                "frecuencia_semanal": 4
            },
            {
                "tipo": "cardio",
                "subtipo": "caminar",
                "duracion": 30,
                "peso": 70,
                "frecuencia_semanal": 3
            }
        ],
        "preferences": {
            "liked_foods": ["pollo", "almendras", "quinoa"],
            "disliked_foods": ["pescado", "cilantro"],
            "cooking_methods": ["horno", "sarten", "plancha"]
        },
        "variety_level": 4,
        "cooking_schedule": "dos_sesiones",
        "max_prep_time": 60
    }
    
    # Crear perfil
    user_profile = profile_system.create_user_profile("12345", sample_profile_data)
    
    print("=== PERFIL DE USUARIO CREADO ===")
    print(f"Objetivo: {user_profile['basic_data']['objetivo_descripcion']}")
    print(f"Available Energy: {user_profile['energy_data']['available_energy']} kcal/kg FFM/día")
    print(f"Estado EA: {user_profile['energy_data']['ea_status']['description']}")
    print(f"Calorías objetivo: {user_profile['macros']['calories']} kcal")
    print(f"Macros: {user_profile['macros']['protein_g']}P / {user_profile['macros']['carbs_g']}C / {user_profile['macros']['fat_g']}F")
    
    # Comparar con subir_masa_lean
    print("\n=== COMPARACIÓN CON SUBIR_MASA_LEAN ===")
    sample_profile_data["objetivo"] = "subir_masa_lean"
    user_profile_lean = profile_system.create_user_profile("12345", sample_profile_data)
    print(f"Objetivo: {user_profile_lean['basic_data']['objetivo_descripcion']}")
    print(f"Calorías objetivo: {user_profile_lean['macros']['calories']} kcal")
    print(f"Macros: {user_profile_lean['macros']['protein_g']}P / {user_profile_lean['macros']['carbs_g']}C / {user_profile_lean['macros']['fat_g']}F")