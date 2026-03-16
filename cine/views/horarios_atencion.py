"""
Vistas para gestión de Horarios de Atención (Sistema Flexible por Día)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction
from django.core.exceptions import ValidationError

from cine.models import ConfiguracionCine, HorarioAtencion, ExcepcionHorario
from cine.forms import HorarioAtencionFormSet, ExcepcionHorarioForm


def es_staff(user):
    """Helper: Verifica que el usuario sea staff"""
    return user.is_staff


@login_required
@user_passes_test(es_staff)
def gestionar_horarios_view(request):
    """
    Vista principal para gestionar todos los horarios de atención.
    Muestra una tabla con los horarios de cada día y permite agregar/editar/eliminar.
    """
    configuracion = ConfiguracionCine.load()
    
    # Ordenar horarios por día de la semana
    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    # Construir estructura de datos para el template
    dias_semana = []
    for dia_num in range(7):
        horarios = HorarioAtencion.objects.filter(
            configuracion_cine=configuracion,
            dia_semana=dia_num
        ).order_by('orden', 'hora_apertura')
        
        dias_semana.append({
            'numero': dia_num,
            'nombre': dias_nombres[dia_num],
            'horarios': horarios
        })
    
    # Obtener excepciones (futuras y pasadas)
    from datetime import date
    hoy = date.today()
    
    excepciones_futuras = ExcepcionHorario.objects.filter(
        configuracion_cine=configuracion,
        fecha__gte=hoy
    ).order_by('fecha')
    
    excepciones_pasadas = ExcepcionHorario.objects.filter(
        configuracion_cine=configuracion,
        fecha__lt=hoy
    ).order_by('-fecha')[:10]  # Últimas 10 excepciones pasadas
    
    context = {
        'configuracion': configuracion,
        'dias_semana': dias_semana,
        'excepciones_futuras': excepciones_futuras,
        'excepciones_pasadas': excepciones_pasadas,
        'title': 'Gestión de Horarios de Atención'
    }
    
    return render(request, 'cine/horarios_atencion_list.html', context)


@login_required
@user_passes_test(es_staff)
@require_http_methods(["GET", "POST"])
def editar_horarios_dia_view(request, dia_semana):
    """
    Vista para editar los horarios de un día específico usando FormSet.
    Permite agregar múltiples rangos horarios para el mismo día.
    
    Args:
        dia_semana (int): Número del día (0=Lunes, 6=Domingo)
    """
    if dia_semana < 0 or dia_semana > 6:
        messages.error(request, '❌ Día de semana inválido.')
        return redirect('cine:gestionar_horarios')
    
    configuracion = ConfiguracionCine.load()
    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dia_nombre = dias_nombres[dia_semana]
    
    # Obtener horarios existentes para este día
    queryset = HorarioAtencion.objects.filter(
        configuracion_cine=configuracion,
        dia_semana=dia_semana
    ).order_by('orden', 'hora_apertura')
    
    if request.method == 'POST':
        # Validar si hay entradas vendidas para este día en el futuro o hoy
        from cine.models import Funcion
        from django.utils import timezone

        iso_dia = dia_semana + 1
        hoy = timezone.now().date()

        funciones_vendidas = Funcion.objects.filter(
            fecha_hora__date__gte=hoy,
            fecha_hora__iso_week_day=iso_dia,
            entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
        ).distinct()

        if funciones_vendidas.exists():
            messages.error(
                request,
                f'No se pueden modificar los horarios del {dia_nombre} porque actualmente hay funciones '
                'con entradas vendidas para este día de la semana. Debes cancelar dichas ventas primero.'
            )
            return redirect('cine:gestionar_horarios')

        formset = HorarioAtencionFormSet(request.POST, queryset=queryset)

        if formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardar todos los formularios del formset
                    instances = formset.save(commit=False)

                    # Asignar configuracion_cine y dia_semana a cada instancia nueva
                    for instance in instances:
                        instance.configuracion_cine = configuracion
                        instance.dia_semana = dia_semana
                        instance.save()

                    # Eliminar los marcados para borrar
                    for obj in formset.deleted_objects:
                        obj.delete()

                    messages.success(
                        request,
                        f'Horarios del {dia_nombre} actualizados correctamente.'
                    )
                    return redirect('cine:gestionar_horarios')

            except ValidationError as e:
                # Capturar errores de validación del modelo (solapamientos, etc.)
                messages.error(request, f'❌ Error de validación: {e}')
            except Exception as e:
                messages.error(request, f'❌ Error al guardar: {str(e)}')
        else:
            messages.error(request, '❌ Hay errores en el formulario. Revisa los campos marcados.')
    else:
        formset = HorarioAtencionFormSet(queryset=queryset)
    
    context = {
        'formset': formset,
        'dia_semana': dia_semana,
        'dia_nombre': dia_nombre,
        'configuracion': configuracion,
        'title': f'Editar Horarios - {dia_nombre}'
    }
    
    return render(request, 'cine/horarios_atencion_edit.html', context)


@login_required
@user_passes_test(es_staff)
@require_POST
def copiar_horarios_dia_view(request):
    """
    Vista AJAX para copiar horarios de un día origen a uno o más días destino.
    
    POST params:
        - dia_origen: int (0-6)
        - dias_destino: list[int] (ej: [1, 2, 5])
        - sobrescribir: bool (default: False)
    
    Returns:
        JSON: {success: bool, message: str, copiados: int}
    """
    try:
        # Obtener parámetros
        dia_origen = int(request.POST.get('dia_origen'))
        dias_destino_str = request.POST.getlist('dias_destino[]')
        dias_destino = [int(d) for d in dias_destino_str if d]
        sobrescribir = request.POST.get('sobrescribir', 'false').lower() == 'true'
        
        # Validaciones
        if dia_origen not in range(7):
            return JsonResponse({'error': 'Día origen inválido (debe ser 0-6)'}, status=400)
        
        if not dias_destino:
            return JsonResponse({'error': 'Debes seleccionar al menos un día destino'}, status=400)
        
        if any(d not in range(7) for d in dias_destino):
            return JsonResponse({'error': 'Algún día destino es inválido (debe ser 0-6)'}, status=400)
        
        if dia_origen in dias_destino:
            return JsonResponse({'error': 'No puedes copiar un día sobre sí mismo'}, status=400)
        
        # Obtener configuración
        config = ConfiguracionCine.load()
        
        # Obtener horarios origen
        horarios_origen = HorarioAtencion.objects.filter(
            configuracion_cine=config,
            dia_semana=dia_origen
        ).order_by('orden')
        
        if not horarios_origen.exists():
            return JsonResponse({
                'error': 'No hay horarios configurados en el día origen para copiar'
            }, status=400)
        
        # Transacción atómica para consistencia
        with transaction.atomic():
            total_copiados = 0
            dias_afectados = []
            dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

            from cine.models import Funcion
            from django.utils import timezone
            hoy = timezone.now().date()

            for dia_destino in dias_destino:
                # Validar restricciones de funciones vendidas para el día destino
                if sobrescribir:
                    iso_dia = dia_destino + 1
                    funciones_vendidas = Funcion.objects.filter(
                        fecha_hora__date__gte=hoy,
                        fecha_hora__iso_week_day=iso_dia,
                        entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
                    ).distinct()

                    if funciones_vendidas.exists():
                        dia_nombre = dias_nombres[dia_destino]
                        return JsonResponse({
                            'error': f'No se puede sobrescribir el horario del {dia_nombre} porque actualmente hay funciones con entradas vendidas para este día de la semana. Debes cancelar dichas ventas primero.'
                        }, status=400)

                    count_eliminados = HorarioAtencion.objects.filter(
                        configuracion_cine=config,
                        dia_semana=dia_destino
                    ).delete()[0]
                    
                    if count_eliminados > 0:
                        print(f"🗑️ Eliminados {count_eliminados} horarios de {dias_nombres[dia_destino]}")
                
                # Copiar cada horario del día origen al día destino
                for horario_orig in horarios_origen:
                    HorarioAtencion.objects.create(
                        configuracion_cine=config,
                        dia_semana=dia_destino,
                        hora_apertura=horario_orig.hora_apertura,
                        hora_cierre=horario_orig.hora_cierre,
                        activo=horario_orig.activo,
                        orden=horario_orig.orden
                    )
                    total_copiados += 1
                
                dias_afectados.append(dias_nombres[dia_destino])
            
            mensaje = (
                f'Copia exitosa: {len(horarios_origen)} horario(s) de '
                f'{dias_nombres[dia_origen]} copiados a {len(dias_destino)} día(s): '
                f'{", ".join(dias_afectados)}'
            )
            
            if sobrescribir:
                mensaje += ' (sobrescribiendo horarios existentes)'
            
            return JsonResponse({
                'success': True,
                'message': mensaje,
                'copiados': total_copiados,
                'dias_afectados': dias_afectados
            })
    
    except ValueError as e:
        return JsonResponse({'error': f'Parámetros inválidos: {str(e)}'}, status=400)
    
    except Exception as e:
        return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)


@login_required
@user_passes_test(es_staff)
@require_POST
def eliminar_horario_view(request, horario_id):
    """
    Vista para eliminar un horario específico.
    """
    horario = get_object_or_404(HorarioAtencion, pk=horario_id)

    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dia_nombre = dias_nombres[horario.dia_semana]
    
    # Validar si hay entradas vendidas para este día en el futuro o hoy
    from cine.models import Funcion
    from django.utils import timezone
    hoy = timezone.now().date()
    iso_dia = horario.dia_semana + 1
    funciones_vendidas = Funcion.objects.filter(
        fecha_hora__date__gte=hoy,
        fecha_hora__iso_week_day=iso_dia,
        entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
    ).distinct()

    if funciones_vendidas.exists():
        messages.error(
            request, 
            f'No se puede eliminar el horario del {dia_nombre} porque actualmente hay funciones '
            'con entradas vendidas para este día de la semana. Debes cancelar dichas ventas primero.'
        )
        return redirect('cine:gestionar_horarios')

    try:
        horario.delete()
        messages.success(
            request,
            f'✅ Horario del {dia_nombre} eliminado correctamente: '
            f'{horario.hora_apertura.strftime("%H:%M")} - {horario.hora_cierre.strftime("%H:%M")}'
        )
    except Exception as e:
        messages.error(request, f'❌ Error al eliminar: {str(e)}')
    
    return redirect('cine:gestionar_horarios')


# ============================================================================
# VISTAS: GESTIÓN DE EXCEPCIONES DE HORARIO
# ============================================================================
# NOTA: Las excepciones se listan en gestionar_horarios_view (vista unificada)
# Este módulo solo contiene las vistas de CRUD (crear/editar/eliminar)

@login_required
@user_passes_test(es_staff)
@require_http_methods(["GET", "POST"])
def crear_excepcion_view(request):
    """
    Vista para crear una nueva excepción de horario.
    
    GET: Muestra el formulario vacío
    POST: Valida y guarda la excepción
    """
    if request.method == 'POST':
        form = ExcepcionHorarioForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    excepcion = form.save()
                    
                    # Mensaje personalizado según tipo de excepción
                    if excepcion.cerrado:
                        mensaje = (
                            f'Excepción creada: Cine CERRADO el {excepcion.fecha.strftime("%d/%m/%Y")}. '
                            f'Motivo: {excepcion.descripcion or "Sin especificar"}'
                        )
                    else:
                        mensaje = (
                            f'Excepción creada: Horario modificado el {excepcion.fecha.strftime("%d/%m/%Y")} '
                            f'({excepcion.hora_apertura.strftime("%H:%M")} - {excepcion.hora_cierre.strftime("%H:%M")}). '
                            f'Motivo: {excepcion.descripcion or "Sin especificar"}'
                        )
                    
                    messages.success(request, mensaje)
                    return redirect('cine:gestionar_horarios')  # Redirigir a horarios principal
                    
            except ValidationError as e:
                # Capturar errores de validación del modelo
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    messages.error(request, f'❌ Error de validación: {e}')
                    
            except Exception as e:
                messages.error(request, f'❌ Error al guardar: {str(e)}')
        else:
            # No mostrar mensaje genérico si el error principal es 'cerrado'
            # (ignorar errores de hora_apertura/hora_cierre que son consecuencia)
            if 'cerrado' in form.errors:
                # Si hay error en 'cerrado', no mostrar mensaje genérico
                # El error específico ya se muestra destacado en el template
                pass
            else:
                # Si hay otros errores, mostrar mensaje genérico
                messages.error(request, '❌ Hay errores en el formulario. Revisa los campos marcados.')
    else:
        form = ExcepcionHorarioForm()
    
    context = {
        'form': form,
        'titulo': 'Crear Excepción de Horario',
        'boton_texto': 'Guardar Excepción',
        'es_edicion': False
    }
    
    return render(request, 'cine/excepcion_form.html', context)


@login_required
@user_passes_test(es_staff)
@require_http_methods(["GET", "POST"])
def editar_excepcion_view(request, excepcion_id):
    """
    Vista para editar una excepción de horario existente.
    
    Args:
        excepcion_id (int): ID de la excepción a editar
    
    GET: Muestra el formulario con datos actuales
    POST: Valida y actualiza la excepción
    """
    excepcion = get_object_or_404(ExcepcionHorario, pk=excepcion_id)
    
    if request.method == 'POST':
        # Validar si hay entradas vendidas en esa vieja excepcion
        from cine.models import Funcion
        fecha_inicio = excepcion.fecha
        fecha_final = excepcion.fecha_fin if excepcion.fecha_fin else excepcion.fecha
        
        funciones_vendidas = Funcion.objects.filter(
            fecha_hora__date__gte=fecha_inicio,
            fecha_hora__date__lte=fecha_final,
            entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
        ).distinct()

        if funciones_vendidas.exists():
            messages.error(
                request, 
                'No se puede modificar la excepción de horario porque hay funciones o entradas vendidas en las fechas originales afectadas.'
            )
            return redirect('cine:gestionar_horarios')

            try:
                with transaction.atomic():
                    excepcion = form.save()
                    
                    # Mensaje personalizado según tipo de excepción
                    if excepcion.cerrado:
                        mensaje = (
                            f'Excepción actualizada: Cine CERRADO el {excepcion.fecha.strftime("%d/%m/%Y")}. '
                            f'Motivo: {excepcion.descripcion or "Sin especificar"}'
                        )
                    else:
                        mensaje = (
                            f'Excepción actualizada: Horario modificado el {excepcion.fecha.strftime("%d/%m/%Y")} '
                            f'({excepcion.hora_apertura.strftime("%H:%M")} - {excepcion.hora_cierre.strftime("%H:%M")}). '
                            f'Motivo: {excepcion.descripcion or "Sin especificar"}'
                        )
                    
                    messages.success(request, mensaje)
                    return redirect('cine:gestionar_horarios')
                    
            except ValidationError as e:
                # Capturar errores de validación del modelo
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    messages.error(request, f'❌ Error de validación: {e}')
                    
            except Exception as e:
                messages.error(request, f'❌ Error al actualizar: {str(e)}')
        else:
            # No mostrar mensaje genérico si el error principal es 'cerrado'
            # (ignorar errores de hora_apertura/hora_cierre que son consecuencia)
            if 'cerrado' in form.errors:
                # Si hay error en 'cerrado', no mostrar mensaje genérico
                # El error específico ya se muestra destacado en el template
                pass
            else:
                # Si hay otros errores, mostrar mensaje genérico
                messages.error(request, '❌ Hay errores en el formulario. Revisa los campos marcados.')
    else:
        form = ExcepcionHorarioForm(instance=excepcion)
    
    context = {
        'form': form,
        'excepcion': excepcion,
        'titulo': f'Editar Excepción - {excepcion.fecha.strftime("%d/%m/%Y")}',
        'boton_texto': 'Actualizar Excepción',
        'es_edicion': True
    }
    
    return render(request, 'cine/excepcion_form.html', context)


@login_required
@user_passes_test(es_staff)
@require_POST
def eliminar_excepcion_view(request, excepcion_id):
    """
    Vista para eliminar una excepción de horario.
    
    Args:
        excepcion_id (int): ID de la excepción a eliminar
    
    Solo acepta método POST por seguridad.
    Muestra mensaje de confirmación y redirige al listado.
    """
    excepcion = get_object_or_404(ExcepcionHorario, pk=excepcion_id)

    # Validar que no haya cancelaciones de ventas (las excepciones no se pueden eliminar si hay compras)
    from cine.models import Funcion
    fecha_inicio = excepcion.fecha
    fecha_final = excepcion.fecha_fin if excepcion.fecha_fin else excepcion.fecha
    
    funciones_vendidas = Funcion.objects.filter(
        fecha_hora__date__gte=fecha_inicio,
        fecha_hora__date__lte=fecha_final,
        entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
    ).distinct()

    if funciones_vendidas.exists():
        messages.error(
            request, 
            'No se puede eliminar la excepción de horario porque hay funciones o entradas vendidas en las fechas afectadas.'
        )
        return redirect('cine:gestionar_horarios')

    # Guardar información para el mensaje antes de eliminar
    fecha_str = excepcion.fecha.strftime('%d/%m/%Y')
    descripcion = excepcion.descripcion or 'Sin descripción'
    es_cerrado = excepcion.cerrado
    
    try:
        excepcion.delete()
        
        # Mensaje personalizado según tipo
        if es_cerrado:
            mensaje = f'✅ Excepción eliminada: Cine cerrado el {fecha_str} ({descripcion})'
        else:
            mensaje = f'✅ Excepción eliminada: Horario modificado del {fecha_str} ({descripcion})'
        
        messages.success(request, mensaje)
        
    except Exception as e:
        messages.error(request, f'❌ Error al eliminar la excepción: {str(e)}')
    
    return redirect('cine:gestionar_horarios')

