"""
Selectores de datos para reportes.
Contienen toda la lógica de consultas ORM reutilizable para dashboard web y exportaciones.
"""
from django.db.models import Sum, Count, Q, F, Value
from django.db.models.functions import Coalesce, ExtractWeekDay
from django.db import models
from decimal import Decimal

from cine.models import Pelicula, Funcion
from ventas.models import Entrada


def get_kpis(start_dt, end_dt):
    """
    Calcula KPIs globales: total_recaudacion, total_tickets, ticket_promedio.
    
    Args:
        start_dt (datetime): fecha/hora de inicio (aware)
        end_dt (datetime): fecha/hora de fin (aware)
    
    Returns:
        dict: {'total_recaudacion': float, 'total_tickets': int, 'ticket_promedio': float}
    """
    totals = Entrada.objects.filter(
        id_funcion__fecha_hora__range=(start_dt, end_dt)
    ).aggregate(
        total_recaudacion=Coalesce(
            Sum('id_funcion__precio_base'),
            Value(Decimal('0.00')),
            output_field=models.DecimalField(max_digits=14, decimal_places=2)
        ),
        total_tickets=Coalesce(Count('id_entrada'), Value(0)),
    )

    total_recaudacion = totals.get('total_recaudacion') or Decimal('0.00')
    total_tickets = totals.get('total_tickets') or 0

    if total_tickets:
        ticket_promedio = (total_recaudacion / Decimal(total_tickets))
    else:
        ticket_promedio = Decimal('0.00')

    return {
        'total_recaudacion': float(total_recaudacion),
        'total_tickets': int(total_tickets),
        'ticket_promedio': float(round(ticket_promedio, 2)),
    }


def get_datos_financieros(start_dt, end_dt, limit=10):
    """
    Obtiene ingresos por película (top N) en el rango de fechas.
    
    Args:
        start_dt (datetime): fecha/hora de inicio (aware)
        end_dt (datetime): fecha/hora de fin (aware)
        limit (int): número máximo de películas a retornar
    
    Returns:
        dict: {
            'labels': [str],  # títulos de películas
            'data_full': [float],  # ingresos precio full (actualmente = total)
            'data_promo': [float],  # ingresos con promo (actualmente cero)
            'detalle': [{'titulo': str, 'total': float, 'full': float, 'promo': float}]
        }
    """
    entradas_fin_qs = (
        Entrada.objects
        .filter(id_funcion__fecha_hora__range=(start_dt, end_dt))
        .values('id_pelicula__titulo')
        .annotate(
            total_recaudacion=Coalesce(
                Sum('id_funcion__precio_base'),
                Value(Decimal('0.00')),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        )
        .order_by('-total_recaudacion')[:limit]
    )

    labels = []
    data_full = []
    data_promo = []
    detalle = []

    for item in entradas_fin_qs:
        titulo = item.get('id_pelicula__titulo') or 'Sin título'
        total = float(item.get('total_recaudacion') or 0)
        labels.append(titulo[:60])
        data_full.append(total)
        data_promo.append(0.0)
        detalle.append({
            'titulo': titulo,
            'total': total,
            'full': total,
            'promo': 0.0
        })

    return {
        'labels': labels,
        'data_full': data_full,
        'data_promo': data_promo,
        'detalle': detalle
    }


def get_datos_ocupacion(start_dt, end_dt):
    """
    Calcula ocupación semanal (% por día de la semana Lunes-Domingo).
    
    Args:
        start_dt (datetime): fecha/hora de inicio (aware)
        end_dt (datetime): fecha/hora de fin (aware)
    
    Returns:
        dict: {
            'labels': [str],  # nombres de días en español
            'data': [float],  # porcentaje ocupación por día
            'detalle': [{'dia': str, 'tickets': int, 'capacidad': int, 'porcentaje': float}]
        }
    """
    # Tickets por weekday
    tickets_by_weekday_qs = (
        Entrada.objects
        .filter(id_funcion__fecha_hora__range=(start_dt, end_dt))
        .annotate(weekday=ExtractWeekDay('id_funcion__fecha_hora'))
        .values('weekday')
        .annotate(tickets=Coalesce(Count('id_entrada'), Value(0)))
    )
    tickets_map = {item['weekday']: item['tickets'] for item in tickets_by_weekday_qs}

    # Capacidad por weekday: suma de butacas no-pasillo de funciones en el rango
    capacity_by_weekday_qs = (
        Funcion.objects
        .filter(fecha_hora__range=(start_dt, end_dt))
        .annotate(weekday=ExtractWeekDay('fecha_hora'))
        .values('weekday')
        .annotate(
            total_capacity=Coalesce(
                Count('sala__butacas', filter=Q(sala__butacas__es_pasillo=False)),
                Value(0)
            )
        )
    )
    capacity_map = {item['weekday']: item['total_capacity'] for item in capacity_by_weekday_qs}

    # ExtractWeekDay: Sunday=1, Monday=2, ...
    # Queremos Lunes-Domingo
    spanish_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    weekday_numbers_monday_start = [2, 3, 4, 5, 6, 7, 1]

    labels = []
    data = []
    detalle = []

    for num, name in zip(weekday_numbers_monday_start, spanish_days):
        tickets = tickets_map.get(num, 0) or 0
        capacity = capacity_map.get(num, 0) or 0
        if capacity:
            pct = float(Decimal(tickets) / Decimal(capacity) * Decimal(100))
        else:
            pct = 0.0
        labels.append(name)
        data.append(round(pct, 2))
        detalle.append({
            'dia': name,
            'tickets': tickets,
            'capacidad': capacity,
            'porcentaje': round(pct, 2)
        })

    return {
        'labels': labels,
        'data': data,
        'detalle': detalle
    }
