from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from cine.models import Funcion, Butaca, ConfiguracionCine, ExcepcionHorario
from ventas.models import Venta, Entrada, Pago, MetodoPago, CajaSesion
from accounts.models import Cliente
from accounts.utils import get_or_create_consumidor_final
from accounts.decorators import solo_empleados
from promociones.services import calcular_precio_final


@login_required
@solo_empleados
def dashboard_presencial(request):
    """Lista funciones del día agrupadas por película para venta rápida en boletería."""
    
    # ✅ LIMPIEZA AUTOMÁTICA: Expirar ventas pendientes antes de renderizar
    try:
        ventas_expiradas, butacas_liberadas = Venta.objects.limpiar_expiradas()
        if ventas_expiradas > 0:
            # Logging opcional para auditoría
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Dashboard empleado: {ventas_expiradas} ventas expiradas, {butacas_liberadas} butacas liberadas")
    except Exception as e:
        # En caso de error, no bloqueamos el dashboard
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error al limpiar ventas expiradas: {str(e)}")
    
    hoy = timezone.localdate()
    ahora = timezone.now()
    funciones = Funcion.objects.filter(
        fecha_hora__date=hoy,
        fecha_hora__gte=ahora
    ).exclude(estado='INACTIVA').select_related('pelicula', 'sala').prefetch_related('formatos_funcion__formato').order_by('pelicula__titulo', 'fecha_hora')

    # Calcular disponibilidad con la misma lógica real del mapa de butacas
    # (respeta 4D/estándar y butacas en mantenimiento)
    for f in funciones:
        disponibles = f.get_asientos_disponibles_reales()
        f.asientos_disponibles = disponibles
        f.agotada = (f.estado == 'AGOTADA') or (disponibles <= 0)

    agrupado = {}
    for f in funciones:
        titulo = f.pelicula.titulo
        agrupado.setdefault(titulo, []).append(f)

    sesion_caja = CajaSesion.objects.filter(empleado=request.user, estado='ABIERTA').first()
    totales_caja = sesion_caja.get_totales() if sesion_caja else None

    return render(request, 'ventas/presencial/dashboard.html', {
        'agrupado': agrupado,
        'sesion_caja': sesion_caja,
        'totales_caja': totales_caja,
    })


@login_required
@solo_empleados
def seleccionar_butacas_presencial(request, funcion_id):
    """Reutiliza la plantilla de selección de butacas pero apunta al flujo presencial."""
    # Guard: no se puede vender sin caja abierta
    if not CajaSesion.objects.filter(empleado=request.user, estado='ABIERTA').exists():
        messages.warning(request, '⚠️ Debés abrir la caja antes de realizar ventas.')
        return redirect('ventas:apertura_caja')

    funcion = get_object_or_404(Funcion, id=funcion_id)
    sala = funcion.sala

    if funcion.get_asientos_disponibles_reales() <= 0:
        messages.error(request, 'La función está agotada. No hay butacas disponibles.')
        return redirect('ventas:dashboard_presencial')

    butacas = Butaca.objects.filter(sala=sala).order_by('fila', 'numero')
    butacas_ocupadas = Entrada.objects.filter(
        id_funcion=funcion,
        estado__in=['RESERVADA', 'VENDIDA', 'USADA']
    ).values_list('id_butaca_id', flat=True)

    butacas_por_fila = {}
    for butaca in butacas:
        butacas_por_fila.setdefault(butaca.fila, []).append({
            'id': butaca.id,
            'numero': butaca.numero,
            'tipo': butaca.tipo,
            'es_pasillo': butaca.es_pasillo,
            'ocupada': butaca.id in butacas_ocupadas
        })

    # Calcular precio base y posibles promociones automáticas
    precio_mostrar = funcion.precio_base
    promocion_aplicada = None
    info_descuento = None
    promo_2x1 = False
    promo_codigo = None

    total, promo_aplicada, detalle = calcular_precio_final(funcion, 1)
    if promo_aplicada:
        from decimal import Decimal, ROUND_HALF_UP
        
        promocion_aplicada = promo_aplicada
        tipo_aplicado = detalle.get('tipo_aplicado', '').upper()
        promo_codigo = promo_aplicada.codigo
        
        # ✅ CORRECCIÓN: Construir descripción con formato idéntico a vista de clientes
        if tipo_aplicado == '2X1':
            promo_2x1 = True
            precio_mostrar = funcion.precio_base  # En 2x1, el precio unitario no cambia
            info_descuento = {
                'tipo': '2X1',
                'descripcion': f'🎉 {promo_aplicada.nombre}: Pagás 1 y llevás 2',
                'precio_con_descuento': funcion.precio_base
            }
        elif tipo_aplicado == 'PORCENTAJE':
            porcentaje = Decimal(promo_aplicada.valor_descuento or 0) / Decimal(100)
            precio_con_desc = (funcion.precio_base * (Decimal(1) - porcentaje)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            precio_mostrar = precio_con_desc
            ahorro = funcion.precio_base - precio_con_desc
            info_descuento = {
                'tipo': 'PORCENTAJE',
                'descripcion': f'🔥 {promo_aplicada.nombre}: {int(promo_aplicada.valor_descuento)}% OFF (ahorrás ${ahorro})',
                'precio_con_descuento': precio_con_desc
            }
        elif tipo_aplicado == 'MONTO_FIJO':
            monto = Decimal(promo_aplicada.valor_descuento or 0)
            precio_con_desc = (funcion.precio_base - monto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if precio_con_desc < 0: 
                precio_con_desc = Decimal('0.00')
            precio_mostrar = precio_con_desc
            info_descuento = {
                'tipo': 'MONTO_FIJO',
                'descripcion': f'💰 {promo_aplicada.nombre}: ${monto} OFF',
                'precio_con_descuento': precio_con_desc
            }
        else:
            # Fallback por si hay un tipo desconocido
            precio_mostrar = detalle.get('precio_unitario_final', funcion.precio_base)
            info_descuento = {
                'tipo': tipo_aplicado,
                'descripcion': detalle.get('descripcion', promo_aplicada.nombre),
                'precio_con_descuento': precio_mostrar
            }

    # Verificar si la función requiere butacas 4D (tiene formato 4D o 4D en experiencia)
    requiere_4d = False
    try:
        from cine.models.funcion_formato import FuncionFormato
        formatos_funcion = FuncionFormato.objects.filter(funcion=funcion).select_related('formato')
        for ff in formatos_funcion:
            # Verificar si el formato es 4D o 4D en la categoría EXPERIENCIA
            if ff.formato.categoria == 'EXPERIENCIA' and ('4D' in ff.formato.nombre.upper()):
                requiere_4d = True
                break
    except Exception:
        pass

    # Obtener tiempo de reserva desde configuración
    try:
        from cine.models.configuracion_cine import ConfiguracionCine
        tiempo_limite = ConfiguracionCine.load().reserva_tiempo_espera
    except Exception:
        tiempo_limite = 10

    context = {
        'funcion': funcion,
        'sala': sala,
        'butacas_por_fila': sorted(butacas_por_fila.items()),
        'precio': precio_mostrar,  # ✅ Precio CON descuento (si aplica)
        'precio_base': funcion.precio_base,  # ✅ Precio SIN descuento (para comparación)
        'promocion_aplicada': promocion_aplicada,
        'info_descuento': info_descuento,
        'form_action_name': 'ventas:confirmar_venta_presencial',
        'mercadopago_public_key': None,
        'venta_id': None,
        'cantidad_requerida': None,
        'promo_2x1': promo_2x1,  # ✅ Ahora se detecta correctamente
        'promo_codigo': promo_codigo,
        'expiracion_iso': (timezone.now() + timedelta(minutes=int(tiempo_limite))).isoformat(),
        'requiere_4d': requiere_4d,
    }

    return render(request, 'ventas/seleccionar_butacas.html', context)


@login_required
@solo_empleados
def confirmar_venta_presencial(request, funcion_id):
    """Muestra resumen y permite seleccionar medio de pago antes de crear la venta."""
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas_presencial', funcion_id=funcion_id)

    funcion = get_object_or_404(Funcion, id=funcion_id)
    butacas_ids = request.POST.getlist('butacas[]')

    if not butacas_ids:
        messages.error(request, 'Debes seleccionar al menos una butaca.')
        return redirect('ventas:seleccionar_butacas_presencial', funcion_id=funcion_id)

    # Validar butacas
    butacas = []
    for butaca_id in butacas_ids:
        butaca = get_object_or_404(Butaca, id=butaca_id)
        existe = Entrada.objects.filter(
            id_funcion=funcion,
            id_butaca=butaca,
            estado__in=['RESERVADA', 'VENDIDA']
        ).exists()
        if existe:
            messages.error(request, f'Butaca {butaca.fila}{butaca.numero} ya está ocupada.')
            return redirect('ventas:seleccionar_butacas_presencial', funcion_id=funcion_id)
        butacas.append(butaca)

    # Calcular precio total
    cantidad = len(butacas_ids)
    total, promo_aplicada, detalle = calcular_precio_final(funcion, cantidad)
    
    # Calcular precio original para mostrar comparación
    precio_original_total = funcion.precio_base * cantidad
    
    # Guardar en sesión para procesar después
    request.session['venta_presencial'] = {
        'funcion_id': funcion_id,
        'butacas_ids': butacas_ids,
        'total': str(total),
        'cantidad': cantidad,
        'precio_unitario': str(detalle.get('precio_unitario_final', funcion.precio_base)),
    }

    context = {
        'funcion': funcion,
        'butacas': butacas,
        'cantidad': cantidad,
        'total': total,
        'precio_unitario': detalle.get('precio_unitario_final', funcion.precio_base),
        'promocion_aplicada': promo_aplicada,
        'detalle': detalle,
        'precio_original_total': precio_original_total,
    }

    return render(request, 'ventas/presencial/confirmar_pago.html', context)


@login_required
@solo_empleados
def procesar_venta_presencial(request):
    """Crea la venta después de seleccionar medio de pago."""
    if request.method != 'POST':
        messages.error(request, 'Método no permitido.')
        return redirect('ventas:dashboard_presencial')

    # Guard de seguridad: no procesar venta sin caja abierta
    if not CajaSesion.objects.filter(empleado=request.user, estado='ABIERTA').exists():
        messages.warning(request, '⚠️ No podés procesar ventas sin una caja abierta.')
        return redirect('ventas:apertura_caja')

    medio_pago_str = request.POST.get('medio_pago', 'EFECTIVO')
    email_cliente  = request.POST.get('email_cliente', '').strip() or None

    # Empleados solo pueden cobrar en Efectivo o QR/MercadoPago — tarjeta no disponible
    if medio_pago_str == 'TARJETA':
        messages.error(request, '❌ El pago con tarjeta no está habilitado para ventas presenciales.')
        return redirect('ventas:dashboard_presencial')

    datos_venta = request.session.get('venta_presencial')

    if not datos_venta:
        messages.error(request, 'Sesión expirada. Vuelve a seleccionar las butacas.')
        return redirect('ventas:dashboard_presencial')

    funcion_id = datos_venta['funcion_id']
    butacas_ids = datos_venta['butacas_ids']
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    from django.contrib.auth import get_user_model as _get_user_model
    _User = _get_user_model()
    cliente = get_or_create_consumidor_final()
    email_invitado_venta = None
    if email_cliente:
        user_encontrado = _User.objects.filter(email__iexact=email_cliente).first()
        if user_encontrado:
            cliente, _ = Cliente.objects.get_or_create(usuario=user_encontrado)
        else:
            email_invitado_venta = email_cliente  # no tiene cuenta; guardar email para el registro

    # Mapeo: String del formulario → Nombre en MetodoPago
    metodo_map = {
        'EFECTIVO': 'Efectivo',
        'TARJETA': 'Tarjeta',
        'MERCADOPAGO': 'Mercado Pago',
    }
    
    metodo_nombre = metodo_map.get(medio_pago_str, 'Efectivo')

    try:
        # Obtener el MetodoPago desde la BD
        metodo_pago_obj = MetodoPago.objects.get(nombre=metodo_nombre)
        
        # Obtener el total calculado desde la sesión
        from decimal import Decimal
        total_venta = Decimal(datos_venta['total'])
        cantidad_entradas = len(butacas_ids)
        precio_unitario_entrada = Decimal(str(datos_venta.get('precio_unitario') or 0))
        if precio_unitario_entrada <= 0 and cantidad_entradas > 0:
            precio_unitario_entrada = (total_venta / cantidad_entradas).quantize(Decimal('0.01'))
        if precio_unitario_entrada <= 0:
            precio_unitario_entrada = Decimal(str(funcion.precio_base))
        
        with transaction.atomic():
            venta = Venta.objects.create(
                id_cliente=cliente,
                id_empleado=getattr(request.user, 'empleado', None),
                tipo_venta='PRESENCIAL',
                estado='CONFIRMADA',
                id_metodo_pago=metodo_pago_obj,
                total=total_venta,  # ✅ Asignar el total calculado
                email_invitado=email_invitado_venta,
            )

            # Crear entradas y marcar como VENDIDA
            for butaca_id in butacas_ids:
                butaca = get_object_or_404(Butaca, id=butaca_id)

                # Verificar disponibilidad nuevamente
                existe = Entrada.objects.filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado__in=['RESERVADA', 'VENDIDA']
                ).exists()
                if existe:
                    raise Exception(f'Butaca {butaca.fila}{butaca.numero} ya ocupada.')

                Entrada.objects.create(
                    id_venta=venta,
                    id_funcion=funcion,
                    id_sala=funcion.sala,
                    id_butaca=butaca,
                    id_pelicula=funcion.pelicula,
                    estado='VENDIDA',
                    reservado_por=request.user,
                    precio_unitario=precio_unitario_entrada,
                )

            # Crear Pago con FK a MetodoPago
            Pago.objects.create(
                id_venta=venta,
                monto=venta.calcular_total(),
                fecha_pago=timezone.now(),
                estado='COMPLETADO',
                nro_transaccion=f'PRES-{venta.id_venta}',
                id_metodo_pago=metodo_pago_obj
            )

            # Limpiar sesión
            if 'venta_presencial' in request.session:
                del request.session['venta_presencial']

            # Enviar ticket por email en segundo plano si el empleado capturó un correo
            if email_cliente:
                import threading
                from core.services import notificacion_service as _ns
                _venta_id = venta.id_venta
                def _enviar():
                    from ventas.models import Venta as _Venta
                    try:
                        _v = _Venta.objects.get(pk=_venta_id)
                        _ns.enviar_ticket_presencial(_v, email_cliente)
                    except Exception as _e:
                        import logging
                        logging.getLogger(__name__).error(f'Error enviando ticket presencial: {_e}')
                threading.Thread(target=_enviar, daemon=True).start()

            # Redirigir a ticket exitoso en lugar de detalle_venta
            return redirect('ventas:ticket_exitoso', venta_id=venta.id_venta)

    except MetodoPago.DoesNotExist:
        messages.error(
            request, 
            f'❌ Método de pago "{metodo_nombre}" no encontrado. '
            'Ejecuta: python scripts/crear_metodos_pago_completos.py'
        )
        return redirect('ventas:dashboard_presencial')
    except Exception as e:
        messages.error(request, f'Error procesando venta: {e}')
        return redirect('ventas:dashboard_presencial')


@login_required
@solo_empleados
def ver_horarios(request):
    """Muestra todas las funciones próximas (hoy y futuras) organizadas por fecha y película."""
    hoy = timezone.now()
    funciones = Funcion.objects.filter(
        fecha_hora__gte=hoy
    ).exclude(estado='INACTIVA').select_related('pelicula', 'sala').order_by('fecha_hora', 'pelicula__titulo')[:50]  # Limitar a 50

    # Calcular disponibilidad con la misma lógica real del mapa de butacas
    # (respeta 4D/estándar y butacas en mantenimiento)
    for f in funciones:
        disponibles = f.get_asientos_disponibles_reales()
        f.asientos_disponibles = disponibles
        f.agotada = (f.estado == 'AGOTADA') or (disponibles <= 0)

    # Agrupar por fecha
    por_fecha = {}
    for f in funciones:
        fecha_key = f.fecha_hora.date()
        por_fecha.setdefault(fecha_key, []).append(f)

    context = {
        'por_fecha': sorted(por_fecha.items()),
        'total_funciones': funciones.count(),
    }
    return render(request, 'ventas/presencial/horarios.html', context)


@login_required
@solo_empleados
def buscar_cliente(request):
    """Permite buscar clientes por datos personales o codigo de venta y ver su historial de compras."""
    # Expirar ventas pendientes antes de listar historial para evitar zombies.
    try:
        Venta.objects.limpiar_expiradas()
    except Exception:
        # No bloquear la vista por una falla de limpieza.
        pass

    query = request.GET.get('q', '').strip()
    clientes = []
    ventas_cliente = []
    cliente_seleccionado = None

    if query:
        # Buscar ventas por codigo de compra o ID de venta para ubicar al cliente.
        filtros_venta = Q(codigo_compra__icontains=query)
        if query.isdigit():
            filtros_venta |= Q(id_venta=int(query))

        ventas_por_codigo = Venta.objects.filter(filtros_venta).select_related('id_cliente__usuario')
        cliente_ids_por_venta = list(ventas_por_codigo.values_list('id_cliente_id', flat=True).distinct())

        # Buscar clientes por DNI, email, username, nombre o por venta encontrada.
        clientes = Cliente.objects.filter(
            Q(usuario__dni__icontains=query) |
            Q(usuario__email__icontains=query) |
            Q(usuario__username__icontains=query) |
            Q(usuario__first_name__icontains=query) |
            Q(usuario__last_name__icontains=query) |
            Q(pk__in=cliente_ids_por_venta)
        ).select_related('usuario').distinct()[:10]

        # Si hay un cliente_id en la query, mostrar su historial
        cliente_id = request.GET.get('cliente_id')
        if not cliente_id and cliente_ids_por_venta:
            cliente_id = str(cliente_ids_por_venta[0])

        if cliente_id:
            try:
                cliente_seleccionado = Cliente.objects.select_related('usuario').get(pk=cliente_id)
                
                # ✅ FILTRO: Excluir ventas cuyas entradas hayan expirado
                # Obtener tiempo de reserva desde configuración
                try:
                    from cine.models.configuracion_cine import ConfiguracionCine
                    minutos = ConfiguracionCine.load().reserva_tiempo_espera
                except Exception:
                    minutos = 10
                
                threshold = timezone.now() - timedelta(minutes=int(minutos))
                
                ventas_cliente = Venta.objects.filter(
                    id_cliente=cliente_seleccionado
                ).prefetch_related('entradas__id_funcion__pelicula').exclude(
                    # Excluir ventas PENDIENTES cuyas entradas hayan expirado
                    Q(estado='PENDIENTE') & Q(entradas__fecha_creacion__lt=threshold)
                ).order_by('-fecha_compra')[:20]
            except Cliente.DoesNotExist:
                messages.error(request, 'Cliente no encontrado.')

    context = {
        'query': query,
        'clientes': clientes,
        'cliente_seleccionado': cliente_seleccionado,
        'ventas_cliente': ventas_cliente,
    }
    return render(request, 'ventas/presencial/buscar_cliente.html', context)


@login_required
@solo_empleados
def ticket_exitoso(request, venta_id):
    """
    Muestra el ticket de venta exitosa con UN TICKET POR CADA ENTRADA.
    Cada entrada tiene su propio QR único.
    """
    from cine.models.configuracion_cine import ConfiguracionCine
    
    venta = get_object_or_404(
        Venta.objects.select_related('id_empleado__usuario').prefetch_related(
            'entradas__id_funcion__pelicula',
            'entradas__id_funcion__sala',
            'entradas__id_butaca'
        ),
        id_venta=venta_id,
        tipo_venta='PRESENCIAL'
    )
    
    # Verificar que sea personal autorizado (empleado/admin/superuser).
    es_personal = getattr(request.user, 'rol', '') in ['empleado', 'admin'] or request.user.is_superuser
    if not es_personal:
        messages.error(request, 'No tienes permiso para ver este ticket.')
        return redirect('ventas:dashboard_presencial')
    
    # Obtener configuración del cine
    config = ConfiguracionCine.objects.first()
    nombre_cine = config.nombre if config else "CineGest"
    
    # Marcar entradas activas como USADA con save() para preservar auditoría.
    entradas_a_usar = Entrada.objects.filter(
        id_venta=venta,
        estado__in=['VENDIDA', 'RESERVADA', 'ENTREGADA']
    )
    for entrada in entradas_a_usar:
        entrada.estado = 'USADA'
        entrada.save(update_fields=['estado'])

    # Re-evaluar desde BD para que el template vea las entradas actualizadas
    entradas = Entrada.objects.filter(id_venta=venta).select_related(
        'id_funcion__pelicula', 'id_funcion__sala', 'id_butaca'
    )
    
    # Calcular precio por entrada (dividir total entre cantidad)
    total_venta = venta.calcular_total()
    cantidad_entradas = entradas.count()
    precio_por_entrada = total_venta / cantidad_entradas if cantidad_entradas > 0 else 0
    
    context = {
        'venta': venta,
        'entradas': entradas,  # Lista de todas las entradas para iterar
        'nombre_cine': nombre_cine,
        'total_venta': total_venta,
        'precio_por_entrada': precio_por_entrada,
        'cantidad_entradas': cantidad_entradas,
    }
    
    return render(request, 'ventas/presencial/ticket_exitoso.html', context)


# ---------------------------------------------------------------------------
# CAJA  — Apertura, Cierre y Detalle
# ---------------------------------------------------------------------------

@login_required
@solo_empleados
def apertura_caja(request):
    """Abre una nueva sesión de caja para el turno del empleado."""
    sesion_abierta = CajaSesion.objects.filter(empleado=request.user, estado='ABIERTA').first()
    if sesion_abierta:
        messages.info(request, f'Ya tenés una caja abierta desde las {sesion_abierta.fecha_apertura.strftime("%H:%M")}.')
        return redirect('ventas:dashboard_presencial')

    # ── Verificación de horarios del cine ──────────────────────────────────
    now = timezone.localtime(timezone.now())
    today = now.date()
    config = ConfiguracionCine.objects.first()
    cine_cerrado_hoy = False
    excepcion_hoy = None
    fuera_de_horario = False
    horarios_hoy = []

    if config:
        excepcion_hoy = ExcepcionHorario.objects.filter(
            configuracion_cine=config,
            fecha__lte=today
        ).filter(
            Q(fecha_fin__isnull=True, fecha=today) |
            Q(fecha_fin__gte=today)
        ).first()

        if excepcion_hoy and excepcion_hoy.cerrado:
            cine_cerrado_hoy = True
        else:
            horarios_hoy = list(config.get_horarios_dia(now.weekday()))
            # Fuera de horario solo si no hay excepción activa que modifique el horario
            if not excepcion_hoy:
                fuera_de_horario = not config.esta_abierto_en(now)

    if request.method == 'POST':
        if cine_cerrado_hoy:
            messages.error(
                request,
                '🚫 No se puede abrir la caja: el cine está cerrado hoy'
                + (f' — {excepcion_hoy.descripcion}.' if excepcion_hoy and excepcion_hoy.descripcion else '.')
            )
        else:
            try:
                from decimal import Decimal, InvalidOperation
                raw = request.POST.get('fondo_inicial', '0').replace(',', '.').strip()
                fondo = Decimal(raw) if raw else Decimal('0')
                if fondo < 0:
                    raise ValueError('El fondo no puede ser negativo.')
                CajaSesion.objects.create(empleado=request.user, fondo_inicial=fondo)
                messages.success(request, f'Caja abierta con fondo inicial de ${fondo:,.2f}.')
                return redirect('ventas:dashboard_presencial')
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Valor inválido para el fondo: {e}')

    return render(request, 'ventas/presencial/apertura_caja.html', {
        'cine_cerrado_hoy': cine_cerrado_hoy,
        'excepcion_hoy': excepcion_hoy,
        'fuera_de_horario': fuera_de_horario,
        'horarios_hoy': horarios_hoy,
    })


@login_required
@solo_empleados
def cierre_caja(request):
    """Muestra el resumen de la sesión actual y permite cerrar la caja."""
    sesion = CajaSesion.objects.filter(empleado=request.user, estado='ABIERTA').first()
    if not sesion:
        messages.warning(request, 'No hay ninguna caja abierta para cerrar.')
        return redirect('ventas:dashboard_presencial')

    totales = sesion.get_totales()
    ventas_sesion = sesion.get_ventas_sesion()[:50]  # Últimas 50 para la tabla

    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        try:
            raw = request.POST.get('efectivo_fisico_contado', '0').replace(',', '.').strip()
            efectivo_contado = Decimal(raw) if raw else Decimal('0')
        except (InvalidOperation, ValueError):
            messages.error(request, 'Valor inválido para el efectivo contado.')
            return redirect('ventas:cierre_caja')

        monto_esperado = totales['monto_esperado']
        diferencia = efectivo_contado - monto_esperado
        observaciones = request.POST.get('observaciones', '').strip()

        # Si hay diferencia, observaciones es obligatoria (defensa de seguridad server-side)
        if abs(diferencia) >= Decimal('0.01') and not observaciones:
            messages.error(request, 'Debés explicar la diferencia en el campo de observaciones.')
            context = {
                'sesion': sesion,
                'totales': totales,
                'ventas_sesion': ventas_sesion,
            }
            return render(request, 'ventas/presencial/cierre_caja.html', context)

        sesion.fecha_cierre = timezone.now()
        sesion.estado = 'CERRADA'
        sesion.observaciones = observaciones
        sesion.total_efectivo_cerrado = totales['efectivo']
        sesion.total_qr_cerrado = totales['qr']
        sesion.total_ventas_cerrado = totales['ventas']
        sesion.monto_esperado = monto_esperado
        sesion.monto_real_declarado = efectivo_contado
        sesion.diferencia = diferencia
        sesion.save()

        return redirect('ventas:turno_finalizado')

    context = {
        'sesion': sesion,
        'totales': totales,
        'ventas_sesion': ventas_sesion,
    }
    return render(request, 'ventas/presencial/cierre_caja.html', context)


@login_required
@solo_empleados
def turno_finalizado(request):
    """Pantalla de confirmación post-cierre de caja. Muestra resumen e impide nuevas ventas."""
    sesion = CajaSesion.objects.filter(
        empleado=request.user, estado='CERRADA'
    ).order_by('-fecha_cierre').first()

    return render(request, 'ventas/presencial/turno_finalizado.html', {'sesion': sesion})


@login_required
@solo_empleados
def presencial_crear_preferencia_qr(request):
    """
    Crea una Venta en PENDIENTE_PAGO + una preferencia de Mercado Pago para cobro QR presencial.
    Devuelve: {init_point, venta_id} o {error}.
    La venta queda en PENDIENTE_PAGO; el webhook la confirma cuando MP aprueba el pago.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    # Guard: caja abierta
    if not CajaSesion.objects.filter(empleado=request.user, estado='ABIERTA').exists():
        return JsonResponse({'error': 'No hay caja abierta.'}, status=403)

    datos_venta = request.session.get('venta_presencial')
    if not datos_venta:
        return JsonResponse({'error': 'Sesión expirada. Seleccioná las butacas nuevamente.'}, status=400)

    # Leer email opcional del body JSON
    import json as _json
    try:
        _body = _json.loads(request.body or '{}')
        email_cliente_qr = (_body.get('email_cliente') or '').strip() or None
    except Exception:
        email_cliente_qr = None

    funcion_id  = datos_venta['funcion_id']
    butacas_ids = datos_venta['butacas_ids']
    funcion     = get_object_or_404(Funcion, id=funcion_id)
    from django.contrib.auth import get_user_model as _get_user_model
    _User = _get_user_model()
    cliente     = get_or_create_consumidor_final()
    email_invitado_venta = None
    if email_cliente_qr:
        user_encontrado = _User.objects.filter(email__iexact=email_cliente_qr).first()
        if user_encontrado:
            cliente, _ = Cliente.objects.get_or_create(usuario=user_encontrado)
        else:
            email_invitado_venta = email_cliente_qr  # no tiene cuenta; guardar email para el registro

    try:
        from decimal import Decimal
        total_venta = Decimal(datos_venta['total'])
        cantidad_entradas = len(butacas_ids)
        precio_unitario_entrada = Decimal(str(datos_venta.get('precio_unitario') or 0))
        if precio_unitario_entrada <= 0 and cantidad_entradas > 0:
            precio_unitario_entrada = (total_venta / cantidad_entradas).quantize(Decimal('0.01'))
        if precio_unitario_entrada <= 0:
            precio_unitario_entrada = Decimal(str(funcion.precio_base))

        metodo_mp = MetodoPago.objects.filter(nombre__icontains='Mercado Pago').first()
        if not metodo_mp:
            metodo_mp = MetodoPago.objects.create(
                nombre='Mercado Pago', descripcion='Cobro presencial por QR'
            )

        with transaction.atomic():
            venta = Venta.objects.create(
                id_cliente=cliente,
                id_empleado=getattr(request.user, 'empleado', None),
                tipo_venta='PRESENCIAL',
                estado='PENDIENTE_PAGO',
                id_metodo_pago=metodo_mp,
                total=total_venta,
                email_invitado=email_invitado_venta,
            )

            for butaca_id in butacas_ids:
                butaca = get_object_or_404(Butaca, id=butaca_id)
                existe = Entrada.objects.filter(
                    id_funcion=funcion, id_butaca=butaca,
                    estado__in=['RESERVADA', 'VENDIDA']
                ).exists()
                if existe:
                    raise Exception(f'Butaca {butaca.fila}{butaca.numero} ya ocupada.')
                Entrada.objects.create(
                    id_venta=venta, id_funcion=funcion,
                    id_sala=funcion.sala, id_butaca=butaca,
                    id_pelicula=funcion.pelicula,
                    estado='RESERVADA', reservado_por=request.user,
                    precio_unitario=precio_unitario_entrada,
                )

        # Crear preferencia de MP con el monto exacto de la venta
        from ventas.mercadopago_service import MercadoPagoService
        mp_service = MercadoPagoService()
        pref_resp = mp_service.crear_preferencia_pago(venta, request, total_override=total_venta, presencial=True)

        if pref_resp.get('status') != 201:
            # Revertir la venta recién creada para no dejar entradas huérfanas
            venta.delete()
            err_msg = pref_resp.get('response', {}).get('message', 'Error al crear preferencia MP')
            return JsonResponse({'error': err_msg}, status=502)

        response_data = pref_resp['response']
        # Sandbox: usar sandbox_init_point; producción: init_point
        init_point = response_data.get('sandbox_init_point') or response_data.get('init_point')

        # Guardar preference_id y email en sesión para tracking y notificación
        request.session[f'mp_pref_{venta.id_venta}'] = response_data.get('id')
        if email_cliente_qr:
            request.session[f'mp_email_{venta.id_venta}'] = email_cliente_qr
            request.session.modified = True

        return JsonResponse({
            'init_point': init_point,
            'venta_id': venta.id_venta,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@solo_empleados
def presencial_estado_venta(request, venta_id):
    """
    Polling endpoint: devuelve el estado actual de la venta.
    Si está todavía PENDIENTE_PAGO consulta activamente la API de MP por si el
    webhook no llegó (dev sin ngrok), confirmando la venta en ese mismo momento.
    """
    try:
        venta = Venta.objects.get(
            id_venta=venta_id,
            tipo_venta='PRESENCIAL',
            id_empleado=getattr(request.user, 'empleado', None),
        )
    except Venta.DoesNotExist:
        venta = get_object_or_404(Venta, id_venta=venta_id, tipo_venta='PRESENCIAL')

    # Si ya está confirmada, responder directamente
    if venta.estado == 'CONFIRMADA':
        return JsonResponse({
            'estado': 'CONFIRMADA',
            'ticket_url': f'/ventas/presencial/ticket/{venta.id_venta}/',
        })

    # Si sigue en PENDIENTE_PAGO, consultar MP directamente (fallback por si el webhook no llegó)
    if venta.estado == 'PENDIENTE_PAGO':
        try:
            from ventas.mercadopago_service import MercadoPagoService
            from ventas.models import Pago
            mp_service = MercadoPagoService()
            search_result = mp_service.sdk.payment().search({
                'external_reference': str(venta.id_venta),
                'status': 'approved',
            })
            if (search_result.get('status') == 200 and
                    search_result['response'].get('results')):
                # Pago aprobado en MP — confirmar la venta (mismo flujo que el webhook)
                metodo_mp = MetodoPago.objects.filter(nombre__icontains='Mercado Pago').first()
                payment_data = search_result['response']['results'][0]
                payment_id = payment_data.get('id')
                with transaction.atomic():
                    venta.estado = 'CONFIRMADA'
                    venta.id_metodo_pago = metodo_mp
                    venta.save(update_fields=['estado', 'id_metodo_pago'])
                    Pago.objects.get_or_create(
                        id_venta=venta,
                        defaults={
                            'monto': venta.total,
                            'estado': 'COMPLETADO',
                            'nro_transaccion': str(payment_id),
                            'id_metodo_pago': metodo_mp,
                        }
                    )

                # Enviar ticket por email si el empleado capturó uno antes de generar el QR
                email_qr = request.session.pop(f'mp_email_{venta_id}', None)
                if email_qr:
                    import threading
                    from core.services import notificacion_service as _ns
                    def _enviar_qr():
                        from ventas.models import Venta as _Venta
                        try:
                            _v = _Venta.objects.get(pk=venta_id)
                            _ns.enviar_ticket_presencial(_v, email_qr)
                        except Exception as _e:
                            import logging
                            logging.getLogger(__name__).error(f'Error enviando ticket QR presencial: {_e}')
                    threading.Thread(target=_enviar_qr, daemon=True).start()

                return JsonResponse({
                    'estado': 'CONFIRMADA',
                    'ticket_url': f'/ventas/presencial/ticket/{venta.id_venta}/',
                })
        except Exception as e:
            # No interrumpir el polling si la consulta a MP falla
            print(f'[presencial_estado_venta] Error consultando MP: {e}')

    return JsonResponse({
        'estado': venta.estado,
        'ticket_url': None,
    })


@login_required
@solo_empleados
def presencial_cancelar_venta_qr(request, venta_id):
    """
    Cancela una venta en PENDIENTE_PAGO creada para cobro QR (si el empleado la descarta).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        venta = Venta.objects.get(
            id_venta=venta_id,
            estado='PENDIENTE_PAGO',
            tipo_venta='PRESENCIAL',
        )
        with transaction.atomic():
            entradas_a_cancelar = Entrada.objects.filter(
                id_venta=venta,
                estado__in=['PENDIENTE', 'RESERVADA', 'VENDIDA', 'ENTREGADA']
            )
            for entrada in entradas_a_cancelar:
                entrada.estado = 'CANCELADA'
                entrada.save(update_fields=['estado'])

            venta.estado = 'CANCELADA'
            venta.save(update_fields=['estado'])
        return JsonResponse({'ok': True})
    except Venta.DoesNotExist:
        return JsonResponse({'error': 'Venta no encontrada o ya procesada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
