"""
Modelos de base de datos usando SQLAlchemy
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class TemperatureReading(Base):
    """
    Modelo para almacenar lecturas de temperatura cada hora.
    """
    __tablename__ = 'temperature_readings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(50), nullable=False, index=True)

    # Datos del sensor
    temperature = Column(Float, nullable=False)
    pressure = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    rssi = Column(Integer, nullable=True)

    # Timestamps
    recorded_at = Column(DateTime, nullable=False, index=True)  # Hora en Bolivia
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return (f"<TemperatureReading(id={self.id}, device='{self.device_id}', "
                f"temp={self.temperature}°C, at={self.recorded_at})>")

    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'temperature': round(self.temperature, 2),
            'pressure': round(self.pressure, 2) if self.pressure else None,
            'altitude': round(self.altitude, 2) if self.altitude else None,
            'rssi': self.rssi,
            'recorded_at': self.recorded_at.strftime('%Y-%m-%d %H:%M:%S') if self.recorded_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class DeviceStatus(Base):
    """
    Modelo para rastrear el estado actual de cada dispositivo.
    Se actualiza con cada heartbeat y lectura.
    """
    __tablename__ = 'device_status'

    device_id = Column(String(50), primary_key=True)

    # Estado de conexión
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, nullable=True)
    last_data_received = Column(DateTime, nullable=True)

    # Estadísticas
    total_readings = Column(Integer, default=0)

    # Última lectura conocida
    last_temperature = Column(Float, nullable=True)
    last_pressure = Column(Float, nullable=True)
    last_altitude = Column(Float, nullable=True)
    last_rssi = Column(Integer, nullable=True)

    # Timestamp de actualización
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        status = "ONLINE" if self.is_online else "OFFLINE"
        return f"<DeviceStatus(device='{self.device_id}', status={status}, temp={self.last_temperature}°C)>"

    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'device_id': self.device_id,
            'is_online': self.is_online,
            'last_heartbeat': self.last_heartbeat.strftime('%Y-%m-%d %H:%M:%S') if self.last_heartbeat else None,
            'last_data_received': self.last_data_received.strftime(
                '%Y-%m-%d %H:%M:%S') if self.last_data_received else None,
            'total_readings': self.total_readings,
            'last_temperature': round(self.last_temperature, 2) if self.last_temperature else None,
            'last_pressure': round(self.last_pressure, 2) if self.last_pressure else None,
            'last_altitude': round(self.last_altitude, 2) if self.last_altitude else None,
            'last_rssi': self.last_rssi,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }