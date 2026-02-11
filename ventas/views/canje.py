"""
Views para el módulo de Canje Rápido de Entradas Online
Sistema de impresión rápida con lector QR
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from accounts.decorators import solo_empleados
from ventas.models import Venta, Entrada
from cine.models.configuracion_cine import ConfiguracionCine
import json


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
        
        # Validar estado de las entradas
        entradas = venta.entradas.all()
        primera_entrada = entradas.first()
        
        # Verificar si ya fueron entregadas o usadas
        estados_entradas = entradas.values_list('estado', flat=True)
        if all(estado in ['ENTREGADA', 'USADA'] for estado in estados_entradas):
            return JsonResponse({
                'success': False,
                'error': '⚠️ Entradas ya retiradas',
                'detalles': f'Esta venta ya fue procesada anteriormente',
                'venta_info': {
                    'id': venta.id_venta,
                    'cliente': venta.id_cliente.usuario.get_full_name() or venta.id_cliente.usuario.username,
                    'pelicula': primera_entrada.id_pelicula.titulo if primera_entrada else 'N/A',
                    'fecha_compra': venta.fecha_compra.strftime('%d/%m/%Y %H:%M')
                }
            }, status=400)
        
        # Obtener configuración del cine
        config = ConfiguracionCine.objects.first()
        nombre_cine = config.nombre if config else "CineGest"
        
        # Calcular precio total y por entrada
        total_venta = venta.calcular_total()
        cantidad_entradas = entradas.count()
        precio_por_entrada = total_venta / cantidad_entradas if cantidad_entradas > 0 else 0
        
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
                'total': float(venta.calcular_total()),
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
    """
    venta = get_object_or_404(Venta, id_venta=venta_id, tipo_venta='ONLINE', estado='CONFIRMADA')
    
    # Obtener entradas y marcarlas como ENTREGADA (usando .save() para disparar validaciones)
    entradas = venta.entradas.all()
    for entrada in entradas:
        entrada.estado = 'ENTREGADA'
        entrada.save()
    
    # Obtener configuración del cine
    config = ConfiguracionCine.objects.first()
    nombre_cine = config.nombre if config else "CineGest"
    
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
    
    return render(request, 'ventas/canje/ticket_canje.html', context)


@login_required
@solo_empleados
@require_http_methods(["POST"])
def marcar_como_impreso(request):
    """
    API endpoint para marcar las entradas como ENTREGADA.
    Se ejecuta después de imprimir el ticket exitosamente.
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
        
        # Actualizar estado de todas las entradas a ENTREGADA (usando .save() para disparar validaciones)
        entradas_a_actualizar = venta.entradas.filter(
            estado__in=['VENDIDA', 'RESERVADA']
        )
        entradas_actualizadas = 0
        for entrada in entradas_a_actualizar:
            entrada.estado = 'ENTREGADA'
            entrada.save()
            entradas_actualizadas += 1
        
        return JsonResponse({
            'success': True,
            'message': f'✅ {entradas_actualizadas} entrada(s) marcada(s) como entregada(s)',
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
