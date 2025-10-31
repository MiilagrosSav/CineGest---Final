from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
import datetime
from cine.models import Funcion
from cine.forms import FuncionForm, FuncionBatchForm
from cine.mixins import AdminRequiredMixin


# --- Vistas del CRUD de Funciones ---
# READ: Vista para listar todas las funciones
class FuncionListView(AdminRequiredMixin, ListView):
    model = Funcion
    template_name = 'cine/funcion_list.html'
    context_object_name = 'funciones'
    paginate_by = 20
    
    def get_queryset(self):
        """Ordenar funciones por fecha_hora y precargar relaciones para optimizar"""
        return Funcion.objects.select_related('pelicula', 'sala').order_by('fecha_hora')

# CREATE: Vista para mostrar el formulario de creación
# CAMBIO 2: REEMPLAZO DE 'FuncionCreateView' POR UNA VISTA DE FUNCIÓN (FBV)
# La 'CreateView' original se reemplaza por esta función
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or getattr(u, 'rol', None) == 'admin'), login_url='/accounts/dashboard/')  # Usamos una comprobación inline para evitar referencia temprana a es_admin
def funcion_create_view(request):
    if request.method == 'POST':
        # Usamos el nuevo formulario 'FuncionBatchForm'
        form = FuncionBatchForm(request.POST)
        # Usamos el nuevo formulario 'FuncionBatchForm'
        form = FuncionBatchForm(request.POST)
        
        if form.is_valid():
            # Los datos ya están validados, incluida la lógica de solapamiento
            
            # 1. Obtené los datos comunes
            pelicula = form.cleaned_data['pelicula']
            sala = form.cleaned_data['sala']
            fecha = form.cleaned_data['fecha']
            precio = form.cleaned_data['precio_base']
            formato = form.cleaned_data['formato_proyeccion']
            
            # 2. Obtené la *lista* de objetos 'time' desde el form
            horarios_obj_lista = form.cleaned_data['horarios']
            
            funciones_creadas = 0
            current_tz = timezone.get_current_timezone() # Para crear datetimes "aware"
            
            # 3. Hacé un bucle por cada horario y creá la función
            for hora_obj in horarios_obj_lista:
                try:
                    # Combina la fecha (date) y la hora (time)
                    fecha_y_hora_final_naive = datetime.datetime.combine(fecha, hora_obj)
                    
                    # Convierte a datetime "aware" (consciente de zona horaria)
                    fecha_y_hora_final_aware = timezone.make_aware(fecha_y_hora_final_naive, current_tz)
                    
                    # Crea y guarda el objeto Funcion
                    Funcion.objects.create(
                        pelicula=pelicula,
                        sala=sala,
                        fecha_hora=fecha_y_hora_final_aware, # Guarda el datetime aware
                        precio_base=precio,
                        formato_proyeccion=formato
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
    form_class = FuncionForm
    template_name = 'cine/funcion_form.html'
    success_url = reverse_lazy('cine:funcion_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '📝 Editar Función'
        context['nombre_boton'] = '💾 Guardar Cambios'
        return context

# DELETE: Vista para confirmar la eliminación
class FuncionDeleteView(AdminRequiredMixin, DeleteView):
    model = Funcion
    template_name = 'cine/funcion_confirm_delete.html'
    success_url = reverse_lazy('cine:funcion_list')