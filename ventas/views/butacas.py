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
    
    # ✅ LIMPIEZA AUTOMÁTICA: Expirar ventas pendientes antes de calcular disponibilidad
    from ventas.models import Venta
    try:
        ventas_expiradas, butacas_liberadas = Venta.objects.limpiar_expiradas()
    except Exception:
        # Si algo falla aquí no queremos romper la vista
        pass
    
    # Liberar reservas expiradas antes de calcular disponibilidad (check-on-access)
    try:
        liberar_reservas_expiradas()
    except Exception:
        # Si algo falla aquí no queremos romper la vista; la liberación
        # puede reintentarse mediante el management command.
        pass
    funcion = get_object_or_404(Funcion, id=funcion_id)
    sala = funcion.sala

    if funcion.get_asientos_disponibles_reales() <= 0:
        messages.error(request, 'La función está agotada. No hay butacas disponibles.')
        return redirect('cine:cartelera')
    
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
            'ocupada': butaca.id in butacas_ocupadas,
            'en_mantenimiento': butaca.en_mantenimiento,
        })
    
    # Ordenar las filas alfabéticamente
    filas_ordenadas = sorted(butacas_por_fila.items())
    
    try:
        tiempo_limite = ConfiguracionCine.load().reserva_tiempo_espera
    except Exception:
        tiempo_limite = 10

    # Timer persistente en BD: reutilizar/crear venta provisional para esta función.
    # De esta forma, al hacer F5 no se reinicia el contador.
    venta_provisional = None
    session_key_reserva = f'reserva_venta_funcion_{funcion.id}'
    try:
        from ventas.models import Venta, MetodoPago

        now = timezone.now()
        venta_id_session = request.session.get(session_key_reserva)
        if venta_id_session:
            venta_provisional = Venta.objects.filter(
                id_venta=venta_id_session,
                id_cliente__usuario=request.user,
                estado='PENDIENTE',
                activo=True,
            ).first()

        if venta_provisional is None:
            from accounts.models import Cliente
            cliente, _ = Cliente.objects.get_or_create(
                usuario=request.user,
                defaults={'fecha_nacimiento': None}
            )

            metodo_pago = MetodoPago.objects.filter(
                nombre__icontains='Mercado Pago'
            ).first() or MetodoPago.objects.filter(
                nombre__icontains='Online'
            ).first()

            if not metodo_pago:
                metodo_pago = MetodoPago.objects.create(
                    nombre='Mercado Pago',
                    descripcion='Pago procesado por Mercado Pago'
                )

            cupon_yield = None
            promo_token = request.session.get('promo_token')
            if promo_token:
                try:
                    from promociones.models.cuponGenerado import CuponGenerado
                    cupon_yield = CuponGenerado.objects.filter(token=str(promo_token), usado=True).first()
                except Exception:
                    cupon_yield = None

            venta_provisional = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='ONLINE',
                estado='PENDIENTE',
                id_metodo_pago=metodo_pago,
                total=0,
                cupon_utilizado=cupon_yield,
            )
            request.session[session_key_reserva] = venta_provisional.id_venta
            request.session.modified = True

        expiracion = venta_provisional.fecha_compra + timedelta(minutes=int(tiempo_limite))
        if expiracion <= now:
            expiracion = now
        expiracion_iso = expiracion.isoformat()
    except Exception:
        venta_provisional = None
        expiracion_iso = (timezone.now() + timedelta(minutes=int(tiempo_limite))).isoformat()

    # Calcular precio con descuento SOLO si hay promoción activa desde link (con token válido)
    precio_mostrar = funcion.precio_base
    promocion_aplicada = None
    info_descuento = None
    promo_2x1 = False
    promo_codigo = None
    
    import logging
    logger = logging.getLogger(__name__)

    # ──────────────────────────────────────────────────────────────────────────
    # JERARQUÍA DE PROMOCIONES
    # ──────────────────────────────────────────────────────────────────────────
    # Paso 1: Verificar si hay una promo automática de vínculo específico.
    #         Si existe, tiene prioridad máxima y hace que cualquier cupón de
    #         sesión sea incompatible (Regla de Exclusión de Cupones).
    # Paso 2: Si NO hay promo específica, aplicar cupón de sesión si es válido.
    # Paso 3: Si tampoco hay cupón, aplicar la mejor promo global (si existe).
    # ──────────────────────────────────────────────────────────────────────────
    from promociones.services import obtener_mejor_promocion, tiene_vinculo_especifico
    from decimal import Decimal, ROUND_HALF_UP

    def _aplicar_promo_en_contexto(p):
        """Rellena precio_mostrar / info_descuento / promo_2x1 / promo_codigo a partir de 'p'."""
        nonlocal precio_mostrar, info_descuento, promo_2x1, promo_codigo
        tipo = str(p.tipo_descuento).upper().strip()
        promo_codigo = p.codigo
        if tipo == '2X1':
            promo_2x1 = True
            info_descuento = {
                'tipo': '2X1',
                'descripcion': f'🎉 {p.nombre}: Pagás 1 y llevás 2',
                'precio_con_descuento': funcion.precio_base,
            }
        elif tipo == 'PORCENTAJE':
            pct = Decimal(p.valor_descuento or 0) / Decimal(100)
            precio_con_desc = (funcion.precio_base * (Decimal(1) - pct)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            precio_mostrar = precio_con_desc
            info_descuento = {
                'tipo': 'PORCENTAJE',
                'descripcion': f'🔥 {p.nombre}: {int(p.valor_descuento)}% OFF (ahorrás ${funcion.precio_base - precio_con_desc})',
                'precio_con_descuento': precio_con_desc,
            }
        elif tipo == 'MONTO_FIJO':
            monto = Decimal(p.valor_descuento or 0)
            precio_con_desc = max(funcion.precio_base - monto, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            precio_mostrar = precio_con_desc
            info_descuento = {
                'tipo': 'MONTO_FIJO',
                'descripcion': f'💰 {p.nombre}: ${monto} OFF',
                'precio_con_descuento': precio_con_desc,
            }

    try:
        # ── Paso 1: buscar mejor promo automática con jerarquía de especificidad ──
        promo_auto, es_auto_especifica = obtener_mejor_promocion(funcion)

        if es_auto_especifica:
            # Promo de VÍNCULO ESPECÍFICO → máxima prioridad, cupones incompatibles
            logger.info(f'[SELECCIONAR_BUTACAS] Promo específica activa: {promo_auto.codigo}. '
                        f'Cupones de sesión descartados.')
            # Limpiar cualquier cupón de sesión (son incompatibles)
            request.session.pop('promo_activa_id', None)
            request.session.pop('promo_token', None)
            request.session.modified = True
            promocion_aplicada = promo_auto
            _aplicar_promo_en_contexto(promo_auto)

        else:
            # ── Paso 2: intentar cupón de sesión (solo si NO hay promo específica) ──
            promo_id = request.session.get('promo_activa_id')
            promo_token = request.session.get('promo_token')
            logger.info(f'[SELECCIONAR_BUTACAS] promo_id sesión: {promo_id}, token: {promo_token}')

            cupon_aplicado = False
            if promo_id and promo_token:
                if not getattr(request.user, 'es_perfil_completo', True):
                    logger.info('[SELECCIONAR_BUTACAS] Cupón bloqueado: perfil incompleto')
                    request.session.pop('promo_activa_id', None)
                    request.session.pop('promo_token', None)
                    request.session.modified = True
                else:
                    from promociones.models.cuponGenerado import CuponGenerado
                    cupon = CuponGenerado.objects.filter(token=str(promo_token), usado=True).first()
                    logger.info(f'[SELECCIONAR_BUTACAS] Cupón encontrado: {cupon is not None}')
                    if cupon:
                        promo = Promocion.objects.filter(pk=promo_id).first()
                        if promo:
                            logger.info(f'[SELECCIONAR_BUTACAS] Aplicando cupón: {promo.codigo}')
                            promocion_aplicada = promo
                            cupon_aplicado = True
                            tipo = str(promo.tipo_descuento).upper().strip()
                            promo_codigo = promo.codigo
                            if tipo == '2X1':
                                promo_2x1 = True
                                info_descuento = {
                                    'tipo': '2X1',
                                    'descripcion': f'🎉 {promo.nombre}: Pagás 1 y llevás 2 entradas',
                                    'precio_con_descuento': funcion.precio_base,
                                }
                            elif tipo == 'PORCENTAJE':
                                pct = Decimal(promo.valor_descuento or 0) / Decimal(100)
                                precio_con_desc = (funcion.precio_base * (Decimal(1) - pct)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                precio_mostrar = precio_con_desc
                                info_descuento = {
                                    'tipo': 'PORCENTAJE',
                                    'descripcion': f'💰 {promo.nombre}: {promo.valor_descuento}% OFF (ahorrás ${funcion.precio_base - precio_con_desc})',
                                    'precio_con_descuento': precio_con_desc,
                                }
                            elif tipo == 'MONTO_FIJO':
                                monto = Decimal(promo.valor_descuento or 0)
                                precio_con_desc = max(funcion.precio_base - monto, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                precio_mostrar = precio_con_desc
                                info_descuento = {
                                    'tipo': 'MONTO_FIJO',
                                    'descripcion': f'💰 {promo.nombre}: ${monto} OFF',
                                    'precio_con_descuento': precio_con_desc,
                                }
                    else:
                        logger.info('[SELECCIONAR_BUTACAS] Cupón no válido, limpiando sesión')
                        request.session.pop('promo_activa_id', None)
                        request.session.pop('promo_token', None)
                        request.session.modified = True
            elif promo_id or promo_token:
                logger.info('[SELECCIONAR_BUTACAS] Sesión incompleta, limpiando')
                request.session.pop('promo_activa_id', None)
                request.session.pop('promo_token', None)
                request.session.modified = True

            # ── Paso 3: si no hubo cupón, usar la mejor promo global ──
            if not cupon_aplicado and promo_auto:
                logger.info(f'[SELECCIONAR_BUTACAS] Aplicando promo global: {promo_auto.codigo}')
                promocion_aplicada = promo_auto
                _aplicar_promo_en_contexto(promo_auto)

    except Exception:
        logger.exception('Error calculando promoción en seleccionar_butacas')
        request.session.pop('promo_activa_id', None)
        request.session.pop('promo_token', None)
        request.session.modified = True

    logger.info(f'[SELECCIONAR_BUTACAS] Resultado: precio={precio_mostrar}, promo={getattr(promocion_aplicada, "codigo", None)}')

    # Verificar si la función requiere butacas 4D (tiene formato 4D o 4D en experiencia)
    requiere_4d = False
    try:
        from cine.models.funcion_formato import FuncionFormato
        formatos_funcion = FuncionFormato.objects.filter(funcion=funcion).select_related('formato')
        for ff in formatos_funcion:
            # Verificar si el formato es 4D, 4D o D-BOX en la categoría EXPERIENCIA
            formato_nombre_upper = ff.formato.nombre.upper()
            if ff.formato.categoria == 'EXPERIENCIA' and ('4D' in formato_nombre_upper or 'D-BOX' in formato_nombre_upper):
                requiere_4d = True
                break
    except Exception as e:
        logger.exception('Error verificando formatos 4D')
    
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
        'provisional_venta_id': venta_provisional.id_venta if venta_provisional else None,
        'cantidad_requerida': None,
        'promo_2x1': promo_2x1,  # ✅ Usar el valor detectado (automática o por cupón)
        'promo_codigo': promo_codigo,  # ✅ Usar el valor detectado
        'expiracion_iso': expiracion_iso,
        'requiere_4d': requiere_4d,
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

    if funcion.get_asientos_disponibles_reales() <= 0:
        messages.error(request, 'La función está agotada. No hay butacas disponibles.')
        return redirect('cine:cartelera')

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
            'ocupada': butaca.id in butacas_ocupadas,
            'en_mantenimiento': butaca.en_mantenimiento,
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

    # Calcular precio con descuento respetando la jerarquía de especificidad
    precio_mostrar = funcion.precio_base
    promocion_aplicada = None
    info_descuento = None
    promo_2x1 = False
    promo_codigo = None

    try:
        from promociones.services import obtener_mejor_promocion
        from decimal import Decimal, ROUND_HALF_UP

        promo_auto, es_auto_especifica = obtener_mejor_promocion(funcion)

        if es_auto_especifica:
            # Promo de vínculo específico → descarta cupón de sesión
            request.session.pop('promo_activa_id', None)
            request.session.pop('promo_token', None)
            request.session.modified = True
            promocion_aplicada = promo_auto
        else:
            # Sin promo específica → aplicar cupón de sesión si existe
            promo_id = request.session.get('promo_activa_id')
            promo_token = request.session.get('promo_token')
            if promo_id and promo_token:
                from promociones.models.cuponGenerado import CuponGenerado
                cupon = CuponGenerado.objects.filter(token=str(promo_token), usado=True).first()
                if cupon:
                    promo = Promocion.objects.filter(pk=promo_id).first()
                    if promo:
                        promocion_aplicada = promo
                else:
                    request.session.pop('promo_activa_id', None)
                    request.session.pop('promo_token', None)
                    request.session.modified = True
            # Fallback: promo global si no hay cupón
            if not promocion_aplicada and promo_auto:
                promocion_aplicada = promo_auto

        if promocion_aplicada:
            cantidad_venta = venta.entradas.count()
            tipo = str(promocion_aplicada.tipo_descuento).upper().strip()
            promo_codigo = promocion_aplicada.codigo
            if tipo == '2X1':
                promo_2x1 = True
                entradas_pagar = (cantidad_venta // 2) + (cantidad_venta % 2)
                info_descuento = {
                    'tipo': '2X1',
                    'descripcion': f'🎉 {promocion_aplicada.nombre}: Pagás {entradas_pagar} y llevás {cantidad_venta} entradas',
                    'precio_con_descuento': funcion.precio_base * entradas_pagar,
                }
            elif tipo == 'PORCENTAJE':
                pct = Decimal(promocion_aplicada.valor_descuento or 0) / Decimal(100)
                precio_con_desc = (funcion.precio_base * (Decimal(1) - pct)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                precio_mostrar = precio_con_desc
                info_descuento = {
                    'tipo': 'PORCENTAJE',
                    'descripcion': f'💰 {promocion_aplicada.nombre}: {promocion_aplicada.valor_descuento}% OFF (ahorrás ${funcion.precio_base - precio_con_desc} por entrada)',
                    'precio_con_descuento': precio_con_desc,
                }
            elif tipo == 'MONTO_FIJO':
                monto = Decimal(promocion_aplicada.valor_descuento or 0)
                precio_con_desc = max(funcion.precio_base - monto, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                precio_mostrar = precio_con_desc
                info_descuento = {
                    'tipo': 'MONTO_FIJO',
                    'descripcion': f'💰 {promocion_aplicada.nombre}: ${monto} OFF por entrada',
                    'precio_con_descuento': precio_con_desc,
                }
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Error calculando descuento en seleccionar_butacas_intercambio')
        request.session.pop('promo_activa_id', None)
        request.session.pop('promo_token', None)
        request.session.modified = True

    # Verificar si la función requiere butacas 4D (tiene formato 4D o 4D en experiencia)
    requiere_4d = False
    try:
        from cine.models.funcion_formato import FuncionFormato
        formatos_funcion = FuncionFormato.objects.filter(funcion=funcion).select_related('formato')
        for ff in formatos_funcion:
            # Verificar si el formato es 4D, 4D o D-BOX en la categoría EXPERIENCIA
            formato_nombre_upper = ff.formato.nombre.upper()
            if ff.formato.categoria == 'EXPERIENCIA' and ('4D' in formato_nombre_upper or 'D-BOX' in formato_nombre_upper):
                requiere_4d = True
                break
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Error verificando formatos 4D en intercambio')

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
        'requiere_4d': requiere_4d,
    }

    return render(request, 'ventas/seleccionar_butacas.html', context)


from django.http import JsonResponse

@login_required
def verificar_butacas_ocupadas(request, funcion_id):
    """Vista API que retorna las butacas ocupadas para sincronización en tiempo real"""
    try:
        funcion = get_object_or_404(Funcion, id=funcion_id)
        
        # Liberar reservas expiradas antes de verificar
        try:
            liberar_reservas_expiradas()
        except Exception:
            pass
        
        # Obtener butacas ocupadas (incluye PENDIENTE, RESERVADA, VENDIDA)
        butacas_ocupadas = list(
            Entrada.objects.filter(
                id_funcion=funcion,
                estado__in=EstadoEntrada.ESTADOS_OCUPADOS
            ).values_list('id_butaca_id', flat=True)
        )

        # Obtener butacas en mantenimiento de esta sala
        butacas_en_mantenimiento = list(
            Butaca.objects.filter(sala=funcion.sala, en_mantenimiento=True)
            .values_list('id', flat=True)
        )

        return JsonResponse({
            'success': True,
            'butacas_ocupadas': butacas_ocupadas,
            'butacas_en_mantenimiento': butacas_en_mantenimiento,
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Error verificando butacas ocupadas')
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
