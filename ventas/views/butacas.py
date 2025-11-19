"""
Vista para seleccionar butacas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from cine.models import Funcion, Butaca
from ventas.models import Entrada


@login_required
def seleccionar_butacas(request, funcion_id):
    """Vista para seleccionar butacas para una función"""
    funcion = get_object_or_404(Funcion, id=funcion_id)
    sala = funcion.sala
    
    # Obtener todas las butacas de la sala ordenadas por fila y número
    butacas = Butaca.objects.filter(sala=sala).order_by('fila', 'numero')
    
    # Obtener las butacas ya vendidas/reservadas para esta función
    butacas_ocupadas = Entrada.objects.filter(
        id_funcion=funcion,
        estado__in=['RESERVADA', 'VENDIDA']
    ).values_list('id_butaca_id', flat=True)
    
    # Organizar butacas por fila
    butacas_por_fila = {}
    for butaca in butacas:
        if butaca.fila not in butacas_por_fila:
            butacas_por_fila[butaca.fila] = []
        butacas_por_fila[butaca.fila].append({
            'id': butaca.id,
            'numero': butaca.numero,
            'tipo': butaca.tipo,
            'es_pasillo': butaca.es_pasillo,
            'ocupada': butaca.id in butacas_ocupadas
        })
    
    # Ordenar las filas alfabéticamente
    filas_ordenadas = sorted(butacas_por_fila.items())
    
    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': filas_ordenadas,
        'precio': funcion.precio_base,
        'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        'form_action_name': 'ventas:procesar_compra',
        'venta_id': None,
        'cantidad_requerida': None,
    }
    
    return render(request, 'ventas/seleccionar_butacas.html', context)


@login_required
def seleccionar_butacas_intercambio(request, venta_id, funcion_id):
    """Vista para seleccionar butacas en modo intercambio: el usuario viene desde una venta
    y debe elegir exactamente la misma cantidad de butacas para la nueva función."""
    from ventas.models import Venta

    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)
    funcion = get_object_or_404(Funcion, id=funcion_id)
    sala = funcion.sala

    # Obtener todas las butacas de la sala ordenadas por fila y número
    butacas = Butaca.objects.filter(sala=sala).order_by('fila', 'numero')

    # Butacas ocupadas para esta función (no cuentan las CANCELADAS)
    butacas_ocupadas = Entrada.objects.filter(
        id_funcion=funcion,
        estado__in=['RESERVADA', 'VENDIDA', 'USADA']
    ).values_list('id_butaca_id', flat=True)

    # Organizar butacas por fila
    butacas_por_fila = {}
    for butaca in butacas:
        if butaca.fila not in butacas_por_fila:
            butacas_por_fila[butaca.fila] = []
        butacas_por_fila[butaca.fila].append({
            'id': butaca.id,
            'numero': butaca.numero,
            'tipo': butaca.tipo,
            'es_pasillo': butaca.es_pasillo,
            'ocupada': butaca.id in butacas_ocupadas
        })

    filas_ordenadas = sorted(butacas_por_fila.items())

    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': filas_ordenadas,
        'precio': funcion.precio_base,
        'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        'form_action_name': 'ventas:procesar_intercambio',
        'venta_id': venta.id_venta,
        'cantidad_requerida': venta.entradas.count(),
    }

    return render(request, 'ventas/seleccionar_butacas.html', context)
