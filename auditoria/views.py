from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import AuditEntry
from django.http import JsonResponse
import json


def _check_audit_permission(user):
    """Verifica si el usuario tiene permisos para ver auditoría."""
    return user.is_superuser or getattr(user, 'rol', '') == 'admin'


@login_required
def audit_list(request):
    """Vista principal de la lista de auditoría con búsqueda y paginación."""
    # Validar permisos
    if not _check_audit_permission(request.user):
        return redirect('accounts:dashboard')

    # Obtener todas las entradas
    qs = AuditEntry.objects.select_related('history_user').all()
    
    # Búsqueda
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(model_name__icontains=q) |
            Q(object_repr__icontains=q) |
            Q(history_user__username__icontains=q) |
            Q(history_user__first_name__icontains=q) |
            Q(history_user__last_name__icontains=q)
        )
    
    # Filtros adicionales
    model_filter = request.GET.get('model', '').strip()
    if model_filter:
        qs = qs.filter(model_name=model_filter)
    
    type_filter = request.GET.get('type', '').strip()
    if type_filter in ['+', '~', '-']:
        qs = qs.filter(history_type=type_filter)

    # Paginación
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Obtener lista de modelos únicos para filtro
    available_models = AuditEntry.objects.values_list('model_name', flat=True).distinct().order_by('model_name')

    return render(request, 'auditoria/list.html', {
        'page_obj': page_obj,
        'q': q,
        'model_filter': model_filter,
        'type_filter': type_filter,
        'available_models': available_models,
    })


@login_required
def audit_detail(request, pk):
    """Vista de detalle de una entrada de auditoría."""
    # Validar permisos
    if not _check_audit_permission(request.user):
        return redirect('accounts:dashboard')

    # Obtener entrada con select_related para optimizar
    entry = get_object_or_404(
        AuditEntry.objects.select_related('history_user'),
        pk=pk
    )

    # Formatear snapshot para visualización
    try:
        snapshot_pretty = json.dumps(entry.snapshot, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        snapshot_pretty = f"Error al formatear snapshot: {str(e)}\n\n{entry.snapshot}"

    return render(request, 'auditoria/detail.html', {
        'entry': entry,
        'snapshot_pretty': snapshot_pretty,
    })


@login_required
def audit_updates(request):
    """Endpoint JSON para polling de actualizaciones (usado por JavaScript)."""
    # Validar permisos
    if not _check_audit_permission(request.user):
        return JsonResponse({'error': 'Acceso denegado'}, status=403)

    # Obtener since_id del query param
    try:
        since_id = int(request.GET.get('since_id', 0))
    except (ValueError, TypeError):
        since_id = 0

    # Contar nuevas entradas
    if since_id:
        new_count = AuditEntry.objects.filter(pk__gt=since_id).count()
    else:
        new_count = 0

    # Obtener ID más reciente (usar valores para performance)
    latest = AuditEntry.objects.order_by('-pk').values('pk').first()
    latest_id = latest['pk'] if latest else None

    return JsonResponse({
        'new_count': new_count,
        'latest_id': latest_id,
        'has_new': new_count > 0
    })
