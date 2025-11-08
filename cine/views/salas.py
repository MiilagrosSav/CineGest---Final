from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
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
    
    def get_success_url(self):
        # Redirigir al diseñador de layout después de crear la sala
        from django.urls import reverse
        return reverse('cine:disenar_layout_sala', kwargs={'sala_id': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🏛️ Añadir Nueva Sala'
        context['nombre_boton'] = '✨ Crear Sala y Configurar Layout'
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sala = self.get_object()
        
        # Obtener funciones asociadas
        funciones = sala.funciones.all()
        funciones_futuras = funciones.filter(fecha_hora__gte=timezone.now())
        
        context['tiene_funciones'] = funciones.exists()
        context['total_funciones'] = funciones.count()
        context['funciones_futuras'] = funciones_futuras.count()
        context['puede_eliminar'] = not funciones.exists()
        
        return context
