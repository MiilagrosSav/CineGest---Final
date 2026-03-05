"""
Utilidades compartidas para el módulo de reportes.
"""
from django.utils import timezone
from datetime import datetime, time, timedelta
import calendar


def parse_date_range_from_request(request):
    """
    Parsea rango de fechas desde request.GET params.
    
    Parámetros GET esperados:
        - fecha_inicio (str): Formato YYYY-MM-DD
        - fecha_fin (str): Formato YYYY-MM-DD
    
    Returns:
        tuple: (start_dt, end_dt, fecha_inicio_str, fecha_fin_str)
            - start_dt (datetime): Inicio del rango (timezone-aware, time.min)
            - end_dt (datetime): Fin del rango (timezone-aware, time.max)
            - fecha_inicio_str (str): Fecha inicio en formato ISO
            - fecha_fin_str (str): Fecha fin en formato ISO
    
    Default: Últimos N días (configurado en reportes.config.DEFAULT_DAYS)
    """
    from reportes.config import config
    
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    
    now = timezone.now()
    default_start_dt = now - timedelta(days=config.DEFAULT_DAYS)
    default_end_dt = now
    
    # Helper para hacer timezone-aware
    def _make_aware_if_naive(dt):
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    
    # Parse fecha inicio
    try:
        if fecha_inicio_str:
            parsed_date = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            start_dt = datetime.combine(parsed_date, time.min)
        else:
            start_dt = datetime.combine(default_start_dt.date(), time.min)
    except (ValueError, TypeError):
        start_dt = datetime.combine(default_start_dt.date(), time.min)
    
    # Parse fecha fin
    try:
        if fecha_fin_str:
            parsed_date = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            end_dt = datetime.combine(parsed_date, time.max)
        else:
            end_dt = datetime.combine(default_end_dt.date(), time.max)
    except (ValueError, TypeError):
        end_dt = datetime.combine(default_end_dt.date(), time.max)
    
    # Convertir a timezone-aware
    start_dt = _make_aware_if_naive(start_dt)
    end_dt = _make_aware_if_naive(end_dt)
    
    # Retornar strings para template
    fecha_inicio_final = fecha_inicio_str or start_dt.date().isoformat()
    fecha_fin_final = fecha_fin_str or end_dt.date().isoformat()
    
    return start_dt, end_dt, fecha_inicio_final, fecha_fin_final


def get_quick_range_querystrings():
    """
    Genera querystrings para botones de rango rápido.
    
    Returns:
        dict: {
            'rango_7_qs': "?fecha_inicio=...&fecha_fin=...",
            'rango_30_qs': "?fecha_inicio=...&fecha_fin=...",
            'rango_mes_qs': "?fecha_inicio=...&fecha_fin=..."
        }
    """
    now = timezone.now()
    now_date = now.date()
    
    # Últimos 7 días
    rango_7_start = (now - timedelta(days=7)).date().isoformat()
    rango_7_end = now_date.isoformat()
    
    # Últimos 30 días
    rango_30_start = (now - timedelta(days=30)).date().isoformat()
    rango_30_end = now_date.isoformat()
    
    # Mes actual completo
    first_day_month = now_date.replace(day=1).isoformat()
    last_day_num = calendar.monthrange(now_date.year, now_date.month)[1]
    last_day_month = now_date.replace(day=last_day_num).isoformat()
    
    return {
        'rango_7_qs': f"?fecha_inicio={rango_7_start}&fecha_fin={rango_7_end}",
        'rango_30_qs': f"?fecha_inicio={rango_30_start}&fecha_fin={rango_30_end}",
        'rango_mes_qs': f"?fecha_inicio={first_day_month}&fecha_fin={last_day_month}",
    }


def is_system_admin(user):
    """
    Verifica si el usuario es administrador del sistema.
    
    Args:
        user: Usuario de Django
    
    Returns:
        bool: True si es admin del sistema o superusuario
    """
    return getattr(user, 'rol', None) == 'admin' or getattr(user, 'is_superuser', False)
