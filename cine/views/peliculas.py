from cine.mixins import AdminRequiredMixin
from cine.forms import PeliculaForm
from django.contrib.auth.decorators import login_required, user_passes_test
from cine.models import Pelicula, Genero
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import redirect
from cine.services.tmdb_service import tmdb_service
import logging

logger = logging.getLogger(__name__)


# --- Vistas del CRUD de Películas ---
# (El resto de tu código estaba perfecto, no necesita cambios)

# READ: Vista para listar todas las películas
class PeliculaListView(AdminRequiredMixin, ListView):
    model = Pelicula
    template_name = 'cine/pelicula_list.html'
    context_object_name = 'peliculas'
    paginate_by = 5 
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtro de búsqueda por título
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(titulo__icontains=search)
        
        # Filtro por género
        genero = self.request.GET.get('genero', '')
        if genero:
            # aceptar id numérico o búsqueda por nombre (case-insensitive)
            if genero.isdigit():
                queryset = queryset.filter(generos__id=int(genero))
            else:
                queryset = queryset.filter(generos__nombre__icontains=genero)
        
        # Ordenamiento
        orden = self.request.GET.get('orden', 'titulo')
        orden_mapping = {
            'titulo': 'titulo',
            'titulo_desc': '-titulo',
            'duracion': 'duracion',
            'duracion_desc': '-duracion',
            'fecha_estreno': 'fecha_estreno',
            'fecha_estreno_desc': '-fecha_estreno',
        }
        queryset = queryset.order_by(orden_mapping.get(orden, 'titulo'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_search'] = self.request.GET.get('search', '')
        context['filtro_genero'] = self.request.GET.get('genero', '')
        context['filtro_orden'] = self.request.GET.get('orden', 'titulo')
        return context 

    def render_to_response(self, context, **response_kwargs):
        """If AJAX request, return the table partial only."""
        request = self.request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.shortcuts import render
            return render(request, 'cine/_pelicula_table.html', context)
        return super().render_to_response(context, **response_kwargs)

# CREATE: Vista para mostrar el formulario de creación
class PeliculaCreateView(AdminRequiredMixin, CreateView):
    model = Pelicula
    form_class = PeliculaForm
    template_name = 'cine/pelicula_form.html'
    success_url = reverse_lazy('cine:pelicula_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🎬 Añadir Nueva Película'
        context['nombre_boton'] = '✨ Crear Película'
        context['titulo_ayuda_extra'] = 'El titulo puede ser solo numeros.'
        # Pasar la lista de géneros para renderizado en plantilla (checkboxes)
        context['generos'] = Genero.objects.all().order_by('nombre')
        return context
    
    def form_valid(self, form):
        """
        Capturar ValidationError del modelo y descargar póster desde TMDB si aplica
        """
        try:
            # Verificar si se proporcionó un poster_path de TMDB
            tmdb_poster_path = self.request.POST.get('tmdb_poster_path', '').strip()
            
            if tmdb_poster_path:
                logger.info(f"Descargando póster desde TMDB: {tmdb_poster_path}")
                
                # Descargar y redimensionar el póster
                poster_file = tmdb_service.download_poster(tmdb_poster_path)
                
                if poster_file:
                    # Guardar el póster en el campo imagen_local
                    form.instance.imagen_local = poster_file
                    logger.info("Póster descargado y asignado correctamente")

                else:
                    logger.warning("No se pudo descargar el póster desde TMDB")
                    messages.warning(
                        self.request,
                        'No se pudo descargar el póster automáticamente. Puedes subirlo manualmente más tarde.'
                    )
            
            # Guardar la película
            response = super().form_valid(form)
            if getattr(form, 'director_warning_message', None):
                messages.warning(self.request, form.director_warning_message)
            messages.success(
                self.request,
                f'✓ Película "{form.instance.titulo}" creada exitosamente'
            )
            return response
            
        except ValidationError as e:
            # Convertir ValidationError del modelo a errores de formulario
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        form.add_error(field, error.message)
            else:
                form.add_error(None, str(e))
            return self.form_invalid(form)

# UPDATE: Vista para mostrar el formulario de edición
class PeliculaUpdateView(AdminRequiredMixin, UpdateView):
    model = Pelicula
    form_class = PeliculaForm
    template_name = 'cine/pelicula_form.html'
    success_url = reverse_lazy('cine:pelicula_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar Película'
        context['nombre_boton'] = 'Guardar Cambios'
        context['titulo_ayuda_extra'] = 'El titulo puede ser solo numeros.'
        # Pasar la lista de géneros para renderizado en plantilla (checkboxes)
        context['generos'] = Genero.objects.all().order_by('nombre')
        return context
    
    def form_valid(self, form):
        """
        Capturar ValidationError del modelo y descargar póster desde TMDB si aplica
        """
        try:
            if form.cleaned_data.get('desactivar'):
                funciones_activas = self.object.funciones.filter(
                    activo=True,
                    fecha_hora__gte=timezone.now(),
                ).exclude(estado='INACTIVA').exists()
                if funciones_activas:
                    form.add_error('desactivar', 'No se puede desactivar porque hay funciones activas.')
                    return self.form_invalid(form)

                self.object.soft_delete(user=self.request.user)
                messages.success(
                    self.request,
                    f'✓ Película "{self.object.titulo}" desactivada correctamente.'
                )
                return redirect(self.success_url)

            # Verificar si se proporcionó un nuevo poster_path de TMDB
            tmdb_poster_path = self.request.POST.get('tmdb_poster_path', '').strip()
            
            if tmdb_poster_path:
                logger.info(f"Actualizando póster desde TMDB: {tmdb_poster_path}")
                
                # Descargar y redimensionar el póster
                poster_file = tmdb_service.download_poster(tmdb_poster_path)
                
                if poster_file:
                    # Actualizar el póster en el campo imagen_local
                    form.instance.imagen_local = poster_file
                    logger.info("Póster actualizado correctamente")
                else:
                    logger.warning("No se pudo descargar el póster desde TMDB")
                    messages.warning(
                        self.request,
                        'No se pudo actualizar el póster automáticamente.'
                    )
            
            # Guardar los cambios
            response = super().form_valid(form)
            if getattr(form, 'director_warning_message', None):
                messages.warning(self.request, form.director_warning_message)
            messages.success(
                self.request,
                f'✓ Película "{form.instance.titulo}" actualizada exitosamente'
            )
            return response
            
        except ValidationError as e:
            # Convertir ValidationError del modelo a errores de formulario
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        form.add_error(field, error.message)
            else:
                form.add_error(None, str(e))
            return self.form_invalid(form)

# DELETE: Vista para confirmar la eliminación
class PeliculaDeleteView(AdminRequiredMixin, DeleteView):
    model = Pelicula
    template_name = 'cine/pelicula_confirm_delete.html'
    success_url = reverse_lazy('cine:pelicula_list')
    
    def get_queryset(self):
        """
        Usar all_objects para permitir acceso a películas ya eliminadas (soft delete).
        Esto previene 404 al acceder a la página de confirmación de eliminación.
        """
        return Pelicula.all_objects.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pelicula = self.get_object()
        
        # Obtener funciones asociadas
        funciones = pelicula.funciones.all()
        funciones_futuras = funciones.filter(fecha_hora__gte=timezone.now())
        
        context['tiene_funciones'] = funciones.exists()
        context['total_funciones'] = funciones.count()
        context['funciones_futuras'] = funciones_futuras.count()
        context['puede_eliminar'] = not funciones.exists()
        
        return context
    
    def delete(self, request, *args, **kwargs):
        """Pasar usuario al soft delete para auditoría"""
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Llamar a soft_delete con el usuario para registro de auditoría
        if hasattr(self.object, 'soft_delete'):
            self.object.soft_delete(user=request.user)
        else:
            self.object.delete()
        
        messages.success(
            request,
            f'✓ La película "{self.object.titulo}" ha sido eliminada exitosamente.'
        )
        return redirect(success_url)
