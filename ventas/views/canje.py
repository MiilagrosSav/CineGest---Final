"""
Views para el módulo de Canje Rápido de Entradas Online
Sistema de impresión rápida con lector QR
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
from accounts.decorators import solo_empleados
from ventas.models import Venta, Entrada
from cine.models.configuracion_cine import ConfiguracionCine
from decimal import Decimal, ROUND_HALF_UP

import json


def _obtener_total_historico_venta(venta, entradas):
    """Obtiene el total histórico realmente cobrado para la venta.

    Prioridad:
    1) pago.monto (fuente financiera)
    2) venta.total persistido
    3) suma de precio_unitario de entradas
    4) fallback a calcular_total() solo si no hay otra fuente
    """
    try:
        pago = getattr(venta, 'pago', None)
        if pago and pago.monto is not None:
            monto_pago = Decimal(str(pago.monto))
            if monto_pago > 0:
                return monto_pago.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        pass

    try:
        if venta.total is not None:
            total_venta = Decimal(str(venta.total))
            if total_venta > 0:
                return total_venta.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        pass

    try:
        total_entradas = sum(
            Decimal(str(e.precio_unitario))
            for e in entradas
            if getattr(e, 'precio_unitario', None) is not None and Decimal(str(e.precio_unitario)) > 0
        )
        if total_entradas > 0:
            return total_entradas.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        pass

    try:
        return Decimal(str(venta.calcular_total())).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


@login_required
@solo_empleados
def canje_rapido_view(request):
    """
    Vista principal del módulo de canje rápido.
    Muestra el buscador para escanear QR o ingresar código manualmente.
    """
    context = {
        'titulo': 'Canje de Entradas Online'
    }
    return render(request, 'ventas/canje/canje_rapido.html', context)


@login_required
@solo_empleados
@require_http_methods(["POST"])
def buscar_venta_para_impresion(request):
    """
    API endpoint para buscar una venta por código QR, ID o DNI.
    Retorna los datos de la venta y el HTML del ticket listo para imprimir.
    """
    try:
        data = json.loads(request.body)
        codigo = data.get('codigo', '').strip()
        
        if not codigo:
            return JsonResponse({
                'success': False,
                'error': 'Debe ingresar un código de búsqueda'
            }, status=400)
        
        # Buscar venta por diferentes criterios
        venta = None
        
        # 1. Buscar por código de compra
        try:
            venta = Venta.objects.filter(
                codigo_compra=codigo,
                estado='CONFIRMADA',
                tipo_venta='ONLINE'
            ).select_related(
                'id_cliente__usuario',
                'id_empleado__usuario'
            ).prefetch_related(
                'entradas__id_funcion__pelicula',
                'entradas__id_funcion__sala',
                'entradas__id_butaca'
            ).first()
        except:
            pass
        
        # 2. Si no encontró, buscar por ID de venta
        if not venta:
            try:
                id_venta = int(codigo)
                venta = Venta.objects.filter(
                    id_venta=id_venta,
                    estado='CONFIRMADA',
                    tipo_venta='ONLINE'
                ).select_related(
                    'id_cliente__usuario',
                    'id_empleado__usuario'
                ).prefetch_related(
                    'entradas__id_funcion__pelicula',
                    'entradas__id_funcion__sala',
                    'entradas__id_butaca'
                ).first()
            except ValueError:
                pass
        
        # 3. Si no encontró, buscar por DNI del cliente
        if not venta:
            venta = Venta.objects.filter(
                id_cliente__usuario__dni=codigo,
                estado='CONFIRMADA',
                tipo_venta='ONLINE'
            ).select_related(
                'id_cliente__usuario',
                'id_empleado__usuario'
            ).prefetch_related(
                'entradas__id_funcion__pelicula',
                'entradas__id_funcion__sala',
                'entradas__id_butaca'
            ).order_by('-fecha_compra').first()
        
        if not venta:
            return JsonResponse({
                'success': False,
                'error': '❌ No se encontró ninguna venta con ese código',
                'detalles': 'Verifica que el código sea correcto y que la venta esté confirmada'
            }, status=404)
        
        # Obtener datos de la venta
        entradas = venta.entradas.all()
        primera_entrada = entradas.first()

        # VALIDACION: evitar re-canje si ya hay entradas usadas.
        # La reimpresion se maneja por una vista explicita desde detalle de venta.
        if entradas.filter(estado='USADA').exists():
            return JsonResponse({
                'success': False,
                'error': '❌ Este QR ya fue canjeado',
                'detalles': 'No se puede canjear dos veces el mismo codigo. Si necesitas reimprimir, hacelo desde el detalle de venta.'
            }, status=409)
        
        # VALIDACIÓN: Verificar si la función ya pasó
        from django.utils import timezone
        ahora = timezone.now()
        funcion_pasada = False
        
        if primera_entrada and primera_entrada.id_funcion.fecha_hora < ahora:
            funcion_pasada = True
        
        # Obtener configuración del cine
        config = ConfiguracionCine.objects.first()
        nombre_cine = config.nombre if config else "CineGest"
        
        # Calcular precio histórico total y por entrada
        total_venta = _obtener_total_historico_venta(venta, entradas)
        cantidad_entradas = entradas.count()
        precio_por_entrada = (
            (total_venta / Decimal(cantidad_entradas)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if cantidad_entradas > 0 else Decimal('0.00')
        )
        
        # Si la función ya pasó, retornar error
        if funcion_pasada:
            return JsonResponse({
                'success': False,
                'error': '⏰ Esta función ya pasó',
                'detalles': f'La función comenzó el {primera_entrada.id_funcion.fecha_hora:%d/%m/%Y a las %H:%M}. Las entradas de funciones pasadas no pueden canjearse.'
            }, status=400)
        
        # Retornar datos exitosos con URL de redirección
        return JsonResponse({
            'success': True,
            'venta_id': venta.id_venta,
            'redirect_url': f'/ventas/canje/ticket/{venta.id_venta}/',
            'venta_info': {
                'id': venta.id_venta,
                'codigo_compra': venta.codigo_compra or f"V-{venta.id_venta}",
                'cliente': venta.id_cliente.usuario.get_full_name() or venta.id_cliente.usuario.username,
                'dni': venta.id_cliente.usuario.dni if hasattr(venta.id_cliente.usuario, 'dni') else 'N/A',
                'pelicula': primera_entrada.id_pelicula.titulo if primera_entrada else 'N/A',
                'sala': primera_entrada.id_sala.nombre if primera_entrada else 'N/A',
                'fecha_funcion': primera_entrada.id_funcion.fecha_hora.strftime('%d/%m/%Y %H:%M') if primera_entrada else 'N/A',
                'cantidad_entradas': entradas.count(),
                'total': float(total_venta),
                'fecha_compra': venta.fecha_compra.strftime('%d/%m/%Y %H:%M')
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar la solicitud: {str(e)}'
        }, status=500)


@login_required
@solo_empleados
def ticket_canje_view(request, venta_id):
    """
    Vista para mostrar el ticket de canje con UN TICKET POR CADA ENTRADA.
    Cada entrada tiene su propio QR único.
    Al imprimir, se marcan como USADA (ticket entregado = acceso permitido).
    """
    from django.utils import timezone
    from django.contrib import messages
    
    venta = get_object_or_404(Venta, id_venta=venta_id, tipo_venta='ONLINE', estado='CONFIRMADA')
    
    # Obtener entradas
    entradas = venta.entradas.all()
    
    # VALIDACIÓN: Verificar que la función no haya pasado
    ahora = timezone.now()
    primera_entrada = entradas.first()
    
    if primera_entrada and primera_entrada.id_funcion.fecha_hora < ahora:
        messages.error(
            request,
            f'❌ No se puede canjear esta entrada. '
            f'La función comenzó el {primera_entrada.id_funcion.fecha_hora:%d/%m/%Y a las %H:%M}. '
            f'Las entradas de funciones pasadas se cancelan automáticamente.'
        )
        return redirect('ventas:canje_rapido')
    
    reimpresion_solicitada = request.GET.get('reimprimir') == '1'
    entradas_ya_usadas = entradas.exists() and not entradas.exclude(estado='USADA').exists()

    if reimpresion_solicitada:
        # Reimpresion solo si ya habia sido canjeado antes.
        if not entradas_ya_usadas:
            messages.warning(request, '⚠️ Esta venta todavia no fue canjeada. Usa el flujo normal de canje QR.')
            return redirect('ventas:canje_rapido')
        messages.info(request, 'ℹ️ Ticket reimpreso: esta venta ya estaba canjeada previamente.')
    else:
        # Flujo normal: no se permite volver a canjear un QR ya usado.
        if entradas.filter(estado='USADA').exists():
            messages.error(request, '❌ Este QR ya fue canjeado. Las entradas ya están usadas.')
            return redirect('ventas:canje_rapido')

        # Marcar entradas como USADA (ticket impreso = acceso válido)
        ahora = timezone.now()
        entradas_actualizadas = Entrada.objects.filter(
            id_venta=venta,
            estado__in=['VENDIDA', 'RESERVADA', 'ENTREGADA']
        ).update(estado='USADA', utilizado=True, fecha_ingreso=ahora)

        if entradas_actualizadas == 0:
            messages.error(request, '❌ No hay entradas activas para imprimir en esta venta.')
            return redirect('ventas:canje_rapido')
    
    # Obtener configuración del cine
    config = ConfiguracionCine.objects.first()
    nombre_cine = config.nombre if config else "CineGest"
    
    # Calcular precio histórico por entrada (sin recálculo dinámico de promociones)
    total_venta = _obtener_total_historico_venta(venta, entradas)
    cantidad_entradas = entradas.count()
    precio_por_entrada = (
        (total_venta / Decimal(cantidad_entradas)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if cantidad_entradas > 0 else Decimal('0.00')
    )
    
    context = {
        'venta': venta,
        'entradas': entradas,  # Lista de todas las entradas para iterar
        'nombre_cine': nombre_cine,
        'total_venta': total_venta,
        'precio_por_entrada': precio_por_entrada,
        'cantidad_entradas': cantidad_entradas,
        'reimpresion': entradas_ya_usadas,
    }
    
    return render(request, 'ventas/canje/ticket_canje.html', context)


@login_required
@solo_empleados
@require_http_methods(["POST"])
def marcar_como_impreso(request):
    """
    API endpoint para marcar las entradas como USADA.
    Se ejecuta después de imprimir el ticket exitosamente.
    (Ticket impreso = acceso permitido, no requiere validación en puerta)
    """
    try:
        data = json.loads(request.body)
        venta_id = data.get('venta_id')
        
        if not venta_id:
            return JsonResponse({
                'success': False,
                'error': 'ID de venta no proporcionado'
            }, status=400)
        
        venta = get_object_or_404(Venta, id_venta=venta_id, tipo_venta='ONLINE', estado='CONFIRMADA')
        
        # Actualizar estado de todas las entradas a USADA (ticket impreso = válido para entrar)
        ahora = timezone.now()
        entradas_actualizadas = Entrada.objects.filter(
            id_venta=venta,
            estado__in=['VENDIDA', 'RESERVADA', 'ENTREGADA']
        ).update(estado='USADA', utilizado=True, fecha_ingreso=ahora)

        if entradas_actualizadas == 0:
            return JsonResponse({
                'success': False,
                'error': 'Este QR ya fue canjeado o no tiene entradas activas.'
            }, status=409)
        
        return JsonResponse({
            'success': True,
            'message': f'✅ {entradas_actualizadas} entrada(s) marcada(s) como usada(s)',
            'entradas_actualizadas': entradas_actualizadas
        })
        
    except Venta.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Venta no encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al marcar como impreso: {str(e)}'
        }, status=500)
