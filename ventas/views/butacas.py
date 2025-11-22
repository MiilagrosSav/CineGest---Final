"""
Vista para seleccionar butacas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from cine.models import Funcion, Butaca
from ventas.models import Entrada
from ventas.services import liberar_reservas_expiradas
from cine.models.configuracion_cine import ConfiguracionCine
from django.utils import timezone
from datetime import timedelta


@login_required
def seleccionar_butacas(request, funcion_id):
    """Vista para seleccionar butacas para una función"""
    # Liberar reservas expiradas antes de calcular disponibilidad (check-on-access)
    try:
        liberar_reservas_expiradas()
    except Exception:
        # Si algo falla aquí no queremos romper la vista; la liberación
        # puede reintentarse mediante el management command.
        pass
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
    
    try:
        tiempo_limite = ConfiguracionCine.load().reserva_tiempo_espera
    except Exception:
        tiempo_limite = 10

    # Calcular fecha/hora de expiración absoluta según reservas del usuario para esta función
    try:
        now = timezone.now()
        usuario = request.user
        reservas_usuario = Entrada.objects.filter(
            id_funcion=funcion,
            reservado_por=usuario,
            estado__in=['PENDIENTE', 'RESERVADA']
        ).order_by('fecha_creacion')

        if reservas_usuario.exists():
            primera = reservas_usuario.first()
            expiracion = primera.fecha_creacion + timedelta(minutes=int(tiempo_limite))
            # si ya expiró, dejar expiracion en now para que el frontend muestre 00:00
            if expiracion <= now:
                expiracion = now
        else:
            expiracion = now + timedelta(minutes=int(tiempo_limite))
        expiracion_iso = expiracion.isoformat()
    except Exception:
        expiracion_iso = (timezone.now() + timedelta(minutes=int(tiempo_limite))).isoformat()

    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': filas_ordenadas,
        'precio': funcion.precio_base,
        'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        'form_action_name': 'ventas:procesar_compra',
        'venta_id': None,
        'cantidad_requerida': None,
        'expiracion_iso': expiracion_iso,
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

    # Liberar reservas expiradas antes de calcular disponibilidad (check-on-access)
    try:
        liberar_reservas_expiradas()
    except Exception:
        pass

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

    try:
        tiempo_limite = ConfiguracionCine.load().reserva_tiempo_espera
    except Exception:
        tiempo_limite = 10

    # Calcular fecha/hora de expiración absoluta para el usuario en modo intercambio
    try:
        now = timezone.now()
        usuario = request.user
        reservas_usuario = Entrada.objects.filter(
            id_funcion=funcion,
            reservado_por=usuario,
            estado__in=['PENDIENTE', 'RESERVADA']
        ).order_by('fecha_creacion')

        if reservas_usuario.exists():
            primera = reservas_usuario.first()
            expiracion = primera.fecha_creacion + timedelta(minutes=int(tiempo_limite))
            if expiracion <= now:
                expiracion = now
        else:
            expiracion = now + timedelta(minutes=int(tiempo_limite))
        expiracion_iso = expiracion.isoformat()
    except Exception:
        expiracion_iso = (timezone.now() + timedelta(minutes=int(tiempo_limite))).isoformat()

    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': filas_ordenadas,
        'precio': funcion.precio_base,
        'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        'form_action_name': 'ventas:procesar_intercambio',
        'venta_id': venta.id_venta,
        'cantidad_requerida': venta.entradas.count(),
        'expiracion_iso': expiracion_iso,
    }

    return render(request, 'ventas/seleccionar_butacas.html', context)
