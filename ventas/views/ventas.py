"""
Vistas para gestionar ventas
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from ventas.models import Venta
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


@login_required
def mis_ventas(request):
    """Vista para que el cliente vea sus ventas/compras"""
    # Obtener todas las ventas del cliente actual
    ventas_todas = Venta.objects.filter(
        id_cliente__usuario=request.user
    ).prefetch_related('entradas', 'entradas__id_funcion', 'entradas__id_pelicula').order_by('-fecha_compra')
    
    # Separar ventas pendientes y confirmadas
    ventas_pendientes = ventas_todas.filter(estado__in=['PENDIENTE', 'PENDIENTE_PAGO'])
    ventas_historial_qs = ventas_todas.filter(estado__in=['CONFIRMADA', 'CANCELADA'])

    # Paginación para el historial (evita cargar muchas ventas en memoria)
    page_number = request.GET.get('page', 1)
    page_size = 3  # items por página — ajustalo si querés
    paginator = Paginator(ventas_historial_qs, page_size)
    try:
        ventas_page = paginator.page(page_number)
    except PageNotAnInteger:
        ventas_page = paginator.page(1)
    except EmptyPage:
        ventas_page = paginator.page(paginator.num_pages)
    
    context = {
        'ventas': ventas_todas,
        'ventas_pendientes': ventas_pendientes,
        'ventas_historial': ventas_historial_qs,
        'ventas_page': ventas_page,
    }
    
    # Si la petición es AJAX, devolvemos solo el partial del historial
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'ventas/_ventas_historial.html', context)

    return render(request, 'ventas/mis_ventas.html', context)


@login_required
def detalle_venta(request, venta_id):
    """Vista para ver el detalle de una venta específica"""
    venta = get_object_or_404(
        Venta,
        id_venta=venta_id,
        id_cliente__usuario=request.user
    )
    
    context = {
        'venta': venta,
    }
    
    return render(request, 'ventas/detalle_venta.html', context)