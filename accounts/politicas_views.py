from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from .views import AdminRequiredMixin
from .forms import PoliticaReembolsoForm
from ventas.models import PoliticaReembolso


class PoliticaReembolsoListView(AdminRequiredMixin, ListView):
    model = PoliticaReembolso
    template_name = 'accounts/politicas_list.html'
    context_object_name = 'politicas'

    def get_queryset(self):
        # Mostrar activas e inactivas para poder gestionarlas desde ABM.
        return PoliticaReembolso.all_objects.all().order_by('-activo', '-updated_at')


class PoliticaReembolsoCreateView(AdminRequiredMixin, CreateView):
    model = PoliticaReembolso
    form_class = PoliticaReembolsoForm
    template_name = 'accounts/politica_form.html'
    success_url = reverse_lazy('accounts:lista_politicas')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Política de Intercambio'
        ctx['nombre_boton'] = 'Crear'
        return ctx


class PoliticaReembolsoUpdateView(AdminRequiredMixin, UpdateView):
    model = PoliticaReembolso
    form_class = PoliticaReembolsoForm
    template_name = 'accounts/politica_form.html'
    success_url = reverse_lazy('accounts:lista_politicas')

    def get_queryset(self):
        # Permitir editar políticas inactivas también.
        return PoliticaReembolso.all_objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Política de Intercambio'
        ctx['nombre_boton'] = 'Guardar cambios'
        return ctx


class PoliticaReembolsoDeleteView(AdminRequiredMixin, DeleteView):
    model = PoliticaReembolso
    template_name = 'accounts/politica_confirm_delete.html'
    success_url = reverse_lazy('accounts:lista_politicas')

    def get_queryset(self):
        """
        Usar all_objects para permitir acceso a politicas ya eliminadas (soft delete).
        """
        return PoliticaReembolso.all_objects.all()

    def delete(self, request, *args, **kwargs):
        """Aplicar baja lógica de la política (sin eliminación física)."""
        self.object = self.get_object()
        self.object.soft_delete(user=request.user)
        return redirect(self.success_url)
