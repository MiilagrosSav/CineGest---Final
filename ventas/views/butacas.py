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
from promociones.models.promocion import Promocion
from promociones.services import calcular_precio_final
from ventas.constants import EstadoEntrada


@login_required
def seleccionar_butacas(request, funcion_id):
    """Vista para seleccionar butacas para una función"""
    # Bloquear acceso a empleados - deben usar el módulo presencial
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados deben usar el módulo de venta presencial.')
        return redirect('ventas:dashboard_presencial')
    
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
    estado__in=EstadoEntrada.ESTADOS_OCUPADOS # <--- Usa la lista completa (incluye PENDIENTE)
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

    # Calcular precio con descuento SOLO si hay promoción activa desde link (con token válido)
    precio_mostrar = funcion.precio_base
    promocion_aplicada = None
    info_descuento = None
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        promo_id = request.session.get('promo_activa_id')
        promo_token = request.session.get('promo_token')
        
        logger.info(f'[SELECCIONAR_BUTACAS] promo_id en sesión: {promo_id}, promo_token: {promo_token}')
        
        # Solo aplicar si hay tanto ID como token (viene de link activado)
        if promo_id and promo_token:
            # Verificar que el token todavía exista y esté marcado como usado (ya fue activado)
            from promociones.models.cuponGenerado import CuponGenerado
            cupon = CuponGenerado.objects.filter(token=str(promo_token), usado=True).first()
            
            logger.info(f'[SELECCIONAR_BUTACAS] Cupón encontrado: {cupon is not None}')
            
            if cupon:
                promo = Promocion.objects.filter(pk=promo_id).first()
                if promo:
                    logger.info(f'[SELECCIONAR_BUTACAS] Aplicando promoción: {promo.codigo} tipo: {promo.tipo_descuento}')
                    promocion_aplicada = promo
                    
                    if promo.tipo_descuento == '2X1':
                        # Para 2x1: mostrar precio base, el descuento se aplica al total
                        precio_mostrar = funcion.precio_base
                        info_descuento = {
                            'tipo': '2X1',
                            'descripcion': f'🎉 {promo.nombre}: Pagás 1 y llevás 2 entradas',
                            'precio_con_descuento': funcion.precio_base  # Se cobra 1 sola
                        }
                    elif promo.tipo_descuento == 'PORCENTAJE':
                        # Aplicar porcentaje
                        from decimal import Decimal, ROUND_HALF_UP
                        porcentaje = Decimal(promo.valor_descuento or 0) / Decimal(100)
                        precio_con_desc = (funcion.precio_base * (Decimal(1) - porcentaje)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        precio_mostrar = precio_con_desc
                        ahorro = funcion.precio_base - precio_con_desc
                        info_descuento = {
                            'tipo': 'PORCENTAJE',
                            'descripcion': f'💰 {promo.nombre}: {promo.valor_descuento}% OFF (ahorrás ${ahorro})',
                            'precio_con_descuento': precio_con_desc
                        }
                    elif promo.tipo_descuento == 'MONTO_FIJO':
                        # Aplicar monto fijo
                        from decimal import Decimal, ROUND_HALF_UP
                        monto = Decimal(promo.valor_descuento or 0)
                        precio_con_desc = (funcion.precio_base - monto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        if precio_con_desc < Decimal('0'):
                            precio_con_desc = Decimal('0')
                        precio_mostrar = precio_con_desc
                        info_descuento = {
                            'tipo': 'MONTO_FIJO',
                            'descripcion': f'💰 {promo.nombre}: ${monto} OFF',
                            'precio_con_descuento': precio_con_desc
                        }
            else:
                # Token no válido o ya no existe, limpiar sesión
                logger.info(f'[SELECCIONAR_BUTACAS] Cupón no válido, limpiando sesión')
                request.session.pop('promo_activa_id', None)
                request.session.pop('promo_token', None)
                request.session.modified = True
        else:
            # Si no hay ambos valores, limpiar lo que haya
            if promo_id or promo_token:
                logger.info(f'[SELECCIONAR_BUTACAS] Sesión incompleta, limpiando')
                request.session.pop('promo_activa_id', None)
                request.session.pop('promo_token', None)
                request.session.modified = True
    except Exception as e:
        # No romper la vista por error al calcular descuento
        logger.exception('Error calculando descuento en seleccionar_butacas')
        # Limpiar sesión en caso de error
        request.session.pop('promo_activa_id', None)
        request.session.pop('promo_token', None)
        request.session.modified = True
    
    logger.info(f'[SELECCIONAR_BUTACAS] Resultado: precio={precio_mostrar}, tiene_descuento={info_descuento is not None}')
    # ==============================================================================
    # BLOQUE NUEVO: BUSCAR PROMOCIONES AUTOMÁTICAS (Si no hay cupón)
    # ==============================================================================
    if not promocion_aplicada:
        hoy = timezone.localdate()
        
        # Buscamos promos automáticas vigentes
        candidatas = Promocion.objects.filter(
            es_automatica=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy
        )
        
        from promociones.services import es_promocion_valida_para_funcion
        
        for p in candidatas:
            if es_promocion_valida_para_funcion(p, funcion):
                promocion_aplicada = p
                
                # Configurar visualización según tipo
                tipo = str(p.tipo_descuento).upper().strip()
                promo_codigo = p.codigo
                
                if tipo == '2X1':
                    promo_2x1 = True
                    info_descuento = {
                        'tipo': '2X1',
                        'descripcion': f'🎉 {p.nombre}: Pagás 1 y llevás 2',
                        'precio_con_descuento': funcion.precio_base
                    }
                elif tipo == 'PORCENTAJE':
                    from decimal import Decimal, ROUND_HALF_UP
                    porcentaje = Decimal(p.valor_descuento or 0) / Decimal(100)
                    precio_con_desc = (funcion.precio_base * (Decimal(1) - porcentaje)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    precio_mostrar = precio_con_desc
                    ahorro = funcion.precio_base - precio_con_desc
                    info_descuento = {
                        'tipo': 'PORCENTAJE',
                        'descripcion': f'🔥 {p.nombre}: {int(p.valor_descuento)}% OFF (ahorrás ${ahorro})',
                        'precio_con_descuento': precio_con_desc
                    }
                elif tipo == 'MONTO_FIJO':
                     from decimal import Decimal, ROUND_HALF_UP
                     monto = Decimal(p.valor_descuento or 0)
                     precio_con_desc = (funcion.precio_base - monto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                     if precio_con_desc < 0: precio_con_desc = 0
                     precio_mostrar = precio_con_desc
                     info_descuento = {
                        'tipo': 'MONTO_FIJO',
                        'descripcion': f'💰 {p.nombre}: ${monto} OFF',
                        'precio_con_descuento': precio_con_desc
                     }
                
                break # Encontramos una, nos quedamos con esa y salimos del bucle
    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': filas_ordenadas,
        'precio': precio_mostrar,
        'precio_base': funcion.precio_base,
        'promocion_aplicada': promocion_aplicada,
        'info_descuento': info_descuento,
        'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        'form_action_name': 'ventas:procesar_compra',
        'venta_id': None,
        'cantidad_requerida': None,
        'promo_2x1': False,
        'promo_codigo': None,
        'expiracion_iso': expiracion_iso,
    }
    
    # Si hay una promoción 2x1 activa en sesión, requerir 2 butacas
    try:
        promo_id = request.session.get('promo_activa_id')
        if promo_id:
            promo = Promocion.objects.filter(pk=promo_id).first()
            if promo and promo.tipo_descuento == '2X1':
                context['cantidad_requerida'] = 2
                context['promo_2x1'] = True
                context['promo_codigo'] = promo.codigo
    except Exception:
        # No romper la vista por error de sesión/promoción
        pass
    
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

    # Calcular precio con descuento SOLO si hay promoción activa desde link (con token válido)
    precio_mostrar = funcion.precio_base
    promocion_aplicada = None
    info_descuento = None
    promo_2x1 = False
    promo_codigo = None
    
    try:
        promo_id = request.session.get('promo_activa_id')
        promo_token = request.session.get('promo_token')
        
        # Solo aplicar si hay tanto ID como token (viene de link activado)
        if promo_id and promo_token:
            from promociones.models.cuponGenerado import CuponGenerado
            cupon = CuponGenerado.objects.filter(token=str(promo_token), usado=True).first()
            
            if cupon:
                promo = Promocion.objects.filter(pk=promo_id).first()
                if promo:
                    promocion_aplicada = promo
                    cantidad_venta = venta.entradas.count()
                    
                    if promo.tipo_descuento == '2X1':
                        precio_mostrar = funcion.precio_base
                        promo_2x1 = True
                        promo_codigo = promo.codigo
                        entradas_pagar = (cantidad_venta // 2) + (cantidad_venta % 2)
                        total_con_desc = funcion.precio_base * entradas_pagar
                        info_descuento = {
                            'tipo': '2X1',
                            'descripcion': f'🎉 {promo.nombre}: Pagás {entradas_pagar} y llevás {cantidad_venta} entradas',
                            'precio_con_descuento': total_con_desc
                        }
                    elif promo.tipo_descuento == 'PORCENTAJE':
                        from decimal import Decimal, ROUND_HALF_UP
                        porcentaje = Decimal(promo.valor_descuento or 0) / Decimal(100)
                        precio_con_desc = (funcion.precio_base * (Decimal(1) - porcentaje)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        precio_mostrar = precio_con_desc
                        ahorro = funcion.precio_base - precio_con_desc
                        info_descuento = {
                            'tipo': 'PORCENTAJE',
                            'descripcion': f'💰 {promo.nombre}: {promo.valor_descuento}% OFF (ahorrás ${ahorro} por entrada)',
                            'precio_con_descuento': precio_con_desc
                        }
                    elif promo.tipo_descuento == 'MONTO_FIJO':
                        from decimal import Decimal, ROUND_HALF_UP
                        monto = Decimal(promo.valor_descuento or 0)
                        precio_con_desc = (funcion.precio_base - monto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        if precio_con_desc < Decimal('0'):
                            precio_con_desc = Decimal('0')
                        precio_mostrar = precio_con_desc
                        info_descuento = {
                            'tipo': 'MONTO_FIJO',
                            'descripcion': f'💰 {promo.nombre}: ${monto} OFF por entrada',
                            'precio_con_descuento': precio_con_desc
                        }
            else:
                # Token no válido, limpiar sesión
                request.session.pop('promo_activa_id', None)
                request.session.pop('promo_token', None)
                request.session.modified = True
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Error calculando descuento en seleccionar_butacas_intercambio')
        # Limpiar sesión en caso de error
        request.session.pop('promo_activa_id', None)
        request.session.pop('promo_token', None)
        request.session.modified = True

    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': filas_ordenadas,
        'precio': precio_mostrar,
        'precio_base': funcion.precio_base,
        'promocion_aplicada': promocion_aplicada,
        'info_descuento': info_descuento,
        'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        'form_action_name': 'ventas:procesar_intercambio',
        'venta_id': venta.id_venta,
        'cantidad_requerida': venta.entradas.count(),
        'promo_2x1': promo_2x1,
        'promo_codigo': promo_codigo,
        'expiracion_iso': expiracion_iso,
    }

    return render(request, 'ventas/seleccionar_butacas.html', context)
