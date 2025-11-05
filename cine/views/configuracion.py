from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from cine.mixins import AdminRequiredMixin
from cine.models import ConfiguracionCine
from cine.forms import ConfiguracionCineForm


class ConfiguracionCineUpdateView(AdminRequiredMixin, UpdateView):
    """
    Vista para editar la configuración del cine.
    Solo accesible para administradores.
    """
    model = ConfiguracionCine
    form_class = ConfiguracionCineForm
    template_name = 'cine/configuracion_form.html'
    success_url = reverse_lazy('accounts:dashboard')
    
    def get_object(self, queryset=None):
        """
        Obtener o crear la configuración del cine (Singleton)
        """
        return ConfiguracionCine.load()
    
    def form_valid(self, form):
        """
        Mensaje de éxito al guardar
        """
        messages.success(
            self.request,
            '✓ Configuración del cine actualizada correctamente'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """
        Agregar datos adicionales al contexto
        """
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Configuración del Cine'
        context['descripcion'] = 'Configure los datos del cine, horarios y redes sociales'
        return context
