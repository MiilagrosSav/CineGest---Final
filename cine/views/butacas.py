from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
import json
from cine.models import Butaca
from django.shortcuts import render
from cine.models import Sala
from django.contrib import messages


# --- Vistas para el Diseñador de Butacas ---
# Función auxiliar para verificar si es admin
def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.rol == 'admin')


@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def disenar_layout_sala(request, sala_id):
    """
    Muestra la página del diseñador visual para una sala específica.
    Solo accesible para administradores.
    Bloquea la edición si la sala tiene butacas vendidas.
    """
    sala = get_object_or_404(Sala, id=sala_id)
    
    # Verificar si la sala tiene butacas vendidas
    if sala.tiene_butacas_vendidas():
        messages.error(
            request, 
            f'No se puede modificar la distribución de asientos de la Sala {sala.numero} porque tiene butacas vendidas. '
            'Por seguridad, no es posible reconfigurar una sala con ventas activas.'
        )
        return redirect('cine:sala_list')
    
    butacas = list(sala.butacas.all().order_by('fila', 'numero').values('fila', 'numero', 'tipo', 'es_pasillo'))
    context = {
        'sala': sala,
        'butacas_existentes': butacas
    }
    return render(request, 'cine/disenar_layout.html', context)


@require_http_methods(["POST"])
@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def api_guardar_layout_sala(request, sala_id):
    """
    Recibe un JSON con la nueva distribución de asientos (incluyendo pasillos), 
    borra las butacas antiguas y crea las nuevas.
    Solo accesible para administradores.
    Bloquea el guardado si la sala tiene butacas vendidas.
    """
    try:
        sala = get_object_or_404(Sala, id=sala_id)
        
        # Verificar si la sala tiene butacas vendidas
        if sala.tiene_butacas_vendidas():
            return JsonResponse({
                'status': 'error', 
                'message': 'No se puede modificar la distribución de asientos porque la sala tiene butacas vendidas.'
            }, status=403)
        
        data = json.loads(request.body)

        # Preparar nuevas (incluyendo pasillos)
        nuevas = []
        seen = set()  # Para detectar duplicados
        duplicados = []
        
        for item in data:
            fila = item.get('fila')
            num = item.get('num')
            tipo = item.get('tipo', 'GENERAL')
            es_pasillo = item.get('es_pasillo', False)
            
            if not fila or num is None:
                continue
            
            # Verificar duplicados
            clave = (fila, num)
            if clave in seen:
                duplicados.append(f"{fila}{num}")
                continue
            seen.add(clave)
            
            # Si es pasillo (tipo 'vacio'), marcar es_pasillo=True
            if tipo == 'vacio':
                es_pasillo = True
                tipo = 'GENERAL'  # Los pasillos son tipo GENERAL pero con flag es_pasillo
            
            nuevas.append(Butaca(
                sala=sala, 
                fila=fila, 
                numero=num, 
                tipo=tipo,
                es_pasillo=es_pasillo
            ))

        # Nunca descartar silenciosamente butacas duplicadas: devolver error para evitar pérdidas.
        if duplicados:
            return JsonResponse({
                'status': 'error',
                'message': (
                    'Se detectaron posiciones duplicadas en la distribución. '
                    'Corrige el diseño antes de guardar.'
                ),
                'duplicados': duplicados,
                'total_enviado': len(data),
                'total_procesado': len(nuevas),
            }, status=400)

        if nuevas:
            try:
                with transaction.atomic():
                    # Reemplazar distribución completa en una sola transacción.
                    sala.butacas.all().delete()
                    Butaca.objects.bulk_create(nuevas)
            except Exception as e:
                error_msg = str(e)
                # Detectar el tipo de error
                if 'unique' in error_msg.lower() or 'duplicate' in error_msg.lower():
                    error_msg = f'Error de duplicados: Una o más butacas ya existen en esta combinación sala-fila-número. {error_msg}'
                else:
                    error_msg = f'Error al crear butacas: {error_msg}'
                    
                return JsonResponse({
                    'status': 'error', 
                    'message': error_msg,
                    'duplicados_detectados': duplicados,
                    'total_enviado': len(data),
                    'total_procesado': len(nuevas)
                }, status=400)

        # Calcular capacidad real (solo butacas, sin pasillos)
        capacidad_real = sala.butacas.filter(es_pasillo=False).count()
        
        # Contar pasillos en la lista de nuevas antes de bulk_create
        total_pasillos = sum(1 for b in nuevas if b.es_pasillo)
        # --- PARCHE PARA ACTUALIZAR CAPACIDAD TOTAL ---
        # Como bulk_create no dispara señales, forzamos la actualización manual aquí.
        sala.capacidad_total = sala.butacas.filter(es_pasillo=False).count()
        sala.save(update_fields=['capacidad_total'])
        
        respuesta = {
            'status': 'ok', 
            'butacas_creadas': len(nuevas),
            'capacidad': capacidad_real,
            'pasillos': total_pasillos
        }
        
        if duplicados:
            respuesta['warning'] = f'{len(duplicados)} butacas duplicadas fueron ignoradas'
            respuesta['duplicados'] = duplicados
        
    
        return JsonResponse(respuesta)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# --- Vistas para Gestión de Mantenimiento de Butacas ---

@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def gestionar_mantenimiento_sala(request, sala_id):
    """
    Vista para que el administrador del sistema gestione el mantenimiento
    de butacas individuales de una sala, independientemente de si la sala
    tiene ventas activas.
    """
    from django.utils import timezone
    from ventas.models import Entrada

    sala = get_object_or_404(Sala, id=sala_id)
    ahora = timezone.now()

    # IDs de butacas con ventas activas futuras (para saber cuáles están bloqueadas)
    butacas_con_venta = set(
        Entrada.objects.filter(
            id_butaca__sala=sala,
            estado__in=['PENDIENTE', 'RESERVADA', 'VENDIDA'],
            id_funcion__fecha_hora__gt=ahora,
        ).values_list('id_butaca_id', flat=True)
    )

    # Construir mapa por filas (solo butacas reales, sin pasillos)
    butacas_qs = sala.butacas.order_by('fila', 'numero')
    filas = {}
    for butaca in butacas_qs:
        fila = butaca.fila
        if fila not in filas:
            filas[fila] = []
        filas[fila].append({
            'butaca': butaca,
            'bloqueada': butaca.id in butacas_con_venta,
        })

    context = {
        'sala': sala,
        'filas': filas,
    }
    return render(request, 'cine/gestionar_mantenimiento.html', context)


@require_http_methods(["POST"])
@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def api_toggle_mantenimiento_butaca(request, sala_id, butaca_id):
    """
    API AJAX para activar/desactivar el mantenimiento de una butaca específica.
    Solo bloquea si la butaca (no la sala completa) tiene ventas activas futuras.
    """
    from django.utils import timezone
    from ventas.models import Entrada

    sala = get_object_or_404(Sala, id=sala_id)
    butaca = get_object_or_404(Butaca, id=butaca_id, sala=sala)

    if butaca.es_pasillo:
        return JsonResponse(
            {'status': 'error', 'message': 'Los pasillos no tienen estado de mantenimiento.'},
            status=400
        )

    # Si se quiere poner en mantenimiento, verificar ventas activas de ESTA butaca
    if not butaca.en_mantenimiento:
        tiene_venta_activa = Entrada.objects.filter(
            id_butaca=butaca,
            estado__in=['PENDIENTE', 'RESERVADA', 'VENDIDA'],
            id_funcion__fecha_hora__gt=timezone.now(),
        ).exists()
        if tiene_venta_activa:
            return JsonResponse({
                'status': 'error',
                'message': (
                    f'No se puede poner en mantenimiento la butaca {butaca.fila}{butaca.numero}: '
                    'tiene entradas vendidas o reservadas para funciones próximas.'
                )
            }, status=400)

    butaca.en_mantenimiento = not butaca.en_mantenimiento
    butaca.save(update_fields=['en_mantenimiento'])

    if butaca.en_mantenimiento:
        mensaje = f'Butaca {butaca.fila}{butaca.numero} puesta en mantenimiento.'
    else:
        mensaje = f'Butaca {butaca.fila}{butaca.numero} disponible nuevamente.'

    return JsonResponse({
        'status': 'ok',
        'en_mantenimiento': butaca.en_mantenimiento,
        'mensaje': mensaje,
    })


@require_http_methods(["POST"])
@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def api_batch_mantenimiento_sala(request, sala_id):
    """
    API AJAX para guardar múltiples cambios de mantenimiento en una sola petición.
    Recibe: {changes: [{butaca_id, en_mantenimiento}]}
    """
    from django.utils import timezone
    from ventas.models import Entrada

    sala = get_object_or_404(Sala, id=sala_id)

    try:
        data = json.loads(request.body)
        changes = data.get('changes', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    if not isinstance(changes, list) or not changes:
        return JsonResponse({'status': 'error', 'message': 'No se enviaron cambios.'}, status=400)

    aplicados = 0
    errores = []

    for change in changes:
        butaca_id = change.get('butaca_id')
        desired = change.get('en_mantenimiento')
        if butaca_id is None or desired is None:
            continue
        try:
            butaca = Butaca.objects.get(id=butaca_id, sala=sala)
        except Butaca.DoesNotExist:
            errores.append(f'Butaca {butaca_id} no encontrada en esta sala.')
            continue
        if butaca.es_pasillo:
            continue
        # Only validate when trying to put IN maintenance
        if desired and not butaca.en_mantenimiento:
            tiene_venta = Entrada.objects.filter(
                id_butaca=butaca,
                estado__in=['PENDIENTE', 'RESERVADA', 'VENDIDA'],
                id_funcion__fecha_hora__gt=timezone.now(),
            ).exists()
            if tiene_venta:
                errores.append(
                    f'Butaca {butaca.fila}{butaca.numero}: tiene entradas activas — no se pudo poner en mantenimiento.'
                )
                continue
        if butaca.en_mantenimiento != desired:
            butaca.en_mantenimiento = desired
            butaca.save(update_fields=['en_mantenimiento'])
            aplicados += 1

    n = aplicados
    msg = f'{n} butaca{"s" if n != 1 else ""} actualizada{"s" if n != 1 else ""} correctamente.'
    return JsonResponse({
        'status': 'ok',
        'aplicados': aplicados,
        'mensaje': msg,
        'errores': errores,
    })
