from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from cine.models import Funcion, Butaca
from ventas.models import Venta, Entrada, Pago, MetodoPago
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

    agrupado = {}
    for f in funciones:
        titulo = f.pelicula.titulo
        agrupado.setdefault(titulo, []).append(f)

    return render(request, 'ventas/presencial/dashboard.html', {'agrupado': agrupado})


@login_required
@solo_empleados
def seleccionar_butacas_presencial(request, funcion_id):
    """Reutiliza la plantilla de selección de butacas pero apunta al flujo presencial."""
    funcion = get_object_or_404(Funcion, id=funcion_id)
    sala = funcion.sala

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

    # Verificar si la función requiere butacas 4D (tiene formato 4DX o 4D en experiencia)
    requiere_4d = False
    try:
        from cine.models.funcion_formato import FuncionFormato
        formatos_funcion = FuncionFormato.objects.filter(funcion=funcion).select_related('formato')
        for ff in formatos_funcion:
            # Verificar si el formato es 4DX o 4D en la categoría EXPERIENCIA
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

    medio_pago_str = request.POST.get('medio_pago', 'EFECTIVO')
    datos_venta = request.session.get('venta_presencial')

    if not datos_venta:
        messages.error(request, 'Sesión expirada. Vuelve a seleccionar las butacas.')
        return redirect('ventas:dashboard_presencial')

    funcion_id = datos_venta['funcion_id']
    butacas_ids = datos_venta['butacas_ids']
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    cliente = get_or_create_consumidor_final()

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
        
        with transaction.atomic():
            venta = Venta.objects.create(
                id_cliente=cliente,
                id_empleado=getattr(request.user, 'empleado', None),
                tipo_venta='PRESENCIAL',
                estado='CONFIRMADA',
                id_metodo_pago=metodo_pago_obj,
                total=total_venta  # ✅ Asignar el total calculado
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
                    reservado_por=request.user
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
    """Permite buscar clientes por DNI, email o nombre y ver su historial de compras."""
    query = request.GET.get('q', '').strip()
    clientes = []
    ventas_cliente = []
    cliente_seleccionado = None

    if query:
        # Buscar clientes por DNI, email, username, nombre
        clientes = Cliente.objects.filter(
            Q(usuario__dni__icontains=query) |
            Q(usuario__email__icontains=query) |
            Q(usuario__username__icontains=query) |
            Q(usuario__first_name__icontains=query) |
            Q(usuario__last_name__icontains=query)
        ).select_related('usuario')[:10]

        # Si hay un cliente_id en la query, mostrar su historial
        cliente_id = request.GET.get('cliente_id')
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
    
    # Verificar que sea el empleado que procesó la venta o admin
    if not (venta.id_empleado and venta.id_empleado.usuario == request.user) and not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para ver este ticket.')
        return redirect('ventas:dashboard_presencial')
    
    # Obtener configuración del cine
    config = ConfiguracionCine.objects.first()
    nombre_cine = config.nombre if config else "CineGest"
    
    # Marcar entradas como USADA (ticket impreso = acceso válido)
    entradas = venta.entradas.all()
    for entrada in entradas:
        if entrada.estado in ['VENDIDA', 'RESERVADA', 'ENTREGADA']:
            entrada.estado = 'USADA'
            entrada.save()
    
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
