"""
Views para validación de entradas en puerta de acceso a sala.
Sistema con scanner QR + fallback manual para casos donde no funcione el QR.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from accounts.decorators import solo_empleados
from ventas.models import Entrada, RegistroAcceso
from cine.models.configuracion_cine import ConfiguracionCine
import json
import re


def obtener_ip_cliente(request):
    """Obtener IP del cliente desde request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
@solo_empleados
def validar_acceso_view(request):
    """
    Vista principal para validación de entradas en puerta.
    Muestra scanner QR con fallback a búsqueda manual.
    """
    context = {
        'titulo': 'Validación de Acceso a Sala'
    }
    return render(request, 'ventas/acceso/validar_acceso.html', context)


@login_required
@solo_empleados
@require_http_methods(["POST"])
def buscar_entrada_api(request):
    """
    API endpoint para validar una entrada por QR, código, o ID.
    Retorna resultado de validación (PERMITIDO/RECHAZADO) con motivo.
    
    Búsqueda soporta múltiples formatos:
    - QR de entrada: "CINEGEST-ENTRADA-123"
    - ID de entrada directo: "123"
    - Código de compra: "COMP-2026-ABC123"
    """
    try:
        data = json.loads(request.body)
        codigo = data.get('codigo', '').strip().upper()
        
        if not codigo:
            return JsonResponse({
                'success': False,
                'error': 'Debe ingresar un código de búsqueda'
            }, status=400)
        
        entrada = None
        tipo_validacion = 'QR'
        
        # ==============================================================
        # FASE 1: BÚSQUEDA DE LA ENTRADA
        # ==============================================================
        
        # 1. Formato QR de entrada: "CINEGEST-ENTRADA-123" o "ENTRADA:123"
        match_qr = re.search(r'ENTRADA[:\-](\d+)', codigo)
        if match_qr:
            entrada_id = match_qr.group(1)
            entrada = Entrada.objects.filter(id_entrada=entrada_id).first()
            tipo_validacion = 'QR'
        
        # 2. ID de entrada directo (número solo): "123"
        elif codigo.isdigit():
            entrada = Entrada.objects.filter(id_entrada=int(codigo)).first()
            tipo_validacion = 'CODIGO'
        
        # 3. Código de compra (traer todas las entradas de esa venta)
        elif codigo.startswith('COMP-') or len(codigo) >= 8:
            from ventas.models import Venta
            venta = Venta.objects.filter(
                codigo_compra=codigo,
                estado='CONFIRMADA'
            ).first()
            
            if venta:
                # Tomar la primera entrada sin usar de esa venta
                entradas_disponibles = venta.entradas.exclude(estado='USADA').order_by('id_entrada')
                entrada = entradas_disponibles.first()
                tipo_validacion = 'CODIGO'
        
        # ==============================================================
        # FASE 2: VALIDACIONES
        # ==============================================================
        
        if not entrada:
            # Registrar intento fallido
            RegistroAcceso.objects.create(
                entrada=None,
                empleado_validador=request.user,
                tipo_validacion=tipo_validacion,
                resultado='RECHAZADO',
                codigo_buscado=codigo,
                motivo_rechazo='Entrada no encontrada',
                ip_origen=obtener_ip_cliente(request)
            )
            
            return JsonResponse({
                'success': False,
                'resultado': 'RECHAZADO',
                'motivo': '❌ Entrada no encontrada',
                'detalle': 'Verifica el código e intenta nuevamente.'
            })
        
        # --- VALIDACIÓN 1: Estado de la entrada ---
        if entrada.estado == 'USADA' or entrada.utilizado:
            RegistroAcceso.objects.create(
                entrada=entrada,
                empleado_validador=request.user,
                tipo_validacion=tipo_validacion,
                resultado='RECHAZADO',
                codigo_buscado=codigo,
                motivo_rechazo='Entrada ya utilizada',
                ip_origen=obtener_ip_cliente(request)
            )

            fecha_uso_str = ''
            if entrada.fecha_ingreso:
                fecha_uso_str = entrada.fecha_ingreso.strftime('%d/%m/%Y %H:%M:%S')

            return JsonResponse({
                'success': False,
                'resultado': 'RECHAZADO',
                'motivo': '🚫 Entrada YA UTILIZADA',
                'detalle': f'Esta entrada fue validada anteriormente.{" Ingreso registrado: " + fecha_uso_str if fecha_uso_str else ""}',
                'entrada_info': {
                    'id': entrada.id_entrada,
                    'pelicula': entrada.id_pelicula.titulo,
                    'funcion': entrada.id_funcion.fecha_hora.strftime('%d/%m/%Y %H:%M'),
                    'butaca': f"{entrada.id_butaca.fila}{entrada.id_butaca.numero}",
                    'estado': entrada.estado,
                    'fecha_ingreso': fecha_uso_str,
                }
            })
        
        if entrada.estado == 'CANCELADA':
            RegistroAcceso.objects.create(
                entrada=entrada,
                empleado_validador=request.user,
                tipo_validacion=tipo_validacion,
                resultado='RECHAZADO',
                codigo_buscado=codigo,
                motivo_rechazo='Entrada cancelada',
                ip_origen=obtener_ip_cliente(request)
            )
            
            return JsonResponse({
                'success': False,
                'resultado': 'RECHAZADO',
                'motivo': '❌ Entrada CANCELADA',
                'detalle': 'Esta entrada fue cancelada y no es válida.',
                'entrada_info': {
                    'id': entrada.id_entrada,
                    'estado': entrada.estado
                }
            })
        
        # --- VALIDACIÓN 2: Horario de la función (CRÍTICO PARA PREVENTA) ---
        ahora = timezone.now()
        funcion_hora = entrada.id_funcion.fecha_hora
        
        # No permitir acceso ANTES de la función
        # (margen de tolerancia: 15 minutos antes)
        margen_minutos = 15
        hora_apertura_puerta = funcion_hora - timezone.timedelta(minutes=margen_minutos)
        
        if ahora < hora_apertura_puerta:
            tiempo_restante = hora_apertura_puerta - ahora
            horas = int(tiempo_restante.total_seconds() // 3600)
            minutos = int((tiempo_restante.total_seconds() % 3600) // 60)
            
            RegistroAcceso.objects.create(
                entrada=entrada,
                empleado_validador=request.user,
                tipo_validacion=tipo_validacion,
                resultado='RECHAZADO',
                codigo_buscado=codigo,
                motivo_rechazo=f'Función no comenzó (abre en {horas}h {minutos}min)',
                ip_origen=obtener_ip_cliente(request)
            )
            
            return JsonResponse({
                'success': False,
                'resultado': 'RECHAZADO',
                'motivo': f'⏰ FUNCIÓN AÚN NO COMIENZA',
                'detalle': f'La función inicia a las {funcion_hora:%H:%M}. Puerta abre {margen_minutos} min antes.',
                'tiempo_restante': f'{horas}h {minutos}min' if horas > 0 else f'{minutos} minutos',
                'hora_apertura': hora_apertura_puerta.strftime('%H:%M'),
                'entrada_info': {
                    'id': entrada.id_entrada,
                    'pelicula': entrada.id_pelicula.titulo,
                    'funcion': funcion_hora.strftime('%d/%m/%Y %H:%M'),
                    'sala': entrada.id_sala.numero,
                    'butaca': f"{entrada.id_butaca.fila}{entrada.id_butaca.numero}"
                }
            })
        
        # --- VALIDACIÓN 3: Función no debe haber terminado ---
        # (margen: hasta 30 minutos después del inicio aún se permite)
        tiempo_limite_ingreso = funcion_hora + timezone.timedelta(minutes=30)
        
        if ahora > tiempo_limite_ingreso:
            RegistroAcceso.objects.create(
                entrada=entrada,
                empleado_validador=request.user,
                tipo_validacion=tipo_validacion,
                resultado='RECHAZADO',
                codigo_buscado=codigo,
                motivo_rechazo='Función ya comenzó (más de 30 min)',
                ip_origen=obtener_ip_cliente(request)
            )
            
            return JsonResponse({
                'success': False,
                'resultado': 'RECHAZADO',
                'motivo': '⏱️ Función YA COMENZÓ',
                'detalle': f'La función inició a las {funcion_hora:%H:%M}. Tiempo límite de ingreso excedido.',
                'entrada_info': {
                    'id': entrada.id_entrada,
                    'pelicula': entrada.id_pelicula.titulo,
                    'funcion': funcion_hora.strftime('%d/%m/%Y %H:%M')
                }
            })
        
        # ==============================================================
        # FASE 3: ACCESO PERMITIDO - MARCAR COMO USADA
        # ==============================================================
        
        # Guardar estado anterior para auditoría
        estado_anterior = entrada.estado
        ahora_ingreso = timezone.now()

        entrada.estado = 'USADA'
        entrada.utilizado = True
        entrada.fecha_ingreso = ahora_ingreso
        entrada.save(update_fields=['estado', 'utilizado', 'fecha_ingreso'])
        
        # Registrar acceso exitoso
        RegistroAcceso.objects.create(
            entrada=entrada,
            empleado_validador=request.user,
            tipo_validacion=tipo_validacion,
            resultado='PERMITIDO',
            codigo_buscado=codigo,
            motivo_rechazo='',
            ip_origen=obtener_ip_cliente(request)
        )
        
        return JsonResponse({
            'success': True,
            'resultado': 'PERMITIDO',
            'motivo': '✅ ACCESO PERMITIDO',
            'detalle': '¡Disfruta la función!',
            'entrada_info': {
                'id': entrada.id_entrada,
                'pelicula': entrada.id_pelicula.titulo,
                'funcion': funcion_hora.strftime('%d/%m/%Y %H:%M'),
                'sala': f"Sala {entrada.id_sala.numero} - {entrada.id_sala.nombre}",
                'butaca': f"{entrada.id_butaca.fila}{entrada.id_butaca.numero}",
                'formato': entrada.id_butaca.tipo,
                'estado_anterior': estado_anterior,
                'estado_actual': 'USADA',
                'validado_por': request.user.get_full_name() or request.user.username,
                'hora_validacion': ahora_ingreso.strftime('%H:%M:%S')
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar validación: {str(e)}'
        }, status=500)


@login_required
@solo_empleados
def validacion_manual_view(request):
    """
    Vista de fallback para validación manual (cuando scanner QR no funciona).
    Permite buscar entrada por ID, DNI del cliente, o código.
    """
    resultados = None
    busqueda = None
    
    if request.method == 'GET' and 'buscar' in request.GET:
        busqueda = request.GET.get('buscar', '').strip()
        
        if busqueda:
            # Buscar por múltiples criterios
            query = Q()
            
            # Si es número, buscar por ID de entrada
            if busqueda.isdigit():
                query |= Q(id_entrada=int(busqueda))
            
            # Buscar por código de compra
            query |= Q(id_venta__codigo_compra__icontains=busqueda)
            
            # Buscar por DNI del cliente (a través de la venta)
            query |= Q(id_venta__id_cliente__usuario__username__icontains=busqueda)
            query |= Q(id_venta__id_cliente__usuario__first_name__icontains=busqueda)
            query |= Q(id_venta__id_cliente__usuario__last_name__icontains=busqueda)
            
            # Filtrar solo entradas de funciones futuras o de hoy
            hoy = timezone.now().date()
            resultados = Entrada.objects.filter(
                query,
                id_funcion__fecha_hora__date__gte=hoy
            ).select_related(
                'id_funcion__pelicula',
                'id_funcion__sala',
                'id_butaca',
                'id_venta__id_cliente__usuario'
            ).order_by('id_funcion__fecha_hora')[:20]  # Limitar a 20 resultados
    
    context = {
        'titulo': 'Validación Manual de Entradas',
        'resultados': resultados,
        'busqueda': busqueda,
    }
    
    return render(request, 'ventas/acceso/validacion_manual.html', context)
