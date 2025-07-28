#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Programación Avanzada de Meal Prep
Optimiza la programación temporal del meal prep basándose en horarios del usuario,
disponibilidad de tiempo y complejidad de recetas para máxima eficiencia
"""

import json
import math
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from collections import defaultdict

class MealPrepScheduler:
    
    def __init__(self):
        # Plantillas de cronogramas base
        self.schedule_templates = {
            "sesion_unica_domingo": {
                "name": "Sesión Única Dominical",
                "description": "Una sesión intensiva de 4-5 horas los domingos",
                "sessions": [
                    {
                        "day": "domingo",
                        "start_time": "10:00",
                        "duration_hours": 4.5,
                        "prep_focus": ["proteinas", "carbohidratos", "verduras", "complementos"],
                        "coverage_days": 5
                    }
                ],
                "pros": ["Máximo tiempo libre entre semana", "Economía de tiempo total"],
                "cons": ["Comidas menos frescas al final", "Requiere mucho tiempo continuo"]
            },
            "dos_sesiones": {
                "name": "Dos Sesiones Semanales",
                "description": "Domingo + Miércoles para máxima frescura",
                "sessions": [
                    {
                        "day": "domingo",
                        "start_time": "10:00",
                        "duration_hours": 3.0,
                        "prep_focus": ["proteinas", "carbohidratos_complejos"],
                        "coverage_days": 3
                    },
                    {
                        "day": "miercoles", 
                        "start_time": "19:00",
                        "duration_hours": 2.0,
                        "prep_focus": ["verduras_frescas", "complementos", "snacks"],
                        "coverage_days": 2
                    }
                ],
                "pros": ["Comidas siempre frescas", "Carga de trabajo distribuida"],
                "cons": ["Requiere dos bloques de tiempo", "Más planificación"]
            },
            "tres_sesiones": {
                "name": "Tres Sesiones Micro",
                "description": "Domingo, Martes, Jueves - preparaciones cortas",
                "sessions": [
                    {
                        "day": "domingo",
                        "start_time": "11:00", 
                        "duration_hours": 2.5,
                        "prep_focus": ["proteinas_base", "carbohidratos"],
                        "coverage_days": 2
                    },
                    {
                        "day": "martes",
                        "start_time": "20:00",
                        "duration_hours": 1.5,
                        "prep_focus": ["verduras", "snacks_complementos"],
                        "coverage_days": 2
                    },
                    {
                        "day": "jueves",
                        "start_time": "20:00",
                        "duration_hours": 1.5,
                        "prep_focus": ["proteinas_variadas", "complementos"],
                        "coverage_days": 1
                    }
                ],
                "pros": ["Máxima frescura", "Sesiones cortas y manejables"],
                "cons": ["Más frecuencia de preparación", "Requiere más planificación"]
            },
            "preparacion_diaria": {
                "name": "Preparación Diaria Rápida",
                "description": "15-30 minutos diarios de preparación fresca",
                "sessions": [
                    {
                        "day": "diario",
                        "start_time": "variable",
                        "duration_hours": 0.5,
                        "prep_focus": ["preparacion_fresca"],
                        "coverage_days": 1
                    }
                ],
                "pros": ["Comida siempre fresca", "No requiere bloques largos"],
                "cons": ["Requiere disciplina diaria", "Menos economía de tiempo"]
            }
        }
        
        # Complejidad de tareas por tipo
        self.task_complexity = {
            "proteinas": {
                "tiempo_base_minutos": 45,
                "factor_porciones": 1.2,
                "preparaciones": {
                    "pollo_plancha": {"tiempo": 25, "dificultad": 2, "batch_max": 6},
                    "salmon_horno": {"tiempo": 35, "dificultad": 3, "batch_max": 4}, 
                    "ternera_guisada": {"tiempo": 90, "dificultad": 4, "batch_max": 8},
                    "pavo_marinado": {"tiempo": 40, "dificultad": 3, "batch_max": 5}
                }
            },
            "carbohidratos": {
                "tiempo_base_minutos": 30,
                "factor_porciones": 1.1,
                "preparaciones": {
                    "quinoa_batch": {"tiempo": 20, "dificultad": 1, "batch_max": 10},
                    "arroz_integral": {"tiempo": 25, "dificultad": 1, "batch_max": 12},
                    "batata_horno": {"tiempo": 45, "dificultad": 2, "batch_max": 8},
                    "pasta_integral": {"tiempo": 15, "dificultad": 1, "batch_max": 10}
                }
            },
            "verduras": {
                "tiempo_base_minutos": 35,
                "factor_porciones": 1.0,
                "preparaciones": {
                    "verduras_vapor": {"tiempo": 20, "dificultad": 1, "batch_max": 8},
                    "ensalada_mixta": {"tiempo": 15, "dificultad": 1, "batch_max": 5},
                    "verduras_asadas": {"tiempo": 40, "dificultad": 2, "batch_max": 10},
                    "brócoli_salteado": {"tiempo": 12, "dificultad": 1, "batch_max": 6}
                }
            },
            "complementos": {
                "tiempo_base_minutos": 20,
                "factor_porciones": 0.8,
                "preparaciones": {
                    "frutos_secos_porcionado": {"tiempo": 10, "dificultad": 1, "batch_max": 15},
                    "yogur_parfait": {"tiempo": 5, "dificultad": 1, "batch_max": 8},
                    "hummus_casero": {"tiempo": 15, "dificultad": 2, "batch_max": 6},
                    "aceitunas_marinadas": {"tiempo": 8, "dificultad": 1, "batch_max": 10}
                }
            }
        }
        
        # Eficiencias por número de porciones (economías de escala)
        self.batch_efficiency = {
            1: 1.0,    # Tiempo base
            2: 0.8,    # 20% más eficiente
            3: 0.7,    # 30% más eficiente
            4: 0.65,   # 35% más eficiente
            5: 0.6,    # 40% más eficiente
            6: 0.58,   # 42% más eficiente
            8: 0.55,   # 45% más eficiente
            10: 0.52,  # 48% más eficiente
            12: 0.5    # 50% más eficiente (máximo)
        }
        
        # Factores de disponibilidad de tiempo por día
        self.time_availability_factors = {
            "lunes": 0.6,      # Inicio de semana, menor disponibilidad
            "martes": 0.8,     # Buena disponibilidad
            "miercoles": 0.9,  # Muy buena disponibilidad
            "jueves": 0.8,     # Buena disponibilidad
            "viernes": 0.5,    # Fin de semana, menor disponibilidad
            "sabado": 1.0,     # Máxima disponibilidad
            "domingo": 1.0     # Máxima disponibilidad
        }
    
    def generate_optimized_schedule(self, user_profile: Dict, preferences: Dict) -> Dict:
        """
        Generar cronograma optimizado de meal prep personalizado
        """
        try:
            # Analizar perfil del usuario
            user_analysis = self._analyze_user_constraints(user_profile, preferences)
            
            # Seleccionar template base óptimo
            base_template = self._select_optimal_template(user_analysis)
            
            # Calcular carga de trabajo total
            workload_analysis = self._calculate_workload_requirements(user_profile)
            
            # Optimizar horarios específicos
            optimized_sessions = self._optimize_session_timing(
                base_template, user_analysis, workload_analysis
            )
            
            # Generar plan de tareas detallado
            task_breakdown = self._generate_task_breakdown(
                optimized_sessions, workload_analysis, user_profile
            )
            
            # Calcular métricas de eficiencia
            efficiency_metrics = self._calculate_efficiency_metrics(
                task_breakdown, user_analysis
            )
            
            return {
                "success": True,
                "schedule": {
                    "template_name": base_template["name"],
                    "sessions": optimized_sessions,
                    "task_breakdown": task_breakdown,
                    "total_time_hours": sum(s["duration_hours"] for s in optimized_sessions),
                    "efficiency_score": efficiency_metrics["overall_score"]
                },
                "user_analysis": user_analysis,
                "workload_analysis": workload_analysis,
                "efficiency_metrics": efficiency_metrics,
                "recommendations": self._generate_schedule_recommendations(
                    user_analysis, efficiency_metrics
                )
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error generating optimized schedule: {str(e)}"
            }
    
    def _analyze_user_constraints(self, user_profile: Dict, preferences: Dict) -> Dict:
        """
        Analizar las limitaciones y preferencias del usuario
        """
        basic_data = user_profile["basic_data"]
        exercise_profile = user_profile.get("exercise_profile", {})
        
        analysis = {
            "available_time_per_week": preferences.get("max_prep_time_hours", 6),
            "preferred_days": preferences.get("preferred_prep_days", ["domingo"]),
            "max_session_duration": preferences.get("max_session_hours", 4),
            "cooking_experience": preferences.get("cooking_experience", "intermedio"),
            "kitchen_equipment": preferences.get("kitchen_equipment", ["basico"]),
            "storage_capacity": preferences.get("storage_capacity", "medio"),
            "freshness_priority": preferences.get("freshness_priority", 7), # 1-10
            "time_efficiency_priority": preferences.get("time_efficiency_priority", 8), # 1-10
        }
        
        # Analizar horario de entrenamiento para optimizar timing
        training_schedule = exercise_profile.get("training_schedule", "variable")
        analysis["training_days"] = self._get_training_days(training_schedule)
        
        # Factor de experiencia (afecta velocidad de preparación)
        experience_factors = {
            "principiante": 1.3,  # 30% más tiempo
            "intermedio": 1.0,    # Tiempo base
            "avanzado": 0.8,      # 20% menos tiempo
            "experto": 0.7        # 30% menos tiempo
        }
        analysis["experience_factor"] = experience_factors.get(
            analysis["cooking_experience"], 1.0
        )
        
        # Analizar restricciones por objetivo nutricional
        objective = basic_data["objetivo"]
        if objective in ["bajar_peso", "recomposicion"]:
            analysis["variety_requirement"] = "alta"  # Más variedad para adherencia
            analysis["portion_precision"] = "alta"   # Más precisión en porciones
        else:
            analysis["variety_requirement"] = "media"
            analysis["portion_precision"] = "media"
        
        return analysis
    
    def _select_optimal_template(self, user_analysis: Dict) -> Dict:
        """
        Seleccionar el template de cronograma más adecuado
        """
        available_time = user_analysis["available_time_per_week"]
        max_session = user_analysis["max_session_duration"]
        freshness_priority = user_analysis["freshness_priority"]
        time_efficiency = user_analysis["time_efficiency_priority"]
        
        # Scoring para cada template
        template_scores = {}
        
        for template_id, template in self.schedule_templates.items():
            score = 0
            
            # Penalizar si excede tiempo disponible
            total_time = sum(session["duration_hours"] for session in template["sessions"])
            if total_time > available_time:
                score -= (total_time - available_time) * 20
            
            # Penalizar si alguna sesión excede duración máxima
            max_template_session = max(s["duration_hours"] for s in template["sessions"])
            if max_template_session > max_session:
                score -= (max_template_session - max_session) * 15
            
            # Bonus por prioridad de frescura
            if template_id == "preparacion_diaria" and freshness_priority >= 8:
                score += 25
            elif template_id == "tres_sesiones" and freshness_priority >= 7:
                score += 20
            elif template_id == "dos_sesiones" and freshness_priority >= 6:
                score += 15
            
            # Bonus por eficiencia de tiempo
            if template_id == "sesion_unica_domingo" and time_efficiency >= 8:
                score += 25
            elif template_id == "dos_sesiones" and time_efficiency >= 6:
                score += 15
            
            # Bonus por días preferidos del usuario
            template_days = [s["day"] for s in template["sessions"]]
            preferred_days = user_analysis["preferred_days"]
            day_match_bonus = len(set(template_days) & set(preferred_days)) * 10
            score += day_match_bonus
            
            template_scores[template_id] = score
        
        # Seleccionar el de mayor puntuación
        best_template_id = max(template_scores, key=template_scores.get)
        return self.schedule_templates[best_template_id].copy()
    
    def _calculate_workload_requirements(self, user_profile: Dict) -> Dict:
        """
        Calcular los requerimientos de carga de trabajo basados en macros y preferencias
        """
        macros = user_profile["macros"]
        preferences = user_profile.get("preferences", {})
        daily_calories = macros["calories"]
        
        # Estimaciones de porciones por semana (5 días de meal prep)
        workload = {
            "proteinas": {
                "porciones_semanales": 15,  # 3 comidas x 5 días
                "gramos_por_porcion": macros["protein_g"] / 3,  # Distribuido en 3 comidas
                "preparaciones_requeridas": []
            },
            "carbohidratos": {
                "porciones_semanales": 15,
                "gramos_por_porcion": macros["carbs_g"] / 3,
                "preparaciones_requeridas": []
            },
            "verduras": {
                "porciones_semanales": 20,  # Más porciones de verduras
                "gramos_por_porcion": 150,  # Porción estándar
                "preparaciones_requeridas": []
            },
            "complementos": {
                "porciones_semanales": 10,  # Snacks y complementos
                "gramos_por_porcion": 30,   # Porción pequeña
                "preparaciones_requeridas": []
            }
        }
        
        # Seleccionar preparaciones específicas basándose en preferencias
        liked_foods = preferences.get("liked_foods", [])
        cooking_methods = preferences.get("cooking_methods", ["sarten", "horno"])
        
        # Mapear preferencias a preparaciones específicas
        for category, category_data in workload.items():
            available_preps = list(self.task_complexity[category]["preparaciones"].keys())
            
            # Filtrar por preferencias del usuario
            preferred_preps = self._filter_preparations_by_preferences(
                available_preps, liked_foods, cooking_methods, category
            )
            
            # Seleccionar 2-3 preparaciones para variedad
            selected_preps = preferred_preps[:3] if len(preferred_preps) >= 3 else preferred_preps
            if not selected_preps:  # Fallback si no hay preferencias
                selected_preps = available_preps[:2]
            
            category_data["preparaciones_requeridas"] = selected_preps
        
        return workload
    
    def _filter_preparations_by_preferences(self, preparations: List[str], 
                                          liked_foods: List[str], 
                                          cooking_methods: List[str],
                                          category: str) -> List[str]:
        """
        Filtrar preparaciones basándose en preferencias del usuario
        """
        filtered = []
        
        # Mapeos de preferencias a preparaciones específicas
        food_prep_mapping = {
            "aves": ["pollo_plancha", "pavo_marinado"],
            "pescados": ["salmon_horno"],
            "carnes_rojas": ["ternera_guisada"],
            "cruciferas": ["brócoli_salteado"],
            "frutos_secos": ["frutos_secos_porcionado"],
            "lacteos": ["yogur_parfait"]
        }
        
        method_prep_mapping = {
            "horno": ["salmon_horno", "batata_horno", "verduras_asadas"],
            "plancha": ["pollo_plancha"],
            "sarten": ["brócoli_salteado"],
            "vapor": ["verduras_vapor"]
        }
        
        for prep in preparations:
            # Verificar si coincide con alimentos preferidos
            food_match = any(
                prep in food_prep_mapping.get(food, []) 
                for food in liked_foods
            )
            
            # Verificar si coincide con métodos preferidos
            method_match = any(
                prep in method_prep_mapping.get(method, [])
                for method in cooking_methods
            )
            
            if food_match or method_match:
                filtered.append(prep)
        
        # Si no hay coincidencias, devolver todas las preparaciones
        return filtered if filtered else preparations
    
    def _optimize_session_timing(self, base_template: Dict, user_analysis: Dict, 
                                workload: Dict) -> List[Dict]:
        """
        Optimizar horarios específicos de las sesiones
        """
        optimized_sessions = []
        training_days = user_analysis["training_days"]
        
        for session in base_template["sessions"]:
            optimized_session = session.copy()
            
            # Ajustar duración basándose en carga de trabajo real
            estimated_duration = self._estimate_session_duration(
                session, workload, user_analysis
            )
            optimized_session["duration_hours"] = estimated_duration
            
            # Optimizar horario para evitar conflictos con entrenamiento
            if session["day"] in training_days:
                optimized_session["start_time"] = self._adjust_for_training_conflict(
                    session["start_time"], session["day"], user_analysis
                )
            
            # Calcular horario de finalización
            start_time = datetime.strptime(session["start_time"], "%H:%M").time()
            end_time = (datetime.combine(datetime.today(), start_time) + 
                       timedelta(hours=estimated_duration)).time()
            optimized_session["end_time"] = end_time.strftime("%H:%M")
            
            # Añadir factor de disponibilidad del día
            day_factor = self.time_availability_factors.get(session["day"], 0.8)
            optimized_session["day_availability_factor"] = day_factor
            
            optimized_sessions.append(optimized_session)
        
        return optimized_sessions
    
    def _estimate_session_duration(self, session: Dict, workload: Dict, 
                                  user_analysis: Dict) -> float:
        """
        Estimar duración real de la sesión basándose en tareas específicas
        """
        total_time_minutes = 0
        prep_focus = session["prep_focus"]
        experience_factor = user_analysis["experience_factor"]
        
        for category in prep_focus:
            if category in workload:
                category_workload = workload[category]
                required_preps = category_workload["preparaciones_requeridas"]
                portions_per_prep = category_workload["porciones_semanales"] / len(required_preps)
                
                for prep_name in required_preps:
                    if prep_name in self.task_complexity[category]["preparaciones"]:
                        prep_data = self.task_complexity[category]["preparaciones"][prep_name]
                        base_time = prep_data["tiempo"]
                        
                        # Aplicar eficiencia por lotes
                        batch_size = min(int(portions_per_prep), prep_data["batch_max"])
                        efficiency = self.batch_efficiency.get(batch_size, 0.5)
                        
                        # Tiempo ajustado por experiencia y eficiencia
                        adjusted_time = base_time * efficiency * experience_factor
                        total_time_minutes += adjusted_time
        
        # Añadir tiempo de setup y limpieza (20% extra)
        total_time_minutes *= 1.2
        
        # Convertir a horas y redondear
        return round(total_time_minutes / 60, 1)
    
    def _adjust_for_training_conflict(self, original_time: str, day: str, 
                                     user_analysis: Dict) -> str:
        """
        Ajustar horario para evitar conflictos con entrenamiento
        """
        # Horarios típicos de entrenamiento por slot
        training_slots = {
            "mañana": ("06:00", "09:00"),
            "mediodia": ("12:00", "14:00"), 
            "tarde": ("17:00", "20:00"),
            "noche": ("20:00", "22:00")
        }
        
        # Para este ejemplo, asumimos que el usuario entrena por la tarde
        # En implementación real, esto vendría del perfil del usuario
        training_start, training_end = training_slots["tarde"]
        
        original_hour = int(original_time.split(":")[0])
        training_start_hour = int(training_start.split(":")[0])
        training_end_hour = int(training_end.split(":")[0])
        
        # Si hay conflicto, mover la sesión
        if training_start_hour <= original_hour <= training_end_hour:
            # Mover antes del entrenamiento si es posible
            if original_hour > 12:
                return "10:00"  # Mañana
            else:
                return "21:00"  # Después del entrenamiento
        
        return original_time
    
    def _generate_task_breakdown(self, sessions: List[Dict], workload: Dict, 
                                user_profile: Dict) -> Dict:
        """
        Generar desglose detallado de tareas por sesión
        """
        task_breakdown = {}
        
        for i, session in enumerate(sessions):
            session_key = f"session_{i+1}_{session['day']}"
            
            tasks = []
            total_session_time = 0
            
            for category in session["prep_focus"]:
                if category in workload:
                    category_workload = workload[category]
                    
                    for prep_name in category_workload["preparaciones_requeridas"]:
                        if prep_name in self.task_complexity[category]["preparaciones"]:
                            prep_data = self.task_complexity[category]["preparaciones"][prep_name]
                            
                            # Calcular detalles de la tarea
                            portions = category_workload["porciones_semanales"] // len(sessions)
                            estimated_time = prep_data["tiempo"]
                            difficulty = prep_data["dificultad"]
                            
                            task = {
                                "name": prep_name.replace("_", " ").title(),
                                "category": category,
                                "portions": portions,
                                "estimated_time_minutes": estimated_time,
                                "difficulty": difficulty,
                                "order": len(tasks) + 1,
                                "equipment_needed": self._get_equipment_for_prep(prep_name),
                                "storage_method": self._get_storage_method(category, prep_name)
                            }
                            
                            tasks.append(task)
                            total_session_time += estimated_time
            
            # Ordenar tareas por eficiencia (difíciles primero cuando tienes más energía)
            tasks.sort(key=lambda x: (-x["difficulty"], x["estimated_time_minutes"]))
            
            # Recalcular orden después de sorting
            for j, task in enumerate(tasks):
                task["order"] = j + 1
            
            task_breakdown[session_key] = {
                "session_info": session,
                "tasks": tasks,
                "total_estimated_time_minutes": total_session_time,
                "task_count": len(tasks),
                "avg_difficulty": sum(t["difficulty"] for t in tasks) / len(tasks) if tasks else 0,
                "preparation_tips": self._generate_session_tips(session, tasks)
            }
        
        return task_breakdown
    
    def _get_equipment_for_prep(self, prep_name: str) -> List[str]:
        """
        Obtener equipamiento necesario para una preparación específica
        """
        equipment_mapping = {
            "pollo_plancha": ["plancha", "taper_vidrio"],
            "salmon_horno": ["horno", "papel_aluminio", "taper_vidrio"],
            "ternera_guisada": ["olla_grande", "taper_vidrio"],
            "quinoa_batch": ["olla_mediana", "taper_hermético"],
            "verduras_vapor": ["vaporera", "taper_vidrio"],
            "frutos_secos_porcionado": ["bolsas_pequenas", "bascula"]
        }
        
        return equipment_mapping.get(prep_name, ["basico"])
    
    def _get_storage_method(self, category: str, prep_name: str) -> Dict:
        """
        Obtener método de almacenamiento óptimo
        """
        storage_methods = {
            "proteinas": {
                "container": "taper_vidrio",
                "duration_days": 4,
                "freezer_option": True,
                "reheating": "microondas_2min"
            },
            "carbohidratos": {
                "container": "taper_hermético",
                "duration_days": 5,
                "freezer_option": True,
                "reheating": "microondas_1min"
            },
            "verduras": {
                "container": "taper_vidrio",
                "duration_days": 3,
                "freezer_option": False,
                "reheating": "sarten_2min"
            },
            "complementos": {
                "container": "bolsas_pequenas",
                "duration_days": 7,
                "freezer_option": False,
                "reheating": "no_requiere"
            }
        }
        
        return storage_methods.get(category, storage_methods["proteinas"])
    
    def _generate_session_tips(self, session: Dict, tasks: List[Dict]) -> List[str]:
        """
        Generar consejos específicos para la sesión
        """
        tips = []
        
        # Tip por duración
        if session["duration_hours"] > 3:
            tips.append("💡 Toma descansos de 10 min cada hora para mantener eficiencia")
        
        # Tip por número de tareas
        if len(tasks) > 6:
            tips.append("⚡ Usa múltiples fuegos/electrodomésticos simultáneamente")
        
        # Tip por dificultad promedio
        avg_difficulty = sum(t["difficulty"] for t in tasks) / len(tasks) if tasks else 0
        if avg_difficulty > 3:
            tips.append("🎯 Prepara ingredientes antes de empezar (mis en place)")
        
        # Tip específico por día
        if session["day"] == "domingo":
            tips.append("📦 Prepara contenedores etiquetados antes de empezar")
        elif session["day"] == "miercoles":
            tips.append("🔄 Revisa qué queda de la prep anterior antes de empezar")
        
        # Tip por horario
        start_hour = int(session["start_time"].split(":")[0])
        if start_hour >= 19:
            tips.append("🌙 Prep nocturna: enfócate en tareas silenciosas")
        elif start_hour <= 9:
            tips.append("🌅 Prep matutina: aprovecha la energía alta para tareas complejas")
        
        return tips[:3]  # Máximo 3 tips por sesión
    
    def _calculate_efficiency_metrics(self, task_breakdown: Dict, 
                                    user_analysis: Dict) -> Dict:
        """
        Calcular métricas de eficiencia del cronograma
        """
        total_time_hours = sum(
            session["total_estimated_time_minutes"] / 60 
            for session in task_breakdown.values()
        )
        
        total_tasks = sum(
            session["task_count"] 
            for session in task_breakdown.values()
        )
        
        # Métricas base
        metrics = {
            "time_efficiency": min(100, (6 / total_time_hours) * 100) if total_time_hours > 0 else 0,
            "task_distribution": self._calculate_task_distribution_score(task_breakdown),
            "freshness_score": self._calculate_freshness_score(task_breakdown),
            "complexity_balance": self._calculate_complexity_balance(task_breakdown),
            "user_alignment": self._calculate_user_alignment_score(task_breakdown, user_analysis)
        }
        
        # Puntuación general (promedio ponderado)
        weights = {
            "time_efficiency": 0.25,
            "task_distribution": 0.20,
            "freshness_score": 0.20,
            "complexity_balance": 0.15,
            "user_alignment": 0.20
        }
        
        overall_score = sum(
            metrics[metric] * weight 
            for metric, weight in weights.items()
        )
        
        metrics["overall_score"] = round(overall_score, 1)
        metrics["grade"] = self._get_efficiency_grade(overall_score)
        
        return metrics
    
    def _calculate_task_distribution_score(self, task_breakdown: Dict) -> float:
        """
        Calcular qué tan bien distribuidas están las tareas entre sesiones
        """
        session_times = [
            session["total_estimated_time_minutes"] 
            for session in task_breakdown.values()
        ]
        
        if not session_times:
            return 0
        
        # Calcular varianza de tiempos (menor varianza = mejor distribución)
        mean_time = sum(session_times) / len(session_times)
        variance = sum((t - mean_time) ** 2 for t in session_times) / len(session_times)
        
        # Convertir a score 0-100 (menos varianza = mejor score)
        max_variance = mean_time ** 2  # Máxima varianza posible
        distribution_score = max(0, 100 - (variance / max_variance) * 100)
        
        return round(distribution_score, 1)
    
    def _calculate_freshness_score(self, task_breakdown: Dict) -> float:
        """
        Calcular score de frescura basándose en frecuencia de prep
        """
        num_sessions = len(task_breakdown)
        
        # Más sesiones = mayor frescura
        freshness_mapping = {
            1: 60,  # Una sesión = 60% frescura
            2: 80,  # Dos sesiones = 80% frescura
            3: 95,  # Tres sesiones = 95% frescura
            4: 100  # Diario = 100% frescura
        }
        
        return freshness_mapping.get(num_sessions, 100)
    
    def _calculate_complexity_balance(self, task_breakdown: Dict) -> float:
        """
        Calcular qué tan bien balanceada está la complejidad entre sesiones
        """
        session_complexities = []
        
        for session in task_breakdown.values():
            if session["tasks"]:
                avg_complexity = session["avg_difficulty"]
                session_complexities.append(avg_complexity)
        
        if not session_complexities:
            return 100
        
        # Score basado en qué tan cerca está cada sesión del nivel intermedio (2.5)
        ideal_complexity = 2.5
        complexity_deviations = [abs(c - ideal_complexity) for c in session_complexities]
        avg_deviation = sum(complexity_deviations) / len(complexity_deviations)
        
        # Convertir a score 0-100
        max_deviation = 2.5  # Máxima desviación posible
        balance_score = max(0, 100 - (avg_deviation / max_deviation) * 100)
        
        return round(balance_score, 1)
    
    def _calculate_user_alignment_score(self, task_breakdown: Dict, 
                                      user_analysis: Dict) -> float:
        """
        Calcular qué tan alineado está el cronograma con las preferencias del usuario
        """
        score = 100
        
        # Penalizar si excede tiempo disponible del usuario
        total_time = sum(
            session["total_estimated_time_minutes"] / 60 
            for session in task_breakdown.values()
        )
        
        available_time = user_analysis["available_time_per_week"]
        if total_time > available_time:
            time_penalty = ((total_time - available_time) / available_time) * 50
            score -= min(time_penalty, 40)  # Máximo 40 puntos de penalización
        
        # Bonus por alineación con días preferidos
        session_days = [
            session["session_info"]["day"] 
            for session in task_breakdown.values()
        ]
        preferred_days = user_analysis["preferred_days"]
        
        day_alignment = len(set(session_days) & set(preferred_days)) / len(session_days)
        score += day_alignment * 10  # Hasta 10 puntos de bonus
        
        return round(max(0, min(100, score)), 1)
    
    def _get_efficiency_grade(self, score: float) -> str:
        """
        Convertir puntuación numérica a calificación
        """
        if score >= 90:
            return "A+ Excelente"
        elif score >= 80:
            return "A Muy Bueno"
        elif score >= 70:
            return "B Bueno"
        elif score >= 60:
            return "C Regular"
        else:
            return "D Necesita Mejoras"
    
    def _generate_schedule_recommendations(self, user_analysis: Dict, 
                                         efficiency_metrics: Dict) -> List[str]:
        """
        Generar recomendaciones para mejorar el cronograma
        """
        recommendations = []
        
        # Recomendaciones por eficiencia de tiempo
        if efficiency_metrics["time_efficiency"] < 70:
            recommendations.append(
                "⏰ Considera reducir variedad de preparaciones para mejorar eficiencia"
            )
        
        # Recomendaciones por distribución de tareas
        if efficiency_metrics["task_distribution"] < 70:
            recommendations.append(
                "⚖️ Rebalancea tareas entre sesiones para carga de trabajo más uniforme"
            )
        
        # Recomendaciones por frescura
        if efficiency_metrics["freshness_score"] < 80:
            recommendations.append(
                "🌿 Añade una sesión mid-week para mejorar frescura de las comidas"
            )
        
        # Recomendaciones por experiencia del usuario
        experience = user_analysis["cooking_experience"]
        if experience == "principiante":
            recommendations.append(
                "👨‍🍳 Empieza con preparaciones simples y ve aumentando complejidad gradualmente"
            )
        elif experience == "experto":
            recommendations.append(
                "🔥 Puedes optimizar tiempo cocinando múltiples platos simultáneamente"
            )
        
        return recommendations[:4]  # Máximo 4 recomendaciones
    
    def _get_training_days(self, training_schedule: str) -> List[str]:
        """
        Obtener días de entrenamiento basándose en el cronograma
        """
        # Mapeo simplificado - en implementación real vendría del perfil completo
        training_mappings = {
            "mañana": ["lunes", "miercoles", "viernes"],
            "tarde": ["martes", "jueves", "sabado"],
            "variable": ["lunes", "miercoles", "viernes"]  # Default
        }
        
        return training_mappings.get(training_schedule, ["lunes", "miercoles", "viernes"])
    
    def format_schedule_for_telegram(self, schedule_data: Dict, user_profile: Dict) -> str:
        """
        Formatear cronograma optimizado para mostrar en Telegram
        """
        if not schedule_data["success"]:
            return f"❌ **Error generando cronograma:** {schedule_data.get('error', 'Error desconocido')}"
        
        schedule = schedule_data["schedule"]
        efficiency = schedule_data["efficiency_metrics"]
        
        # Encabezado
        text = f"""
🗓️ **CRONOGRAMA OPTIMIZADO DE MEAL PREP**

👤 **Usuario:** {user_profile['basic_data']['objetivo_descripcion']}
📋 **Template:** {schedule['template_name']}
⏱️ **Tiempo total semanal:** {schedule['total_time_hours']} horas
📊 **Puntuación de eficiencia:** {efficiency['overall_score']}/100 ({efficiency['grade']})

"""
        
        # Métricas de eficiencia
        text += "📈 **MÉTRICAS DE EFICIENCIA:**\n"
        text += f"• ⚡ Eficiencia temporal: {efficiency['time_efficiency']:.1f}%\n"
        text += f"• ⚖️ Distribución de tareas: {efficiency['task_distribution']:.1f}%\n"
        text += f"• 🌿 Score de frescura: {efficiency['freshness_score']:.1f}%\n"
        text += f"• 🎯 Balance de complejidad: {efficiency['complexity_balance']:.1f}%\n"
        text += f"• 👤 Alineación personal: {efficiency['user_alignment']:.1f}%\n\n"
        
        # Sesiones detalladas
        text += "📅 **CRONOGRAMA DETALLADO:**\n\n"
        
        task_breakdown = schedule["task_breakdown"]
        for session_key, session_data in task_breakdown.items():
            session_info = session_data["session_info"]
            day = session_info["day"].title()
            start_time = session_info["start_time"]
            end_time = session_info["end_time"]
            duration = session_info["duration_hours"]
            
            text += f"**🗓️ {day} ({start_time} - {end_time})**\n"
            text += f"⏱️ Duración: {duration} horas\n"
            text += f"📋 {session_data['task_count']} tareas programadas\n"
            text += f"🎯 Complejidad promedio: {session_data['avg_difficulty']:.1f}/5\n\n"
            
            # Tareas de la sesión
            text += "**TAREAS PROGRAMADAS:**\n"
            for task in session_data["tasks"][:5]:  # Mostrar máximo 5 tareas
                difficulty_stars = "⭐" * task["difficulty"]
                text += f"  {task['order']}. {task['name']} ({task['estimated_time_minutes']}min) {difficulty_stars}\n"
                text += f"     📦 {task['portions']} porciones • 🥄 {task['equipment_needed'][0]}\n"
            
            if len(session_data["tasks"]) > 5:
                text += f"     ... y {len(session_data['tasks']) - 5} tareas más\n"
            
            # Tips de la sesión
            if session_data["preparation_tips"]:
                text += f"\n💡 **TIPS:**\n"
                for tip in session_data["preparation_tips"]:
                    text += f"  • {tip}\n"
            
            text += "\n"
        
        # Recomendaciones
        recommendations = schedule_data.get("recommendations", [])
        if recommendations:
            text += "💡 **RECOMENDACIONES PARA OPTIMIZAR:**\n"
            for rec in recommendations:
                text += f"• {rec}\n"
            text += "\n"
        
        # Próximos pasos
        text += f"""
🚀 **PRÓXIMOS PASOS:**
• Bloquea estos horarios en tu calendario
• Prepara equipamiento necesario antes de cada sesión
• Sigue el orden de tareas sugerido para máxima eficiencia
• Usa `/planificar_semana` para cronogramas específicos

🎯 **COMANDOS RELACIONADOS:**
• `/lista_compras` - Lista optimizada para este cronograma
• `/menu` - Ver menú semanal correspondiente
• `/progreso` - Trackear eficiencia real vs estimada

**¡Cronograma personalizado para tu perfil y horarios!**
"""
        
        return text

# Ejemplo de uso
if __name__ == "__main__":
    scheduler = MealPrepScheduler()
    
    # Perfil de usuario de ejemplo
    sample_profile = {
        "basic_data": {
            "objetivo": "recomposicion",
            "objetivo_descripcion": "Recomposición corporal"
        },
        "macros": {
            "calories": 2400,
            "protein_g": 180,
            "carbs_g": 240,
            "fat_g": 80
        },
        "preferences": {
            "liked_foods": ["aves", "pescados", "frutos_secos"],
            "cooking_methods": ["horno", "plancha"],
            "disliked_foods": []
        },
        "exercise_profile": {
            "training_schedule": "tarde"
        }
    }
    
    # Preferencias de cronograma
    schedule_preferences = {
        "max_prep_time_hours": 5,
        "preferred_prep_days": ["domingo", "miercoles"],
        "max_session_hours": 3,
        "cooking_experience": "intermedio",
        "freshness_priority": 8,
        "time_efficiency_priority": 7
    }
    
    # Generar cronograma optimizado
    result = scheduler.generate_optimized_schedule(sample_profile, schedule_preferences)
    
    if result["success"]:
        formatted_schedule = scheduler.format_schedule_for_telegram(result, sample_profile)
        print("=== CRONOGRAMA OPTIMIZADO ===")
        print(formatted_schedule)
    else:
        print(f"Error: {result['error']}")