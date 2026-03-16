"""
Vistas para gestión de Clasificaciones de Edad
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone

from cine.models import Clasificacion, Funcion
from cine.forms import ClasificacionForm


def es_staff(user):
    """Helper: Verifica que el usuario sea staff"""
    return user.is_staff


@login_required
@user_passes_test(es_staff)
def gestionar_clasificaciones_view(request):
    """
    Vista principal para gestionar las clasificaciones de edad.
    Muestra lista de clasificaciones activas e inactivas.
    Incluye información sobre si pueden ser desactivadas.
    """
    clasificaciones_activas = Clasificacion.objects.filter(activo=True).order_by('edad_minima', 'nombre')
    clasificaciones_inactivas = Clasificacion.objects.filter(activo=False).order_by('edad_minima', 'nombre')
    
    # Determinar qué clasificaciones pueden desactivarse
    ahora = timezone.now()
    clasificaciones_activas_info = []
    for clasificacion in clasificaciones_activas:
        peliculas_activas = clasificacion.peliculas.filter(activo=True)
        puede_desactivar = True
        razon_bloqueo = ""
        
        if peliculas_activas.exists():
            funciones_vigentes = Funcion.objects.filter(
                pelicula__in=peliculas_activas,
                fecha_hora__gte=ahora,
                activo=True
            ).count()
            
            if funciones_vigentes > 0:
                puede_desactivar = False
                razon_bloqueo = f"Hay {funciones_vigentes} función(es) vigente(s)"
        
        clasificaciones_activas_info.append({
            'clasificacion': clasificacion,
            'puede_desactivar': puede_desactivar,
            'razon_bloqueo': razon_bloqueo
        })
    
    context = {
        'clasificaciones_activas': clasificaciones_activas_info,
        'clasificaciones_inactivas': clasificaciones_inactivas,
        'title': 'Gestión de Clasificaciones de Edad'
    }
    
    return render(request, 'cine/clasificaciones_list.html', context)


@login_required
@user_passes_test(es_staff)
def crear_clasificacion_view(request):
    """
    Vista para crear una nueva clasificación.
    """
    if request.method == 'POST':
        form = ClasificacionForm(request.POST, is_creation=True)
        if form.is_valid():
            clasificacion = form.save(commit=False)
            clasificacion.activo = True  # Establecer activo=True por defecto
            clasificacion.save()
            messages.success(
                request,
                f' Clasificación "{clasificacion.nombre}" creada correctamente.'
            )
            return redirect('cine:gestionar_clasificaciones')
        else:
            messages.error(request, '❌ Hay errores en el formulario. Revisa los campos marcados.')
    else:
        form = ClasificacionForm(is_creation=True)
    
    context = {
        'form': form,
        'title': 'Nueva Clasificación',
        'accion': 'Crear'
    }
    
    return render(request, 'cine/clasificacion_form.html', context)


@login_required
@user_passes_test(es_staff)
def editar_clasificacion_view(request, pk):
    """
    Vista para editar una clasificación existente.
    No se puede desactivar si hay funciones vigentes.
    """
    clasificacion = get_object_or_404(Clasificacion.all_objects, pk=pk)
    
    if request.method == 'POST':
        form = ClasificacionForm(request.POST, instance=clasificacion)
        if form.is_valid():
            # Verificar si se intenta desactivar
            estaba_activo = clasificacion.activo
            nuevo_estado = form.cleaned_data.get('activo', True)
            
            if estaba_activo and not nuevo_estado:
                # Verificar funciones vigentes antes de permitir desactivación
                peliculas_activas = clasificacion.peliculas.filter(activo=True)
                if peliculas_activas.exists():
                    ahora = timezone.now()
                    funciones_vigentes = Funcion.objects.filter(
                        pelicula__in=peliculas_activas,
                        fecha_hora__gte=ahora,
                        activo=True
                    ).count()
                    
                    if funciones_vigentes > 0:
                        messages.error(
                            request,
                            f'❌ No se puede desactivar la clasificación "{clasificacion.nombre}" '
                            f'porque hay {funciones_vigentes} función(es) vigente(s) de películas con esta clasificación.'
                        )
                        return redirect('cine:gestionar_clasificaciones')
            
            clasificacion = form.save()
            messages.success(
                request,
                f' Clasificación "{clasificacion.nombre}" actualizada correctamente.'
            )
            return redirect('cine:gestionar_clasificaciones')
        else:
            messages.error(request, '❌ Hay errores en el formulario. Revisa los campos marcados.')
    else:
        form = ClasificacionForm(instance=clasificacion)
    
    context = {
        'form': form,
        'clasificacion': clasificacion,
        'title': f'Editar Clasificación: {clasificacion.nombre}',
        'accion': 'Actualizar'
    }
    
    return render(request, 'cine/clasificacion_form.html', context)


@login_required
@user_passes_test(es_staff)
@require_POST
def eliminar_clasificacion_view(request, pk):
    """
    Vista para eliminar (soft delete) una clasificación.
    No se puede desactivar si hay películas con funciones vigentes.
    """
    clasificacion = get_object_or_404(Clasificacion, pk=pk)
    
    # Verificar que no esté siendo usada por películas activas
    peliculas_activas = clasificacion.peliculas.filter(activo=True)
    peliculas_count = peliculas_activas.count()
    
    if peliculas_count > 0:
        # Verificar si hay funciones vigentes (futuras o en curso)
        ahora = timezone.now()
        funciones_vigentes = Funcion.objects.filter(
            pelicula__in=peliculas_activas,
            fecha_hora__gte=ahora,
            activo=True
        ).count()
        
        if funciones_vigentes > 0:
            messages.error(
                request,
                f'❌ No se puede desactivar la clasificación "{clasificacion.nombre}" '
                f'porque hay {funciones_vigentes} función(es) vigente(s) de películas con esta clasificación.'
            )
        else:
            messages.error(
                request,
                f'❌ No se puede desactivar la clasificación "{clasificacion.nombre}" '
                f'porque está asignada a {peliculas_count} película(s) activa(s).'
            )
    else:
        clasificacion.activo = False
        clasificacion.save()
        messages.success(
            request,
            f' Clasificación "{clasificacion.nombre}" desactivada correctamente.'
        )
    
    return redirect('cine:gestionar_clasificaciones')


@login_required
@user_passes_test(es_staff)
@require_POST
def activar_clasificacion_view(request, pk):
    """
    Vista para reactivar una clasificación.
    """
    clasificacion = get_object_or_404(Clasificacion.all_objects, pk=pk)
    
    clasificacion.activo = True
    clasificacion.save()
    messages.success(
        request,
        f' Clasificación "{clasificacion.nombre}" activada correctamente.'
    )
    
    return redirect('cine:gestionar_clasificaciones')
