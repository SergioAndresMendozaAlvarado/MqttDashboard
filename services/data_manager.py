"""
Gestor central de datos del sistema.
Coordina MQTT, Base de Datos y Análisis de Temperatura.
"""
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from datetime import datetime

from config.config import config
from utils.logger import logger
from utils.time_utils import should_save_reading, get_bolivia_now
from database.db_manager import db_manager
from services.temperature_analyzer import TemperatureAnalyzer


class DataManager(QObject):
    """
    Gestor central que:
    - Recibe datos del MQTT client
    - Actualiza el analizador de temperatura
    - Decide cuándo guardar en BD (cada hora)
    - Emite señales para actualizar la UI
    """

    # Señales para la UI
    new_data_available = pyqtSignal(dict)  # Nuevos datos listos para mostrar
    temperature_alert = pyqtSignal(dict)  # Alerta de temperatura
    data_saved_to_db = pyqtSignal(dict)  # Se guardó en BD

    def __init__(self):
        super().__init__()

        # Componentes internos
        self.temp_analyzer = TemperatureAnalyzer()

        # Último dato recibido (para mostrar en UI)
        self.current_data = {
            'device_id': config.MQTT_DEVICE_ID,
            'temperature': None,
            'pressure': None,
            'altitude': None,
            'rssi': None,
            'timestamp': None,
            'status': 'waiting'
        }

        # Tracking de guardado en BD
        self.last_save_time = None
        self.total_readings_received = 0
        self.total_readings_saved = 0

        # Timer para verificar si es hora de guardar (cada minuto)
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self._check_save_to_db)

        logger.info("DataManager inicializado")

    def start(self):
        """Inicia el gestor de datos"""
        # Verificar cada minuto si debemos guardar
        self.save_timer.start(60000)  # 60 segundos
        logger.info("DataManager iniciado")

    def stop(self):
        """Detiene el gestor de datos"""
        self.save_timer.stop()
        logger.info("DataManager detenido")

    def process_sensor_data(self, data):
        """
        Procesa datos recibidos del sensor vía MQTT.

        Args:
            data: dict con keys: device_id, temperature, pressure, altitude, rssi, timestamp
        """
        try:
            self.total_readings_received += 1

            # Extraer datos
            temperature = data['temperature']
            pressure = data['pressure']
            altitude = data['altitude']
            rssi = data['rssi']
            timestamp = data['timestamp']

            # Actualizar datos actuales
            self.current_data.update({
                'temperature': temperature,
                'pressure': pressure,
                'altitude': altitude,
                'rssi': rssi,
                'timestamp': timestamp,
                'status': 'normal'
            })

            # Analizar temperatura
            analysis = self.temp_analyzer.add_reading(temperature)

            # Agregar análisis a los datos
            self.current_data['analysis'] = analysis

            # Si hay alerta, emitir señal
            if analysis['alert_type'].value != 'none':
                logger.warning(f"⚠️ Alerta de temperatura: {analysis['alert_message']}")
                self.temperature_alert.emit(analysis)

            # Actualizar estado del dispositivo en BD (sin bloquear)
            try:
                db_manager.update_device_data(
                    device_id=data['device_id'],
                    temperature=temperature,
                    pressure=pressure,
                    altitude=altitude,
                    rssi=rssi,
                    timestamp=timestamp
                )
            except Exception as e:
                logger.error(f"Error al actualizar device_status: {e}")

            # Emitir señal para actualizar UI
            self.new_data_available.emit(self.current_data)

            logger.info(f"📊 Datos procesados: {temperature}°C | Total recibidas: {self.total_readings_received}")

        except Exception as e:
            logger.error(f"Error al procesar datos del sensor: {e}")

    def _check_save_to_db(self):
        """
        Verifica si es hora de guardar datos en la BD.
        Se ejecuta cada minuto por el QTimer.

        Guarda solo si:
        - Estamos en el minuto :00 de alguna hora (9:00, 10:00, etc)
        - Ha pasado al menos 1 hora desde el último guardado
        - Hay datos disponibles
        """
        if self.current_data['temperature'] is None:
            logger.debug("No hay datos disponibles para guardar")
            return

        # Verificar si debemos guardar
        if should_save_reading(self.last_save_time):
            self._save_to_database()

    def _save_to_database(self):
        """Guarda la lectura actual en la base de datos"""
        try:
            now = get_bolivia_now()

            reading = db_manager.save_temperature_reading(
                device_id=self.current_data['device_id'],
                temperature=self.current_data['temperature'],
                pressure=self.current_data['pressure'],
                altitude=self.current_data['altitude'],
                rssi=self.current_data['rssi'],
                recorded_at=now
            )

            if reading:
                self.last_save_time = now
                self.total_readings_saved += 1

                logger.success(f"💾 Datos guardados en BD: {reading.temperature}°C a las {now.strftime('%H:%M')}")

                # Emitir señal
                self.data_saved_to_db.emit({
                    'temperature': reading.temperature,
                    'timestamp': reading.recorded_at,
                    'total_saved': self.total_readings_saved
                })
            else:
                logger.error("No se pudo guardar en BD")

        except Exception as e:
            logger.error(f"Error al guardar en base de datos: {e}")

    def get_current_data(self):
        """Retorna los datos actuales"""
        return self.current_data.copy()

    def get_statistics(self):
        """Retorna estadísticas del gestor"""
        temp_stats = self.temp_analyzer.get_statistics()

        return {
            'total_received': self.total_readings_received,
            'total_saved': self.total_readings_saved,
            'last_save_time': self.last_save_time,
            'temperature_stats': temp_stats,
            'current_data': self.current_data
        }

    def force_save(self):
        """Fuerza el guardado inmediato en BD (útil para testing)"""
        logger.info("Forzando guardado en BD...")
        self._save_to_database()