"""
Selectores de datos para reportes.
Contienen toda la lógica de consultas ORM reutilizable para dashboard web y exportaciones.
"""
from django.db.models import Sum, Count, Q, F, Value, Avg, ExpressionWrapper, FloatField, DecimalField
from django.db.models.functions import Coalesce, ExtractWeekDay, Cast, ExtractHour, ExtractMinute
from django.db import models
from decimal import Decimal

from cine.models import Pelicula, Funcion, Sala
from ventas.models import Entrada
from ventas.models.venta import Venta
from ventas.models.pago import Pago
from ventas.constants import EstadoEntrada
from promociones.models.cuponGenerado import CuponGenerado
from reportes.config import config

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

        # Acumular (incluimos capacidad para calcular RevPAS y tickets vendidos)
        if titulo not in accum:
            accum[titulo] = {'full': 0.0, 'paid': 0.0, 'capacity': 0.0, 'tickets': 0}
        accum[titulo]['full'] += total_full
        accum[titulo]['paid'] += monto_pagado
        accum[titulo]['capacity'] += capacidad_total
        accum[titulo]['tickets'] += len(entradas_validas)

    # Convertir a lista ordenada por ingresos pagados (descendente)
    items = []
    for titulo, vals in accum.items():
        total_paid = vals['paid']
        total_full = vals['full']
        total_capacity = vals.get('capacity', 0.0)
        total_tickets = vals.get('tickets', 0)
        promo = max(0.0, total_full - total_paid)
        # RevPAS: ingreso promedio por butaca ofertada
        revpas = (total_paid / total_capacity) if total_capacity and total_capacity > 0 else 0.0
        items.append({'titulo': titulo, 'paid': total_paid, 'full': total_full, 'promo': promo, 'revpas': revpas, 'tickets': total_tickets})

    items.sort(key=lambda x: x['paid'], reverse=True)
    items = items[:limit]

    labels = [it['titulo'] for it in items]
    data_full = [round(it['full'], 2) for it in items]
    data_promo = [round(it['promo'], 2) for it in items]
    detalle = [
        {
            'titulo': it['titulo'], 
            'total': round(it['paid'], 2), 
            'full': round(it['full'], 2), 
            'promo': round(it['promo'], 2), 
            'revpas': round(it.get('revpas', 0.0), 2), 
            'tickets': it.get('tickets', 0),
            'ticket_promedio': round(it['paid'] / it['tickets'], 2) if it.get('tickets', 0) > 0 else 0.0
        } 
        for it in items
    ]

    return {
        'labels': labels,
        'data_full': data_full,
        'data_promo': data_promo,
        'detalle': detalle
    }


def get_datos_ocupacion(start_dt, end_dt, filtrar_dias=False):
    """
    Calcula ocupación semanal (% por día de la semana Lunes-Domingo).
    
    Args:
        start_dt: datetime de inicio
        end_dt: datetime de fin
        filtrar_dias: Si True, solo incluye días que existen en el rango de fechas.
                      Si False, incluye todos los días de la semana con 0% si no hay datos.
    """
    # Calcular qué días de la semana existen en el rango
    dias_en_rango = set()
    if filtrar_dias:
        from datetime import timedelta
        current = start_dt.date()
        end_date = end_dt.date()
        while current <= end_date:
            # Django weekday: 1=Domingo, 2=Lunes, ..., 7=Sábado
            weekday_num = (current.isoweekday() % 7) + 1
            dias_en_rango.add(weekday_num)
            current += timedelta(days=1)
    
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
    spanish_days = config.DIAS_SEMANA_ES
    weekday_numbers_monday_start = config.WEEKDAY_NUMBERS_MONDAY_START

    labels = []
    data = []
    detalle = []

    for num, name in zip(weekday_numbers_monday_start, spanish_days):
        # Si filtrar_dias está activo y este día no está en el rango, omitir
        if filtrar_dias and num not in dias_en_rango:
            continue
            
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

    spanish_days = config.DIAS_SEMANA_ES
    franjas = config.FRANJAS_HORARIAS

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


def get_ranking_peliculas_performance(fecha_inicio, fecha_fin):
    """
    Retorna ranking de películas ordenadas por índice de performance.
    
    Performance = (Ocupación × 0.6) + (Revenue normalizado × 0.4)
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        
    Returns:
        Lista de diccionarios con:
        - titulo_pelicula (str)
        - total_entradas (int)
        - total_capacidad (int)
        - ocupacion_promedio (float) # Porcentaje
        - revenue_total (Decimal)
        - indice_performance (int) # 0-100
        - rating (str) # 'EXCELENTE', 'BUENO', 'REGULAR', 'MALO'
    """
    # Query optimizada: obtener funciones con annotate para contar entradas válidas
    funciones_qs = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).select_related('pelicula', 'sala').annotate(
        num_entradas_validas=Count(
            'entradas',
            filter=Q(entradas__estado__in=[
                EstadoEntrada.VENDIDA, 
                EstadoEntrada.USADA, 
                EstadoEntrada.RESERVADA
            ])
        )
    ).values(
        'pelicula__id',
        'pelicula__titulo',
        'sala__capacidad_total',
        'precio_base',
        'num_entradas_validas'
    )
    
    # Diccionario para acumular datos por película
    peliculas_data = {}
    
    for funcion in funciones_qs:
        pelicula_id = funcion['pelicula__id']
        titulo = funcion['pelicula__titulo'] or 'Sin título'
        
        # Inicializar película si no existe
        if pelicula_id not in peliculas_data:
            peliculas_data[pelicula_id] = {
                'titulo': titulo,
                'total_entradas': 0,
                'total_capacidad': 0,
                'revenue_total': Decimal('0.00')
            }
        
        # Sumar capacidad de la sala de esta función
        capacidad_sala = funcion['sala__capacidad_total'] or 0
        peliculas_data[pelicula_id]['total_capacidad'] += capacidad_sala
        
        # Sumar entradas válidas de esta función (ya contadas por annotate)
        num_entradas = funcion['num_entradas_validas'] or 0
        peliculas_data[pelicula_id]['total_entradas'] += num_entradas
        
        # Sumar revenue (precio_base * número de entradas)
        precio_base = funcion['precio_base'] or Decimal('0.00')
        peliculas_data[pelicula_id]['revenue_total'] += (precio_base * num_entradas)
    
    # Convertir a lista y calcular métricas
    peliculas_list = []
    max_revenue = Decimal('0.00')
    
    # Primero encontrar el revenue máximo para normalización
    for data in peliculas_data.values():
        if data['revenue_total'] > max_revenue:
            max_revenue = data['revenue_total']
    
    # Calcular performance para cada película
    for data in peliculas_data.values():
        total_entradas = data['total_entradas']
        total_capacidad = data['total_capacidad']
        revenue_total = data['revenue_total']
        
        # Calcular ocupación promedio
        if total_capacidad > 0:
            ocupacion_promedio = float((Decimal(total_entradas) / Decimal(total_capacidad)) * Decimal('100'))
        else:
            ocupacion_promedio = 0.0
        
        # Normalizar revenue (0-100)
        if max_revenue > 0:
            revenue_normalizado = float((revenue_total / max_revenue) * Decimal('100'))
        else:
            revenue_normalizado = 0.0
        
        # Calcular índice de performance: (Ocupación × 0.6) + (Revenue normalizado × 0.4)
        indice_performance = int(round((ocupacion_promedio * 0.6) + (revenue_normalizado * 0.4)))
        
        # Determinar rating
        thresholds = config.PERFORMANCE_RATING_THRESHOLDS
        if indice_performance >= thresholds['EXCELENTE']:
            rating = 'EXCELENTE'
        elif indice_performance >= thresholds['BUENO']:
            rating = 'BUENO'
        elif indice_performance >= thresholds['REGULAR']:
            rating = 'REGULAR'
        else:
            rating = 'MALO'
        
        peliculas_list.append({
            'titulo_pelicula': data['titulo'],
            'total_entradas': total_entradas,
            'total_capacidad': total_capacidad,
            'ocupacion_promedio': round(ocupacion_promedio, 2),
            'revenue_total': float(revenue_total),
            'indice_performance': indice_performance,
            'rating': rating
        })
    
    # Ordenar por índice de performance (descendente)
    peliculas_list.sort(key=lambda x: x['indice_performance'], reverse=True)
    
    return peliculas_list


def get_ranking_horarios_dia(fecha_inicio, fecha_fin, filtrar_dias=False):
    """
    Calcula ocupación REAL, asientos libres y mejores/peores horarios por día.
    
    MATEMÁTICA CORRECTA:
    - Ocupación Real = (Total Entradas Vendidas / Total Capacidad Ofrecida) * 100
    - Asientos Libres = 100 - Ocupación Real
    - Mejor/Peor Horario = Horarios con mayor/menor ocupación
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        filtrar_dias: Si True, solo incluye días que existen en el rango de fechas.
        
    Returns:
        Lista de diccionarios (uno por día) con:
        - dia_nombre (str)
        - mejor_horario (str)
        - peor_horario (str)
        - ocupacion_real (float)
        - asientos_libres (float)
        - recomendacion (str)
    """
    # Calcular qué días de la semana existen en el rango
    dias_en_rango = set()
    if filtrar_dias:
        from datetime import timedelta
        current = fecha_inicio.date() if hasattr(fecha_inicio, 'date') else fecha_inicio
        end_date = fecha_fin.date() if hasattr(fecha_fin, 'date') else fecha_fin
        while current <= end_date:
            weekday_num = (current.isoweekday() % 7) + 1
            dias_en_rango.add(weekday_num)
            current += timedelta(days=1)
    
    # Obtener funciones agrupadas por día y horario
    funciones_qs = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).annotate(
        dia_semana=ExtractWeekDay('fecha_hora'),
        hora=ExtractHour('fecha_hora'),
        minuto=ExtractMinute('fecha_hora')
    ).values('dia_semana', 'hora', 'minuto').annotate(
        capacidad_total=Sum('sala__capacidad_total'),
        entradas_vendidas=Count(
            'entradas',
            filter=Q(entradas__estado__in=[
                EstadoEntrada.VENDIDA,
                EstadoEntrada.USADA,
                EstadoEntrada.RESERVADA
            ])
        )
    )
    
    # Organizar datos por día de la semana
    dias_data = {}
    for funcion in funciones_qs:
        dia_num = funcion['dia_semana']
        hora = funcion['hora']
        minuto = funcion['minuto']
        horario = f"{hora:02d}:{minuto:02d}"
        
        capacidad = funcion['capacidad_total'] or 0
        entradas = funcion['entradas_vendidas'] or 0
        
        # Calcular ocupación
        if capacidad > 0:
            ocupacion = float((Decimal(entradas) / Decimal(capacidad)) * Decimal(100))
        else:
            ocupacion = 0.0
        
        # Inicializar día si no existe
        if dia_num not in dias_data:
            dias_data[dia_num] = {'horarios': {}, 'capacidad_total': 0, 'entradas_total': 0}
        
        # Agregar datos del horario
        if horario not in dias_data[dia_num]['horarios']:
            dias_data[dia_num]['horarios'][horario] = {
                'capacidad': capacidad,
                'entradas': entradas,
                'ocupacion': ocupacion
            }
        else:
            # Acumular si hay múltiples funciones en el mismo horario
            dias_data[dia_num]['horarios'][horario]['capacidad'] += capacidad
            dias_data[dia_num]['horarios'][horario]['entradas'] += entradas
            cap_total = dias_data[dia_num]['horarios'][horario]['capacidad']
            ent_total = dias_data[dia_num]['horarios'][horario]['entradas']
            if cap_total > 0:
                dias_data[dia_num]['horarios'][horario]['ocupacion'] = float((Decimal(ent_total) / Decimal(cap_total)) * Decimal(100))
        
        # Acumular totales del día
        dias_data[dia_num]['capacidad_total'] += capacidad
        dias_data[dia_num]['entradas_total'] += entradas
    
    # Mapeo de días
    spanish_days = config.DIAS_SEMANA_ES
    weekday_numbers_monday_start = config.WEEKDAY_NUMBERS_MONDAY_START
    
    resultado = []
    
    for num, name in zip(weekday_numbers_monday_start, spanish_days):
        # Si filtrar_dias está activo y este día no está en el rango, omitir
        if filtrar_dias and num not in dias_en_rango:
            continue
            
        if num in dias_data and len(dias_data[num]['horarios']) > 0:
            # Hay datos para este día
            data = dias_data[num]
            horarios = data['horarios']
            capacidad_total = data['capacidad_total']
            entradas_total = data['entradas_total']
            
            # Encontrar mejor y peor horario
            mejor_horario = None
            mejor_ocupacion_horario = -1.0
            peor_horario = None
            peor_ocupacion_horario = float('inf')
            
            for horario, horario_data in horarios.items():
                ocupacion = horario_data['ocupacion']
                
                if ocupacion > mejor_ocupacion_horario:
                    mejor_ocupacion_horario = ocupacion
                    mejor_horario = horario
                
                if ocupacion < peor_ocupacion_horario:
                    peor_ocupacion_horario = ocupacion
                    peor_horario = horario
            
            # CÁLCULO CORRECTO: Ocupación Real del DÍA (no promedio de horarios)
            if capacidad_total > 0:
                ocupacion_real = float((Decimal(entradas_total) / Decimal(capacidad_total)) * Decimal(100))
            else:
                ocupacion_real = 0.0
            
            # CÁLCULO CORRECTO: Asientos Libres = 100 - Ocupación
            asientos_libres = 100.0 - ocupacion_real
            
            # Generar recomendación basada en asientos libres
            if asientos_libres > 70:
                recomendacion = f"ALERTA CRÍTICA: {asientos_libres:.1f}% de capacidad desaprovechada"
            elif asientos_libres > 50:
                recomendacion = f"Alerta: Baja ocupación ({ocupacion_real:.1f}%), {asientos_libres:.1f}% libre"
            elif asientos_libres > 30:
                recomendacion = f"Moderado: {ocupacion_real:.1f}% ocupación, margen de mejora"
            else:
                recomendacion = f"Éxito: Buena ocupación ({ocupacion_real:.1f}%)"
            
            resultado.append({
                'dia_nombre': name,
                'mejor_horario': mejor_horario,
                'peor_horario': peor_horario,
                'ocupacion_real': round(ocupacion_real, 1),
                'asientos_libres': round(asientos_libres, 1),
                'recomendacion': recomendacion
            })
        else:
            # No hay datos para este día
            if not filtrar_dias:
                resultado.append({
                    'dia_nombre': name,
                    'mejor_horario': 'Sin datos',
                    'peor_horario': 'Sin datos',
                    'ocupacion_real': 0.0,
                    'asientos_libres': 100.0,
                    'recomendacion': 'Sin funciones programadas'
                })
    
    return resultado


def get_dashboard_alertas(fecha_inicio, fecha_fin):
    """
    Genera un dashboard de alertas con métricas clave y recomendaciones automáticas.
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        
    Returns:
        Diccionario con:
        - ocupacion_global (float): Porcentaje de ocupación global
        - capacidad_desperdiciada (float): Porcentaje de capacidad no utilizada
        - status (str): 'CRITICO', 'BAJO', 'NORMAL', 'BUENO'
        - total_funciones (int): Total de funciones en el período
        - total_peliculas (int): Total de películas únicas en cartelera
        - ticket_promedio (float): Precio promedio por ticket (de get_kpis)
        - recomendaciones (list): Lista de strings con recomendaciones automáticas
    """
    # 1. Calcular métricas de ocupación
    # Obtener total de entradas válidas
    total_entradas = Entrada.objects.filter(
        id_funcion__fecha_hora__range=(fecha_inicio, fecha_fin),
        estado__in=[EstadoEntrada.VENDIDA, EstadoEntrada.USADA, EstadoEntrada.RESERVADA]
    ).count()
    
    # Obtener capacidad total ofertada
    capacidad_total_agg = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).aggregate(
        capacidad_total=Coalesce(Sum('sala__capacidad_total'), Value(0))
    )
    capacidad_total = capacidad_total_agg['capacidad_total'] or 0
    
    # Calcular ocupación global
    if capacidad_total > 0:
        ocupacion_global = float((Decimal(total_entradas) / Decimal(capacidad_total)) * Decimal(100))
    else:
        ocupacion_global = 0.0
    
    # Calcular capacidad desperdiciada
    capacidad_desperdiciada = 100.0 - ocupacion_global
    
    # 2. Determinar status según umbrales
    if ocupacion_global < 5:
        status = 'CRITICO'
    elif ocupacion_global < 20:
        status = 'BAJO'
    elif ocupacion_global < 40:
        status = 'NORMAL'
    else:
        status = 'BUENO'
    
    # 3. Contar funciones y películas
    total_funciones = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).count()
    
    total_peliculas = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).values('pelicula').distinct().count()
    
    # 4. Obtener ticket_promedio de get_kpis
    kpis = get_kpis(fecha_inicio, fecha_fin)
    ticket_promedio = kpis.get('ticket_promedio', 0.0)
    
    # 5. Generar recomendaciones automáticas
    recomendaciones = []
    
    # CRÍTICO: ocupación < 5%
    if ocupacion_global < 5:
        recomendaciones.append('🚨 CRÍTICO: Reducir funciones entre 40-60% inmediatamente')
        recomendaciones.append('🎟️ URGENTE: Implementar promociones 2×1 en horarios de bajo rendimiento')
        recomendaciones.append('📢 Intensificar campañas de marketing digital con inversión adicional')
    
    # WARNING: ocupación < 10%
    if ocupacion_global < 10:
        recomendaciones.append('⚠️ WARNING: Ocupación muy baja - revisar cartelera de películas')
        recomendaciones.append('💰 Considerar descuentos progresivos (15-25% según horario)')
    
    # Capacidad excesiva: desperdicio > 90%
    if capacidad_desperdiciada > 90:
        recomendaciones.append('📊 Capacidad excesiva: Considerar cerrar salas con menor demanda')
        recomendaciones.append('🔄 Consolidar funciones en salas más pequeñas')
    
    # NORMAL: ocupación entre 20-40%
    if 20 <= ocupacion_global < 40:
        recomendaciones.append('💡 Optimizar distribución: Ajustar horarios según análisis de franjas')
        recomendaciones.append('🎯 Implementar promociones segmentadas por día de la semana')
        recomendaciones.append('📱 Aumentar presencia en redes sociales y marketing de contenido')
    
    # BUENO: ocupación >= 40%
    if ocupacion_global >= 40:
        recomendaciones.append('✅ Excelente desempeño: Mantener estrategia actual')
        recomendaciones.append('📈 Considerar agregar funciones en horarios pico identificados')
        if ocupacion_global >= 60:
            recomendaciones.append('🌟 Ocupación óptima: Evaluar incremento de precios en funciones premium')
    
    # Recomendación si hay pocas películas en cartelera
    if total_peliculas < 3:
        recomendaciones.append('🎬 Diversificar cartelera: Agregar más opciones cinematográficas')
    
    # Si no hay recomendaciones, agregar mensaje genérico
    if not recomendaciones:
        recomendaciones.append('📊 Monitorear métricas semanalmente para identificar tendencias')
    
    return {
        'ocupacion_global': round(ocupacion_global, 2),
        'capacidad_desperdiciada': round(capacidad_desperdiciada, 2),
        'status': status,
        'total_funciones': total_funciones,
        'total_peliculas': total_peliculas,
        'ticket_promedio': ticket_promedio,
        'recomendaciones': recomendaciones
    }


def get_ranking_revpas(fecha_inicio, fecha_fin):
    """
    Calcula revenue por asiento disponible (no solo vendido).
    RevPAS = Revenue Total / Capacidad Total Ofrecida
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        
    Returns:
        Lista ordenada por RevPAS descendente con:
        - titulo_pelicula (str)
        - revenue_total (float)
        - capacidad_total (int)
        - entradas_vendidas (int)
        - revpas (float)
        - rating (str) # 'EXCELENTE' (≥$0.40), 'BUENO' (≥$0.25), 'REGULAR' (≥$0.15), 'MALO' (<$0.15)
    """
    # Query optimizada: agrupar por película usando annotate
    funciones_qs = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).select_related('pelicula', 'sala').annotate(
        num_entradas_validas=Count(
            'entradas',
            filter=Q(entradas__estado__in=[
                EstadoEntrada.VENDIDA,
                EstadoEntrada.USADA,
                EstadoEntrada.RESERVADA
            ])
        )
    ).values(
        'pelicula__id',
        'pelicula__titulo',
        'sala__capacidad_total',
        'precio_base',
        'num_entradas_validas'
    )
    
    # Acumular datos por película
    peliculas_data = {}
    
    for funcion in funciones_qs:
        pelicula_id = funcion['pelicula__id']
        titulo = funcion['pelicula__titulo'] or 'Sin título'
        
        if pelicula_id not in peliculas_data:
            peliculas_data[pelicula_id] = {
                'titulo': titulo,
                'revenue_total': Decimal('0.00'),
                'capacidad_total': 0,
                'entradas_vendidas': 0
            }
        
        # Sumar capacidad de la sala
        capacidad_sala = funcion['sala__capacidad_total'] or 0
        peliculas_data[pelicula_id]['capacidad_total'] += capacidad_sala
        
        # Sumar entradas vendidas
        num_entradas = funcion['num_entradas_validas'] or 0
        peliculas_data[pelicula_id]['entradas_vendidas'] += num_entradas
        
        # Sumar revenue (precio_base * número de entradas)
        precio_base = funcion['precio_base'] or Decimal('0.00')
        peliculas_data[pelicula_id]['revenue_total'] += (precio_base * num_entradas)
    
    # Convertir a lista y calcular RevPAS
    resultado = []
    
    for data in peliculas_data.values():
        revenue_total = float(data['revenue_total'])
        capacidad_total = data['capacidad_total']
        entradas_vendidas = data['entradas_vendidas']
        
        # Calcular RevPAS
        if capacidad_total > 0:
            revpas = revenue_total / capacidad_total
        else:
            revpas = 0.0
        
        # Determinar rating según umbrales
        thresholds = config.REVPAS_RATING_THRESHOLDS
        if revpas >= thresholds['EXCELENTE']:
            rating = 'EXCELENTE'
        elif revpas >= thresholds['BUENO']:
            rating = 'BUENO'
        elif revpas >= thresholds['REGULAR']:
            rating = 'REGULAR'
        else:
            rating = 'MALO'
        
        resultado.append({
            'titulo_pelicula': data['titulo'],
            'revenue_total': round(revenue_total, 2),
            'capacidad_total': capacidad_total,
            'entradas_vendidas': entradas_vendidas,
            'revpas': round(revpas, 2),
            'rating': rating
        })
    
    # Ordenar por RevPAS descendente
    resultado.sort(key=lambda x: x['revpas'], reverse=True)
    
    return resultado


def get_ranking_dia_revenue(fecha_inicio, fecha_fin, order_by='revenue_total', order_dir='desc'):
    """
    Analiza revenue por día de la semana.
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        order_by: str - Campo por el cual ordenar ('revenue_total', 'total_tickets', 'indice', etc.)
        order_dir: str - Dirección de ordenamiento ('asc' o 'desc')
        
    Returns:
        Lista ordenada con elementos (máximo 7 para Lunes-Domingo) con:
        - dia_nombre (str)
        - total_tickets (int)
        - revenue_total (float)
        - precio_promedio (float)
        - porcentaje_revenue_total (float) # Del revenue total del período
        - indice (int) # Normalizado 0-100, mejor día = 100
        
    Por defecto retorna ordenado por revenue_total descendente.
    """
    # Obtener revenue y tickets por día de la semana usando annotate
    entradas_qs = Entrada.objects.filter(
        id_funcion__fecha_hora__range=(fecha_inicio, fecha_fin),
        estado__in=[EstadoEntrada.VENDIDA, EstadoEntrada.USADA, EstadoEntrada.RESERVADA]
    ).annotate(
        dia_semana=ExtractWeekDay('id_funcion__fecha_hora')
    ).values('dia_semana').annotate(
        total_tickets=Count('id_entrada'),
        revenue_total=Coalesce(
            Sum('id_funcion__precio_base'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )
    
    # Crear mapa de datos por día
    datos_por_dia = {}
    revenue_total_periodo = Decimal('0.00')
    
    for item in entradas_qs:
        dia_num = item['dia_semana']
        tickets = item['total_tickets'] or 0
        revenue = item['revenue_total'] or Decimal('0.00')
        
        datos_por_dia[dia_num] = {
            'tickets': tickets,
            'revenue': float(revenue)
        }
        revenue_total_periodo += revenue
    
    # Mapeo de días (Django: 1=Domingo, 2=Lunes, ... 7=Sábado)
    spanish_days = config.DIAS_SEMANA_ES
    weekday_numbers_monday_start = config.WEEKDAY_NUMBERS_MONDAY_START
    
    # Construir resultado con todos los días
    resultado = []
    max_revenue = 0.0
    
    # Primera pasada: recopilar datos y encontrar máximo
    for num, name in zip(weekday_numbers_monday_start, spanish_days):
        if num in datos_por_dia:
            data = datos_por_dia[num]
            tickets = data['tickets']
            revenue = data['revenue']
        else:
            tickets = 0
            revenue = 0.0
        
        if revenue > max_revenue:
            max_revenue = revenue
        
        # Calcular precio promedio
        if tickets > 0:
            precio_promedio = revenue / tickets
        else:
            precio_promedio = 0.0
        
        # Calcular porcentaje del total
        if float(revenue_total_periodo) > 0:
            porcentaje_revenue = (revenue / float(revenue_total_periodo)) * 100
        else:
            porcentaje_revenue = 0.0
        
        resultado.append({
            'dia_nombre': name,
            'total_tickets': tickets,
            'revenue_total': round(revenue, 2),
            'precio_promedio': round(precio_promedio, 2),
            'porcentaje_revenue_total': round(porcentaje_revenue, 2),
            'indice': 0  # Se calculará en la segunda pasada
        })
    
    # Segunda pasada: calcular índice normalizado
    for item in resultado:
        if max_revenue > 0:
            item['indice'] = int(round((item['revenue_total'] / max_revenue) * 100))
        else:
            item['indice'] = 0
    
    # Filtrar días sin datos (revenue_total = 0)
    resultado_con_datos = [item for item in resultado if item['revenue_total'] > 0]
    
    # Aplicar ordenamiento antes de retornar
    reverse_order = (order_dir.lower() == 'desc')
    
    # Validar que el campo existe en los datos
    valid_fields = ['dia_nombre', 'total_tickets', 'revenue_total', 'precio_promedio', 'porcentaje_revenue_total', 'indice']
    if order_by not in valid_fields:
        order_by = 'revenue_total'  # Fallback seguro
    
    resultado_ordenado = sorted(
        resultado_con_datos, 
        key=lambda x: x.get(order_by, 0), 
        reverse=reverse_order
    )
    
    return resultado_ordenado


def get_analisis_franjas_horarias(fecha_inicio, fecha_fin):
    """
    Analiza aprovechamiento por hora exacta (NO franjas predefinidas).
    Agrupa por hora de inicio de funciones (ExtractHour).
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        
    Returns:
        Lista ordenada por hora con:
        - hora (str) # Formato 'HH:00' ej: '14:00', '20:00'
        - total_funciones (int)
        - capacidad_total (int)
        - entradas_vendidas (int)
        - ocupacion (float) # Porcentaje
        - desperdicio (float) # Porcentaje
        - recomendacion (str) # Automática según umbrales
    """
    # Agrupar funciones por hora usando annotate
    funciones_qs = Funcion.objects.filter(
        fecha_hora__range=(fecha_inicio, fecha_fin)
    ).annotate(
        hora_inicio=ExtractHour('fecha_hora')
    ).values('hora_inicio').annotate(
        total_funciones=Count('id'),
        capacidad_total=Coalesce(Sum('sala__capacidad_total'), Value(0)),
        entradas_vendidas=Count(
            'entradas',
            filter=Q(entradas__estado__in=[
                EstadoEntrada.VENDIDA,
                EstadoEntrada.USADA,
                EstadoEntrada.RESERVADA
            ])
        )
    )
    
    # Convertir a lista y calcular métricas
    resultado = []
    
    for item in funciones_qs:
        hora = item['hora_inicio']
        total_funciones = item['total_funciones'] or 0
        capacidad_total = item['capacidad_total'] or 0
        entradas_vendidas = item['entradas_vendidas'] or 0
        
        # Calcular ocupación
        if capacidad_total > 0:
            ocupacion = float((Decimal(entradas_vendidas) / Decimal(capacidad_total)) * Decimal(100))
        else:
            ocupacion = 0.0
        
        # Calcular desperdicio
        desperdicio = 100.0 - ocupacion
        
        # Generar recomendación según umbrales
        if desperdicio > 95 and ocupacion < 2:
            recomendacion = "🔴 ELIMINAR - Ocupación crítica"
        elif desperdicio > 90:
            recomendacion = "⚠️ Reducir cantidad de funciones"
        elif desperdicio > 80:
            recomendacion = "💡 Optimizar programación"
        elif desperdicio > 60:
            recomendacion = "✅ Aprovechamiento moderado"
        else:
            recomendacion = "✅ Buen aprovechamiento"
        
        resultado.append({
            'hora': f"{hora:02d}:00",
            'total_funciones': total_funciones,
            'capacidad_total': capacidad_total,
            'entradas_vendidas': entradas_vendidas,
            'ocupacion': round(ocupacion, 2),
            'desperdicio': round(desperdicio, 2),
            'recomendacion': recomendacion
        })
    
    # Ordenar por hora
    resultado.sort(key=lambda x: x['hora'])
    
    return resultado


def get_ranking_salas(fecha_inicio, fecha_fin):
    """
    Ranking de salas ordenadas por porcentaje de ocupación promedio.
    
    Args:
        fecha_inicio: datetime
        fecha_fin: datetime
        
    Returns:
        Lista de diccionarios ordenada por ocupacion_promedio descendente:
        - nombre_sala (str)         # Ej: 'Sala Premium A'
        - numero_sala (int)         # Número de sala
        - capacidad_total (int)     # Butacas de la sala
        - total_funciones (int)     # Funciones realizadas en el período
        - butacas_ofrecidas (int)   # capacidad_total × total_funciones
        - butacas_ocupadas (int)    # Entradas vendidas/usadas/reservadas
        - ocupacion_promedio (float) # Porcentaje sobre butacas_ofrecidas
        - evaluacion (str)          # 'Bien aprovechada', 'Aprovechamiento moderado', 'Subutilizada'
    """
    # Query optimizada con annotate (evitar N+1)
    salas_qs = Sala.objects.filter(
        funciones__fecha_hora__range=(fecha_inicio, fecha_fin)
    ).annotate(
        total_funciones=Count('funciones', distinct=True),
        butacas_ocupadas=Count(
            'funciones__entradas',
            filter=Q(funciones__entradas__estado__in=[
                EstadoEntrada.VENDIDA,
                EstadoEntrada.USADA,
                EstadoEntrada.RESERVADA
            ]),
            distinct=True  # Evita contar la misma entrada dos veces si hay JOINs múltiples
        )
    ).values('id', 'nombre', 'numero', 'capacidad_total', 'total_funciones', 'butacas_ocupadas')
    
    # Procesar datos y calcular métricas
    resultado = []
    
    for sala in salas_qs:
        nombre_sala = sala['nombre'] or f"Sala {sala['numero']}"
        numero_sala = sala['numero']
        capacidad_total = sala['capacidad_total'] or 0
        total_funciones = sala['total_funciones'] or 0
        butacas_ocupadas = sala['butacas_ocupadas'] or 0
        
        # Calcular butacas ofrecidas (capacidad × funciones)
        butacas_ofrecidas = capacidad_total * total_funciones
        
        # Calcular ocupación promedio
        if butacas_ofrecidas > 0:
            ocupacion_promedio = float((Decimal(butacas_ocupadas) / Decimal(butacas_ofrecidas)) * Decimal(100))
        else:
            ocupacion_promedio = 0.0
        
        # Evaluación según ocupación
        if ocupacion_promedio >= 40:
            evaluacion = 'Bien aprovechada'
        elif ocupacion_promedio >= 15:
            evaluacion = 'Aprovechamiento moderado'
        else:
            evaluacion = 'Subutilizada'
        
        resultado.append({
            'nombre': nombre_sala,  # Cambio: usar 'nombre' en lugar de 'nombre_sala' para consistencia con template
            'numero': numero_sala,  # Cambio: usar 'numero' en lugar de 'numero_sala'
            'capacidad_total': capacidad_total,
            'total_funciones': total_funciones,
            'butacas_ofrecidas': butacas_ofrecidas,
            'butacas_ocupadas': butacas_ocupadas,
            'ocupacion_promedio': round(ocupacion_promedio, 2),
            'evaluacion': evaluacion
        })
    
    # Ordenar por ocupacion_promedio descendente
    resultado.sort(key=lambda x: x['ocupacion_promedio'], reverse=True)
    
    return resultado


def aplicar_ordenamiento_tabla(datos, tipo_tabla, columna_idx, direccion='desc'):
    """
    Aplica ordenamiento dinámico a tablas de reportes.
    
    Args:
        datos: Lista de diccionarios con datos de la tabla
        tipo_tabla: str - Tipo de tabla ('revpas', 'dia_revenue', 'peliculas', 'horarios', 'salas', 'detalle_peliculas', 'ocupacion_detalle')
        columna_idx: str - Índice de columna a ordenar (como string '0', '1', etc.)
        direccion: str - 'asc' o 'desc'
    
    Returns:
        Lista ordenada según parámetros
    """
    if not datos:
        return datos
    
    # Mapeos de columnas por tipo de tabla
    mapeos = {
        'revpas': {
            '0': lambda x: x.get('titulo_pelicula', ''),
            '1': lambda x: x.get('entradas_vendidas', 0),
            '2': lambda x: x.get('capacidad_total', 0),
            '3': lambda x: x.get('revenue_total', 0),
            '4': lambda x: x.get('revpas', 0),
            '5': lambda x: x.get('rating', '')
        },
        'dia_revenue': {
            '0': lambda x: config.DIAS_SEMANA_ES.index(x.get('dia_nombre', '')) if x.get('dia_nombre', '') in config.DIAS_SEMANA_ES else 999,
            '1': lambda x: x.get('total_tickets', 0),
            '2': lambda x: x.get('precio_promedio', 0),
            '3': lambda x: x.get('revenue_total', 0),
            '4': lambda x: x.get('porcentaje_revenue_total', 0),
            '5': lambda x: x.get('indice', 0)
        },
        'peliculas': {
            '0': lambda x: x.get('_original_index', 0),
            '1': lambda x: x.get('titulo_pelicula', ''),
            '2': lambda x: x.get('ocupacion_promedio', 0),
            '3': lambda x: x.get('revenue_total', 0),
            '4': lambda x: x.get('indice_performance', 0),
            '5': lambda x: x.get('rating', ''),
            '6': lambda x: x.get('total_entradas', 0)
        },
        'horarios': {
            '0': lambda x: config.DIAS_SEMANA_ES.index(x.get('dia_nombre', '')) if x.get('dia_nombre', '') in config.DIAS_SEMANA_ES else 999,
            '1': lambda x: x.get('mejor_horario', ''),
            '2': lambda x: x.get('peor_horario', ''),
            '3': lambda x: x.get('ocupacion_real', 0),
            '4': lambda x: x.get('asientos_libres', 0),
            '5': lambda x: x.get('recomendacion', '')
        },
        'salas': {
            '0': lambda x: x.get('_original_index', 0),
            '1': lambda x: x.get('nombre', ''),
            '2': lambda x: x.get('capacidad_total', 0),
            '3': lambda x: x.get('total_funciones', 0),
            '4': lambda x: x.get('butacas_ofrecidas', 0),
            '5': lambda x: x.get('butacas_ocupadas', 0),
            '6': lambda x: x.get('ocupacion_promedio', 0),
            '7': lambda x: x.get('evaluacion', '')
        },
        'detalle_peliculas': {
            '0': lambda x: x.get('titulo', ''),
            '1': lambda x: x.get('tickets', 0),
            '2': lambda x: x.get('ticket_promedio', 0),
            '3': lambda x: x.get('total', 0),
            '4': lambda x: x.get('full', 0),
            '5': lambda x: x.get('promo', 0),
            '6': lambda x: x.get('revpas', 0)
        },
        'ocupacion_detalle': {
            '0': lambda x: config.DIAS_SEMANA_ES.index(x.get('dia', '')) if x.get('dia', '') in config.DIAS_SEMANA_ES else 999,
            '1': lambda x: x.get('tickets', 0),
            '2': lambda x: x.get('capacidad', 0),
            '3': lambda x: x.get('porcentaje', 0)
        }
    }
    
    # Validar tipo de tabla
    if tipo_tabla not in mapeos:
        return datos
    
    col_map = mapeos[tipo_tabla]
    
    # Validar columna
    if columna_idx not in col_map:
        return datos
    
    # Aplicar ordenamiento
    reverse_order = (direccion.lower() == 'desc')
    
    return sorted(
        datos,
        key=col_map[columna_idx],
        reverse=reverse_order
    )