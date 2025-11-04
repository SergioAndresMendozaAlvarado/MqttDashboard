"""
Configuración global del sistema de monitoreo de refrigerador
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class Config:
    """Configuración centralizada de la aplicación"""

    # ==================== MQTT ====================
    MQTT_BROKER = os.getenv('MQTT_BROKER', '192.168.0.13')
    MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
    MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', 'dashboard-python-001')
    MQTT_DEVICE_ID = os.getenv('MQTT_DEVICE_ID', 'esp32-fridge-001')
    MQTT_KEEPALIVE = 60
    MQTT_QOS = 1

    # Topics MQTT
    MQTT_TOPIC_SENSOR = f"fridge/{MQTT_DEVICE_ID}/sensor_data"
    MQTT_TOPIC_HEARTBEAT = f"fridge/{MQTT_DEVICE_ID}/heartbeat"

    # ==================== DATABASE ====================
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '7843')
    DB_NAME = os.getenv('DB_NAME', 'fridge_monitoring')

    # Connection string para SQLAlchemy
    @property
    def DATABASE_URL(self):
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ==================== APPLICATION ====================
    TIMEZONE = os.getenv('TIMEZONE', 'America/La_Paz')
    HEARTBEAT_TIMEOUT = int(os.getenv('HEARTBEAT_TIMEOUT', 6))
    SAVE_INTERVAL_HOURS = int(os.getenv('SAVE_INTERVAL_HOURS', 1))

    # ==================== TEMPERATURE ALERTS ====================
    # Cambio rápido (probable apertura de puerta)
    TEMP_ALERT_RAPID_CHANGE = float(os.getenv('TEMP_ALERT_RAPID_CHANGE', 3.0))

    # Cambio lento pero sostenido (problema real)
    TEMP_ALERT_SLOW_INCREASE = float(os.getenv('TEMP_ALERT_SLOW_INCREASE', 1.5))

    # Tiempo típico de apertura de puerta
    TEMP_ALERT_DOOR_OPEN_TIME = int(os.getenv('TEMP_ALERT_DOOR_OPEN_TIME', 5))

    # Rango normal de temperatura
    TEMP_NORMAL_RANGE_MIN = float(os.getenv('TEMP_NORMAL_RANGE_MIN', -5.0))
    TEMP_NORMAL_RANGE_MAX = float(os.getenv('TEMP_NORMAL_RANGE_MAX', 8.0))

    # ==================== UI ====================
    # Cuántos puntos mostrar en el gráfico en tiempo real
    CHART_MAX_POINTS = 50

    # Intervalo de actualización de UI (ms)
    UI_UPDATE_INTERVAL = 1000

    # ==================== LOGGING ====================
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/fridge_monitor.log"
    LOG_ROTATION = "10 MB"
    LOG_RETENTION = "1 month"

    @classmethod
    def validate(cls):
        """Valida que la configuración sea correcta"""
        errors = []

        if not cls.MQTT_BROKER:
            errors.append("MQTT_BROKER no configurado")

        if not cls.DB_PASSWORD:
            errors.append("DB_PASSWORD no configurado")

        if not cls.DB_NAME:
            errors.append("DB_NAME no configurado")

        if errors:
            raise ValueError(f"Errores de configuración: {', '.join(errors)}")

        return True


# Crear instancia global
config = Config()