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
        # 🔍 IMPORTANTE: Excluir salas con BAJA LÓGICA (fecha_baja IS NOT NULL)
        # Solo mostrar salas ACTIVAS o INACTIVAS (modificación de estado)
        queryset = Sala.all_objects.filter(fecha_baja__isnull=True)
        
        # Filtro por estado (activas/inactivas/todas)
        estado = self.request.GET.get('estado', 'activas')
        if estado == 'activas':
            queryset = queryset.filter(activo=True)
        elif estado == 'inactivas':
            # INACTIVAS: activo=False pero SIN fecha_baja (no borradas)
            queryset = queryset.filter(activo=False)
        # Si es 'todas', no filtrar por activo (pero sí excluir borradas)
        
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
        context['filtro_estado'] = self.request.GET.get('estado', 'activas')
        return context

    def render_to_response(self, context, **response_kwargs):
        """Return only the table fragment for AJAX requests."""
        request = self.request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.shortcuts import render
            return render(request, 'cine/_sala_table.html', context)
        return super().render_to_response(context, **response_kwargs)

# CREATE: Vista para mostrar el formulario de creación
class SalaCreateView(AdminRequiredMixin, CreateView):
    model = Sala
    form_class = SalaForm
    template_name = 'cine/sala_form.html'
    
    def get_success_url(self):
        # Redirigir al diseñador de distribución de asientos después de crear la sala
        from django.urls import reverse
        return reverse('cine:disenar_distribucion_asientos', kwargs={'sala_id': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🏛️ Añadir Nueva Sala'
        context['nombre_boton'] = '✨ Crear Sala y Configurar Distribución de Asientos'
        return context

# UPDATE: Vista para mostrar el formulario de edición
class SalaUpdateView(AdminRequiredMixin, UpdateView):
    model = Sala
    form_class = SalaForm
    template_name = 'cine/sala_form.html'
    success_url = reverse_lazy('cine:sala_list')

    def get_queryset(self):
        """
        ✅ Permitir editar salas ACTIVAS e INACTIVAS (modificación de estado)
        ❌ NO permitir editar salas con BAJA LÓGICA (fecha_baja IS NOT NULL)
        """
        return Sala.all_objects.filter(fecha_baja__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🏛️ Editar Sala'
        context['nombre_boton'] = '💾 Guardar Cambios'
        # Verificar si la sala tiene butacas vendidas
        context['tiene_butacas_vendidas'] = self.object.tiene_butacas_vendidas()
        return context

# DELETE: Vista para confirmar la eliminación
class SalaDeleteView(AdminRequiredMixin, DeleteView):
    model = Sala
    template_name = 'cine/sala_confirm_delete.html'
    success_url = reverse_lazy('cine:sala_list')
    
    def get_queryset(self):
        """
        Usar all_objects para permitir acceso a salas ya eliminadas (soft delete).
        Esto previene 404 al acceder a la página de confirmación de eliminación.
        """
        return Sala.all_objects.all()
    
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
            f'✓ La sala "{self.object.nombre}" ha sido eliminada exitosamente.'
        )
        return redirect(success_url)
