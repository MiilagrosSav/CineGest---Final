"""
Utilidades compartidas para el módulo de reportes.
"""
from django.utils import timezone
from datetime import datetime, time, timedelta
import calendar
from urllib.parse import urlencode


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


def parse_report_filters_from_request(request):
    """
    Parsea filtros opcionales de reportes desde request.GET.

    Returns:
        dict: Filtros normalizados listos para aplicar en consultas.
    """
    filters = {
        'empleado': (request.GET.get('empleado') or '').strip(),
        'tipo_venta': (request.GET.get('tipo_venta') or '').strip(),
        'sala': (request.GET.get('sala') or '').strip(),
        'pelicula': (request.GET.get('pelicula') or '').strip(),
        'pelicula_busqueda': (request.GET.get('pelicula_busqueda') or '').strip(),
        'metodo_pago': (request.GET.get('metodo_pago') or '').strip(),
        'estado_venta': (request.GET.get('estado_venta') or '').strip(),
        'estado_pago': (request.GET.get('estado_pago') or '').strip(),
    }

    # Normalizar IDs numéricos para evitar valores inválidos en ORM.
    for numeric_key in ('empleado', 'sala', 'metodo_pago'):
        value = filters.get(numeric_key)
        if not value:
            continue
        if value == 'sin_empleado' and numeric_key == 'empleado':
            continue
        try:
            filters[numeric_key] = str(int(value))
        except (TypeError, ValueError):
            filters[numeric_key] = ''

    # Limpiar tipo_venta a opciones conocidas.
    if filters['tipo_venta'] not in ('ONLINE', 'PRESENCIAL', ''):
        filters['tipo_venta'] = ''

    # Soportar filtro antiguo por ID de película solo si es numérico.
    pelicula_id = filters.get('pelicula')
    if pelicula_id:
        try:
            filters['pelicula'] = str(int(pelicula_id))
        except (TypeError, ValueError):
            filters['pelicula'] = ''

    # Validar búsqueda de película: requiere al menos 1 caracter alfanumérico.
    pelicula_busqueda = filters.get('pelicula_busqueda', '')
    if pelicula_busqueda and not any(ch.isalnum() for ch in pelicula_busqueda):
        filters['pelicula_busqueda'] = ''

    return filters


def get_quick_range_querystrings(extra_params=None):
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
    
    base_params = {}
    if extra_params:
        base_params = {
            k: v for k, v in extra_params.items()
            if v not in (None, '', []) and k not in ('fecha_inicio', 'fecha_fin')
        }

    def _build_qs(fecha_inicio, fecha_fin):
        params = {'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin, **base_params}
        return f"?{urlencode(params)}"

    return {
        'rango_7_qs': _build_qs(rango_7_start, rango_7_end),
        'rango_30_qs': _build_qs(rango_30_start, rango_30_end),
        'rango_mes_qs': _build_qs(first_day_month, last_day_month),
    }


def get_report_filters_summary(filters):
    """Construye un resumen legible de filtros activos para mostrar en el PDF."""
    labels = {
        'empleado': 'Empleado',
        'tipo_venta': 'Tipo venta',
        'sala': 'Sala',
        'pelicula': 'Película',
        'pelicula_busqueda': 'Película contiene',
        'metodo_pago': 'Método pago',
        'estado_venta': 'Estado venta',
        'estado_pago': 'Estado pago',
    }
    def _resolve_value(key, value):
        if key == 'empleado':
            if value == 'sin_empleado':
                return 'Sin empleado'
            try:
                from accounts.models import Empleado
                emp = Empleado.objects.select_related('usuario').filter(usuario_id=int(value)).first()
                if emp:
                    return emp.usuario.get_full_name() or emp.usuario.username
            except Exception:
                pass
        if key == 'sala':
            try:
                from cine.models import Sala
                sala = Sala.objects.filter(id=int(value)).first()
                if sala:
                    return sala.nombre
            except Exception:
                pass
        if key == 'pelicula':
            try:
                from cine.models import Pelicula
                peli = Pelicula.objects.filter(id=int(value)).first()
                if peli:
                    return peli.titulo
            except Exception:
                pass
        if key == 'metodo_pago':
            try:
                from ventas.models import MetodoPago
                metodo = MetodoPago.objects.filter(id_metodo_pago=int(value)).first()
                if metodo:
                    return metodo.nombre
            except Exception:
                pass
        return value

    items = []
    for key, value in (filters or {}).items():
        if value in (None, ''):
            continue
        items.append(f"{labels.get(key, key)}: {_resolve_value(key, value)}")
    return ' | '.join(items) if items else 'Sin filtros adicionales'


def is_system_admin(user):
    """
    Verifica si el usuario es administrador del sistema.
    
    Args:
        user: Usuario de Django
    
    Returns:
        bool: True si es admin del sistema o superusuario
    """
    return getattr(user, 'rol', None) == 'admin' or getattr(user, 'is_superuser', False)
