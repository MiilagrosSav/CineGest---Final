from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .views import AdminRequiredMixin
from .forms import PoliticaReembolsoForm
from ventas.models import PoliticaReembolso


class PoliticaReembolsoListView(AdminRequiredMixin, ListView):
    model = PoliticaReembolso
    template_name = 'accounts/politicas_list.html'
    context_object_name = 'politicas'


class PoliticaReembolsoCreateView(AdminRequiredMixin, CreateView):
    model = PoliticaReembolso
    form_class = PoliticaReembolsoForm
    template_name = 'accounts/politica_form.html'
    success_url = reverse_lazy('lista_politicas')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Política de Reembolso'
        ctx['nombre_boton'] = 'Crear'
        return ctx


class PoliticaReembolsoUpdateView(AdminRequiredMixin, UpdateView):
    model = PoliticaReembolso
    form_class = PoliticaReembolsoForm
    template_name = 'accounts/politica_form.html'
    success_url = reverse_lazy('lista_politicas')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Política de Reembolso'
        ctx['nombre_boton'] = 'Guardar cambios'
        return ctx


class PoliticaReembolsoDeleteView(AdminRequiredMixin, DeleteView):
    model = PoliticaReembolso
    template_name = 'accounts/politica_confirm_delete.html'
    success_url = reverse_lazy('lista_politicas')
