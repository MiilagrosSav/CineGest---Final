from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from cine.models import Sala
from cine.forms import SalaForm
from cine.mixins import AdminRequiredMixin


# --- Vistas del CRUD de Salas ---

# READ: Vista para listar todas las salas
class SalaListView(AdminRequiredMixin, ListView):
    model = Sala
    template_name = 'cine/sala_list.html'
    context_object_name = 'salas'
    paginate_by = 5
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtro de búsqueda por nombre
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(nombre__icontains=search)
        
        # Filtro por número de sala
        numero = self.request.GET.get('numero', '')
        if numero:
            try:
                queryset = queryset.filter(numero=int(numero))
            except ValueError:
                pass  # Si no es un número válido, ignorar el filtro
        
        # Ordenamiento
        orden = self.request.GET.get('orden', 'numero')
        orden_mapping = {
            'numero': 'numero',
            'numero_desc': '-numero',
            'nombre': 'nombre',
            'nombre_desc': '-nombre',
        }
        queryset = queryset.order_by(orden_mapping.get(orden, 'numero'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_search'] = self.request.GET.get('search', '')
        context['filtro_numero'] = self.request.GET.get('numero', '')
        context['filtro_orden'] = self.request.GET.get('orden', 'numero')
        return context

# CREATE: Vista para mostrar el formulario de creación
class SalaCreateView(AdminRequiredMixin, CreateView):
    model = Sala
    form_class = SalaForm
    template_name = 'cine/sala_form.html'
    success_url = reverse_lazy('cine:sala_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🏛️ Añadir Nueva Sala'
        context['nombre_boton'] = '✨ Crear Sala'
        return context

# UPDATE: Vista para mostrar el formulario de edición
class SalaUpdateView(AdminRequiredMixin, UpdateView):
    model = Sala
    form_class = SalaForm
    template_name = 'cine/sala_form.html'
    success_url = reverse_lazy('cine:sala_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar Sala'
        context['nombre_boton'] = 'Guardar Cambios'
        return context

# DELETE: Vista para confirmar la eliminación
class SalaDeleteView(AdminRequiredMixin, DeleteView):
    model = Sala
    template_name = 'cine/sala_confirm_delete.html'
    success_url = reverse_lazy('cine:sala_list')
