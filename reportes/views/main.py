from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
import json

from reportes.selectors import (
    get_kpis, 
    get_datos_financieros, 
    get_datos_ocupacion,
    get_ranking_peliculas_performance,
    get_ranking_horarios_dia,
    get_ranking_salas,
    get_dashboard_alertas,
    get_ranking_revpas,
    get_ranking_dia_revenue,
    get_analisis_franjas_horarias
)
from reportes.utils import (
    parse_date_range_from_request,
    get_quick_range_querystrings,
    is_system_admin
)
from reportes.config import config


@login_required
def reporte_financiero_view(request):
    if not is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')

    # Parsear rango de fechas usando utilidad centralizada
    start_dt, end_dt, fecha_inicio_final, fecha_fin_final = parse_date_range_from_request(request)
    
    # Obtener querystrings para botones de rango rápido
    quick_ranges = get_quick_range_querystrings()

    kpis = get_kpis(start_dt, end_dt)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=config.LIMIT_DEFAULT)
    # Métricas avanzadas (moved to ocupacion view)
    
    # Agregar rankings financieros para el dashboard web
    ranking_revpas = get_ranking_revpas(start_dt, end_dt)
    ranking_dia_revenue = get_ranking_dia_revenue(start_dt, end_dt)  # Ya viene ordenado por revenue descendente
    analisis_franjas = get_analisis_franjas_horarias(start_dt, end_dt)

    context = {
        'kpis': kpis,
        'fin_data': fin_data,
        'fecha_inicio': fecha_inicio_final,
        'fecha_fin': fecha_fin_final,
        **quick_ranges,
        'fin_chart_json': json.dumps({
            'labels': fin_data['labels'],
            'values': fin_data['data_full']
        }),
        # Rankings financieros
        'ranking_revpas': ranking_revpas,
        'ranking_dia_revenue': ranking_dia_revenue,  # Ya ordenado en selector
        'analisis_franjas': analisis_franjas,
    }

    return render(request, 'reportes/financiero.html', context)


@login_required
def reporte_ocupacion_view(request):
    if not is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')

    # Parsear rango de fechas usando utilidad centralizada
    start_dt, end_dt, fecha_inicio_final, fecha_fin_final = parse_date_range_from_request(request)
    
    # Obtener querystrings para botones de rango rápido
    quick_ranges = get_quick_range_querystrings()

    # Determinar si filtrar por días específicos (rangos cortos)
    dias_diferencia = (end_dt.date() - start_dt.date()).days
    filtrar_dias = dias_diferencia <= config.FILTRO_DIAS_THRESHOLD

    # Ocupación y horarios SE FILTRAN por días cuando el rango es corto
    occ_data = get_datos_ocupacion(start_dt, end_dt, filtrar_dias=filtrar_dias)
    ranking_horarios = get_ranking_horarios_dia(start_dt, end_dt, filtrar_dias=filtrar_dias)

    # Métricas avanzadas para la vista de ocupación: heatmap y marketing
    from reportes.selectors import get_ocupacion_por_franja_horaria, get_metricas_marketing
    heatmap = get_ocupacion_por_franja_horaria(start_dt, end_dt)
    marketing = get_metricas_marketing(start_dt, end_dt)
    labels = heatmap.get('labels', []) or []
    grid = heatmap.get('grid', []) or []
    # If heatmap data is missing, provide a sensible default (Lunes..Domingo with 0%)
    if not labels or not grid:
        labels = config.DIAS_SEMANA_ES
        grid = [[0, 0, 0] for _ in labels]
    heatmap_rows = list(zip(labels, grid))
    marketing_json = json.dumps(marketing.get('donut', {}))
    
    # Películas, salas y alertas SIEMPRE usan el rango completo (NO se filtran por día)
    dashboard_alertas = get_dashboard_alertas(start_dt, end_dt)
    ranking_peliculas = get_ranking_peliculas_performance(start_dt, end_dt)
    ranking_salas = get_ranking_salas(start_dt, end_dt)

    context = {
        'occ_data': occ_data,
        'heatmap': heatmap,
        'heatmap_rows': heatmap_rows,
        'marketing': marketing,
        'marketing_json': marketing_json,
        'fecha_inicio': fecha_inicio_final,
        'fecha_fin': fecha_fin_final,
        **quick_ranges,
        'occ_chart_json': json.dumps({
            'labels': occ_data['labels'],
            'values': occ_data['data']
        }),
        # Rankings operacionales
        'dashboard_alertas': dashboard_alertas,
        'ranking_peliculas': ranking_peliculas,
        'ranking_horarios': ranking_horarios,
        'ranking_salas': ranking_salas,
    }

    return render(request, 'reportes/ocupacion.html', context)


__all__ = ["reporte_financiero_view", "reporte_ocupacion_view"]
