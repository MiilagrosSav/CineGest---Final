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
from ventas.models.venta import Venta
from ventas.models.pago import Pago
from ventas.constants import EstadoEntrada  # Importar constantes para filtrar bien
from promociones.models.cuponGenerado import CuponGenerado
from django.db.models import Sum

def get_kpis(start_dt, end_dt):
    """
    Calcula KPIs globales: total_recaudacion, total_tickets, ticket_promedio.
    """
    totals = Entrada.objects.filter(
        id_funcion__fecha_hora__range=(start_dt, end_dt),
        estado__in=[EstadoEntrada.VENDIDA, EstadoEntrada.USADA, EstadoEntrada.RESERVADA] # Filtrar solo válidas
    ).aggregate(
        total_recaudacion=Coalesce(
            Sum('id_funcion__precio_base'), # O precio_final si lo guardas en la entrada/venta
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
    Obtiene ingresos por película (top N).
    """
    # Para evitar conteos duplicados por joins entre entradas y pagos, agrupamos por Venta
    ventas_qs = (
        Venta.objects
        .filter(entradas__id_funcion__fecha_hora__range=(start_dt, end_dt))
        .distinct()
        .prefetch_related('entradas__id_funcion__pelicula', 'pago')
    )

    # Acumular por título de película
    accum = {}
    for venta in ventas_qs:
        # considerar solo entradas de la venta cuya función esté en el rango
        entradas_validas = [e for e in venta.entradas.all() if start_dt <= e.id_funcion.fecha_hora <= end_dt and e.estado in [EstadoEntrada.VENDIDA, EstadoEntrada.USADA, EstadoEntrada.RESERVADA]]
        if not entradas_validas:
            continue

        # Determinar título (tomamos la primera entrada como representante)
        titulo = (entradas_validas[0].id_pelicula.titulo or 'Sin título')[:60]

        # Suma full = sum(precio_base) de esas entradas
        total_full = sum([float(e.id_funcion.precio_base or 0) for e in entradas_validas])

        # Capacidad ofertada por la película en esas funciones (sumar capacidad por función una sola vez)
        funciones_unicas = {e.id_funcion.pk: e.id_funcion for e in entradas_validas}
        capacidad_total = 0.0
        for f in funciones_unicas.values():
            try:
                capacidad_total += float(getattr(f.sala, 'capacidad_total', 0) or 0)
            except Exception:
                pass

        # Monto pagado: preferir el Pago asociado, sino usar el total calculado de la venta
        monto_pagado = 0.0
        try:
            pago = getattr(venta, 'pago', None)
            if pago and getattr(pago, 'monto', None) is not None:
                monto_pagado = float(pago.monto)
            else:
                # fallback: calcular a partir de la venta (sin request)
                monto_pagado = float(venta.calcular_total())
        except Exception:
            monto_pagado = float(venta.calcular_total() or 0)

        # Acumular (incluimos capacidad para calcular RevPAS)
        if titulo not in accum:
            accum[titulo] = {'full': 0.0, 'paid': 0.0, 'capacity': 0.0}
        accum[titulo]['full'] += total_full
        accum[titulo]['paid'] += monto_pagado
        accum[titulo]['capacity'] += capacidad_total

    # Convertir a lista ordenada por ingresos pagados (descendente)
    items = []
    for titulo, vals in accum.items():
        total_paid = vals['paid']
        total_full = vals['full']
        total_capacity = vals.get('capacity', 0.0)
        promo = max(0.0, total_full - total_paid)
        # RevPAS: ingreso promedio por butaca ofertada
        revpas = (total_paid / total_capacity) if total_capacity and total_capacity > 0 else 0.0
        items.append({'titulo': titulo, 'paid': total_paid, 'full': total_full, 'promo': promo, 'revpas': revpas})

    items.sort(key=lambda x: x['paid'], reverse=True)
    items = items[:limit]

    labels = [it['titulo'] for it in items]
    data_full = [round(it['full'], 2) for it in items]
    data_promo = [round(it['promo'], 2) for it in items]
    detalle = [{'titulo': it['titulo'], 'total': round(it['paid'], 2), 'full': round(it['full'], 2), 'promo': round(it['promo'], 2), 'revpas': round(it.get('revpas', 0.0), 2)} for it in items]

    return {
        'labels': labels,
        'data_full': data_full,
        'data_promo': data_promo,
        'detalle': detalle
    }


def get_datos_ocupacion(start_dt, end_dt):
    """
    Calcula ocupación semanal (% por día de la semana Lunes-Domingo).
    """
    # 1. Demanda (Tickets Vendidos)
    tickets_by_weekday_qs = (
        Entrada.objects
        .filter(
            id_funcion__fecha_hora__range=(start_dt, end_dt),
            estado__in=[EstadoEntrada.VENDIDA, EstadoEntrada.USADA, EstadoEntrada.RESERVADA]
        )
        .annotate(weekday=ExtractWeekDay('id_funcion__fecha_hora'))
        .values('weekday')
        .annotate(tickets=Coalesce(Count('id_entrada'), Value(0)))
    )
    tickets_map = {item['weekday']: item['tickets'] for item in tickets_by_weekday_qs}

    # 2. Oferta (Capacidad Total Ofertada)
    # CORRECCIÓN CLAVE: Usamos Sum('sala__capacidad_total')
    capacity_by_weekday_qs = (
        Funcion.objects
        .filter(fecha_hora__range=(start_dt, end_dt))
        .annotate(weekday=ExtractWeekDay('fecha_hora'))
        .values('weekday')
        .annotate(
            total_capacity=Coalesce(
                Sum('sala__capacidad_total'), # <--- ¡AQUÍ ESTÁ LA MAGIA!
                Value(0)
            )
        )
    )
    capacity_map = {item['weekday']: item['total_capacity'] for item in capacity_by_weekday_qs}

    # Mapeo de días (Django: 1=Domingo... 7=Sábado) -> Queremos orden Lunes a Domingo
    spanish_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    weekday_numbers_monday_start = [2, 3, 4, 5, 6, 7, 1]

    labels = []
    data = []
    detalle = []

    for num, name in zip(weekday_numbers_monday_start, spanish_days):
        tickets = tickets_map.get(num, 0) or 0
        capacity = capacity_map.get(num, 0) or 0
        
        if capacity > 0:
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


def get_ocupacion_por_franja_horaria(start_dt, end_dt):
    """
    Devuelve ocupación por franja horaria y por día de la semana.

    Franjas:
      - matiné: hora < 16
      - tarde: 16 <= hora <= 20
      - noche: hora > 20

    Retorna dict con keys: 'labels' (dias Lunes..Domingo), 'franjas' (['Matiné','Tarde','Noche']),
    y 'grid' como lista de filas (por día) con porcentajes [matine,tarde,noche].
    """
    from django.db.models.functions import ExtractWeekDay, ExtractHour

    # Inicializar map para tickets y capacidad por (weekday, franja)
    tickets_map = {}
    capacity_map = {}

    entradas_qs = (
        Entrada.objects
        .filter(
            id_funcion__fecha_hora__range=(start_dt, end_dt),
            estado__in=[EstadoEntrada.VENDIDA, EstadoEntrada.USADA, EstadoEntrada.RESERVADA]
        )
        .select_related('id_funcion__sala')
    )

    for e in entradas_qs:
        fh = e.id_funcion.fecha_hora
        weekday = fh.weekday()  # 0=Monday
        hour = fh.time().hour
        if hour < 16:
            fr = 'Matiné'
        elif 16 <= hour <= 20:
            fr = 'Tarde'
        else:
            fr = 'Noche'

        key = (weekday, fr)
        tickets_map[key] = tickets_map.get(key, 0) + 1

    # Calcular capacidad ofertada por funciones en rango, por franja
    funciones = (
        Funcion.objects
        .filter(fecha_hora__range=(start_dt, end_dt))
        .select_related('sala')
    )

    for f in funciones:
        weekday = f.fecha_hora.weekday()
        hour = f.fecha_hora.time().hour
        if hour < 16:
            fr = 'Matiné'
        elif 16 <= hour <= 20:
            fr = 'Tarde'
        else:
            fr = 'Noche'

        key = (weekday, fr)
        try:
            cap = float(getattr(f.sala, 'capacidad_total', 0) or 0)
        except Exception:
            cap = 0.0
        capacity_map[key] = capacity_map.get(key, 0.0) + cap

    spanish_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    franjas = ['Matiné', 'Tarde', 'Noche']

    grid = []
    labels = []
    for i, name in enumerate(spanish_days):
        labels.append(name)
        row = []
        for fr in franjas:
            key = (i, fr)
            tickets = tickets_map.get(key, 0)
            cap = capacity_map.get(key, 0.0)
            if cap and cap > 0:
                pct = float(Decimal(tickets) / Decimal(cap) * Decimal(100))
            else:
                pct = 0.0
            row.append(round(pct, 2))
        grid.append(row)

    return {'labels': labels, 'franjas': franjas, 'grid': grid}


def get_metricas_marketing(start_dt, end_dt):
    """
    Métricas de marketing relacionadas a cupones: enviados, canjeados y tasa.
    """
    qs = CuponGenerado.objects.filter(creado_en__range=(start_dt, end_dt))
    total_enviados = qs.count()
    total_canjeados = qs.filter(usado=True).count()
    tasa = (total_canjeados / total_enviados * 100) if total_enviados else 0.0

    # Datos para Doughnut chart (Ignorados vs Canjeados)
    donut = {
        'labels': ['Ignorados', 'Canjeados'],
        'data': [total_enviados - total_canjeados, total_canjeados]
    }

    return {
        'total_enviados': total_enviados,
        'total_canjeados': total_canjeados,
        'tasa_conversion': round(tasa, 2),
        'donut': donut
    }