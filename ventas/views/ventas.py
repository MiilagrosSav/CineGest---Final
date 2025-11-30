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
try:
    from valoraciones.services import puede_valorar
    from valoraciones.models import Valoracion
except Exception:
    puede_valorar = None
    Valoracion = None
from cine.models import Funcion, Butaca
from ventas.forms import IntercambioEntradaForm
from ventas.services import obtener_funciones_candidatas
from ventas.models import PoliticaReembolso
from django.utils import timezone
from django.db.models import Q


@login_required
def mis_ventas(request):
    """Vista para que el cliente vea sus ventas/compras"""
    # Bloquear acceso a empleados
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados no tienen acceso a "Mis Ventas". Usa el módulo de búsqueda de clientes.')
        return redirect('accounts:dashboard')
    
    # Obtener todas las ventas del cliente actual
    ventas_todas = Venta.objects.filter(
        id_cliente__usuario=request.user
    ).prefetch_related('entradas', 'entradas__id_funcion', 'entradas__id_pelicula', 'intercambios').order_by('-fecha_compra')
    
    # Leer filtro de categoría desde GET (confirmadas, intercambiadas, canceladas)
    requested_filter = request.GET.get('filter', 'confirmadas')
    
    # Leer término de búsqueda
    search_query = request.GET.get('search', '').strip()

    # Paginación
    page_number = request.GET.get('page', 1)
    page_size = 5  # items por página

    # Construir queryset del historial según el filtro solicitado
    if requested_filter == 'confirmadas':
        # Mostrar solo ventas CONFIRMADAS que NO tengan entradas CANCELADAS (no intercambiadas)
        ventas_historial_qs = ventas_todas.filter(
            estado='CONFIRMADA'
        ).exclude(
            entradas__estado='CANCELADA'
        ).distinct()
    elif requested_filter == 'intercambiadas':
        # Mostrar ventas que tienen al menos un registro de intercambio
        ventas_historial_qs = ventas_todas.filter(
            intercambios__isnull=False
        ).distinct()
    elif requested_filter == 'canceladas':
        # Mostrar ventas con estado CANCELADA (no intercambios, que son detectados por tener registro Intercambio)
        ventas_historial_qs = ventas_todas.filter(
            estado='CANCELADA'
        ).distinct()
    else:
        # fallback: mostrar todas confirmadas sin intercambios
        ventas_historial_qs = ventas_todas.filter(
            estado='CONFIRMADA'
        ).exclude(
            entradas__estado='CANCELADA'
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
def detalle_venta(request, venta_id):
    """Vista para ver el detalle de una venta específica"""
    # Permitir que el cliente vea sus ventas O que un empleado vea cualquier venta (búsqueda de clientes)
    venta = get_object_or_404(Venta, id_venta=venta_id)
    
    # Verificar permisos: debe ser el cliente dueño O empleado O admin
    es_cliente = venta.id_cliente.usuario == request.user
    es_empleado = hasattr(request.user, 'rol') and request.user.rol == 'empleado'
    es_admin = getattr(request.user, 'is_superuser', False) or getattr(request.user, 'rol', '') == 'admin'
    
    if not (es_cliente or es_empleado or es_admin):
        messages.error(request, 'No tienes permiso para ver esta venta.')
        return redirect('accounts:dashboard')
    
    # Preparar entradas activas y canceladas para la plantilla (evitar lógica en templates)
    entradas_activas = venta.entradas.exclude(estado='CANCELADA')
    entradas_canceladas = venta.entradas.filter(estado='CANCELADA')

    # Calcular qué funciones dentro de esta venta puede valorar el cliente
    # Construir info detallada por función para mostrar en la plantilla
    # SOLO incluir funciones que el cliente PUEDE valorar (no mostrar las que no puede)
    can_valorar_info = []
    if es_cliente:
        try:
            cliente_obj = Cliente.objects.get(usuario=request.user)
            funciones = list({e.id_funcion for e in entradas_activas})
            ahora = timezone.now()
            for func in funciones:
                # Tiene entrada en esta venta para esa función en estado VENDIDA o USADA?
                tiene_entrada = entradas_activas.filter(id_funcion=func, estado__in=['VENDIDA', 'USADA']).exists()
                # Función finalizada?
                try:
                    fin = func.get_hora_fin()
                    funcion_finalizada = bool(fin and fin <= ahora)
                except Exception:
                    funcion_finalizada = False

                # Ya valoró?
                ya_valorada = False
                if Valoracion is not None:
                    try:
                        ya_valorada = Valoracion.objects.filter(cliente=cliente_obj, funcion=func).exists()
                    except Exception:
                        ya_valorada = False

                # Evaluar puede_valorar (si el servicio está disponible)
                puede = False
                if puede_valorar:
                    try:
                        puede = puede_valorar(cliente_obj, func)
                    except Exception:
                        puede = False

                # SOLO agregar si puede valorar (filtrar las que no puede desde el backend)
                if puede:
                    can_valorar_info.append({
                        'funcion': func,
                        'tiene_entrada': tiene_entrada,
                        'finalizada': funcion_finalizada,
                        'ya_valorada': ya_valorada,
                        'puede_valorar': puede,
                    })
        except Cliente.DoesNotExist:
            can_valorar_info = []

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
    elif venta.tipo_venta == 'PRESENCIAL':
        # Las ventas presenciales no permiten intercambio en línea
        motivo_no_intercambio = 'Las ventas presenciales deben gestionarse en boletería.'
        puede_intercambiar = False
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
        'can_valorar_info': can_valorar_info,
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