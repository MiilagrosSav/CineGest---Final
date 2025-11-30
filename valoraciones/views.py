from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from accounts.models import Cliente
from cine.models.funcion import Funcion
from valoraciones.services import puede_valorar
from valoraciones.models import Valoracion


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
