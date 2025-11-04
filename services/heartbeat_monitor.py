"""
Monitor de heartbeat del ESP32.
Detecta cuando el dispositivo se desconecta (no recibe heartbeat en 6 segundos).
"""
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from datetime import datetime

from config.config import config
from utils.logger import logger
from utils.time_utils import get_bolivia_now


class HeartbeatMonitor(QObject):
    """
    Monitor que verifica si el ESP32 sigue enviando heartbeats.
    Si no recibe heartbeat en HEARTBEAT_TIMEOUT segundos, emite señal de desconexión.
    """

    # Señales
    device_connected = pyqtSignal()  # Dispositivo conectado/reconectado
    device_disconnected = pyqtSignal()  # Dispositivo desconectado (timeout)

    def __init__(self):
        super().__init__()

        self.last_heartbeat_time = None
        self.is_online = False
        self.timeout_seconds = config.HEARTBEAT_TIMEOUT

        # Timer para verificar timeout cada segundo
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_timeout)

        logger.info(f"HeartbeatMonitor inicializado (timeout: {self.timeout_seconds}s)")

    def start(self):
        """Inicia el monitoreo"""
        self.timer.start(1000)  # Verificar cada 1 segundo
        logger.info("HeartbeatMonitor iniciado")

    def stop(self):
        """Detiene el monitoreo"""
        self.timer.stop()
        logger.info("HeartbeatMonitor detenido")

    def register_heartbeat(self):
        """
        Registra que se recibió un heartbeat.
        Debe llamarse cada vez que llega un mensaje de heartbeat del ESP32.
        """
        now = get_bolivia_now()
        was_offline = not self.is_online

        self.last_heartbeat_time = now
        self.is_online = True

        # Si estaba offline y ahora recibimos heartbeat, el dispositivo se reconectó
        if was_offline:
            logger.success(f"✅ ESP32 CONECTADO - Heartbeat recibido")
            self.device_connected.emit()

        logger.debug(f"💓 Heartbeat registrado: {now.strftime('%H:%M:%S')}")

    def _check_timeout(self):
        """
        Verifica si ha pasado demasiado tiempo desde el último heartbeat.
        Se ejecuta cada segundo por el QTimer.
        """
        if self.last_heartbeat_time is None:
            # Aún no se ha recibido ningún heartbeat
            return

        now = get_bolivia_now()
        elapsed_seconds = (now - self.last_heartbeat_time).total_seconds()

        # Si pasó más tiempo del timeout y el dispositivo estaba online
        if elapsed_seconds > self.timeout_seconds and self.is_online:
            self.is_online = False
            logger.error(f"❌ ESP32 DESCONECTADO - Sin heartbeat por {elapsed_seconds:.0f}s")
            self.device_disconnected.emit()

    def get_status(self):
        """
        Retorna el estado actual del dispositivo.

        Returns:
            dict: {
                'is_online': bool,
                'last_heartbeat': datetime or None,
                'seconds_since_heartbeat': float or None
            }
        """
        if self.last_heartbeat_time is None:
            return {
                'is_online': False,
                'last_heartbeat': None,
                'seconds_since_heartbeat': None
            }

        now = get_bolivia_now()
        elapsed = (now - self.last_heartbeat_time).total_seconds()

        return {
            'is_online': self.is_online,
            'last_heartbeat': self.last_heartbeat_time,
            'seconds_since_heartbeat': elapsed
        }

    def get_time_since_last_heartbeat(self):
        """
        Retorna cuánto tiempo ha pasado desde el último heartbeat (en segundos).
        Retorna None si nunca se ha recibido heartbeat.
        """
        if self.last_heartbeat_time is None:
            return None

        now = get_bolivia_now()
        return (now - self.last_heartbeat_time).total_seconds()