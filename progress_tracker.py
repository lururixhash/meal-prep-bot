#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Seguimiento de Progreso y Analíticas
Registra y analiza el progreso nutricional del usuario a lo largo del tiempo
"""

import json
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import math

class ProgressTracker:
    
    def __init__(self):
        # Métricas que se pueden trackear
        self.trackable_metrics = {
            "weight": {
                "name": "Peso Corporal",
                "unit": "kg",
                "emoji": "⚖️",
                "min_value": 30.0,
                "max_value": 200.0,
                "decimal_places": 1
            },
            "body_fat": {
                "name": "Porcentaje de Grasa",
                "unit": "%",
                "emoji": "📊",
                "min_value": 3.0,
                "max_value": 50.0,
                "decimal_places": 1
            },
            "muscle_mass": {
                "name": "Masa Muscular",
                "unit": "kg",
                "emoji": "💪",
                "min_value": 20.0,
                "max_value": 100.0,
                "decimal_places": 1
            },
            "waist_circumference": {
                "name": "Circunferencia de Cintura",
                "unit": "cm",
                "emoji": "📏",
                "min_value": 50.0,
                "max_value": 150.0,
                "decimal_places": 1
            },
            "energy_level": {
                "name": "Nivel de Energía",
                "unit": "/10",
                "emoji": "⚡",
                "min_value": 1,
                "max_value": 10,
                "decimal_places": 0
            },
            "sleep_quality": {
                "name": "Calidad de Sueño",
                "unit": "/10",
                "emoji": "💤",
                "min_value": 1,
                "max_value": 10,
                "decimal_places": 0
            },
            "recovery_rate": {
                "name": "Recuperación Post-Entreno",
                "unit": "/10",
                "emoji": "🔄",
                "min_value": 1,
                "max_value": 10,
                "decimal_places": 0
            },
            "appetite": {
                "name": "Control del Apetito",
                "unit": "/10",
                "emoji": "🍽️",
                "min_value": 1,
                "max_value": 10,
                "decimal_places": 0
            }
        }
        
        # Períodos de análisis
        self.analysis_periods = {
            "week": {"days": 7, "name": "Última Semana"},
            "month": {"days": 30, "name": "Último Mes"},
            "quarter": {"days": 90, "name": "Últimos 3 Meses"},
            "semester": {"days": 180, "name": "Últimos 6 Meses"},
            "year": {"days": 365, "name": "Último Año"}
        }
    
    def record_metric(self, user_profile: Dict, metric_name: str, value: float, notes: str = "") -> Dict:
        """
        Registrar una métrica específica para el usuario
        """
        try:
            if metric_name not in self.trackable_metrics:
                return {
                    "success": False,
                    "error": f"Métrica '{metric_name}' no es válida"
                }
            
            metric_config = self.trackable_metrics[metric_name]
            
            # Validar valor
            if not (metric_config["min_value"] <= value <= metric_config["max_value"]):
                return {
                    "success": False,
                    "error": f"Valor debe estar entre {metric_config['min_value']} y {metric_config['max_value']} {metric_config['unit']}"
                }
            
            # Inicializar sistema de tracking si no existe
            if "progress_tracking" not in user_profile:
                user_profile["progress_tracking"] = self._initialize_tracking_system()
            
            tracking_data = user_profile["progress_tracking"]
            
            # Crear registro
            metric_record = {
                "value": round(value, metric_config["decimal_places"]),
                "timestamp": datetime.now().isoformat(),
                "notes": notes,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Inicializar métrica si no existe
            if metric_name not in tracking_data["metrics"]:
                tracking_data["metrics"][metric_name] = []
            
            # Agregar registro
            tracking_data["metrics"][metric_name].append(metric_record)
            
            # Mantener solo los últimos 365 registros por métrica
            if len(tracking_data["metrics"][metric_name]) > 365:
                tracking_data["metrics"][metric_name] = tracking_data["metrics"][metric_name][-365:]
            
            # Actualizar estadísticas básicas
            self._update_basic_statistics(tracking_data, metric_name)
            
            # Calcular tendencias
            trend_analysis = self._calculate_trends(tracking_data["metrics"][metric_name], metric_name)
            
            # Actualizar Available Energy si se registró peso
            if metric_name == "weight":
                self._update_available_energy(user_profile, value)
            
            # Generar insights automáticos
            insights = self._generate_metric_insights(
                tracking_data["metrics"][metric_name], 
                metric_name, 
                user_profile
            )
            
            return {
                "success": True,
                "metric_recorded": {
                    "name": metric_config["name"],
                    "value": metric_record["value"],
                    "unit": metric_config["unit"],
                    "date": metric_record["date"]
                },
                "trend_analysis": trend_analysis,
                "insights": insights,
                "total_records": len(tracking_data["metrics"][metric_name])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error registrando métrica: {str(e)}"
            }
    
    def _initialize_tracking_system(self) -> Dict:
        """
        Inicializar sistema de tracking para usuario nuevo
        """
        return {
            "tracking_start_date": datetime.now().isoformat(),
            "metrics": {},
            "goals": {},
            "milestones": [],
            "basic_statistics": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def _update_basic_statistics(self, tracking_data: Dict, metric_name: str) -> None:
        """
        Actualizar estadísticas básicas para una métrica
        """
        metric_records = tracking_data["metrics"][metric_name]
        values = [record["value"] for record in metric_records]
        
        if not values:
            return
        
        # Calcular estadísticas
        stats = {
            "count": len(values),
            "current_value": values[-1],
            "min_value": min(values),
            "max_value": max(values),
            "average": round(sum(values) / len(values), 2),
            "median": round(statistics.median(values), 2) if len(values) > 1 else values[0],
            "range": round(max(values) - min(values), 2),
            "last_updated": datetime.now().isoformat()
        }
        
        # Calcular desviación estándar si hay suficientes datos
        if len(values) > 1:
            stats["std_deviation"] = round(statistics.stdev(values), 2)
        else:
            stats["std_deviation"] = 0.0
        
        tracking_data["basic_statistics"][metric_name] = stats
    
    def _calculate_trends(self, metric_records: List[Dict], metric_name: str) -> Dict:
        """
        Calcular tendencias para una métrica específica
        """
        if len(metric_records) < 2:
            return {
                "trend": "insuficientes_datos",
                "trend_description": "Necesitas al menos 2 registros para analizar tendencias",
                "change_rate": 0.0
            }
        
        # Obtener valores de los últimos 30 días
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_records = [
            record for record in metric_records
            if datetime.fromisoformat(record["timestamp"]) >= thirty_days_ago
        ]
        
        if len(recent_records) < 2:
            # Usar todos los registros si no hay suficientes en 30 días
            recent_records = metric_records[-10:]  # Últimos 10 registros
        
        # Calcular tendencia usando regresión lineal simple
        values = [record["value"] for record in recent_records]
        n = len(values)
        x_values = list(range(n))
        
        # Calcular pendiente
        x_mean = sum(x_values) / n
        y_mean = sum(values) / n
        
        numerator = sum((x_values[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # Determinar tendencia
        if abs(slope) < 0.01:
            trend = "estable"
            trend_description = "Se mantiene estable"
        elif slope > 0:
            trend = "ascendente" if metric_name in ["muscle_mass", "energy_level", "sleep_quality", "recovery_rate", "appetite"] else "aumentando"
            trend_description = "Tendencia al alza"
        else:
            trend = "descendente" if metric_name in ["weight", "body_fat", "waist_circumference"] else "disminuyendo"
            trend_description = "Tendencia a la baja"
        
        # Calcular tasa de cambio (por semana)
        days_span = (datetime.fromisoformat(recent_records[-1]["timestamp"]) - 
                    datetime.fromisoformat(recent_records[0]["timestamp"])).days
        
        if days_span > 0:
            weekly_change_rate = slope * 7 * (len(recent_records) - 1) / days_span
        else:
            weekly_change_rate = 0
        
        return {
            "trend": trend,
            "trend_description": trend_description,
            "change_rate": round(weekly_change_rate, 3),
            "data_points": len(recent_records),
            "period_analyzed": f"{days_span} días"
        }
    
    def _update_available_energy(self, user_profile: Dict, new_weight: float) -> None:
        """
        Actualizar Available Energy cuando cambia el peso
        """
        try:
            # Obtener datos actuales
            basic_data = user_profile["basic_data"]
            current_weight = basic_data.get("peso", new_weight)
            
            # Solo actualizar si el peso ha cambiado significativamente (>0.5kg)
            if abs(new_weight - current_weight) < 0.5:
                return
            
            # Actualizar peso en basic_data
            basic_data["peso"] = new_weight
            
            # Recalcular macros con nuevo peso
            height = basic_data["altura"]
            age = basic_data["edad"]
            sex = basic_data["sexo"]
            activity_level = basic_data["activity_level"]
            objective = basic_data["objetivo"]
            
            # Calcular nuevo BMR
            if sex == "masculino":
                bmr = 88.362 + (13.397 * new_weight) + (4.799 * height) - (5.677 * age)
            else:
                bmr = 447.593 + (9.247 * new_weight) + (3.098 * height) - (4.330 * age)
            
            # Calcular nuevo TDEE
            tdee = bmr * activity_level
            
            # Ajustar según objetivo
            objective_adjustments = {
                "bajar_peso": -0.20,     # -20% déficit
                "subir_masa": 0.15,      # +15% superávit
                "subir_masa_lean": 0.10, # +10% superávit limpio
                "recomposicion": 0.0,    # Mantenimiento
                "mantener": 0.0          # Mantenimiento
            }
            
            adjustment = objective_adjustments.get(objective, 0.0)
            daily_calories = int(tdee * (1 + adjustment))
            
            # Calcular nuevos macros
            if objective == "bajar_peso":
                protein_ratio, carbs_ratio, fat_ratio = 0.35, 0.30, 0.35
            elif objective == "subir_masa":
                protein_ratio, carbs_ratio, fat_ratio = 0.25, 0.45, 0.30
            elif objective == "subir_masa_lean":
                protein_ratio, carbs_ratio, fat_ratio = 0.30, 0.40, 0.30
            elif objective == "recomposicion":
                protein_ratio, carbs_ratio, fat_ratio = 0.35, 0.35, 0.30
            else:  # mantener
                protein_ratio, carbs_ratio, fat_ratio = 0.25, 0.45, 0.30
            
            protein_g = int((daily_calories * protein_ratio) / 4)
            carbs_g = int((daily_calories * carbs_ratio) / 4)
            fat_g = int((daily_calories * fat_ratio) / 9)
            
            # Actualizar macros en perfil
            user_profile["macros"] = {
                "calories": daily_calories,
                "protein_g": protein_g,
                "carbs_g": carbs_g,
                "fat_g": fat_g
            }
            
            # Recalcular Available Energy
            ffm = new_weight * (1 - (basic_data.get("body_fat_percentage", 15) / 100))
            exercise_calories = basic_data.get("exercise_calories_per_session", 300)
            weekly_sessions = basic_data.get("weekly_sessions", 4)
            daily_exercise_calories = (exercise_calories * weekly_sessions) / 7
            
            available_energy = (daily_calories - daily_exercise_calories) / ffm
            
            # Actualizar energy_data
            user_profile["energy_data"]["available_energy"] = round(available_energy, 1)
            user_profile["energy_data"]["tdee"] = int(tdee)
            user_profile["energy_data"]["daily_exercise_calories"] = int(daily_exercise_calories)
            
        except Exception as e:
            print(f"Error updating available energy: {e}")
    
    def _generate_metric_insights(self, metric_records: List[Dict], metric_name: str, user_profile: Dict) -> List[str]:
        """
        Generar insights automáticos basados en los datos de la métrica
        """
        insights = []
        
        if len(metric_records) < 2:
            return ["Registra más datos para obtener insights personalizados"]
        
        recent_value = metric_records[-1]["value"]
        metric_config = self.trackable_metrics[metric_name]
        
        # Insights específicos por métrica
        if metric_name == "weight":
            objective = user_profile["basic_data"]["objetivo"]
            
            if len(metric_records) >= 4:  # Al menos 4 registros
                last_week_avg = sum(r["value"] for r in metric_records[-7:]) / min(7, len(metric_records[-7:]))
                previous_week_avg = sum(r["value"] for r in metric_records[-14:-7]) / min(7, len(metric_records[-14:-7]))
                
                weekly_change = last_week_avg - previous_week_avg
                
                if objective == "bajar_peso":
                    if weekly_change < -0.5:
                        insights.append("✅ Excelente pérdida de peso semanal")
                    elif weekly_change < -0.2:
                        insights.append("🟡 Pérdida de peso moderada - considera ajustar déficit")
                    else:
                        insights.append("🔴 Peso estable - revisa tu plan nutricional")
                
                elif objective in ["subir_masa", "subir_masa_lean"]:
                    if weekly_change > 0.2:
                        insights.append("✅ Ganancia de peso óptima para tu objetivo")
                    elif weekly_change > 0:
                        insights.append("🟡 Ganancia lenta - considera aumentar calorías")
                    else:
                        insights.append("🔴 No hay ganancia - aumenta tu superávit calórico")
        
        elif metric_name == "energy_level":
            if recent_value >= 8:
                insights.append("🔥 Excelente nivel de energía - tu plan está funcionando")
            elif recent_value >= 6:
                insights.append("🟡 Energía moderada - optimiza tu descanso y timing")
            else:
                insights.append("⚠️ Energía baja - revisa tu Available Energy y recuperación")
        
        elif metric_name == "sleep_quality":
            if recent_value >= 8:
                insights.append("😴 Calidad de sueño excelente - clave para tus resultados")
            elif recent_value >= 6:
                insights.append("🌙 Sueño moderado - considera mejorar tu higiene del sueño")
            else:
                insights.append("⚠️ Sueño deficiente - prioriza 7-9 horas de sueño de calidad")
        
        elif metric_name == "recovery_rate":
            if recent_value >= 8:
                insights.append("💪 Recuperación excelente - puedes mantener tu intensidad")
            elif recent_value >= 6:
                insights.append("🔄 Recuperación moderada - considera días de descanso activo")
            else:
                insights.append("⚠️ Recuperación lenta - reduce intensidad o aumenta descanso")
        
        # Insight sobre consistencia
        if len(metric_records) >= 7:
            last_week_records = len([r for r in metric_records if 
                                   (datetime.now() - datetime.fromisoformat(r["timestamp"])).days <= 7])
            
            if last_week_records >= 3:
                insights.append("📈 Buena consistencia en el tracking - sigue así")
            elif last_week_records >= 1:
                insights.append("📊 Trackea más frecuentemente para mejores insights")
        
        return insights[:3]  # Máximo 3 insights
    
    def generate_progress_report(self, user_profile: Dict, period: str = "month") -> Dict:
        """
        Generar reporte completo de progreso para un período específico
        """
        try:
            tracking_data = user_profile.get("progress_tracking", {})
            
            if not tracking_data or not tracking_data.get("metrics"):
                return {
                    "success": False,
                    "error": "No hay datos de seguimiento disponibles"
                }
            
            period_config = self.analysis_periods.get(period, self.analysis_periods["month"])
            cutoff_date = datetime.now() - timedelta(days=period_config["days"])
            
            report = {
                "success": True,
                "period": period_config["name"],
                "generated_at": datetime.now().isoformat(),
                "metrics_analysis": {},
                "overall_assessment": {},
                "recommendations": [],
                "achievements": []
            }
            
            # Analizar cada métrica
            for metric_name, records in tracking_data["metrics"].items():
                if not records:
                    continue
                
                # Filtrar registros del período
                period_records = [
                    record for record in records
                    if datetime.fromisoformat(record["timestamp"]) >= cutoff_date
                ]
                
                if not period_records:
                    continue
                
                metric_config = self.trackable_metrics[metric_name]
                
                # Análisis de la métrica
                metric_analysis = {
                    "name": metric_config["name"],
                    "emoji": metric_config["emoji"],
                    "unit": metric_config["unit"],
                    "records_count": len(period_records),
                    "current_value": period_records[-1]["value"],
                    "trend": self._calculate_trends(records, metric_name),
                    "statistics": self._calculate_period_statistics(period_records),
                    "insights": self._generate_metric_insights(records, metric_name, user_profile)
                }
                
                report["metrics_analysis"][metric_name] = metric_analysis
            
            # Evaluación general
            report["overall_assessment"] = self._generate_overall_assessment(
                report["metrics_analysis"], user_profile
            )
            
            # Recomendaciones
            report["recommendations"] = self._generate_recommendations(
                report["metrics_analysis"], user_profile
            )
            
            # Logros
            report["achievements"] = self._identify_achievements(
                report["metrics_analysis"], user_profile
            )
            
            return report
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error generando reporte: {str(e)}"
            }
    
    def _calculate_period_statistics(self, records: List[Dict]) -> Dict:
        """
        Calcular estadísticas para un período específico
        """
        if not records:
            return {}
        
        values = [record["value"] for record in records]
        
        stats = {
            "min": min(values),
            "max": max(values),
            "average": round(sum(values) / len(values), 2),
            "median": round(statistics.median(values), 2),
            "change": round(values[-1] - values[0], 2) if len(values) > 1 else 0,
            "change_percentage": round(((values[-1] - values[0]) / values[0]) * 100, 1) if len(values) > 1 and values[0] != 0 else 0
        }
        
        return stats
    
    def _generate_overall_assessment(self, metrics_analysis: Dict, user_profile: Dict) -> Dict:
        """
        Generar evaluación general del progreso
        """
        if not metrics_analysis:
            return {"score": 0, "description": "Sin datos suficientes"}
        
        objective = user_profile["basic_data"]["objetivo"]
        total_score = 0
        scored_metrics = 0
        
        # Puntuación por métrica según objetivo
        objective_weights = {
            "bajar_peso": {
                "weight": 0.4, "body_fat": 0.3, "waist_circumference": 0.2, 
                "energy_level": 0.1
            },
            "subir_masa": {
                "weight": 0.3, "muscle_mass": 0.4, "recovery_rate": 0.2, 
                "energy_level": 0.1
            },
            "recomposicion": {
                "body_fat": 0.3, "muscle_mass": 0.3, "weight": 0.2, 
                "energy_level": 0.2
            }
        }
        
        weights = objective_weights.get(objective, {"weight": 0.5, "energy_level": 0.5})
        
        for metric_name, analysis in metrics_analysis.items():
            if metric_name not in weights:
                continue
            
            # Puntuación basada en tendencia
            trend = analysis["trend"]["trend"]
            metric_score = 0
            
            if objective == "bajar_peso" and metric_name in ["weight", "body_fat", "waist_circumference"]:
                metric_score = 100 if trend == "descendente" else 50 if trend == "estable" else 0
            elif objective == "subir_masa" and metric_name in ["weight", "muscle_mass"]:
                metric_score = 100 if trend == "ascendente" else 50 if trend == "estable" else 0
            elif metric_name in ["energy_level", "sleep_quality", "recovery_rate", "appetite"]:
                metric_score = 100 if trend == "ascendente" else 50 if trend == "estable" else 0
            
            total_score += metric_score * weights[metric_name]
            scored_metrics += weights[metric_name]
        
        if scored_metrics == 0:
            final_score = 0
        else:
            final_score = int(total_score / scored_metrics)
        
        # Descripción del progreso
        if final_score >= 80:
            description = "Excelente progreso hacia tu objetivo"
            emoji = "🏆"
        elif final_score >= 60:
            description = "Buen progreso, mantén el rumbo"
            emoji = "📈"
        elif final_score >= 40:
            description = "Progreso moderado, considera ajustes"
            emoji = "🟡"
        else:
            description = "Progreso lento, revisa tu estrategia"
            emoji = "⚠️"
        
        return {
            "score": final_score,
            "description": description,
            "emoji": emoji,
            "scored_metrics": scored_metrics
        }
    
    def _generate_recommendations(self, metrics_analysis: Dict, user_profile: Dict) -> List[str]:
        """
        Generar recomendaciones específicas basadas en el análisis
        """
        recommendations = []
        objective = user_profile["basic_data"]["objetivo"]
        
        # Recomendaciones por métrica
        for metric_name, analysis in metrics_analysis.items():
            trend = analysis["trend"]["trend"]
            current_value = analysis["current_value"]
            
            if metric_name == "weight":
                if objective == "bajar_peso" and trend != "descendente":
                    recommendations.append("💡 Considera aumentar tu déficit calórico o revisar tu adherencia")
                elif objective in ["subir_masa", "subir_masa_lean"] and trend != "ascendente":
                    recommendations.append("💡 Aumenta tu superávit calórico para promover ganancia de peso")
            
            elif metric_name == "energy_level" and current_value < 6:
                recommendations.append("⚡ Optimiza tu Available Energy y revisa tu descanso")
            
            elif metric_name == "sleep_quality" and current_value < 7:
                recommendations.append("😴 Prioriza 7-9 horas de sueño de calidad cada noche")
            
            elif metric_name == "recovery_rate" and current_value < 6:
                recommendations.append("🔄 Considera reducir intensidad o añadir más días de descanso")
        
        # Recomendaciones generales
        if len(metrics_analysis) < 3:
            recommendations.append("📊 Registra más métricas para obtener un análisis más completo")
        
        # Verificar frecuencia de tracking
        total_records = sum(analysis["records_count"] for analysis in metrics_analysis.values())
        if total_records < 10:
            recommendations.append("📈 Aumenta la frecuencia de registro para mejores insights")
        
        return recommendations[:5]  # Máximo 5 recomendaciones
    
    def _identify_achievements(self, metrics_analysis: Dict, user_profile: Dict) -> List[str]:
        """
        Identificar logros y hitos alcanzados
        """
        achievements = []
        objective = user_profile["basic_data"]["objetivo"]
        
        for metric_name, analysis in metrics_analysis.items():
            records_count = analysis["records_count"]
            trend = analysis["trend"]["trend"]
            statistics = analysis["statistics"]
            
            # Logros por consistencia
            if records_count >= 30:
                achievements.append(f"🏅 30+ registros de {analysis['name']} - ¡Excelente consistencia!")
            elif records_count >= 14:
                achievements.append(f"⭐ 2+ semanas registrando {analysis['name']}")
            
            # Logros por progreso
            if abs(statistics.get("change_percentage", 0)) >= 5:
                if metric_name == "weight" and objective == "bajar_peso" and statistics["change"] < 0:
                    achievements.append(f"🎯 {abs(statistics['change']):.1f}kg perdidos - ¡Gran trabajo!")
                elif metric_name == "weight" and objective in ["subir_masa", "subir_masa_lean"] and statistics["change"] > 0:
                    achievements.append(f"💪 {statistics['change']:.1f}kg ganados hacia tu objetivo")
                elif metric_name in ["energy_level", "sleep_quality", "recovery_rate"] and statistics["change"] > 0:
                    achievements.append(f"⬆️ Mejora del {statistics['change_percentage']}% en {analysis['name']}")
            
            # Logros por valores altos
            current_value = analysis["current_value"]
            if metric_name in ["energy_level", "sleep_quality", "recovery_rate", "appetite"] and current_value >= 8:
                achievements.append(f"🔥 {analysis['name']} excelente ({current_value}/10)")
        
        return achievements[:4]  # Máximo 4 logros
    
    def format_progress_report_for_telegram(self, report_data: Dict, user_profile: Dict) -> str:
        """
        Formatear reporte de progreso para mostrar en Telegram
        """
        if not report_data["success"]:
            return f"❌ **Error generando reporte:** {report_data.get('error', 'Error desconocido')}"
        
        # Encabezado
        text = f"""
📊 **REPORTE DE PROGRESO PERSONAL**

👤 **Usuario:** {user_profile['basic_data']['objetivo_descripcion']}
📅 **Período:** {report_data['period']}
📈 **Generado:** {datetime.fromisoformat(report_data['generated_at']).strftime('%d/%m/%Y %H:%M')}

"""
        
        # Evaluación general
        overall = report_data["overall_assessment"]
        text += f"{overall['emoji']} **EVALUACIÓN GENERAL: {overall['score']}/100**\n"
        text += f"_{overall['description']}_\n\n"
        
        # Análisis por métrica
        text += "📈 **ANÁLISIS POR MÉTRICA:**\n\n"
        
        for metric_name, analysis in report_data["metrics_analysis"].items():
            emoji = analysis["emoji"]
            name = analysis["name"]
            current = analysis["current_value"]
            unit = analysis["unit"]
            trend = analysis["trend"]
            stats = analysis["statistics"]
            
            text += f"{emoji} **{name}**\n"
            text += f"   📍 Actual: {current}{unit}\n"
            text += f"   📊 Tendencia: {trend['trend_description']}\n"
            
            if stats.get("change") != 0:
                change_emoji = "📈" if stats["change"] > 0 else "📉"
                text += f"   {change_emoji} Cambio: {stats['change']:+.1f}{unit} ({stats['change_percentage']:+.1f}%)\n"
            
            text += f"   📋 Registros: {analysis['records_count']}\n\n"
        
        # Logros
        if report_data.get("achievements"):
            text += "🏆 **LOGROS ALCANZADOS:**\n"
            for achievement in report_data["achievements"]:
                text += f"• {achievement}\n"
            text += "\n"
        
        # Recomendaciones
        if report_data.get("recommendations"):
            text += "💡 **RECOMENDACIONES:**\n"
            for rec in report_data["recommendations"]:
                text += f"• {rec}\n"
            text += "\n"
        
        # Próximos pasos
        text += f"""
🚀 **PRÓXIMOS PASOS:**
• Continúa registrando métricas consistentemente
• Ajusta tu plan según las recomendaciones
• Usa `/nueva_semana` para planes adaptados
• Revisa tu progreso semanalmente

💪 **¡Mantén el momentum hacia tu objetivo!**
"""
        
        return text
    
    def get_metric_entry_keyboard(self, metric_name: str) -> str:
        """
        Generar texto de ayuda para entrada de métrica específica
        """
        metric_config = self.trackable_metrics.get(metric_name, {})
        
        if not metric_config:
            return "Métrica no válida"
        
        return f"""
{metric_config['emoji']} **REGISTRAR {metric_config['name'].upper()}**

📝 **Formato:** Envía solo el número
📊 **Rango válido:** {metric_config['min_value']}-{metric_config['max_value']} {metric_config['unit']}
📅 **Frecuencia recomendada:** Diaria o semanal

**Ejemplos válidos:**
• {metric_config['min_value'] + (metric_config['max_value'] - metric_config['min_value']) * 0.3:.1f}
• {metric_config['min_value'] + (metric_config['max_value'] - metric_config['min_value']) * 0.7:.1f}

_Nota: También puedes añadir notas opcionales después del número_
"""

# Ejemplo de uso
if __name__ == "__main__":
    tracker = ProgressTracker()
    
    # Perfil de usuario de ejemplo
    sample_profile = {
        "basic_data": {
            "objetivo": "bajar_peso",
            "objetivo_descripcion": "Perder grasa manteniendo músculo",
            "peso": 75.0,
            "altura": 175,
            "edad": 30,
            "sexo": "masculino"
        },
        "macros": {"calories": 2200}
    }
    
    # Simular registro de peso
    result = tracker.record_metric(sample_profile, "weight", 74.2, "Después de una semana de déficit")
    
    print("=== REGISTRO DE MÉTRICA ===")
    print(f"Éxito: {result['success']}")
    if result["success"]:
        print(f"Métrica: {result['metric_recorded']['name']}")
        print(f"Valor: {result['metric_recorded']['value']}{result['metric_recorded']['unit']}")
        print(f"Tendencia: {result['trend_analysis']['trend_description']}")
        print("Insights:", result['insights'])
    
    # Generar reporte de ejemplo
    report = tracker.generate_progress_report(sample_profile, "month")
    if report["success"]:
        formatted_report = tracker.format_progress_report_for_telegram(report, sample_profile)
        print("\n=== REPORTE DE PROGRESO ===")
        print(formatted_report)