"""
Analizador inteligente de temperatura del refrigerador.
Detecta:
- Aperturas de puerta (cambios rápidos que luego se recuperan)
- Problemas reales (aumentos sostenidos de temperatura)
- Descensos anormales
"""
from collections import deque
from datetime import datetime, timedelta
from enum import Enum

from config.config import config
from utils.logger import logger
from utils.time_utils import get_bolivia_now


class TemperatureAlertType(Enum):
    """Tipos de alertas de temperatura"""
    NONE = "none"
    DOOR_OPENING = "door_opening"  # Probable apertura de puerta
    CRITICAL_INCREASE = "critical_increase"  # Aumento crítico sostenido
    CRITICAL_DECREASE = "critical_decrease"  # Descenso anormal
    OUT_OF_RANGE = "out_of_range"  # Fuera del rango normal


class TemperatureReading:
    """Lectura de temperatura con timestamp"""

    def __init__(self, temperature, timestamp):
        self.temperature = temperature
        self.timestamp = timestamp


class TemperatureAnalyzer:
    """
    Analiza patrones de temperatura para distinguir entre:
    - Apertura normal de puerta (cambio rápido + recuperación rápida)
    - Problema real del refrigerador (cambio sostenido sin recuperación)
    """

    def __init__(self):
        # Buffer circular para almacenar últimas lecturas (últimos 30 minutos aprox)
        # Con lecturas cada 15s, 120 lecturas = 30 minutos
        self.readings = deque(maxlen=120)

        # Tracking del estado actual
        self.baseline_temp = None  # Temperatura base (promedio de los últimos 5 minutos)
        self.last_alert = None
        self.alert_start_time = None
        self.recovery_detected = False

        # Contadores para análisis
        self.consecutive_increases = 0
        self.consecutive_decreases = 0

        logger.info("TemperatureAnalyzer inicializado")

    def add_reading(self, temperature):
        """
        Agrega una nueva lectura y retorna análisis.

        Args:
            temperature: Temperatura en °C

        Returns:
            dict: {
                'alert_type': TemperatureAlertType,
                'alert_message': str,
                'current_temp': float,
                'baseline_temp': float,
                'temp_change': float,
                'is_recovering': bool
            }
        """
        now = get_bolivia_now()
        reading = TemperatureReading(temperature, now)
        self.readings.append(reading)

        # Si no hay suficientes lecturas, solo establecer baseline
        if len(self.readings) < 5:
            self._update_baseline()
            return self._create_result(TemperatureAlertType.NONE, "Calibrando sistema...")

        # Actualizar baseline (promedio de últimos 5 minutos en condiciones estables)
        self._update_baseline()

        # Analizar patrones
        return self._analyze_pattern(temperature, now)

    def _update_baseline(self):
        """
        Actualiza la temperatura baseline (referencia).
        Usa el promedio de las últimas 20 lecturas (5 minutos)
        solo si no hay alertas activas.
        """
        if len(self.readings) < 20:
            if len(self.readings) > 0:
                self.baseline_temp = sum(r.temperature for r in self.readings) / len(self.readings)
            return

        # Si hay alerta activa, no actualizar baseline (mantener referencia pre-alerta)
        if self.last_alert and self.last_alert != TemperatureAlertType.NONE:
            return

        # Calcular promedio de últimas 20 lecturas (5 minutos)
        recent_temps = [r.temperature for r in list(self.readings)[-20:]]
        self.baseline_temp = sum(recent_temps) / len(recent_temps)

    def _analyze_pattern(self, current_temp, now):
        """
        Analiza el patrón de temperatura y determina el tipo de alerta.

        Lógica:
        1. Cambio rápido (>3°C en <5 min) → Probable apertura de puerta
           - Si se recupera en <10 min → Confirma apertura de puerta
           - Si NO se recupera → Escala a problema crítico

        2. Cambio gradual (>1.5°C en >10 min) → Problema real del refrigerador

        3. Fuera de rango normal → Alerta inmediata
        """
        if self.baseline_temp is None:
            return self._create_result(TemperatureAlertType.NONE, "Estableciendo baseline...")

        # Calcular cambio de temperatura
        temp_change = current_temp - self.baseline_temp

        # 1. Verificar si está fuera del rango normal operativo
        if current_temp < config.TEMP_NORMAL_RANGE_MIN:
            return self._create_result(
                TemperatureAlertType.OUT_OF_RANGE,
                f"⚠️ Temperatura demasiado baja: {current_temp:.1f}°C (mín: {config.TEMP_NORMAL_RANGE_MIN}°C)"
            )

        if current_temp > config.TEMP_NORMAL_RANGE_MAX:
            return self._create_result(
                TemperatureAlertType.OUT_OF_RANGE,
                f"🔥 Temperatura demasiado alta: {current_temp:.1f}°C (máx: {config.TEMP_NORMAL_RANGE_MAX}°C)"
            )

        # 2. Analizar cambio rápido (probable apertura de puerta)
        rapid_change = self._check_rapid_change(current_temp, now)
        if rapid_change:
            return rapid_change

        # 3. Analizar cambio gradual sostenido (problema real)
        gradual_change = self._check_gradual_change(current_temp, temp_change, now)
        if gradual_change:
            return gradual_change

        # 4. Verificar recuperación de alerta previa
        if self.last_alert and self.last_alert != TemperatureAlertType.NONE:
            recovery = self._check_recovery(current_temp, temp_change)
            if recovery:
                return recovery

        # Todo normal
        self.consecutive_increases = 0
        self.consecutive_decreases = 0
        return self._create_result(TemperatureAlertType.NONE, "Temperatura normal")

    def _check_rapid_change(self, current_temp, now):
        """
        Detecta cambios rápidos (>3°C en <5 minutos).
        Esto generalmente indica apertura de puerta.
        """
        # Obtener lecturas de hace 5 minutos
        five_min_ago = now - timedelta(minutes=5)
        old_readings = [r for r in self.readings if r.timestamp >= five_min_ago]

        if len(old_readings) < 5:
            return None

        # Temperatura hace 5 minutos
        oldest_temp = old_readings[0].temperature
        temp_change_5min = current_temp - oldest_temp

        # Si aumentó más de 3°C en 5 minutos
        if temp_change_5min > config.TEMP_ALERT_RAPID_CHANGE:
            if self.last_alert != TemperatureAlertType.DOOR_OPENING:
                self.alert_start_time = now
                logger.warning(f"🚪 Posible apertura de puerta detectada: +{temp_change_5min:.1f}°C en 5 min")

            return self._create_result(
                TemperatureAlertType.DOOR_OPENING,
                f"🚪 Posible apertura de puerta: +{temp_change_5min:.1f}°C en 5 minutos"
            )

        return None

    def _check_gradual_change(self, current_temp, temp_change, now):
        """
        Detecta cambios graduales sostenidos (>1.5°C en >10 minutos).
        Esto indica un problema real del refrigerador.
        """
        # Tracking de incrementos consecutivos
        if len(self.readings) >= 2:
            prev_temp = self.readings[-2].temperature
            if current_temp > prev_temp:
                self.consecutive_increases += 1
                self.consecutive_decreases = 0
            elif current_temp < prev_temp:
                self.consecutive_decreases += 1
                self.consecutive_increases = 0
            else:
                # Temperatura estable
                pass

        # Obtener lecturas de hace 10 minutos
        ten_min_ago = now - timedelta(minutes=10)
        old_readings = [r for r in self.readings if r.timestamp >= ten_min_ago]

        if len(old_readings) < 10:
            return None

        # Temperatura hace 10 minutos
        oldest_temp = old_readings[0].temperature
        temp_change_10min = current_temp - oldest_temp

        # Si ha habido aumento sostenido
        if temp_change_10min > config.TEMP_ALERT_SLOW_INCREASE and self.consecutive_increases >= 5:
            if self.last_alert != TemperatureAlertType.CRITICAL_INCREASE:
                self.alert_start_time = now
                logger.error(f"🔥 PROBLEMA CRÍTICO: Aumento sostenido de {temp_change_10min:.1f}°C en 10 min")

            return self._create_result(
                TemperatureAlertType.CRITICAL_INCREASE,
                f"🔥 PROBLEMA CRÍTICO: Temperatura aumentando constantemente (+{temp_change_10min:.1f}°C en 10 min)"
            )

        # Si ha habido descenso sostenido anormal
        if temp_change_10min < -config.TEMP_ALERT_SLOW_INCREASE and self.consecutive_decreases >= 5:
            if self.last_alert != TemperatureAlertType.CRITICAL_DECREASE:
                self.alert_start_time = now
                logger.error(f"❄️ PROBLEMA CRÍTICO: Descenso sostenido de {temp_change_10min:.1f}°C en 10 min")

            return self._create_result(
                TemperatureAlertType.CRITICAL_DECREASE,
                f"❄️ PROBLEMA CRÍTICO: Temperatura descendiendo anormalmente ({temp_change_10min:.1f}°C en 10 min)"
            )

        return None

    def _check_recovery(self, current_temp, temp_change):
        """
        Verifica si la temperatura está regresando a la normalidad
        después de una alerta.
        """
        # Si estaba en alerta de apertura de puerta
        if self.last_alert == TemperatureAlertType.DOOR_OPENING:
            # Si la temperatura está cerca del baseline (±0.5°C)
            if abs(temp_change) < 0.5:
                logger.info("✅ Temperatura recuperada tras apertura de puerta")
                self.consecutive_increases = 0
                self.alert_start_time = None
                return self._create_result(
                    TemperatureAlertType.NONE,
                    "✅ Temperatura recuperada tras apertura de puerta",
                    is_recovering=True
                )

        # Si estaba en alerta crítica y está mejorando
        if self.last_alert in [TemperatureAlertType.CRITICAL_INCREASE, TemperatureAlertType.CRITICAL_DECREASE]:
            if abs(temp_change) < 1.0:
                logger.info("✅ Temperatura estabilizada")
                self.consecutive_increases = 0
                self.consecutive_decreases = 0
                self.alert_start_time = None
                return self._create_result(
                    TemperatureAlertType.NONE,
                    "✅ Temperatura estabilizada",
                    is_recovering=True
                )

        return None

    def _create_result(self, alert_type, message, is_recovering=False):
        """Crea el diccionario de resultado del análisis"""
        self.last_alert = alert_type

        current_temp = self.readings[-1].temperature if self.readings else 0.0
        temp_change = current_temp - self.baseline_temp if self.baseline_temp else 0.0

        return {
            'alert_type': alert_type,
            'alert_message': message,
            'current_temp': round(current_temp, 2),
            'baseline_temp': round(self.baseline_temp, 2) if self.baseline_temp else None,
            'temp_change': round(temp_change, 2),
            'is_recovering': is_recovering,
            'consecutive_increases': self.consecutive_increases,
            'consecutive_decreases': self.consecutive_decreases
        }

    def get_statistics(self):
        """Retorna estadísticas del análisis"""
        if not self.readings:
            return None

        temps = [r.temperature for r in self.readings]

        return {
            'count': len(temps),
            'current': temps[-1],
            'min': min(temps),
            'max': max(temps),
            'avg': sum(temps) / len(temps),
            'baseline': self.baseline_temp,
            'range_minutes': (self.readings[-1].timestamp - self.readings[0].timestamp).total_seconds() / 60
        }