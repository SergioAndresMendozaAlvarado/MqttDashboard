"""
Procesador de mensajes MQTT recibidos del ESP32
"""
import json
from datetime import datetime
from utils.logger import logger
from utils.time_utils import BOLIVIA_TZ


class MessageHandler:
    """Maneja el parsing y validación de mensajes MQTT"""

    @staticmethod
    def parse_sensor_data(payload):
        """
        Parsea el mensaje JSON de datos del sensor.

        Formato esperado:
        {
            "device_id": "esp32-fridge-001",
            "timestamp": 78741,
            "temperature": 19.7,
            "pressure": 63408,
            "altitude": 3783.08,
            "rssi": -71,
            "status": "normal"
        }

        Args:
            payload: bytes del mensaje MQTT

        Returns:
            dict: Datos parseados o None si hay error
        """
        try:
            # Decodificar payload
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')

            # Parsear JSON
            data = json.loads(payload)

            # Validar campos requeridos
            required_fields = ['device_id', 'temperature']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Campo requerido '{field}' no encontrado en mensaje")
                    return None

            # Extraer y validar temperatura
            temperature = float(data['temperature'])
            if temperature < -50 or temperature > 100:
                logger.warning(f"Temperatura fuera de rango válido: {temperature}°C")
                return None

            # Construir diccionario de respuesta
            result = {
                'device_id': data['device_id'],
                'temperature': temperature,
                'pressure': float(data.get('pressure', 0)),
                'altitude': float(data.get('altitude', 0)),
                'rssi': int(data.get('rssi', 0)),
                'status': data.get('status', 'unknown'),
                'timestamp': datetime.now(BOLIVIA_TZ)
            }

            logger.debug(f"Sensor data parseado: {result['temperature']}°C")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON: {e}")
            return None
        except (ValueError, TypeError) as e:
            logger.error(f"Error al validar datos: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al parsear sensor data: {e}")
            return None

    @staticmethod
    def parse_heartbeat(payload):
        """
        Parsea el mensaje JSON de heartbeat.

        Formato esperado:
        {
            "device_id": "esp32-fridge-001",
            "timestamp": 118910,
            "status": "alive"
        }

        Args:
            payload: bytes del mensaje MQTT

        Returns:
            dict: Datos parseados o None si hay error
        """
        try:
            # Decodificar payload
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')

            # Parsear JSON
            data = json.loads(payload)

            # Validar campo requerido
            if 'device_id' not in data:
                logger.error("Campo 'device_id' no encontrado en heartbeat")
                return None

            result = {
                'device_id': data['device_id'],
                'status': data.get('status', 'alive'),
                'timestamp': datetime.now(BOLIVIA_TZ)
            }

            logger.debug(f"Heartbeat recibido de {result['device_id']}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON de heartbeat: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al parsear heartbeat: {e}")
            return None