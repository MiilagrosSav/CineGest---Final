from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from cine.models import Funcion, Butaca
from ventas.models import Venta, Entrada
from accounts.models import Cliente
from accounts.utils import get_or_create_consumidor_final
from accounts.decorators import solo_empleados
from promociones.services import calcular_precio_final


@login_required
@solo_empleados
def dashboard_presencial(request):
    """Lista funciones del día agrupadas por película para venta rápida en boletería."""
    hoy = timezone.localdate()
    funciones = Funcion.objects.filter(fecha_hora__date=hoy).select_related('pelicula', 'sala').order_by('pelicula__titulo', 'fecha_hora')

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

    total, promo_aplicada, detalle = calcular_precio_final(funcion, 1)
    if promo_aplicada:
        promocion_aplicada = promo_aplicada
        precio_mostrar = detalle.get('precio_unitario_final', precio_mostrar) or precio_mostrar
        info_descuento = {'tipo': detalle.get('tipo_aplicado'), 'descripcion': detalle.get('descripcion'), 'precio_con_descuento': precio_mostrar}

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
        'precio': precio_mostrar,
        'precio_base': funcion.precio_base,
        'promocion_aplicada': promocion_aplicada,
        'info_descuento': info_descuento,
        'form_action_name': 'ventas:confirmar_venta_presencial',
        'mercadopago_public_key': None,
        'venta_id': None,
        'cantidad_requerida': None,
        'promo_2x1': False,
        'promo_codigo': None,
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

    medio_pago = request.POST.get('medio_pago', 'EFECTIVO')
    datos_venta = request.session.get('venta_presencial')

    if not datos_venta:
        messages.error(request, 'Sesión expirada. Vuelve a seleccionar las butacas.')
        return redirect('ventas:dashboard_presencial')

    funcion_id = datos_venta['funcion_id']
    butacas_ids = datos_venta['butacas_ids']
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    cliente = get_or_create_consumidor_final()

    try:
        with transaction.atomic():
            venta = Venta.objects.create(
                id_cliente=cliente,
                id_empleado=getattr(request.user, 'empleado', None),
                tipo_venta='PRESENCIAL',
                estado='CONFIRMADA',
                medio_pago=medio_pago
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

            # Limpiar sesión
            if 'venta_presencial' in request.session:
                del request.session['venta_presencial']

            # Redirigir a ticket exitoso en lugar de detalle_venta
            return redirect('ventas:ticket_exitoso', venta_id=venta.id_venta)

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
    ).select_related('pelicula', 'sala').order_by('fecha_hora', 'pelicula__titulo')[:50]  # Limitar a 50

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
                ventas_cliente = Venta.objects.filter(
                    id_cliente=cliente_seleccionado
                ).prefetch_related('entradas__id_funcion__pelicula').order_by('-fecha_compra')[:20]
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
    """Muestra el ticket de venta exitosa estilo térmico para imprimir."""
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
    
    # Obtener entradas agrupadas
    entradas = venta.entradas.all()
    primera_entrada = entradas.first()
    
    context = {
        'venta': venta,
        'entradas': entradas,
        'primera_entrada': primera_entrada,
        'nombre_cine': nombre_cine,
        'total': venta.calcular_total(),
    }
    
    return render(request, 'ventas/presencial/ticket_exitoso.html', context)
