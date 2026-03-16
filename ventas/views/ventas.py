"""
Vistas para gestionar ventas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from ventas.models import Venta, Entrada
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from accounts.models import Cliente
from cine.models import Funcion, Butaca
from ventas.forms import IntercambioEntradaForm
from ventas.services import obtener_funciones_candidatas
from ventas.models import PoliticaReembolso
from django.db.models import Q
from django.db.models import Count, Sum
from cine.models.configuracion_cine import ConfiguracionCine


@login_required
def mis_ventas(request):
    """Vista para que el cliente vea sus ventas/compras"""
    # Expirar pendientes al cargar historial para evitar mostrar ventas zombie.
    try:
        Venta.objects.limpiar_expiradas()
    except Exception:
        # No impedir el acceso al historial si falla la limpieza.
        pass

    # Bloquear acceso a empleados
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados no tienen acceso a "Mis Ventas". Usa el módulo de búsqueda de clientes.')
        return redirect('accounts:dashboard')
    
    # Obtener todas las ventas del cliente actual
    # ✅ OPTIMIZACIÓN: Agregado select_related para evitar N+1 queries
    ventas_todas = Venta.objects.filter(
        id_cliente__usuario=request.user
    ).select_related(
        'id_cliente__usuario',
        'pago',
        'pago__id_metodo_pago',
        'id_empleado__usuario'
    ).prefetch_related('entradas', 'entradas__id_funcion', 'entradas__id_pelicula', 'intercambios').order_by('-fecha_compra')
    
    # Leer filtro de categoría desde GET (confirmadas, intercambiadas, expiradas)
    requested_filter = request.GET.get('filter', 'confirmadas')
    # Compatibilidad hacia atrás: URLs viejas con "canceladas" ahora se tratan como "expiradas"
    if requested_filter == 'canceladas':
        requested_filter = 'expiradas'
    
    # Leer término de búsqueda
    search_query = request.GET.get('search', '').strip()

    # Paginación
    page_number = request.GET.get('page', 1)
    page_size = 5  # items por página

    # Construir queryset del historial según el filtro solicitado
    if requested_filter == 'confirmadas':
        # Mostrar solo ventas CONFIRMADAS sin intercambios realizados
        ventas_historial_qs = ventas_todas.filter(
            estado='CONFIRMADA'
        ).exclude(
            entradas__estado='CANCELADA'
        ).exclude(
            intercambios__isnull=False
        ).distinct()
    elif requested_filter == 'intercambiadas':
        # Mostrar ventas que tienen al menos un registro de intercambio
        ventas_historial_qs = ventas_todas.filter(
            intercambios__isnull=False
        ).distinct()
    elif requested_filter == 'expiradas':
        # Mostrar ventas vencidas por timeout de reserva
        ventas_historial_qs = ventas_todas.filter(
            estado='EXPIRADA'
        ).distinct()
    else:
        # fallback: mostrar todas confirmadas sin intercambios
        ventas_historial_qs = ventas_todas.filter(
            estado='CONFIRMADA'
        ).exclude(
            entradas__estado='CANCELADA'
        ).exclude(
            intercambios__isnull=False
        ).distinct()

    # Aplicar búsqueda si hay término de búsqueda
    if search_query:
        ventas_historial_qs = ventas_historial_qs.filter(
            Q(id_venta__icontains=search_query) |  # Buscar por ID de compra
            Q(codigo_compra__icontains=search_query) |  # Buscar por código de compra
            Q(entradas__id_pelicula__titulo__icontains=search_query) |  # Buscar por título de película
            Q(id_cliente__usuario__first_name__icontains=search_query) |  # Buscar por nombre
            Q(id_cliente__usuario__last_name__icontains=search_query)  # Buscar por apellido
        ).distinct()

    # Historial paginator (según el queryset filtrado)
    paginator = Paginator(ventas_historial_qs, page_size)
    try:
        ventas_page = paginator.page(page_number)
    except PageNotAnInteger:
        ventas_page = paginator.page(1)
    except EmptyPage:
        ventas_page = paginator.page(paginator.num_pages)

    # Exponer total real abonado por venta para UI:
    # prioridad pago.monto (fuente financiera) > venta.total persistido.
    for _venta in ventas_page.object_list:
        monto_real = None
        if getattr(_venta, 'pago', None) and _venta.pago and _venta.pago.monto is not None:
            monto_real = _venta.pago.monto
        elif _venta.total is not None:
            monto_real = _venta.total
        else:
            monto_real = _venta.calcular_total()
        _venta.total_real_abonado = monto_real
    
    context = {
        'ventas': ventas_todas,
        'ventas_historial': ventas_historial_qs,
        'ventas_page': ventas_page,
        'current_filter': requested_filter,
        'search_query': search_query,
    }
    
    # Si la petición es AJAX, devolvemos solo el partial del historial
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'ventas/_ventas_historial.html', context)

    return render(request, 'ventas/mis_ventas.html', context)


@login_required
def lista_ventas(request):
    """Lista plana y paginada de ventas para administradores y empleados."""
    es_admin = (
        getattr(request.user, 'is_superuser', False)
        or getattr(request.user, 'is_staff', False)
        or getattr(request.user, 'rol', '') == 'admin'
    )
    es_empleado = getattr(request.user, 'rol', '') == 'empleado'

    if not (es_admin or es_empleado):
        messages.error(request, 'No tienes permisos para ver el listado de ventas.')
        return redirect('accounts:dashboard')

    ventas_qs = Venta.objects.select_related(
        'id_cliente__usuario',
        'id_empleado__usuario',
        'id_metodo_pago',
        'pago',
    ).annotate(
        cantidad_entradas=Count('entradas', distinct=True),
        total_entradas_precio=Sum('entradas__precio_unitario'),
    ).order_by('-fecha_compra')

    empleados_disponibles = []
    metodos_pago = []

    filtro_empleado = request.GET.get('empleado', '').strip()
    filtro_desde = request.GET.get('fecha_desde', '').strip()
    filtro_hasta = request.GET.get('fecha_hasta', '').strip()
    filtro_medio_pago = request.GET.get('medio_pago', '').strip()
    filtro_estado = request.GET.get('estado', '').strip()
    search_query = request.GET.get('search', '').strip()

    if es_admin:
        from accounts.models import Empleado
        from ventas.models import MetodoPago

        empleados_disponibles = Empleado.objects.select_related('usuario').order_by(
            'usuario__first_name', 'usuario__last_name', 'usuario__username'
        )
        metodos_pago = MetodoPago.objects.exclude(nombre__icontains='tarjeta').order_by('nombre')

        if filtro_empleado:
            if filtro_empleado == 'sin_empleado':
                ventas_qs = ventas_qs.filter(id_empleado__isnull=True)
            else:
                ventas_qs = ventas_qs.filter(id_empleado_id=filtro_empleado)

        if filtro_desde:
            ventas_qs = ventas_qs.filter(fecha_compra__date__gte=filtro_desde)

        if filtro_hasta:
            ventas_qs = ventas_qs.filter(fecha_compra__date__lte=filtro_hasta)

        if filtro_medio_pago:
            ventas_qs = ventas_qs.filter(id_metodo_pago_id=filtro_medio_pago)

        if filtro_estado:
            ventas_qs = ventas_qs.filter(estado=filtro_estado)

        if search_query:
            ventas_qs = ventas_qs.filter(
                Q(id_venta__icontains=search_query)
                | Q(codigo_compra__icontains=search_query)
                | Q(id_cliente__usuario__first_name__icontains=search_query)
                | Q(id_cliente__usuario__last_name__icontains=search_query)
                | Q(id_cliente__usuario__username__icontains=search_query)
                | Q(email_invitado__icontains=search_query)
                | Q(entradas__id_pelicula__titulo__icontains=search_query)
            ).distinct()
    else:
        try:
            empleado_actual = request.user.empleado
        except Exception:
            messages.error(request, 'No se encontró el perfil de empleado asociado a tu usuario.')
            return redirect('accounts:dashboard')

        hoy = timezone.localdate()
        ventas_qs = ventas_qs.filter(
            id_empleado=empleado_actual,
            fecha_compra__date=hoy,
            tipo_venta='PRESENCIAL',
        )

        if filtro_estado:
            ventas_qs = ventas_qs.filter(estado=filtro_estado)

        if search_query:
            ventas_qs = ventas_qs.filter(
                Q(id_venta__icontains=search_query)
                | Q(codigo_compra__icontains=search_query)
                | Q(id_cliente__usuario__first_name__icontains=search_query)
                | Q(id_cliente__usuario__last_name__icontains=search_query)
                | Q(id_cliente__usuario__username__icontains=search_query)
                | Q(email_invitado__icontains=search_query)
                | Q(entradas__id_pelicula__titulo__icontains=search_query)
            ).distinct()

    paginator = Paginator(ventas_qs, 15)
    page_number = request.GET.get('page', 1)
    try:
        ventas_page = paginator.page(page_number)
    except PageNotAnInteger:
        ventas_page = paginator.page(1)
    except EmptyPage:
        ventas_page = paginator.page(paginator.num_pages)

    # Total mostrado robusto: evita ver 0 en ventas confirmadas por datos legacy.
    for venta in ventas_page.object_list:
        monto_mostrado = None
        if getattr(venta, 'pago', None) and venta.pago and venta.pago.monto is not None and venta.pago.monto > 0:
            monto_mostrado = venta.pago.monto
        elif venta.total is not None and venta.total > 0:
            monto_mostrado = venta.total
        elif getattr(venta, 'total_entradas_precio', None) is not None and venta.total_entradas_precio > 0:
            monto_mostrado = venta.total_entradas_precio
        else:
            monto_mostrado = venta.total or 0

        venta.total_mostrado = monto_mostrado

    context = {
        'ventas_page': ventas_page,
        'es_admin': es_admin,
        'es_empleado': es_empleado,
        'empleados_disponibles': empleados_disponibles,
        'metodos_pago': metodos_pago,
        'filtro_empleado': filtro_empleado,
        'filtro_desde': filtro_desde,
        'filtro_hasta': filtro_hasta,
        'filtro_medio_pago': filtro_medio_pago,
        'filtro_estado': filtro_estado,
        'search_query': search_query,
        'hoy': timezone.localdate(),
    }
    return render(request, 'ventas/lista_ventas.html', context)


def _venta_con_promo_especifica(venta):
    """Devuelve True si la función de la venta tiene activa una promoción de vínculo específico."""
    try:
        entrada = venta.entradas.exclude(estado='CANCELADA').select_related('id_funcion').first()
        if not entrada:
            return False
        from promociones.services import obtener_mejor_promocion
        _, es_especifica = obtener_mejor_promocion(entrada.id_funcion)
        return es_especifica
    except Exception:
        return False


@login_required
def detalle_venta(request, venta_id):
    """Vista para ver el detalle de una venta específica"""
    # Permitir que el cliente vea sus ventas O que un empleado vea cualquier venta (búsqueda de clientes)
    venta = get_object_or_404(Venta, id_venta=venta_id)
    
    # Verificar permisos: debe ser el cliente dueño O empleado O admin
    es_cliente = venta.id_cliente.usuario == request.user
    es_empleado = hasattr(request.user, 'rol') and request.user.rol == 'empleado'
    es_admin = getattr(request.user, 'is_superuser', False) or getattr(request.user, 'rol', '') == 'admin'

    # Retorno seguro para volver al origen (lista de ventas, búsqueda, etc.)
    return_url = request.GET.get('next', '').strip()
    if not return_url.startswith('/') or return_url.startswith('//'):
        return_url = ''
    
    if not (es_cliente or es_empleado or es_admin):
        messages.error(request, 'No tienes permiso para ver esta venta.')
        return redirect('accounts:dashboard')
    
    # Preparar entradas activas y canceladas para la plantilla (evitar lógica en templates)
    entradas_activas = venta.entradas.exclude(estado='CANCELADA')
    entradas_canceladas = venta.entradas.filter(estado='CANCELADA')

    # Resumen económico real de la compra (usar total persistido, no recálculo dinámico)
    from decimal import Decimal, ROUND_HALF_UP
    entradas_compra = venta.entradas.select_related('id_funcion')
    cantidad_compra = entradas_compra.count()
    funcion_origen = entradas_compra.first().id_funcion if cantidad_compra > 0 else None
    monto_pagado_bd = None
    if getattr(venta, 'pago', None) and venta.pago and venta.pago.monto is not None:
        monto_pagado_bd = venta.pago.monto
    elif venta.total is not None:
        monto_pagado_bd = venta.total
    else:
        monto_pagado_bd = Decimal('0.00')

    total_pagado = Decimal(monto_pagado_bd).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_sin_descuento = Decimal('0.00')
    ahorro_total = Decimal('0.00')
    es_compra_por_intercambio = venta.intercambios.filter(estado='COMPLETADO').exists()
    promo_compra = {
        'aplicada': False,
        'tipo': None,
        'nombre': None,
        'ahorro': Decimal('0.00'),
    }

    if funcion_origen and cantidad_compra > 0 and not es_compra_por_intercambio:
        total_sin_descuento = (Decimal(funcion_origen.precio_base) * Decimal(cantidad_compra)).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
        ahorro_total = (total_sin_descuento - total_pagado).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if ahorro_total > 0:
            promo_compra['aplicada'] = True
            promo_compra['tipo'] = 'AUTOMATICA'
            promo_compra['nombre'] = 'Promoción aplicada'
            promo_compra['ahorro'] = ahorro_total

    # Si hubo cupón guardado, priorizar mostrar ese origen de descuento
    if venta.cupon_utilizado and not es_compra_por_intercambio:
        politica_origen = getattr(venta.cupon_utilizado, 'politica_origen', None)
        promo_origen = politica_origen.promocion_a_otorgar if politica_origen else None
        promo_compra['aplicada'] = True
        promo_compra['tipo'] = 'CUPON'
        promo_compra['nombre'] = promo_origen.nombre if promo_origen else 'Cupón aplicado'
        promo_compra['ahorro'] = ahorro_total if ahorro_total > 0 else Decimal('0.00')

    # Determinar si la venta todavía puede intercambiarse:
    # - Debe estar confirmada y tener pago
    # - La política activa define límites, reintercambio y promociones permitidas
    politica = PoliticaReembolso.objects.filter(activo=True).first()
    configuracion_cine = ConfiguracionCine.objects.first()
    nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
    
    puede_intercambiar = False
    info_no_intercambio = None  # Cambio de string a dict con título, mensaje y tipo

    # Evaluar condiciones y proporcionar motivo legible cuando no se permite
    if es_admin:
        # Regla de negocio: administradores no deben realizar intercambio desde detalle.
        puede_intercambiar = False
        info_no_intercambio = {
            'titulo': 'Intercambio no disponible para administradores',
            'mensaje': 'Los intercambios solo están habilitados para el flujo del cliente titular de la compra.',
            'tipo': 'info'
        }
    elif venta.estado != 'CONFIRMADA':
        info_no_intercambio = {
            'titulo': 'Intercambio no disponible',
            'mensaje': 'Tu compra debe estar <strong>confirmada y pagada</strong> para poder realizar un intercambio de entradas.',
            'tipo': 'warning'
        }
    elif venta.tipo_venta == 'PRESENCIAL':
        # Las ventas presenciales no permiten intercambio en línea
        info_no_intercambio = {
            'titulo': 'Intercambio no disponible',
            'mensaje': 'Las compras realizadas en <strong>boletería presencial</strong> deben gestionarse directamente en nuestras instalaciones. Por favor, acercate a nuestra boletería para realizar el cambio.',
            'tipo': 'info'
        }
        puede_intercambiar = False
    elif not getattr(venta, 'pago', None):
        info_no_intercambio = {
            'titulo': 'Intercambio no disponible',
            'mensaje': 'No se encontró un <strong>registro de pago</strong> asociado a esta compra. Contactá a nuestro soporte para más información.',
            'tipo': 'warning'
        }
    else:
        # Si hay política activa, delegar validación
        if politica:
            permite, motivo = politica.permite_intercambio_para_venta(venta)
            if permite:
                puede_intercambiar = True
            else:
                puede_intercambiar = False
                # Personalizar mensajes según el motivo específico de la política
                if 'día(s) de anticipación' in motivo:
                    dias_minimos = politica.dias_antes_minimo
                    horas_minimas = dias_minimos * 24
                    info_no_intercambio = {
                        'titulo': 'Tiempo insuficiente para intercambio',
                        'mensaje': f'Lo sentimos, las políticas de {nombre_cine} requieren al menos <strong>{dias_minimos} día{"s" if dias_minimos > 1 else ""} ({horas_minimas} horas)</strong> de anticipación para realizar intercambios. Tu función está muy próxima y ya no es posible modificar la reserva.',
                        'tipo': 'error'
                    }
                elif 'ya comenzó o finalizó' in motivo:
                    info_no_intercambio = {
                        'titulo': 'Intercambio no disponible',
                        'mensaje': 'La función original ya comenzó o finalizó, por lo que no es posible realizar el intercambio.',
                        'tipo': 'error'
                    }
                elif 'cupón o promoción' in motivo:
                    info_no_intercambio = {
                        'titulo': 'Intercambio no disponible',
                        'mensaje': f'Las políticas de {nombre_cine} no permiten intercambios para compras con <strong>cupón o promoción</strong>.',
                        'tipo': 'info'
                    }
                elif 'no permite reintercambio' in motivo:
                    info_no_intercambio = {
                        'titulo': 'Intercambio no disponible',
                        'mensaje': 'Esta compra ya tuvo un intercambio y la política activa no permite reintercambio.',
                        'tipo': 'info'
                    }
                elif 'Has alcanzado el límite máximo' in motivo:
                    info_no_intercambio = {
                        'titulo': 'Límite de intercambios alcanzado',
                        'mensaje': motivo,
                        'tipo': 'info'
                    }
                else:
                    info_no_intercambio = {
                        'titulo': 'Intercambio no disponible',
                        'mensaje': motivo or f'Las políticas vigentes de {nombre_cine} no permiten el intercambio para esta compra en este momento.',
                        'tipo': 'warning'
                    }
        else:
            # Sin política activa no se permiten intercambios.
            puede_intercambiar = False
            info_no_intercambio = {
                'titulo': 'Intercambio no disponible',
                'mensaje': 'No hay una política de intercambio activa en este momento.',
                'tipo': 'warning'
            }

    context = {
        'venta': venta,
        'entradas_activas': entradas_activas,
        'entradas_canceladas': entradas_canceladas,
        'total_pagado': total_pagado,
        'total_sin_descuento': total_sin_descuento,
        'promo_compra': promo_compra,
        'politica': politica,
        'puede_intercambiar': puede_intercambiar,
        'info_no_intercambio': info_no_intercambio,
        'configuracion_cine': configuracion_cine,
        'es_empleado': es_empleado,
        'es_admin': es_admin,
        'return_url': return_url,
    }
    
    return render(request, 'ventas/detalle_venta.html', context)


# NOTA: Vista intercambiar_entrada_view deprecada y movida a reembolsos.py
# El flujo ahora redirige a la cartelera con ?intercambio_for para seleccionar película/función
# Ver: ventas.views.reembolsos.intercambiar_entrada_view


@login_required
def comprobante_pago(request, venta_id):
    """
    Genera una vista de comprobante de pago.
    Diseño identico al mail de comprobante de pago.
    """
    venta = get_object_or_404(Venta, id_venta=venta_id)

    # Verificar permisos: dueno de la venta, empleado o admin
    es_cliente = venta.id_cliente.usuario == request.user
    es_empleado = hasattr(request.user, 'rol') and request.user.rol == 'empleado'
    es_admin = getattr(request.user, 'is_superuser', False) or getattr(request.user, 'rol', '') == 'admin'

    if not (es_cliente or es_empleado or es_admin):
        messages.error(request, 'No tenés permiso para ver este comprobante.')
        return redirect('accounts:dashboard')

    entradas_activas = venta.entradas.exclude(estado='CANCELADA').select_related(
        'id_pelicula', 'id_funcion', 'id_sala', 'id_butaca'
    )
    configuracion_cine = ConfiguracionCine.objects.first()

    # Pago y método
    pago = getattr(venta, 'pago', None)
    metodo_pago = venta.id_metodo_pago.nombre if venta.id_metodo_pago else 'N/A'

    # Armar conceptos por tipo de butaca / precio
    from collections import defaultdict
    from decimal import Decimal
    grupos = defaultdict(lambda: {'cantidad': 0, 'precio_unitario': Decimal('0')})
    for entrada in entradas_activas:
        desc = entrada.id_pelicula.titulo if entrada.id_pelicula else 'Entrada'
        precio = entrada.precio_final if hasattr(entrada, 'precio_final') and entrada.precio_final else (
            entrada.id_funcion.precio_base if entrada.id_funcion else Decimal('0')
        )
        grupos[desc]['cantidad'] += 1
        grupos[desc]['precio_unitario'] = precio

    conceptos = [
        {
            'descripcion': desc,
            'cantidad': g['cantidad'],
            'precio_unitario': g['precio_unitario'],
            'subtotal': g['cantidad'] * g['precio_unitario'],
        }
        for desc, g in grupos.items()
    ]

    es_compra_por_intercambio = venta.intercambios.filter(estado='COMPLETADO').exists()

    # Descuento
    descuento_aplicado = None
    if venta.cupon_utilizado and not es_compra_por_intercambio:
        politica = getattr(venta.cupon_utilizado, 'politica_origen', None)
        promo = politica.promocion_a_otorgar if politica else None
        if promo:
            descuento_aplicado = {
                'nombre': promo.nombre,
                'tipo': promo.tipo_descuento,
                'valor': promo.valor_descuento,
            }

    from django.utils import timezone as tz
    context = {
        'venta': venta,
        'entradas': entradas_activas,
        'configuracion_cine': configuracion_cine,
        'pago': pago,
        'usuario': venta.id_cliente.usuario,
        'metodo_pago': metodo_pago,
        'fecha_emision': pago.fecha_pago if pago else venta.fecha_compra,
        'conceptos': conceptos,
        'descuento_aplicado': descuento_aplicado,
    }
    return render(request, 'ventas/comprobante_pago.html', context)


@login_required
def comprobante_compra(request, venta_id):
    """Comprobante de confirmación de compra. Diseño idéntico al mail de confirmacion."""
    venta = get_object_or_404(Venta, id_venta=venta_id)

    es_cliente = venta.id_cliente.usuario == request.user
    es_empleado = hasattr(request.user, 'rol') and request.user.rol == 'empleado'
    es_admin = getattr(request.user, 'is_superuser', False) or getattr(request.user, 'rol', '') == 'admin'

    if not (es_cliente or es_empleado or es_admin):
        messages.error(request, 'No tenés permiso para ver este comprobante.')
        return redirect('accounts:dashboard')

    entradas_activas = venta.entradas.exclude(estado='CANCELADA').select_related(
        'id_pelicula', 'id_funcion', 'id_sala', 'id_butaca'
    )
    configuracion_cine = ConfiguracionCine.objects.first()
    usuario = venta.id_cliente.usuario
    primera_entrada = entradas_activas.first()
    cantidad = entradas_activas.count()

    # Armar lista compatible con el template del email [{entrada: e}, ...]
    entradas_lista = [{'entrada': e} for e in entradas_activas]

    # QR
    qr_src = None
    if venta.codigo_compra:
        qr_src = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={venta.codigo_compra}"

    # Total
    total_real = venta.calcular_total()

    es_compra_por_intercambio = venta.intercambios.filter(estado='COMPLETADO').exists()

    # Promoción
    promocion_aplicada = None
    if venta.cupon_utilizado and not es_compra_por_intercambio:
        politica = getattr(venta.cupon_utilizado, 'politica_origen', None)
        if politica:
            promocion_aplicada = politica.promocion_a_otorgar

    context = {
        'venta': venta,
        'usuario': usuario,
        'entradas': entradas_lista,
        'primera_entrada': primera_entrada,
        'cantidad': cantidad,
        'qr_src': qr_src,
        'total_real': total_real,
        'configuracion_cine': configuracion_cine,
        'promocion_aplicada': promocion_aplicada,
        'descuento_info': None,
    }
    return render(request, 'ventas/comprobante_compra.html', context)