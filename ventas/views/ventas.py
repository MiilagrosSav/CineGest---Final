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
from cine.models.configuracion_cine import ConfiguracionCine


@login_required
def mis_ventas(request):
    """Vista para que el cliente vea sus ventas/compras"""
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

    # Determinar si la venta todavía puede intercambiarse:
    # - Debe estar confirmada y tener pago
    # - No debe haber usado un cupón (las compras con cupón no permiten intercambio)
    # - No debe haber intercambios previos (entradas canceladas)
    # - La política, si existe, debe permitir el intercambio
    politica = PoliticaReembolso.objects.filter(activo=True).first()
    configuracion_cine = ConfiguracionCine.objects.first()
    nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
    
    puede_intercambiar = False
    info_no_intercambio = None  # Cambio de string a dict con título, mensaje y tipo

    # Evaluar condiciones y proporcionar motivo legible cuando no se permite
    if venta.estado != 'CONFIRMADA':
        info_no_intercambio = {
            'titulo': 'Intercambio no disponible',
            'mensaje': 'Tu compra debe estar <strong>confirmada y pagada</strong> para poder realizar un intercambio de entradas.',
            'tipo': 'warning'
        }
    elif venta.cupon_utilizado:
        # Las compras con cupón no permiten intercambio
        info_no_intercambio = {
            'titulo': 'Intercambio no disponible',
            'mensaje': f'Las políticas de {nombre_cine} establecen que las compras realizadas con <strong>cupones o promociones especiales</strong> no son elegibles para intercambio.',
            'tipo': 'info'
        }
        puede_intercambiar = False
    elif entradas_canceladas.count() > 0:
        info_no_intercambio = {
            'titulo': 'Intercambio ya realizado',
            'mensaje': 'Esta compra ya tiene un <strong>intercambio previo</strong>. Solo se permite un intercambio por compra.',
            'tipo': 'info'
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
                else:
                    info_no_intercambio = {
                        'titulo': 'Intercambio no disponible',
                        'mensaje': motivo or f'Las políticas vigentes de {nombre_cine} no permiten el intercambio para esta compra en este momento.',
                        'tipo': 'warning'
                    }
        else:
            # Sin política, permitir por defecto
            puede_intercambiar = True

    context = {
        'venta': venta,
        'entradas_activas': entradas_activas,
        'entradas_canceladas': entradas_canceladas,
        'politica': politica,
        'puede_intercambiar': puede_intercambiar,
        'info_no_intercambio': info_no_intercambio,
        'configuracion_cine': configuracion_cine,
    }
    
    return render(request, 'ventas/detalle_venta.html', context)


# NOTA: Vista intercambiar_entrada_view deprecada y movida a reembolsos.py
# El flujo ahora redirige a la cartelera con ?intercambio_for para seleccionar película/función
# Ver: ventas.views.reembolsos.intercambiar_entrada_view