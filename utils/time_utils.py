"""
Utilidades para manejo de tiempo y zona horaria
"""
from datetime import datetime, timedelta
import pytz
from config.config import config

# Zona horaria de Bolivia
BOLIVIA_TZ = pytz.timezone(config.TIMEZONE)


def get_bolivia_now():
    """Obtiene la hora actual en zona horaria de Bolivia"""
    return datetime.now(BOLIVIA_TZ)


def get_bolivia_today_start():
    """Obtiene el inicio del día actual en Bolivia (00:00:00)"""
    now = get_bolivia_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_bolivia_today_end():
    """Obtiene el fin del día actual en Bolivia (23:59:59)"""
    now = get_bolivia_now()
    return now.replace(hour=23, minute=59, second=59, microsecond=999999)


def is_on_the_hour():
    """
    Verifica si estamos exactamente en el minuto 00 de alguna hora.
    Retorna True solo si minute == 0 y second < 5 (ventana de 5 segundos)
    """
    now = get_bolivia_now()
    return now.minute == 0 and now.second < 5


def should_save_reading(last_save_time):
    """
    Determina si debemos guardar una lectura en la base de datos.

    Criterios:
    - Estamos en el minuto :00 de alguna hora
    - Ha pasado al menos 1 hora desde el último guardado

    Args:
        last_save_time: datetime del último guardado (o None si nunca se guardó)

    Returns:
        bool: True si debemos guardar
    """
    if not is_on_the_hour():
        return False

    if last_save_time is None:
        return True

    now = get_bolivia_now()
    time_diff = (now - last_save_time).total_seconds()

    # Debe haber pasado al menos 59 minutos (usamos 59 en vez de 60 por margen)
    return time_diff >= 3540  # 59 minutos en segundos


def format_datetime(dt):
    """Formatea un datetime para mostrar en UI"""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_time_ago(dt):
    """
    Formatea cuánto tiempo ha pasado desde un datetime.
    Ej: "hace 3 segundos", "hace 2 minutos"
    """
    if dt is None:
        return "Nunca"

    now = get_bolivia_now()

    # Asegurar que dt tenga zona horaria
    if dt.tzinfo is None:
        dt = BOLIVIA_TZ.localize(dt)

    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return "En el futuro"
    elif seconds < 60:
        return f"hace {seconds} segundo{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"hace {minutes} minuto{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"hace {hours} hora{'s' if hours != 1 else ''}"
    else:
        days = seconds // 86400
        return f"hace {days} día{'s' if days != 1 else ''}"


def parse_datetime(dt_string):
    """
    Parsea un string de fecha/hora a datetime con zona horaria Bolivia
    Formatos soportados:
    - "2025-11-04 15:30:00"
    - "2025-11-04"
    """
    try:
        if len(dt_string) == 10:  # Solo fecha
            dt = datetime.strptime(dt_string, "%Y-%m-%d")
        else:
            dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")

        return BOLIVIA_TZ.localize(dt)
    except Exception:
        return None


def get_hour_ranges_for_day(date):
    """
    Genera una lista de rangos horarios para un día específico.
    Útil para mostrar datos por hora.

    Args:
        date: datetime del día

    Returns:
        List[tuple]: Lista de (hora_inicio, hora_fin) para cada hora del día
    """
    if date.tzinfo is None:
        date = BOLIVIA_TZ.localize(date)

    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    ranges = []

    for hour in range(24):
        start = day_start + timedelta(hours=hour)
        end = start + timedelta(hours=1) - timedelta(microseconds=1)
        ranges.append((start, end))

    return ranges