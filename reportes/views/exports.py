"""
Vistas para exportación de reportes en PDF y Excel.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from datetime import datetime, time, timedelta

from reportes.selectors import get_kpis, get_datos_financieros, get_datos_ocupacion
from reportes.services import (
    generar_excel_financiero,
    generar_pdf_financiero,
    generar_excel_operativo,
    generar_pdf_operativo
)


def _is_system_admin(user):
    return getattr(user, 'rol', None) == 'admin' or getattr(user, 'is_superuser', False)


def _parse_date_range(request):
    """Helper para parsear rango de fechas desde GET params."""
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    
    now = timezone.now()
    default_start_dt = now - timedelta(days=30)
    default_end_dt = now
    
    def _make_aware_if_naive(dt):
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    
    try:
        if fecha_inicio_str:
            parsed_date = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            start_dt = datetime.combine(parsed_date, time.min)
        else:
            start_dt = datetime.combine(default_start_dt.date(), time.min)
    except Exception:
        start_dt = datetime.combine(default_start_dt.date(), time.min)
    
    try:
        if fecha_fin_str:
            parsed_date = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            end_dt = datetime.combine(parsed_date, time.max)
        else:
            end_dt = datetime.combine(default_end_dt.date(), time.max)
    except Exception:
        end_dt = datetime.combine(default_end_dt.date(), time.max)
    
    start_dt = _make_aware_if_naive(start_dt)
    end_dt = _make_aware_if_naive(end_dt)
    
    fecha_inicio_final = (fecha_inicio_str or start_dt.date().isoformat())
    fecha_fin_final = (fecha_fin_str or end_dt.date().isoformat())
    
    return start_dt, end_dt, fecha_inicio_final, fecha_fin_final


@login_required
def exportar_financiero_pdf(request):
    """Exporta reporte financiero en PDF."""
    if not _is_system_admin(request.user):
        return HttpResponseForbidden("No autorizado")
    
    start_dt, end_dt, fecha_inicio, fecha_fin = _parse_date_range(request)
    
    # Obtener datos usando selectores
    kpis = get_kpis(start_dt, end_dt)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=10)
    # Accept optional chart image via POST JSON (chart_image: data:image/png;base64,...)
    chart_base64 = None
    if request.method == 'POST':
        try:
            import json as _json
            payload = _json.loads(request.body.decode('utf-8') or '{}')
            chart_base64 = payload.get('chart_image')
        except Exception:
            chart_base64 = None

    # Identify requester
    # Build a robust display name for the requesting user
    requested_by = None
    try:
        if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            name = (request.user.get_full_name() or '').strip()
            if not name:
                name = getattr(request.user, 'username', '')
            requested_by = name or 'Usuario'
        else:
            requested_by = 'Usuario no autenticado'
    except Exception:
        requested_by = 'Usuario'

    # Generar PDF (may include embedded chart image)
    buffer = generar_pdf_financiero(
        kpis, fin_data, fecha_inicio, fecha_fin,
        chart_base64=chart_base64,
        requested_by=requested_by
    )
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_financiero_{fecha_inicio}_{fecha_fin}.pdf"'
    return response


@login_required
def exportar_financiero_excel(request):
    """Exporta reporte financiero en Excel."""
    if not _is_system_admin(request.user):
        return HttpResponseForbidden("No autorizado")
    
    start_dt, end_dt, fecha_inicio, fecha_fin = _parse_date_range(request)
    
    # Obtener datos usando selectores
    kpis = get_kpis(start_dt, end_dt)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=10)
    
    # Generar Excel
    buffer = generar_excel_financiero(kpis, fin_data, fecha_inicio, fecha_fin)
    
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reporte_financiero_{fecha_inicio}_{fecha_fin}.xlsx"'
    return response


@login_required
def exportar_operativo_pdf(request):
    """Exporta reporte operativo en PDF."""
    if not _is_system_admin(request.user):
        return HttpResponseForbidden("No autorizado")
    
    start_dt, end_dt, fecha_inicio, fecha_fin = _parse_date_range(request)
    
    # Obtener datos usando selectores
    occ_data = get_datos_ocupacion(start_dt, end_dt)
    # Accept optional chart/heatmap/marketing images via POST JSON
    chart_base64 = None
    heatmap_base64 = None
    marketing_base64 = None
    if request.method == 'POST':
        try:
            import json as _json
            payload = _json.loads(request.body.decode('utf-8') or '{}')
            chart_base64 = payload.get('chart_image')
            heatmap_base64 = payload.get('heatmap_image')
            marketing_base64 = payload.get('marketing_image')
        except Exception:
            chart_base64 = None
            heatmap_base64 = None
            marketing_base64 = None

    # Build a robust display name for the requesting user
    requested_by = None
    try:
        if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            name = (request.user.get_full_name() or '').strip()
            if not name:
                name = getattr(request.user, 'username', '')
            requested_by = name or 'Usuario'
        else:
            requested_by = 'Usuario no autenticado'
    except Exception:
        requested_by = 'Usuario'

    # Generar PDF
    buffer = generar_pdf_operativo(
        occ_data, fecha_inicio, fecha_fin,
        chart_base64=chart_base64,
        heatmap_base64=heatmap_base64,
        marketing_base64=marketing_base64,
        requested_by=requested_by
    )
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_operativo_{fecha_inicio}_{fecha_fin}.pdf"'
    return response


@login_required
def exportar_operativo_excel(request):
    """Exporta reporte operativo en Excel."""
    if not _is_system_admin(request.user):
        return HttpResponseForbidden("No autorizado")
    
    start_dt, end_dt, fecha_inicio, fecha_fin = _parse_date_range(request)
    
    # Obtener datos usando selectores
    occ_data = get_datos_ocupacion(start_dt, end_dt)
    
    # Generar Excel
    buffer = generar_excel_operativo(occ_data, fecha_inicio, fecha_fin)
    
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reporte_operativo_{fecha_inicio}_{fecha_fin}.xlsx"'
    return response
