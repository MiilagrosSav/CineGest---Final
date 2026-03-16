from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import AuditEntry
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation
import json


def _parse_decimal(value):
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, int):
        return Decimal(value)

    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, str):
        raw = value.strip().replace(',', '.')
        if not raw:
            return None
        try:
            return Decimal(raw)
        except (InvalidOperation, ValueError):
            return None

    return None


def _normalize_for_compare(value):
    if isinstance(value, dict):
        return tuple(sorted((k, _normalize_for_compare(v)) for k, v in value.items()))

    if isinstance(value, list):
        return tuple(_normalize_for_compare(v) for v in value)

    decimal_value = _parse_decimal(value)
    if decimal_value is not None:
        return decimal_value.quantize(Decimal('0.01'))

    if isinstance(value, str):
        return value.strip()

    return value

def _check_audit_permission(user):
    """Verifica si el usuario tiene permisos para ver auditoría."""
    return user.is_superuser or getattr(user, 'rol', '') == 'admin'

@login_required
def audit_list(request):
    """Vista principal de la lista de auditoría con búsqueda y paginación."""
    if not _check_audit_permission(request.user):
        return redirect('accounts:dashboard')

    qs = AuditEntry.objects.select_related('history_user').all().order_by('-history_date')
    
    # Búsqueda
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(model_name__icontains=q) |
            Q(object_repr__icontains=q) |
            Q(history_user__username__icontains=q)
        )
    
    # Filtro por tipo
    type_filter = request.GET.get('type', '').strip()
    if type_filter:
        qs = qs.filter(history_type=type_filter)

    # Paginación
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'auditoria/list.html', {
        'page_obj': page_obj,
        'q': q,
        'type_filter': type_filter,
    })

@login_required
def audit_detail(request, pk):
    """Vista de detalle con comparación inteligente (Antes y Después)."""
    if not _check_audit_permission(request.user):
        return redirect('accounts:dashboard')

    entry = get_object_or_404(AuditEntry.objects.select_related('history_user'), pk=pk)

    # Buscamos el registro anterior para comparar cambios
    prev_entry = AuditEntry.objects.filter(
        model_name=entry.model_name,
        object_id=entry.object_id,
        history_date__lt=entry.history_date
    ).order_by('-history_date').first()

    diff = {}
    datos_eliminados = {}

    # Lógica de comparación si es actualización
    if entry.history_type == '~' and prev_entry:
        current_data = entry.snapshot
        prev_data = prev_entry.snapshot
        for key, value in current_data.items():
            old_value = prev_data.get(key)
            if _normalize_for_compare(value) != _normalize_for_compare(old_value):
                diff[key] = {'antes': old_value, 'despues': value}
    
    # Si es eliminación, guardamos el snapshot final
    elif entry.history_type == '-':
        datos_eliminados = entry.snapshot

    return render(request, 'auditoria/detail.html', {
        'entry': entry,
        'diff': diff,
        'datos_eliminados': datos_eliminados,
        'snapshot_pretty': json.dumps(entry.snapshot, indent=2, ensure_ascii=False, default=str),
    })

@login_required
def audit_updates(request):
    """Endpoint JSON para polling de actualizaciones."""
    if not _check_audit_permission(request.user):
        return JsonResponse({'error': 'Acceso denegado'}, status=403)

    try:
        since_id = int(request.GET.get('since_id', 0))
    except (ValueError, TypeError):
        since_id = 0

    new_count = AuditEntry.objects.filter(pk__gt=since_id).count() if since_id else 0
    latest = AuditEntry.objects.order_by('-pk').values('pk').first()
    latest_id = latest['pk'] if latest else None

    return JsonResponse({
        'new_count': new_count,
        'latest_id': latest_id,
        'has_new': new_count > 0
    })