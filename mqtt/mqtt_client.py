"""
Cliente MQTT para recibir datos del ESP32
"""
import paho.mqtt.client as mqtt
from PyQt6.QtCore import QObject, pyqtSignal
import time

from config.config import config
from utils.logger import logger
from mqtt.message_handler import MessageHandler


class MQTTClient(QObject):
    """
    Cliente MQTT que se conecta al broker y recibe mensajes.
    Usa señales PyQt6 para comunicarse con la UI.
    """

    # Señales para comunicar eventos a la UI
    sensor_data_received = pyqtSignal(dict)  # Emite cuando llegan datos del sensor
    heartbeat_received = pyqtSignal(dict)  # Emite cuando llega heartbeat
    connection_status_changed = pyqtSignal(bool)  # Emite True/False según conexión

    def __init__(self):
        super().__init__()

        self.client = None
        self.connected = False
        self.message_handler = MessageHandler()

        # Topics a los que nos suscribiremos
        self.topics = [
            (config.MQTT_TOPIC_SENSOR, config.MQTT_QOS),
            (config.MQTT_TOPIC_HEARTBEAT, config.MQTT_QOS)
        ]

        logger.info(f"MQTTClient inicializado para device: {config.MQTT_DEVICE_ID}")

    def initialize(self):
        """Inicializa el cliente MQTT y configura callbacks"""
        try:
            # Crear cliente MQTT
            self.client = mqtt.Client(
                client_id=config.MQTT_CLIENT_ID,
                clean_session=True,
                protocol=mqtt.MQTTv311
            )

            # Configurar callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            logger.info(f"Cliente MQTT configurado: {config.MQTT_CLIENT_ID}")
            return True

        except Exception as e:
            logger.error(f"Error al inicializar cliente MQTT: {e}")
            return False

    def connect(self):
        """Conecta al broker MQTT"""
        try:
            logger.info(f"Conectando a broker MQTT: {config.MQTT_BROKER}:{config.MQTT_PORT}")

            self.client.connect(
                config.MQTT_BROKER,
                config.MQTT_PORT,
                config.MQTT_KEEPALIVE
            )

            # Iniciar loop en segundo plano
            self.client.loop_start()

            return True

        except Exception as e:
            logger.error(f"Error al conectar a broker MQTT: {e}")
            self.connection_status_changed.emit(False)
            return False

    def disconnect(self):
        """Desconecta del broker MQTT"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Desconectado del broker MQTT")

    def _on_connect(self, client, userdata, flags, rc):
        """
        Callback cuando se conecta al broker.

        Args:
            rc: Código de resultado de la conexión
                0: Conexión exitosa
                1-5: Diferentes errores de conexión
        """
        if rc == 0:
            logger.success(f"✅ Conectado a broker MQTT: {config.MQTT_BROKER}")
            self.connected = True
            self.connection_status_changed.emit(True)

            # Suscribirse a los topics
            for topic, qos in self.topics:
                self.client.subscribe(topic, qos)
                logger.info(f"Suscrito a topic: {topic}")
        else:
            error_messages = {
                1: "Protocolo incorrecto",
                2: "Client ID inválido",
                3: "Broker no disponible",
                4: "Credenciales inválidas",
                5: "No autorizado"
            }
            error_msg = error_messages.get(rc, f"Error desconocido ({rc})")
            logger.error(f"❌ Error de conexión MQTT: {error_msg}")
            self.connected = False
            self.connection_status_changed.emit(False)

    def _on_disconnect(self, client, userdata, rc):
        """Callback cuando se desconecta del broker"""
        self.connected = False
        self.connection_status_changed.emit(False)

        if rc == 0:
            logger.info("Desconexión limpia del broker MQTT")
        else:
            logger.warning(f"Desconexión inesperada del broker MQTT (rc={rc})")
            logger.info("Intentando reconectar...")

            # Intentar reconectar después de 5 segundos
            time.sleep(5)
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Error al reconectar: {e}")

    def _on_message(self, client, userdata, msg):
        """
        Callback cuando llega un mensaje MQTT.

        Args:
            msg: Objeto mensaje con topic y payload
        """
        try:
            topic = msg.topic
            payload = msg.payload

            logger.debug(f"Mensaje recibido en topic: {topic}")

            # Procesar según el topic
            if topic == config.MQTT_TOPIC_SENSOR:
                self._handle_sensor_data(payload)
            elif topic == config.MQTT_TOPIC_HEARTBEAT:
                self._handle_heartbeat(payload)
            else:
                logger.warning(f"Topic desconocido: {topic}")

        except Exception as e:
            logger.error(f"Error al procesar mensaje MQTT: {e}")

    def _handle_sensor_data(self, payload):
        """Procesa datos del sensor y emite señal"""
        data = self.message_handler.parse_sensor_data(payload)

        if data:
            logger.info(f"📊 Datos del sensor: {data['temperature']}°C, "
                        f"Presión: {data['pressure']} Pa, "
                        f"Altitud: {data['altitude']} m, "
                        f"RSSI: {data['rssi']} dBm")

            # Emitir señal para que otros componentes procesen
            self.sensor_data_received.emit(data)
        else:
            logger.error("No se pudo parsear datos del sensor")

    def _handle_heartbeat(self, payload):
        """Procesa heartbeat y emite señal"""
        data = self.message_handler.parse_heartbeat(payload)

        if data:
            logger.debug(f"💓 Heartbeat de {data['device_id']}")

            # Emitir señal
            self.heartbeat_received.emit(data)
        else:
            logger.error("No se pudo parsear heartbeat")

    def is_connected(self):
        """Retorna True si está conectado al broker"""
        return self.connected

    def get_status(self):
        """Retorna el estado de conexión como string"""
        if self.connected:
            return f"Conectado a {config.MQTT_BROKER}"
        else:
            return "Desconectado"