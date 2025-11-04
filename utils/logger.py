"""
Sistema de logging con loguru
"""
import sys
from pathlib import Path
from loguru import logger
from config.config import config

# Crear directorio de logs si no existe
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

# Remover handler por defecto
logger.remove()

# Handler para consola (con colores)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=config.LOG_LEVEL,
    colorize=True
)

# Handler para archivo (con rotación)
logger.add(
    config.LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=config.LOG_LEVEL,
    rotation=config.LOG_ROTATION,
    retention=config.LOG_RETENTION,
    compression="zip",
    encoding="utf-8"
)

# Exportar logger configurado
__all__ = ['logger']