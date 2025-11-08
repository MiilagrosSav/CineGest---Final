from cine.mixins import AdminRequiredMixin
from cine.forms import PeliculaForm
from django.contrib.auth.decorators import login_required, user_passes_test
from cine.models import Pelicula
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone


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
            queryset = queryset.filter(genero__icontains=genero)
        
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
        return context

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
        return context

# DELETE: Vista para confirmar la eliminación
class PeliculaDeleteView(AdminRequiredMixin, DeleteView):
    model = Pelicula
    template_name = 'cine/pelicula_confirm_delete.html'
    success_url = reverse_lazy('cine:pelicula_list')
    
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