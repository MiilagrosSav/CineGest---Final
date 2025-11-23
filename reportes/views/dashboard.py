from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.db.models import Sum, Count, Q, F, Value
from django.db.models.functions import Coalesce, ExtractWeekDay
from django.utils import timezone
from django.db import models
from decimal import Decimal
import calendar
import json
from datetime import datetime, time, timedelta

from cine.models import Pelicula, Funcion
from ventas.models import Entrada
from reportes.selectors import get_kpis, get_datos_financieros, get_datos_ocupacion


def _is_system_admin(user):
    # system admin role is 'admin' in this project (not Django superuser)
    # allow Django superusers as a convenience (dev/admins)
    return getattr(user, 'rol', None) == 'admin' or getattr(user, 'is_superuser', False)


@login_required
def dashboard_view(request):
    if not _is_system_admin(request.user):
        return HttpResponseForbidden("No autorizado")

    # --- Date range handling -------------------------------------------------
    # Read GET params 'fecha_inicio' and 'fecha_fin' (YYYY-MM-DD). If missing,
    # default to last 30 days (from now - 30 days to now).
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    now = timezone.now()
    default_start_dt = (now - timedelta(days=30))
    default_end_dt = now

    def _make_aware_if_naive(dt):
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    # parse start
    try:
        if fecha_inicio_str:
            parsed_date = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            start_dt = datetime.combine(parsed_date, time.min)
        else:
            start_dt = datetime.combine(default_start_dt.date(), time.min)
    except Exception:
        start_dt = datetime.combine(default_start_dt.date(), time.min)

    # parse end
    try:
        if fecha_fin_str:
            parsed_date = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            end_dt = datetime.combine(parsed_date, time.max)
        else:
            end_dt = datetime.combine(default_end_dt.date(), time.max)
    except Exception:
        end_dt = datetime.combine(default_end_dt.date(), time.max)

    # make them timezone-aware
    start_dt = _make_aware_if_naive(start_dt)
    end_dt = _make_aware_if_naive(end_dt)

    # keep strings for the template inputs (YYYY-MM-DD)
    fecha_inicio_final = (fecha_inicio_str or start_dt.date().isoformat())
    fecha_fin_final = (fecha_fin_str or end_dt.date().isoformat())

    # Quick range querystrings for template buttons
    today_date = now.date()
    rango_7_start = (now - timedelta(days=7)).date().isoformat()
    rango_7_end = today_date.isoformat()

    rango_30_start = (now - timedelta(days=30)).date().isoformat()
    rango_30_end = today_date.isoformat()

    # first and last day of current month
    first_day_month = today_date.replace(day=1).isoformat()
    last_day_num = calendar.monthrange(today_date.year, today_date.month)[1]
    last_day_month = today_date.replace(day=last_day_num).isoformat()

    rango_7_qs = f"?fecha_inicio={rango_7_start}&fecha_fin={rango_7_end}"
    rango_30_qs = f"?fecha_inicio={rango_30_start}&fecha_fin={rango_30_end}"
    rango_mes_qs = f"?fecha_inicio={first_day_month}&fecha_fin={last_day_month}"

    # Use selectors to get data (reusable for exports)
    kpis = get_kpis(start_dt, end_dt)
    fin_data = get_datos_financieros(start_dt, end_dt, limit=10)
    occ_data = get_datos_ocupacion(start_dt, end_dt)

    context = {
        'kpis': kpis,
        'fin_chart': {
            'labels': fin_data['labels'],
            'data_full': fin_data['data_full'],
            'data_promo': fin_data['data_promo'],
        },
        'occ_chart': {
            'labels': occ_data['labels'],
            'data': occ_data['data'],
        }
    }

    # Pass JSON-encoded strings for safe inclusion in JS
    context['fin_chart_json'] = json.dumps(context['fin_chart'])
    context['occ_chart_json'] = json.dumps(context['occ_chart'])

    # pass selected date strings so the template inputs keep their values
    context['fecha_inicio'] = fecha_inicio_final
    context['fecha_fin'] = fecha_fin_final
    # quick range links (querystrings)
    context['rango_7_qs'] = rango_7_qs
    context['rango_30_qs'] = rango_30_qs
    context['rango_mes_qs'] = rango_mes_qs

    return render(request, 'reportes/dashboard.html', context)
