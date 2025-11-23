from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, time, timedelta
import calendar
import json

from reportes.selectors import get_kpis, get_datos_financieros, get_datos_ocupacion


def _is_system_admin(user):
    return getattr(user, 'rol', None) == 'admin' or getattr(user, 'is_superuser', False)


@login_required
def reporte_financiero_view(request):
    if not _is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')

    # Date range handling (same behavior as previous dashboard)
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    now = timezone.now()
    default_start_dt = (now - timedelta(days=30))
    default_end_dt = now

    def _make_aware_if_naive(dt):
        from django.utils import timezone as _tz
        if _tz.is_naive(dt):
            return _tz.make_aware(dt, _tz.get_current_timezone())
        return dt

    from datetime import datetime as _dt
    try:
        if fecha_inicio_str:
            parsed_date = _dt.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            start_dt = _dt.combine(parsed_date, time.min)
        else:
            start_dt = _dt.combine(default_start_dt.date(), time.min)
    except Exception:
        start_dt = _dt.combine(default_start_dt.date(), time.min)

    try:
        if fecha_fin_str:
            parsed_date = _dt.strptime(fecha_fin_str, '%Y-%m-%d').date()
            end_dt = _dt.combine(parsed_date, time.max)
        else:
            end_dt = _dt.combine(default_end_dt.date(), time.max)
    except Exception:
        end_dt = _dt.combine(default_end_dt.date(), time.max)

    start_dt = _make_aware_if_naive(start_dt)
    end_dt = _make_aware_if_naive(end_dt)

    fecha_inicio_final = (fecha_inicio_str or start_dt.date().isoformat())
    fecha_fin_final = (fecha_fin_str or end_dt.date().isoformat())

    now_date = now.date()
    rango_7_qs = f"?fecha_inicio={(now - timedelta(days=7)).date().isoformat()}&fecha_fin={now_date.isoformat()}"
    rango_30_qs = f"?fecha_inicio={(now - timedelta(days=30)).date().isoformat()}&fecha_fin={now_date.isoformat()}"
    first_day_month = now_date.replace(day=1).isoformat()
    last_day_num = calendar.monthrange(now_date.year, now_date.month)[1]
    last_day_month = now_date.replace(day=last_day_num).isoformat()
    rango_mes_qs = f"?fecha_inicio={first_day_month}&fecha_fin={last_day_month}"

    kpis = get_kpis(start_dt, end_dt)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=50)

    context = {
        'kpis': kpis,
        'fin_data': fin_data,
        'fecha_inicio': fecha_inicio_final,
        'fecha_fin': fecha_fin_final,
        'rango_7_qs': rango_7_qs,
        'rango_30_qs': rango_30_qs,
        'rango_mes_qs': rango_mes_qs,
        'fin_chart_json': json.dumps({
            'labels': fin_data['labels'],
            'values': fin_data['data_full']
        })
    }

    return render(request, 'reportes/financiero.html', context)


@login_required
def reporte_ocupacion_view(request):
    if not _is_system_admin(request.user):
        return HttpResponseForbidden('No autorizado')

    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    now = timezone.now()
    default_start_dt = (now - timedelta(days=30))
    default_end_dt = now

    def _make_aware_if_naive(dt):
        from django.utils import timezone as _tz
        if _tz.is_naive(dt):
            return _tz.make_aware(dt, _tz.get_current_timezone())
        return dt

    from datetime import datetime as _dt
    try:
        if fecha_inicio_str:
            parsed_date = _dt.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            start_dt = _dt.combine(parsed_date, time.min)
        else:
            start_dt = _dt.combine(default_start_dt.date(), time.min)
    except Exception:
        start_dt = _dt.combine(default_start_dt.date(), time.min)

    try:
        if fecha_fin_str:
            parsed_date = _dt.strptime(fecha_fin_str, '%Y-%m-%d').date()
            end_dt = _dt.combine(parsed_date, time.max)
        else:
            end_dt = _dt.combine(default_end_dt.date(), time.max)
    except Exception:
        end_dt = _dt.combine(default_end_dt.date(), time.max)

    start_dt = _make_aware_if_naive(start_dt)
    end_dt = _make_aware_if_naive(end_dt)

    fecha_inicio_final = (fecha_inicio_str or start_dt.date().isoformat())
    fecha_fin_final = (fecha_fin_str or end_dt.date().isoformat())

    now_date = now.date()
    rango_7_qs = f"?fecha_inicio={(now - timedelta(days=7)).date().isoformat()}&fecha_fin={now_date.isoformat()}"
    rango_30_qs = f"?fecha_inicio={(now - timedelta(days=30)).date().isoformat()}&fecha_fin={now_date.isoformat()}"
    first_day_month = now_date.replace(day=1).isoformat()
    last_day_num = calendar.monthrange(now_date.year, now_date.month)[1]
    last_day_month = now_date.replace(day=last_day_num).isoformat()
    rango_mes_qs = f"?fecha_inicio={first_day_month}&fecha_fin={last_day_month}"

    occ_data = get_datos_ocupacion(start_dt, end_dt)

    context = {
        'occ_data': occ_data,
        'fecha_inicio': fecha_inicio_final,
        'fecha_fin': fecha_fin_final,
        'rango_7_qs': rango_7_qs,
        'rango_30_qs': rango_30_qs,
        'rango_mes_qs': rango_mes_qs,
        'occ_chart_json': json.dumps({
            'labels': occ_data['labels'],
            'values': occ_data['data']
        })
    }

    return render(request, 'reportes/ocupacion.html', context)


__all__ = ["reporte_financiero_view", "reporte_ocupacion_view"]
