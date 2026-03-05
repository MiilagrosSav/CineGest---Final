from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from accounts.models import Cliente
from cine.models.funcion import Funcion
from valoraciones.services import puede_valorar
from valoraciones.models import Valoracion, NotificacionValoracion as Notificacion


@login_required
@require_POST
def registrar_valoracion(request):
    funcion_id = request.POST.get('funcion_id')
    estrellas = request.POST.get('estrellas')
    comentario = request.POST.get('comentario', '').strip()

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    # Log básico para diagnóstico
    try:
        logger.debug('registrar_valoracion called; AJAX=%s; headers=%s', is_ajax, {k: v for k, v in request.headers.items()})
    except Exception:
        pass

    # Obtener cliente
    try:
        cliente = Cliente.objects.get(usuario=request.user)
    except Cliente.DoesNotExist:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Solo clientes pueden dejar valoraciones.'}, status=403)
        messages.error(request, 'Solo clientes pueden dejar valoraciones.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # Validar inputs
    if not funcion_id or not estrellas:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Datos de valoración incompletos.'}, status=400)
        messages.error(request, 'Datos de valoración incompletos.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        funcion = get_object_or_404(Funcion, pk=int(funcion_id))
    except Exception:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Función inválida.'}, status=400)
        messages.error(request, 'Función inválida.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # Validar reglas de negocio
    try:
        if not puede_valorar(cliente, funcion):
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'No estás autorizado a valorar esta función (comprueba asistencia o espera a que la función termine).'}, status=403)
            messages.error(request, 'No estás autorizado a valorar esta función (comprueba asistencia o espera a que la función termine).')
            return redirect(request.META.get('HTTP_REFERER', '/'))
    except Exception as e:
        logger.exception('Error al evaluar puede_valorar: %s', e)
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Error interno al validar la valoración.'}, status=500)
        messages.error(request, 'Error interno al validar la valoración.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # Guardar valoración
    try:
        puntuacion = int(estrellas)
        if puntuacion < 1 or puntuacion > 5:
            raise ValueError()
    except Exception:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Puntuación inválida.'}, status=400)
        messages.error(request, 'Puntuación inválida.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        Valoracion.objects.create(
            cliente=cliente,
            pelicula=funcion.pelicula,
            funcion=funcion,
            puntuacion=puntuacion,
            comentario=comentario[:500]
        )
        logger.info('Valoracion creada exitosamente: cliente=%s, funcion=%s, puntuacion=%s', cliente.usuario.username, funcion.id, puntuacion)
    except Exception as e:
        logger.exception('Error al crear Valoracion: %s', e)
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'No se pudo guardar la valoración.'}, status=500)
        messages.error(request, 'No se pudo guardar la valoración.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # SIEMPRE devolver JSON para peticiones AJAX
    if is_ajax:
        return JsonResponse({'success': True, 'message': 'Gracias por tu valoración.'}, status=200)

    # Para peticiones normales (no AJAX), redirigir con mensaje
    messages.success(request, 'Gracias por tu valoración.')
    return redirect(request.META.get('HTTP_REFERER', '/'))

from django.shortcuts import render

# Create your views here.


@login_required
def obtener_notificaciones(request):
    """Vista AJAX para obtener notificaciones del cliente."""
    try:
        cliente = Cliente.objects.get(usuario=request.user)
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'notificaciones': []}, status=403)
    
    notificaciones = Notificacion.objects.filter(
        cliente=cliente
    ).order_by('-fecha_creacion')[:10]  # Últimas 10 notificaciones
    
    data = {
        'success': True,
        'notificaciones': [
            {
                'id': n.id,
                'mensaje': n.mensaje,
                'url_destino': n.url_destino,
                'leido': n.leido,
                'fecha': n.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'funcion_id': n.funcion.id if n.funcion else None,
                'pelicula_titulo': n.funcion.pelicula.titulo if n.funcion else ''
            }
            for n in notificaciones
        ],
        'count_no_leidas': Notificacion.objects.filter(cliente=cliente, leido=False).count()
    }
    
    return JsonResponse(data)


@login_required
@require_POST
def marcar_notificacion_leida(request, notificacion_id):
    """Marcar una notificación como leída."""
    try:
        cliente = Cliente.objects.get(usuario=request.user)
        notificacion = get_object_or_404(Notificacion, id=notificacion_id, cliente=cliente)
        notificacion.leido = True
        notificacion.save()
        
        return JsonResponse({
            'success': True,
            'count_no_leidas': Notificacion.objects.filter(cliente=cliente, leido=False).count()
        })
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Cliente no encontrado.'}, status=403)
    except Exception as e:
        logger.exception(f"Error al marcar notificación como leída: {e}")
        return JsonResponse({'success': False, 'message': 'Error al marcar notificación.'}, status=500)


@login_required
def marcar_todas_leidas(request):
    """Marcar todas las notificaciones como leídas."""
    try:
        cliente = Cliente.objects.get(usuario=request.user)
        Notificacion.objects.filter(cliente=cliente, leido=False).update(leido=True)
        
        return JsonResponse({'success': True, 'count_no_leidas': 0})
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Cliente no encontrado.'}, status=403)
    except Exception as e:
        logger.exception(f"Error al marcar todas las notificaciones: {e}")
        return JsonResponse({'success': False, 'message': 'Error.'}, status=500)


@login_required
def modal_valoracion(request):
    """Vista para mostrar el modal de valoración."""
    funcion_id = request.GET.get('funcion_id')
    
    if not funcion_id:
        messages.error(request, 'Función no especificada.')
        return redirect('cine:cartelera')
    
    try:
        cliente = Cliente.objects.get(usuario=request.user)
        funcion = get_object_or_404(Funcion, pk=int(funcion_id))
        
        # Verificar que puede valorar
        if not puede_valorar(cliente, funcion):
            # Mensaje más detallado según la razón
            from valoraciones.models import Valoracion
            if Valoracion.objects.filter(cliente=cliente, funcion=funcion).exists():
                messages.warning(request, '✅ Ya valoraste esta función anteriormente.')
            else:
                from django.utils import timezone
                try:
                    fin_funcion = funcion.get_hora_fin()
                    if fin_funcion and fin_funcion > timezone.now():
                        messages.warning(request, '⏰ Esta función aún no ha terminado. Podrás valorarla cuando finalice.')
                    else:
                        messages.error(request, '❌ No compraste entrada para esta función.')
                except:
                    messages.error(request, '❌ No puedes valorar esta función.')
            
            # Marcar notificación como leída si existe
            try:
                from valoraciones.models import NotificacionValoracion
                notif = NotificacionValoracion.objects.filter(
                    cliente=cliente, 
                    funcion=funcion,
                    leido=False
                ).first()
                if notif:
                    notif.leido = True
                    notif.save()
            except:
                pass
            
            return redirect('cine:cartelera')
        
        context = {
            'funcion': funcion,
            'solo_modal': True
        }
        
        return render(request, 'valoraciones/modal_valoracion_page.html', context)
        
    except Cliente.DoesNotExist:
        messages.error(request, 'Solo clientes pueden valorar.')
        return redirect('cine:cartelera')
    except Exception as e:
        logger.exception(f"Error en modal_valoracion: {e}")
        messages.error(request, 'Error al cargar valoración.')
        return redirect('cine:cartelera')


@login_required
def comentarios_pelicula(request, pelicula_id):
    """Vista para mostrar todos los comentarios de una película."""
    from cine.models import Pelicula
    
    pelicula = get_object_or_404(Pelicula, pk=pelicula_id)
    
    # Obtener todas las valoraciones para esta película
    valoraciones = Valoracion.objects.filter(
        pelicula=pelicula
    ).select_related('cliente__usuario').order_by('-fecha_creacion')
    
    # Calcular estadísticas
    stats = pelicula.get_valoraciones_stats()
    
    context = {
        'pelicula': pelicula,
        'valoraciones': valoraciones,
        'stats': stats,
        'total_comentarios': valoraciones.count(),
    }
    
    return render(request, 'valoraciones/comentarios_pelicula.html', context)


def obtener_valoraciones_pelicula(request, pelicula_id):
    """Vista AJAX para obtener valoraciones paginadas de una película."""
    from cine.models import Pelicula
    from django.core.paginator import Paginator
    
    try:
        pelicula = get_object_or_404(Pelicula, pk=pelicula_id)
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 5))
        
        # Obtener todas las valoraciones (con o sin comentario)
        valoraciones_qs = Valoracion.objects.filter(
            pelicula=pelicula
        ).select_related('cliente__usuario').order_by('-fecha_creacion')
        
        # Paginación
        paginator = Paginator(valoraciones_qs, page_size)
        valoraciones_page = paginator.get_page(page)
        
        # Serializar datos
        valoraciones_data = []
        for val in valoraciones_page:
            nombre_cliente = val.cliente.usuario.get_full_name() or val.cliente.usuario.username or 'Anónimo'
            valoraciones_data.append({
                'cliente': nombre_cliente,
                'puntuacion': val.puntuacion,
                'comentario': val.comentario,
                'fecha': val.fecha_creacion.strftime('%d/%m/%Y %H:%M')
            })
        
        # Calcular estadísticas
        stats = pelicula.get_valoraciones_stats()
        
        return JsonResponse({
            'success': True,
            'valoraciones': valoraciones_data,
            'total': paginator.count,
            'page': valoraciones_page.number,
            'total_pages': paginator.num_pages,
            'has_next': valoraciones_page.has_next(),
            'has_previous': valoraciones_page.has_previous(),
            'stats': {
                'promedio': stats.get('promedio', 0),
                'total': stats.get('total', 0),
                'estrellas_llenas': stats.get('estrellas_llenas', 0)
            }
        })
    except Exception as e:
        logger.exception(f"Error al obtener valoraciones: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Error al cargar valoraciones.'
        }, status=500)

