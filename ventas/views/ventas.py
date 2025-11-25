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
from cine.models import Funcion, Butaca
from ventas.forms import IntercambioEntradaForm
from ventas.services import obtener_funciones_candidatas
from ventas.models import PoliticaReembolso
from django.utils import timezone
from django.db.models import Q


@login_required
def mis_ventas(request):
    """Vista para que el cliente vea sus ventas/compras"""
    # Obtener todas las ventas del cliente actual
    ventas_todas = Venta.objects.filter(
        id_cliente__usuario=request.user
    ).prefetch_related('entradas', 'entradas__id_funcion', 'entradas__id_pelicula').order_by('-fecha_compra')
    
    # Separar ventas pendientes y el historial (incluye confirmadas, canceladas y reembolsadas)
    # Excluir ventas pendientes cuyos eventos ya ocurrieron (fecha_hora en el pasado)
    ahora = timezone.now()
    ventas_pendientes = ventas_todas.filter(
        estado__in=['PENDIENTE', 'PENDIENTE_PAGO'],
        entradas__id_funcion__fecha_hora__gte=ahora
    ).distinct()
    ventas_historial_qs = ventas_todas.filter(estado__in=['CONFIRMADA', 'CANCELADA', 'REEMBOLSADO'])

    # Leer filtro de categoría desde GET (confirmadas, pendientes, canceladas, reembolsadas)
    requested_filter = request.GET.get('filter', 'confirmadas')

    # Paginación
    page_number = request.GET.get('page', 1)
    pending_page_number = request.GET.get('pending_page', 1)
    page_size = 3  # items por página — ajustalo si querés

    # Construir queryset del historial según el filtro solicitado
    if requested_filter == 'confirmadas':
        ventas_historial_qs = ventas_todas.filter(estado='CONFIRMADA')
    elif requested_filter == 'canceladas':
        # Mostrar ventas cuyo estado sea CANCELADA o que tengan alguna entrada marcada como CANCELADA
        ventas_historial_qs = ventas_todas.filter(
            Q(estado='CANCELADA') | Q(entradas__estado='CANCELADA')
        ).distinct()
    elif requested_filter == 'reembolsadas':
        ventas_historial_qs = ventas_todas.filter(estado='REEMBOLSADO')
    else:
        # fallback: mostrar todas las del historial (confirmadas/canceladas/reembolsadas)
        ventas_historial_qs = ventas_todas.filter(estado__in=['CONFIRMADA', 'CANCELADA', 'REEMBOLSADO'])

    # Historial paginator (según el queryset filtrado)
    paginator = Paginator(ventas_historial_qs, page_size)
    try:
        ventas_page = paginator.page(page_number)
    except PageNotAnInteger:
        ventas_page = paginator.page(1)
    except EmptyPage:
        ventas_page = paginator.page(paginator.num_pages)

    # Paginación para pendientes (siempre por separado)
    pending_paginator = Paginator(ventas_pendientes, page_size)
    try:
        ventas_pendientes_page = pending_paginator.page(pending_page_number)
    except PageNotAnInteger:
        ventas_pendientes_page = pending_paginator.page(1)
    except EmptyPage:
        ventas_pendientes_page = pending_paginator.page(pending_paginator.num_pages)
    
    context = {
        'ventas': ventas_todas,
        'ventas_pendientes': ventas_pendientes,
        'ventas_pendientes_page': ventas_pendientes_page,
        'ventas_historial': ventas_historial_qs,
        'ventas_page': ventas_page,
        'current_filter': requested_filter,
    }
    
    # Si la petición es AJAX, devolvemos solo el partial del historial
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Si el cliente pidió la categoría 'pendientes' devolvemos su partial
        if requested_filter == 'pendientes':
            return render(request, 'ventas/_ventas_pendientes.html', context)
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
    # Preparar entradas activas y canceladas para la plantilla (evitar lógica en templates)
    entradas_activas = venta.entradas.exclude(estado='CANCELADA')
    entradas_canceladas = venta.entradas.filter(estado='CANCELADA')
    # Determinar si la venta todavía puede intercambiarse:
    # - Debe estar confirmada y tener pago
    # - No debe haber intercambios previos (entradas canceladas)
    # - La política, si existe, debe permitir el intercambio
    politica = PoliticaReembolso.objects.filter(activo=True).first()
    puede_intercambiar = False
    motivo_no_intercambio = None

    # Evaluar condiciones y proporcionar motivo legible cuando no se permite
    if venta.estado != 'CONFIRMADA':
        motivo_no_intercambio = 'La venta no está confirmada.'
    elif entradas_canceladas.count() > 0:
        motivo_no_intercambio = 'La venta ya tiene intercambios previos (entradas canceladas).'
    elif not getattr(venta, 'pago', None):
        motivo_no_intercambio = 'No se encontró un pago registrado para esta venta.'
    else:
        # Si hay política activa, delegar validación
        if politica:
            permite, motivo = politica.permite_intercambio_para_venta(venta)
            if permite:
                puede_intercambiar = True
            else:
                puede_intercambiar = False
                motivo_no_intercambio = motivo or 'La política vigente no permite intercambio para esta venta.'
        else:
            # Sin política, permitir por defecto
            puede_intercambiar = True

    context = {
        'venta': venta,
        'entradas_activas': entradas_activas,
        'entradas_canceladas': entradas_canceladas,
        'politica': politica,
        'puede_intercambiar': puede_intercambiar,
    }
    
    return render(request, 'ventas/detalle_venta.html', context)


@login_required
def intercambiar_entrada_view(request, venta_id):
    """Vista para intercambiar las entradas de una venta por otra función válida."""
    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

    # Obtener funciones candidatas
    candidatas = obtener_funciones_candidatas(venta)

    # Consultar política activa (si existe) y validarla respecto a la venta
    politica = PoliticaReembolso.objects.filter(activo=True).first()
    if politica:
        permite, motivo = politica.permite_intercambio_para_venta(venta)
        if not permite:
            messages.error(request, motivo)
            return redirect('ventas:detalle_venta', venta_id=venta.id_venta)

    # Si no hay candidatas, mostrar mensaje informativo
    if not candidatas.exists():
        precio = None
        entradas = venta.entradas.all()
        if entradas.exists():
            precio = entradas[0].id_funcion.precio_base

        context = {
            'venta': venta,
            'mensaje_no_candidatas': True,
            'precio': precio,
        }
        return render(request, 'ventas/intercambiar_entrada.html', context)

    # Instanciar form
    if request.method == 'POST':
        # Soportar dos modos de envío: el form select (nueva_funcion) o botones individuales que envían 'nueva_funcion_id'
        nueva_funcion = None
        if 'nueva_funcion_id' in request.POST:
            try:
                nueva_funcion = Funcion.objects.get(pk=int(request.POST.get('nueva_funcion_id')))
            except Exception:
                nueva_funcion = None
            form = IntercambioEntradaForm(request.POST, compra=venta)
        else:
            form = IntercambioEntradaForm(request.POST, compra=venta)
            if form.is_valid():
                nueva_funcion = form.cleaned_data.get('nueva_funcion')
        # Si no se obtuvo una función válida, mostrar error
        if not nueva_funcion:
            messages.error(request, 'Seleccioná una función válida para el intercambio.')
        else:
            cantidad = venta.entradas.count()

            # Ejecutar la operación de intercambio dentro de una transacción
            try:
                with transaction.atomic():
                    # Determinar butacas ya asociadas a la nueva función (cualquier estado)
                    ocupadas_ids_all = set(
                        Entrada.objects.filter(
                            id_funcion=nueva_funcion
                        ).values_list('id_butaca_id', flat=True)
                    )

                    # Buscar butacas disponibles (excluir las que ya tienen una Entrada para esa función,
                    # independientemente de su estado, para no violar la restricción UNIQUE)
                    disponibles_qs = Butaca.objects.filter(
                        sala=nueva_funcion.sala,
                        es_pasillo=False
                    ).exclude(id__in=ocupadas_ids_all).order_by('fila', 'numero')

                    disponibles = list(disponibles_qs[:cantidad])
                    if len(disponibles) < cantidad:
                        raise Exception('No hay suficientes butacas disponibles en la nueva función.')

                    # Marcar entradas antiguas como canceladas para dejar registro
                    venta.entradas.update(estado='CANCELADA')

                    # Crear nuevas entradas asignando las butacas
                    for butaca in disponibles:
                        Entrada.objects.create(
                            id_venta=venta,
                            id_funcion=nueva_funcion,
                            id_sala=nueva_funcion.sala,
                            id_butaca=butaca,
                            id_pelicula=nueva_funcion.pelicula,
                            estado='RESERVADA'
                        )

                messages.success(request, '✅ Intercambio realizado con éxito.')
                return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
            except Exception as e:
                messages.error(request, f'❌ No se pudo completar el intercambio: {str(e)}')
    else:
        form = IntercambioEntradaForm(compra=venta)

    context = {
        'venta': venta,
        'form': form,
        'candidatas': candidatas,
        'politica': politica,
    }
    return render(request, 'ventas/intercambiar_entrada.html', context)