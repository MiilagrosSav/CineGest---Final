"""
Vistas para exportación de reportes en PDF y Excel.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
import logging

from reportes.selectors import (
    get_kpis, 
    get_datos_financieros, 
    get_datos_ocupacion, 
    get_ranking_peliculas_performance, 
    get_ranking_horarios_dia, 
    get_dashboard_alertas, 
    get_ranking_revpas, 
    get_ranking_dia_revenue, 
    get_analisis_franjas_horarias,
    get_ranking_salas,
    aplicar_ordenamiento_tabla
)
from reportes.services import (
    generar_excel_financiero,
    generar_pdf_financiero,
    generar_excel_operativo,
    generar_pdf_operativo
)
from reportes.utils import parse_date_range_from_request, is_system_admin
from reportes.utils import parse_report_filters_from_request, get_report_filters_summary
from reportes.config import config


def _get_user_display_name(request):
    """
    Obtiene el nombre completo del usuario autenticado para mostrar en PDFs.
    
    Returns:
        str: Nombre completo, username o 'Usuario' como fallback
    """
    try:
        if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            name = (request.user.get_full_name() or '').strip()
            if not name:
                name = getattr(request.user, 'username', '')
            return name or 'Usuario'
        else:
            return 'Usuario no autenticado'
    except Exception:
        return 'Usuario'


def _extract_chart_images_from_post(request):
    """
    Extrae imágenes de gráficos desde POST request (formato base64).
    
    Returns:
        dict: Diccionario con claves 'chart_image', 'heatmap_image', 'marketing_image' (o None)
    """
    images = {
        'chart_image': None,
        'heatmap_image': None,
        'marketing_image': None
    }
    
    if request.method == 'POST':
        try:
            import json as _json
            payload = _json.loads(request.body.decode('utf-8') or '{}')
            images['chart_image'] = payload.get('chart_image')
            images['heatmap_image'] = payload.get('heatmap_image')
            images['marketing_image'] = payload.get('marketing_image')
        except Exception:
            pass
    
    return images


@login_required
def exportar_financiero_pdf(request):
    """Exporta reporte financiero en PDF con ordenamiento dinámico."""
    if not is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')
    
    logger = logging.getLogger(__name__)
    
    # Parsear rango de fechas usando utilidad centralizada
    start_dt, end_dt, fecha_inicio, fecha_fin = parse_date_range_from_request(request)
    filters = parse_report_filters_from_request(request)
    
    # Obtener datos usando selectores
    kpis = get_kpis(start_dt, end_dt, filters=filters)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=config.RANKING_LIMITS['peliculas'], filters=filters)
    ranking_revpas = get_ranking_revpas(start_dt, end_dt, filters=filters)
    ranking_dia_revenue = get_ranking_dia_revenue(start_dt, end_dt, filters=filters)
    
    # CAPTURAR PARÁMETROS DE ORDENAMIENTO DESDE GET
    revpas_order_col = request.GET.get('revpas_order_col', '4')
    revpas_order_dir = request.GET.get('revpas_order_dir', 'desc')
    dia_order_col = request.GET.get('dia_order_col', '3')
    dia_order_dir = request.GET.get('dia_order_dir', 'desc')
    detalle_order_col = request.GET.get('detalle_order_col', '5')
    detalle_order_dir = request.GET.get('detalle_order_dir', 'desc')
    promo_order_col = request.GET.get('promo_order_col', '4')
    promo_order_dir = request.GET.get('promo_order_dir', 'desc')
    
    logger.info(f"📊 Parámetros de ordenamiento PDF Financiero:")
    logger.info(f"   RevPAS: col={revpas_order_col}, dir={revpas_order_dir}")
    logger.info(f"   Día Revenue: col={dia_order_col}, dir={dia_order_dir}")
    logger.info(f"   Detalle Películas: col={detalle_order_col}, dir={detalle_order_dir}")
    logger.info(f"   Eficiencia Promociones: col={promo_order_col}, dir={promo_order_dir}")
    
    # APLICAR ORDENAMIENTO DINÁMICO usando función centralizada
    ranking_revpas = aplicar_ordenamiento_tabla(ranking_revpas, 'revpas', revpas_order_col, revpas_order_dir)
    ranking_dia_revenue = aplicar_ordenamiento_tabla(ranking_dia_revenue, 'dia_revenue', dia_order_col, dia_order_dir)
    
    detalle_peliculas = fin_data.get('detalle', [])
    detalle_peliculas = aplicar_ordenamiento_tabla(detalle_peliculas, 'detalle_peliculas', detalle_order_col, detalle_order_dir)
    fin_data['detalle'] = detalle_peliculas

    promociones_data = list(fin_data.get('detalle', []))
    promociones_data = aplicar_ordenamiento_tabla(promociones_data, 'promociones', promo_order_col, promo_order_dir)
    
    # Extraer imágenes de gráficos
    images = _extract_chart_images_from_post(request)
    
    # Identificar solicitante
    requested_by = _get_user_display_name(request)
    filtros_resumen = get_report_filters_summary(filters)

    # Generar PDF
    buffer = generar_pdf_financiero(
        kpis, fin_data, fecha_inicio, fecha_fin,
        chart_base64=images['chart_image'],
        requested_by=requested_by,
        ranking_revpas=ranking_revpas,
        ranking_dia_revenue=ranking_dia_revenue,
        promociones_data=promociones_data,
        filtros_resumen=filtros_resumen
    )
    
    filename_prefix = config.EXPORT_FILENAME_PREFIX['financiero_pdf']
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}_{fecha_inicio}_{fecha_fin}.pdf"'
    return response


@login_required
def exportar_financiero_excel(request):
    """Exporta reporte financiero en Excel."""
    if not is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')
    
    # Parsear rango de fechas usando utilidad centralizada
    start_dt, end_dt, fecha_inicio, fecha_fin = parse_date_range_from_request(request)
    
    # Obtener datos usando selectores
    kpis = get_kpis(start_dt, end_dt)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=config.RANKING_LIMITS['peliculas'])
    
    # Generar Excel
    buffer = generar_excel_financiero(kpis, fin_data, fecha_inicio, fecha_fin)
    
    filename_prefix = config.EXPORT_FILENAME_PREFIX['financiero_excel']
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}_{fecha_inicio}_{fecha_fin}.xlsx"'
    return response


@login_required
def exportar_operativo_pdf(request):
    """Exporta reporte operativo en PDF con ordenamiento dinámico."""
    if not is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')
    
    logger = logging.getLogger(__name__)
    
    # Parsear rango de fechas usando utilidad centralizada
    start_dt, end_dt, fecha_inicio, fecha_fin = parse_date_range_from_request(request)
    filters = parse_report_filters_from_request(request)
    
    # Determinar si filtrar por días específicos (rangos cortos)
    dias_diferencia = (end_dt.date() - start_dt.date()).days
    filtrar_dias = dias_diferencia <= config.FILTRO_DIAS_THRESHOLD
    
    # CAPTURAR PARÁMETROS DE ORDENAMIENTO DE LAS TABLAS
    peliculas_order_col = request.GET.get('peliculas_order_col', '0')
    peliculas_order_dir = request.GET.get('peliculas_order_dir', 'asc')
    
    horarios_order_col = request.GET.get('horarios_order_col', '4')
    horarios_order_dir = request.GET.get('horarios_order_dir', 'desc')
    
    salas_order_col = request.GET.get('salas_order_col', '0')
    salas_order_dir = request.GET.get('salas_order_dir', 'asc')
    
    detalle_order_col = request.GET.get('detalle_order_col', '0')
    detalle_order_dir = request.GET.get('detalle_order_dir', 'asc')
    
    # Detectar si hay filtros personalizados
    tiene_filtros_personalizados = any([
        peliculas_order_col != '0' or peliculas_order_dir != 'asc',
        horarios_order_col != '4' or horarios_order_dir != 'desc',
        salas_order_col != '0' or salas_order_dir != 'asc',
        detalle_order_col != '0' or detalle_order_dir != 'asc'
    ])
    
    logger.info(f"📊 Parámetros de ordenamiento PDF Operativo:")
    logger.info(f"   Películas: col={peliculas_order_col}, dir={peliculas_order_dir}")
    logger.info(f"   Horarios: col={horarios_order_col}, dir={horarios_order_dir}")
    logger.info(f"   Salas: col={salas_order_col}, dir={salas_order_dir}")
    logger.info(f"   Detalle: col={detalle_order_col}, dir={detalle_order_dir}")
    logger.info(f"   Filtros personalizados: {tiene_filtros_personalizados}")
    
    # Obtener datos usando selectores
    # Ocupación y horarios SE FILTRAN por días cuando el rango es corto
    occ_data = get_datos_ocupacion(start_dt, end_dt, filtrar_dias=filtrar_dias, filters=filters)
    ranking_horarios = get_ranking_horarios_dia(start_dt, end_dt, filtrar_dias=filtrar_dias, filters=filters)
    
    # Películas y salas SIEMPRE usan el rango completo (NO se filtran por día)
    dashboard_alertas = get_dashboard_alertas(start_dt, end_dt, filters=filters)
    ranking_peliculas = get_ranking_peliculas_performance(start_dt, end_dt, filters=filters)
    ranking_salas = get_ranking_salas(start_dt, end_dt, filters=filters)
    
    # Agregar índice original para preservar orden en templates
    for idx, pelicula in enumerate(ranking_peliculas):
        pelicula['_original_index'] = idx
        pelicula['posicion_ranking'] = idx + 1
    
    for idx, sala in enumerate(ranking_salas):
        sala['_original_index'] = idx
        sala['posicion_ranking'] = idx + 1
    
    # APLICAR ORDENAMIENTO DINÁMICO usando función centralizada
    ranking_peliculas = aplicar_ordenamiento_tabla(ranking_peliculas, 'peliculas', peliculas_order_col, peliculas_order_dir)
    ranking_horarios = aplicar_ordenamiento_tabla(ranking_horarios, 'horarios', horarios_order_col, horarios_order_dir)
    ranking_salas = aplicar_ordenamiento_tabla(ranking_salas, 'salas', salas_order_col, salas_order_dir)
    occ_data['detalle'] = aplicar_ordenamiento_tabla(occ_data.get('detalle', []), 'ocupacion_detalle', detalle_order_col, detalle_order_dir)
    
    # Extraer imágenes de gráficos
    images = _extract_chart_images_from_post(request)
    
    # Identificar solicitante
    requested_by = _get_user_display_name(request)
    filtros_resumen = get_report_filters_summary(filters)

    # Generar PDF
    buffer = generar_pdf_operativo(
        occ_data, fecha_inicio, fecha_fin,
        chart_base64=images['chart_image'],
        heatmap_base64=images['heatmap_image'],
        marketing_base64=images['marketing_image'],
        requested_by=requested_by,
        dashboard_alertas=dashboard_alertas,
        ranking_peliculas=ranking_peliculas,
        ranking_horarios=ranking_horarios,
        ranking_salas=ranking_salas,
        tiene_filtros_personalizados=tiene_filtros_personalizados,
        filtros_resumen=filtros_resumen
    )
    
    filename_prefix = config.EXPORT_FILENAME_PREFIX['operativo_pdf']
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}_{fecha_inicio}_{fecha_fin}.pdf"'
    return response


@login_required
def exportar_operativo_excel(request):
    """Exporta reporte operativo en Excel."""
    if not is_system_admin(request.user):
        return HttpResponseForbidden("No autorizado")
    
    # Parsear rango de fechas usando utilidad centralizada
    start_dt, end_dt, fecha_inicio, fecha_fin = parse_date_range_from_request(request)
    
    # Obtener datos usando selectores
    occ_data = get_datos_ocupacion(start_dt, end_dt)
    
    # Generar Excel
    buffer = generar_excel_operativo(occ_data, fecha_inicio, fecha_fin)
    
    filename_prefix = config.EXPORT_FILENAME_PREFIX['operativo_excel']
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}_{fecha_inicio}_{fecha_fin}.xlsx"'
    return response
