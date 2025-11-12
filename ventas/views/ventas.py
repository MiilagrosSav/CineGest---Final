"""
Vistas para gestionar ventas
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from ventas.models import Venta


@login_required
def mis_ventas(request):
    """Vista para que el cliente vea sus ventas/compras"""
    # Obtener todas las ventas del cliente actual
    ventas_todas = Venta.objects.filter(
        id_cliente__usuario=request.user
    ).prefetch_related('entradas', 'entradas__id_funcion', 'entradas__id_pelicula').order_by('-fecha_compra')
    
    # Separar ventas pendientes y confirmadas
    ventas_pendientes = ventas_todas.filter(estado__in=['PENDIENTE', 'PENDIENTE_PAGO'])
    ventas_historial = ventas_todas.filter(estado__in=['CONFIRMADA', 'CANCELADA'])
    
    context = {
        'ventas': ventas_todas,
        'ventas_pendientes': ventas_pendientes,
        'ventas_historial': ventas_historial,
    }
    
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