from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
from django.http import JsonResponse 
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import datetime, timedelta, date, time
import json
from cine.models import Funcion, Pelicula, Sala
from cine.forms import FuncionForm, FuncionBatchForm
from cine.mixins import AdminRequiredMixin


# --- Vistas del CRUD de Funciones ---
# READ: Vista para listar todas las funciones
class FuncionListView(AdminRequiredMixin, ListView):
    model = Funcion
    template_name = 'cine/funcion_list.html'
    context_object_name = 'funciones'
    paginate_by = 5
    
    def get_queryset(self):
        """Filtrar y ordenar funciones según parámetros de búsqueda"""
        queryset = Funcion.objects.select_related('pelicula', 'sala').prefetch_related('formatos_funcion__formato')
        
        # Filtro por búsqueda (título de película o sala)
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                pelicula__titulo__icontains=search
            ) | queryset.filter(
                sala__nombre__icontains=search
            )
        
        # Filtro por película específica
        pelicula_id = self.request.GET.get('pelicula', '').strip()
        if pelicula_id:
            queryset = queryset.filter(pelicula_id=pelicula_id)
        
        # Filtro por sala específica
        sala_id = self.request.GET.get('sala', '').strip()
        if sala_id:
            queryset = queryset.filter(sala_id=sala_id)
        
        # Filtro por fecha
        fecha = self.request.GET.get('fecha', '').strip()
        if fecha:
            try:
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_hora__date=fecha_obj)
            except ValueError:
                pass
        
        # Filtro por formato
        formato_id = self.request.GET.get('formato', '').strip()
        if formato_id:
            queryset = queryset.filter(formatos_funcion__formato_id=formato_id)
        
        # Ordenamiento
        orden = self.request.GET.get('orden', 'fecha')
        orden_mapping = {
            'pelicula': 'pelicula__titulo',
            'pelicula_desc': '-pelicula__titulo',
            'sala': 'sala__numero',
            'sala_desc': '-sala__numero',
            'fecha': 'fecha_hora',
            'fecha_desc': '-fecha_hora',
            'precio': 'precio_base',
            'precio_desc': '-precio_base',
            'duracion': 'pelicula__duracion',
            'duracion_desc': '-pelicula__duracion',
        }
        queryset = queryset.order_by(orden_mapping.get(orden, 'fecha_hora'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Agregar parámetros de búsqueda al contexto"""
        from cine.models import Formato
        
        context = super().get_context_data(**kwargs)
        context['filtro_search'] = self.request.GET.get('search', '')
        context['filtro_pelicula'] = self.request.GET.get('pelicula', '')
        context['filtro_sala'] = self.request.GET.get('sala', '')
        
        # Manejar fecha en formato YYYY-MM-DD (para el input hidden)
        fecha_filtro = self.request.GET.get('fecha', '')
        context['filtro_fecha'] = fecha_filtro
        
        # Convertir a formato DD-MM-YYYY para mostrar al usuario
        if fecha_filtro:
            try:
                fecha_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
                context['filtro_fecha_display'] = fecha_obj.strftime('%d-%m-%Y')
            except ValueError:
                context['filtro_fecha_display'] = ''
        else:
            context['filtro_fecha_display'] = ''
        
        context['filtro_formato'] = self.request.GET.get('formato', '')
        context['filtro_orden'] = self.request.GET.get('orden', 'fecha')
        
        # Pasar listas para los selects
        context['peliculas'] = Pelicula.objects.all().order_by('titulo')
        context['salas'] = Sala.objects.all().order_by('numero')
        context['formatos'] = Formato.objects.all().order_by('nombre')
        
        return context

# CREATE: Vista para mostrar el formulario de creación
# CAMBIO 2: REEMPLAZO DE 'FuncionCreateView' POR UNA VISTA DE FUNCIÓN (FBV)
# La 'CreateView' original se reemplaza por esta función
@ensure_csrf_cookie
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or getattr(u, 'rol', None) == 'admin'), login_url='/accounts/dashboard/')  # Usamos una comprobación inline para evitar referencia temprana a es_admin
def funcion_create_view(request):
    if request.method == 'POST':
        # Usamos el nuevo formulario 'FuncionBatchForm'
        form = FuncionBatchForm(request.POST)
        
        if form.is_valid():
            # Los datos ya están validados, incluida la lógica de solapamiento
            
            # 1. Obtené los datos comunes
            pelicula = form.cleaned_data['pelicula']
            sala = form.cleaned_data['sala']
            fecha = form.cleaned_data['fecha']
            precio = form.cleaned_data['precio_base']
            idioma = form.cleaned_data.get('idioma')  # String: 'DOBLADA', 'SUBTITULADA', etc.
            # Formatos por categoría (un solo objeto por categoría)
            formato_visual = form.cleaned_data.get('formatos_visual')
            formato_pantalla = form.cleaned_data.get('formatos_pantalla')
            formato_experiencia = form.cleaned_data.get('formatos_experiencia')
            
            # 2. Obtené la *lista* de objetos 'time' desde el form
            horarios_obj_lista = form.cleaned_data['horarios']
            
            funciones_creadas = 0
            current_tz = timezone.get_current_timezone() # Para crear datetimes "aware"
            
            # 3. Hacé un bucle por cada horario y creá la función
            for hora_obj in horarios_obj_lista:
                try:
                    # Combina la fecha (date) y la hora (time)
                    fecha_y_hora_final_naive = datetime.combine(fecha, hora_obj)
                    
                    # Convierte a datetime "aware" (consciente de zona horaria)
                    fecha_y_hora_final_aware = timezone.make_aware(fecha_y_hora_final_naive, current_tz)
                    
                    # Crea y guarda el objeto Funcion con el campo idioma
                    funcion = Funcion.objects.create(
                        pelicula=pelicula,
                        sala=sala,
                        fecha_hora=fecha_y_hora_final_aware,
                        precio_base=precio,
                        idioma=idioma  # Guardar el idioma en el modelo
                    )
                    
                    # Crea las relaciones con los formatos en la tabla intermedia
                    from cine.models import FuncionFormato
                    for formato in (formato_visual, formato_pantalla, formato_experiencia):
                        if formato:
                            FuncionFormato.objects.create(
                                funcion=funcion,
                                formato=formato
                            )
                    
                    funciones_creadas += 1
                
                except Exception as e:
                    # Si algo falla (aunque el form debería atajar todo)
                    messages.error(request, f"Error al crear horario {hora_obj.strftime('%H:%M')}: {e}")

            if funciones_creadas > 0:
                messages.success(request, f"¡Se crearon {funciones_creadas} funciones exitosamente!")
            
            # Mostrar cualquier error de validación 'clean' (ej. solapamiento)
            if form.non_field_errors():
                for error in form.non_field_errors():
                    messages.error(request, error)
            
            # Si no hubo errores de solapamiento, redirigir
            if not form.non_field_errors():
                return redirect('cine:funcion_list')

    else:
        # Si es un GET, solo muestra el formulario vacío
        form = FuncionBatchForm()

    # Contexto para el template
    context = {
        'form': form,
        'titulo_pagina': '🎭 Programar Nuevas Funciones (por Lote)',
        'nombre_boton': '✨ Crear Funciones'
    }
    return render(request, 'cine/funcion_form.html', context)

# FIN DEL CAMBIO 2

# UPDATE: Vista para mostrar el formulario de edición
class FuncionUpdateView(AdminRequiredMixin, UpdateView):
    model = Funcion
    form_class = FuncionBatchForm  # Usar el mismo formulario que para creación
    template_name = 'cine/funcion_form.html'
    success_url = reverse_lazy('cine:funcion_list')

    def dispatch(self, request, *args, **kwargs):
        """Validar que la función no haya terminado antes de permitir edición"""
        # Necesitamos establecer self.object antes de validar
        self.object = self.get_object()
        funcion = self.object
        ahora = timezone.now()
        
        # Calcular hora de fin de la función
        duracion_pelicula = funcion.pelicula.duracion
        hora_fin = funcion.fecha_hora + timedelta(minutes=duracion_pelicula)
        
        # Si la función ya terminó, no permitir edición
        if hora_fin < ahora:
            messages.error(
                request,
                f'❌ No se puede editar la función de "{funcion.pelicula.titulo}" porque ya finalizó '
                f'el {hora_fin.strftime("%d/%m/%Y a las %H:%M")}.'
            )
            return redirect('cine:funcion_list')
        
        return super(UpdateView, self).dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Sobrescribir para no pasar 'instance' a un Form (solo para ModelForm)"""
        kwargs = {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
        }
        
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
        
        return kwargs
    
    def get_initial(self):
        """Inicializar el formulario con los datos de la función existente"""
        initial = super().get_initial()
        funcion = self.object
        
        # Separar fecha_hora en fecha y horarios
        initial['pelicula'] = funcion.pelicula.id
        initial['sala'] = funcion.sala.id
        initial['fecha'] = funcion.fecha_hora.date()
        # NO establecer horarios aquí - se cargarán automáticamente via AJAX
        # initial['horarios'] se dejará vacío para que JavaScript lo llene
        initial['precio_base'] = funcion.precio_base
        
        # Cargar los formatos actuales usando los IDs
        formatos_actuales = funcion.formatos_funcion.select_related('formato').all()
        visual = formatos_actuales.filter(formato__nombre__in=['2D', '3D']).first()
        pantalla = formatos_actuales.filter(formato__nombre__in=['Pantalla Standard', 'IMAX', 'ScreenX']).first()
        experiencia = formatos_actuales.filter(formato__nombre__in=['Experiencia Standard', '4DX', 'D-BOX']).first()
        
        if visual:
            initial['formatos_visual'] = visual.formato.id
        if pantalla:
            initial['formatos_pantalla'] = pantalla.formato.id
        if experiencia:
            initial['formatos_experiencia'] = experiencia.formato.id
        
        # Cargar el idioma desde el campo directo de Funcion (no desde formatos)
        if funcion.idioma:
            initial['idioma'] = funcion.idioma
        
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '📝 Editar Función'
        context['nombre_boton'] = '💾 Guardar Cambios'
        context['es_edicion'] = True
        
        # Agregar info de la función actual para el JavaScript (como JSON)
        funcion = self.object
        funcion_data = {
            'id': funcion.id,
            'pelicula_id': funcion.pelicula.id,
            'sala_id': funcion.sala.id,
            'fecha': funcion.fecha_hora.strftime('%Y-%m-%d'),
            'hora': funcion.fecha_hora.strftime('%H:%M'),
        }
        context['funcion_actual'] = json.dumps(funcion_data)
        
        return context
    
    def form_valid(self, form):
        """Actualizar la función con los datos del formulario batch"""
        from cine.models import FuncionFormato
        
        # Validar nuevamente que la función no haya terminado
        ahora = timezone.now()
        duracion_pelicula = self.object.pelicula.duracion
        hora_fin = self.object.fecha_hora + timedelta(minutes=duracion_pelicula)
        
        if hora_fin < ahora:
            messages.error(
                self.request,
                '❌ No se puede modificar una función que ya finalizó.'
            )
            return redirect('cine:funcion_list')
        
        # Obtener los datos del formulario
        pelicula = form.cleaned_data['pelicula']
        sala = form.cleaned_data['sala']
        fecha = form.cleaned_data['fecha']
        horarios = form.cleaned_data['horarios']  # Lista de objetos time
        precio_base = form.cleaned_data['precio_base']
        idioma = form.cleaned_data.get('idioma')  # String: 'DOBLADA', 'SUBTITULADA', 'NATIVA'
        
        # En edición, tomar el primer horario seleccionado
        # (Si seleccionaron múltiples, solo se usará el primero para actualizar esta función)
        if isinstance(horarios, list) and len(horarios) > 0:
            horario = horarios[0]
        else:
            horario = horarios
        
        # Combinar fecha + horario en datetime
        fecha_hora = timezone.make_aware(datetime.combine(fecha, horario))
        
        # Actualizar la función
        self.object.pelicula = pelicula
        self.object.sala = sala
        self.object.fecha_hora = fecha_hora
        self.object.precio_base = precio_base
        self.object.idioma = idioma  # Actualizar el idioma
        self.object.save()
        
        # Obtener los formatos seleccionados por categoría (solo los 3 formatos reales)
        formato_visual = form.cleaned_data.get('formatos_visual')
        formato_pantalla = form.cleaned_data.get('formatos_pantalla')
        formato_experiencia = form.cleaned_data.get('formatos_experiencia')

        # Eliminar formatos antiguos
        self.object.formatos_funcion.all().delete()

        # Crear los nuevos formatos (solo los 3 formatos, no el idioma)
        for formato in (formato_visual, formato_pantalla, formato_experiencia):
            if formato:
                FuncionFormato.objects.create(funcion=self.object, formato=formato)
        
        messages.success(self.request, '✓ Función actualizada correctamente.')
        return redirect(self.success_url)

# DELETE: Vista para confirmar la eliminación
class FuncionDeleteView(AdminRequiredMixin, DeleteView):
    model = Funcion
    template_name = 'cine/funcion_confirm_delete.html'
    success_url = reverse_lazy('cine:funcion_list')


# AJAX: Vista para calcular horarios disponibles
@login_required
def calcular_horarios_disponibles(request):
    """
    Vista AJAX que recibe película, sala y fecha,
    y devuelve una lista de horarios disponibles que no se solapan.
    """
    if request.method == 'GET':
        pelicula_id = request.GET.get('pelicula_id')
        sala_id = request.GET.get('sala_id')
        fecha_str = request.GET.get('fecha')  # formato: YYYY-MM-DD
        funcion_id = request.GET.get('funcion_id')  # opcional, para excluir en modo edición
        
        if not all([pelicula_id, sala_id, fecha_str]):
            return JsonResponse({'error': 'Faltan parámetros'}, status=400)
        
        try:
            from cine.models import ConfiguracionCine
            
            pelicula = Pelicula.objects.get(pk=pelicula_id)
            sala = Sala.objects.get(pk=sala_id)
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # Verificar que la fecha no sea en el pasado
            if fecha < date.today():
                return JsonResponse({'error': 'La fecha no puede ser en el pasado'}, status=400)
            
            # Obtener configuración del cine
            configuracion = ConfiguracionCine.load()
            minutos_limpieza = configuracion.minutos_limpieza
            
            # Calcular duración total (película + minutos de limpieza configurados)
            duracion_total_minutos = pelicula.duracion + minutos_limpieza
            
            # Obtener funciones ya programadas en esa sala y día
            funciones_existentes = Funcion.objects.filter(
                sala=sala,
                fecha_hora__date=fecha
            )
            
            # Si es modo edición, excluir la función actual
            if funcion_id:
                funciones_existentes = funciones_existentes.exclude(pk=funcion_id)
            
            funciones_existentes = funciones_existentes.order_by('fecha_hora')
            
            # Usar horarios de apertura y cierre de la configuración
            hora_inicio = configuracion.horario_apertura
            hora_fin = configuracion.horario_cierre
            
            # Generar todos los horarios posibles cada 15 minutos
            horarios_disponibles = []
            current_tz = timezone.get_current_timezone()
            
            # Crear datetime para el inicio del día
            hora_actual = datetime.combine(fecha, hora_inicio)
            hora_cierre = datetime.combine(fecha, hora_fin)
            
            # IMPORTANTE: Si es HOY, solo mostrar horarios después de la hora actual
            ahora = timezone.now()
            if fecha == ahora.date():
                # Es hoy, necesitamos filtrar horarios pasados
                hora_minima = ahora + timedelta(minutes=30)  # Al menos 30 min en el futuro
                hora_minima_naive = hora_minima.replace(tzinfo=None)
                
                # Si la hora actual del bucle es menor a la hora mínima, avanzar
                if hora_actual < hora_minima_naive:
                    hora_actual = hora_minima_naive
                    # Redondear al próximo múltiplo de 15 minutos
                    minutos = hora_actual.minute
                    minutos_redondeados = ((minutos + 14) // 15) * 15
                    if minutos_redondeados >= 60:
                        hora_actual = hora_actual.replace(minute=0) + timedelta(hours=1)
                    else:
                        hora_actual = hora_actual.replace(minute=minutos_redondeados)
            
            while hora_actual <= hora_cierre:
                # Calcular fin de esta posible función (incluyendo limpieza)
                fin_funcion = hora_actual + timedelta(minutes=duracion_total_minutos)
                
                # Verificar que la función termine antes del cierre
                if fin_funcion.time() > hora_fin:
                    break
                
                # Verificar si se solapa con alguna función existente
                hay_solapamiento = False
                for funcion_existente in funciones_existentes:
                    inicio_existente = funcion_existente.fecha_hora
                    # Convertir a naive para comparar (si es aware)
                    if timezone.is_aware(inicio_existente):
                        inicio_existente = timezone.localtime(inicio_existente).replace(tzinfo=None)
                    
                    fin_existente = inicio_existente + timedelta(minutes=funcion_existente.pelicula.duracion + 30)
                    
                    # Comparar en naive datetime
                    if hora_actual < fin_existente and fin_funcion > inicio_existente:
                        hay_solapamiento = True
                        break
                
                # Si no hay solapamiento, agregar
                if not hay_solapamiento:
                    horarios_disponibles.append(hora_actual.strftime('%H:%M'))
                
                # Avanzar 15 minutos
                hora_actual += timedelta(minutes=15)
            
            return JsonResponse({
                'horarios': horarios_disponibles,
                'duracion_total': duracion_total_minutos,
                'mensaje': f'Cada función dura {pelicula.duracion} min + {minutos_limpieza} min de limpieza = {duracion_total_minutos} min total'
            })
            
        except (Pelicula.DoesNotExist, Sala.DoesNotExist):
            return JsonResponse({'error': 'Película o sala no encontrada'}, status=404)
        except ValueError:
            return JsonResponse({'error': 'Formato de fecha inválido'}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)