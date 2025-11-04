"""
Gestor de base de datos - Maneja conexiones y operaciones
"""
from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from datetime import datetime, timedelta

from database.models import Base, TemperatureReading, DeviceStatus
from config.config import config
from utils.logger import logger
from utils.time_utils import BOLIVIA_TZ


class DatabaseManager:
    """Gestor centralizado de base de datos"""

    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._initialized = False

    def initialize(self):
        """Inicializa la conexión a la base de datos"""
        try:
            logger.info(f"Conectando a MySQL: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")

            # Crear engine con pool de conexiones
            self.engine = create_engine(
                config.DATABASE_URL,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verifica conexión antes de usar
                pool_recycle=3600,  # Recicla conexiones cada hora
                echo=False  # No mostrar SQL queries
            )

            # Crear todas las tablas si no existen
            Base.metadata.create_all(self.engine)
            logger.success("Tablas de base de datos creadas/verificadas")

            # Crear session factory
            self.session_factory = scoped_session(sessionmaker(bind=self.engine))

            self._initialized = True
            logger.success("Base de datos inicializada correctamente")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error al inicializar base de datos: {e}")
            return False

    @contextmanager
    def get_session(self):
        """Context manager para obtener una sesión de BD"""
        if not self._initialized:
            raise RuntimeError("DatabaseManager no inicializado")

        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error en sesión de BD: {e}")
            raise
        finally:
            session.close()

    # ==================== TEMPERATURE READINGS ====================

    def save_temperature_reading(self, device_id, temperature, pressure=None, altitude=None, rssi=None,
                                 recorded_at=None):
        """
        Guarda una lectura de temperatura en la base de datos.

        Args:
            device_id: ID del dispositivo
            temperature: Temperatura en °C
            pressure: Presión en Pa (opcional)
            altitude: Altitud en m (opcional)
            rssi: Señal WiFi en dBm (opcional)
            recorded_at: Datetime de la lectura (si None, usa hora actual)

        Returns:
            TemperatureReading: El objeto guardado o None si falla
        """
        try:
            if recorded_at is None:
                recorded_at = datetime.now(BOLIVIA_TZ)

            with self.get_session() as session:
                reading = TemperatureReading(
                    device_id=device_id,
                    temperature=temperature,
                    pressure=pressure,
                    altitude=altitude,
                    rssi=rssi,
                    recorded_at=recorded_at
                )

                session.add(reading)
                session.commit()

                logger.info(f"Lectura guardada: {temperature}°C a las {recorded_at.strftime('%H:%M:%S')}")
                return reading

        except SQLAlchemyError as e:
            logger.error(f"Error al guardar lectura: {e}")
            return None

    def get_readings_by_date_range(self, device_id, start_date, end_date):
        """
        Obtiene lecturas en un rango de fechas.

        Args:
            device_id: ID del dispositivo
            start_date: Fecha/hora inicio
            end_date: Fecha/hora fin

        Returns:
            List[TemperatureReading]: Lista de lecturas
        """
        try:
            with self.get_session() as session:
                readings = session.query(TemperatureReading).filter(
                    and_(
                        TemperatureReading.device_id == device_id,
                        TemperatureReading.recorded_at >= start_date,
                        TemperatureReading.recorded_at <= end_date
                    )
                ).order_by(TemperatureReading.recorded_at.desc()).all()

                return readings

        except SQLAlchemyError as e:
            logger.error(f"Error al obtener lecturas: {e}")
            return []

    def get_latest_readings(self, device_id, limit=50):
        """
        Obtiene las últimas N lecturas de un dispositivo.

        Args:
            device_id: ID del dispositivo
            limit: Cantidad máxima de lecturas

        Returns:
            List[TemperatureReading]: Lista de lecturas
        """
        try:
            with self.get_session() as session:
                readings = session.query(TemperatureReading).filter(
                    TemperatureReading.device_id == device_id
                ).order_by(TemperatureReading.recorded_at.desc()).limit(limit).all()

                return readings

        except SQLAlchemyError as e:
            logger.error(f"Error al obtener últimas lecturas: {e}")
            return []

    def get_total_readings_count(self, device_id):
        """Obtiene el total de lecturas guardadas para un dispositivo"""
        try:
            with self.get_session() as session:
                count = session.query(func.count(TemperatureReading.id)).filter(
                    TemperatureReading.device_id == device_id
                ).scalar()

                return count or 0

        except SQLAlchemyError as e:
            logger.error(f"Error al contar lecturas: {e}")
            return 0

    # ==================== DEVICE STATUS ====================

    def update_device_heartbeat(self, device_id, timestamp=None):
        """
        Actualiza el heartbeat de un dispositivo.

        Args:
            device_id: ID del dispositivo
            timestamp: Datetime del heartbeat (si None, usa hora actual)
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(BOLIVIA_TZ)

            with self.get_session() as session:
                device = session.query(DeviceStatus).filter(
                    DeviceStatus.device_id == device_id
                ).first()

                if device is None:
                    # Crear nuevo registro
                    device = DeviceStatus(
                        device_id=device_id,
                        is_online=True,
                        last_heartbeat=timestamp
                    )
                    session.add(device)
                else:
                    # Actualizar existente
                    device.is_online = True
                    device.last_heartbeat = timestamp

                session.commit()

        except SQLAlchemyError as e:
            logger.error(f"Error al actualizar heartbeat: {e}")

    def update_device_data(self, device_id, temperature, pressure=None, altitude=None, rssi=None, timestamp=None):
        """
        Actualiza los datos del dispositivo (última lectura conocida).

        Args:
            device_id: ID del dispositivo
            temperature: Temperatura en °C
            pressure: Presión en Pa (opcional)
            altitude: Altitud en m (opcional)
            rssi: Señal WiFi en dBm (opcional)
            timestamp: Datetime de la lectura (si None, usa hora actual)
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(BOLIVIA_TZ)

            with self.get_session() as session:
                device = session.query(DeviceStatus).filter(
                    DeviceStatus.device_id == device_id
                ).first()

                if device is None:
                    # Crear nuevo registro
                    device = DeviceStatus(
                        device_id=device_id,
                        is_online=True,
                        last_data_received=timestamp,
                        last_temperature=temperature,
                        last_pressure=pressure,
                        last_altitude=altitude,
                        last_rssi=rssi,
                        total_readings=1
                    )
                    session.add(device)
                else:
                    # Actualizar existente
                    device.is_online = True
                    device.last_data_received = timestamp
                    device.last_temperature = temperature
                    device.last_pressure = pressure
                    device.last_altitude = altitude
                    device.last_rssi = rssi
                    device.total_readings += 1

                session.commit()

        except SQLAlchemyError as e:
            logger.error(f"Error al actualizar datos del dispositivo: {e}")

    def set_device_offline(self, device_id):
        """Marca un dispositivo como offline"""
        try:
            with self.get_session() as session:
                device = session.query(DeviceStatus).filter(
                    DeviceStatus.device_id == device_id
                ).first()

                if device:
                    device.is_online = False
                    session.commit()
                    logger.warning(f"Dispositivo {device_id} marcado como OFFLINE")

        except SQLAlchemyError as e:
            logger.error(f"Error al marcar dispositivo offline: {e}")

    def get_device_status(self, device_id):
        """
        Obtiene el estado actual de un dispositivo.

        Returns:
            DeviceStatus: El objeto de estado o None si no existe
        """
        try:
            with self.get_session() as session:
                device = session.query(DeviceStatus).filter(
                    DeviceStatus.device_id == device_id
                ).first()

                return device

        except SQLAlchemyError as e:
            logger.error(f"Error al obtener estado del dispositivo: {e}")
            return None

    def close(self):
        """Cierra las conexiones a la base de datos"""
        if self.session_factory:
            self.session_factory.remove()

        if self.engine:
            self.engine.dispose()

        logger.info("Conexiones de base de datos cerradas")


# Instancia global del gestor
db_manager = DatabaseManager()