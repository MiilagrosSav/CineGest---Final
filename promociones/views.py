from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models

from .models.promocion import Promocion
from .models.politicaPromocion import PoliticaPromocion
from .models.cuponGenerado import CuponGenerado
from .forms import PoliticaPromocionForm, PromocionForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que requiere que el usuario sea admin o superuser"""
    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user, 'rol', None) == 'admin'


@login_required
def dashboard_promociones(request):
    # Solo accesible por administradores (rol == 'admin' o superuser)
    user = request.user
    if not (user.is_superuser or getattr(user, 'rol', None) == 'admin'):
        return HttpResponseForbidden('Acceso denegado')

    # Información rápida para mostrar en el dashboard de promociones
    context = {
        'promociones_count': Promocion.objects.count(),
        'politicas_count': PoliticaPromocion.objects.count(),
        'cupones_recientes': CuponGenerado.objects.order_by('-creado_en')[:10],
    }

    return render(request, 'promociones/dashboard.html', context)


# Vistas CRUD para Políticas de Promoción
class PoliticaPromocionListView(AdminRequiredMixin, ListView):
    model = PoliticaPromocion
    template_name = 'promociones/politica_list.html'
    context_object_name = 'politicas'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtro por búsqueda (nombre de política o nombre de promoción vinculada)
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(nombre__icontains=search) | 
                models.Q(promocion_a_otorgar__nombre__icontains=search) |
                models.Q(promocion_a_otorgar__codigo__icontains=search)
            )
        
        # Filtro por estado (activa/inactiva)
        estado = self.request.GET.get('estado', '').strip()
        if estado == 'activa':
            qs = qs.filter(activa=True)
        elif estado == 'inactiva':
            qs = qs.filter(activa=False)
        
        return qs.order_by('-activa', 'nombre')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_search'] = self.request.GET.get('search', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', '')
        return ctx
    
    def render_to_response(self, context, **response_kwargs):
        # Si es una petición AJAX, devolver solo la tabla parcial
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.template_name = 'promociones/_politica_table.html'
        return super().render_to_response(context, **response_kwargs)


class PoliticaPromocionCreateView(AdminRequiredMixin, CreateView):
    model = PoliticaPromocion
    form_class = PoliticaPromocionForm
    template_name = 'promociones/politica_form.html'
    success_url = reverse_lazy('promociones:politica_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Política de Promoción'
        ctx['nombre_boton'] = 'Crear'
        # Mapa de promociones para el JS (id -> es_automatica)
        ctx['promociones_map'] = {p.pk: bool(p.es_automatica) for p in Promocion.objects.all()}
        return ctx


class PoliticaPromocionUpdateView(AdminRequiredMixin, UpdateView):
    model = PoliticaPromocion
    form_class = PoliticaPromocionForm
    template_name = 'promociones/politica_form.html'
    success_url = reverse_lazy('promociones:politica_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Política de Promoción'
        ctx['nombre_boton'] = 'Guardar cambios'
        ctx['promociones_map'] = {p.pk: bool(p.es_automatica) for p in Promocion.objects.all()}
        return ctx


class PoliticaPromocionDeleteView(AdminRequiredMixin, DeleteView):
    model = PoliticaPromocion
    template_name = 'promociones/politica_confirm_delete.html'
    success_url = reverse_lazy('promociones:politica_list')


# Vistas CRUD para Promociones
class PromocionListView(AdminRequiredMixin, ListView):
    model = Promocion
    template_name = 'promociones/promocion_list.html'
    context_object_name = 'promociones'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtro por búsqueda (nombre, código)
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(nombre__icontains=search) | 
                models.Q(codigo__icontains=search)
            )
        
        # Filtro por tipo (automática o cupón)
        tipo = self.request.GET.get('tipo', '').strip()
        if tipo == 'auto':
            qs = qs.filter(es_automatica=True)
        elif tipo == 'cupon':
            qs = qs.filter(es_automatica=False)
        
        return qs.order_by('-fecha_inicio')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_search'] = self.request.GET.get('search', '')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        return ctx
    
    def render_to_response(self, context, **response_kwargs):
        # Si es una petición AJAX, devolver solo la tabla parcial
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.template_name = 'promociones/_promocion_table.html'
        return super().render_to_response(context, **response_kwargs)


class PromocionCreateView(AdminRequiredMixin, CreateView):
    model = Promocion
    form_class = PromocionForm
    template_name = 'promociones/promocion_form.html'
    success_url = reverse_lazy('promociones:promocion_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Promoción'
        ctx['nombre_boton'] = 'Crear'
        return ctx


class PromocionUpdateView(AdminRequiredMixin, UpdateView):
    model = Promocion
    form_class = PromocionForm
    template_name = 'promociones/promocion_form.html'
    success_url = reverse_lazy('promociones:promocion_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Promoción'
        ctx['nombre_boton'] = 'Guardar cambios'
        return ctx


class PromocionDeleteView(AdminRequiredMixin, DeleteView):
    model = Promocion
    template_name = 'promociones/promocion_confirm_delete.html'
    success_url = reverse_lazy('promociones:promocion_list')


@login_required
def promocion_is_automatica(request, pk):
    """Endpoint pequeño que devuelve si una promoción es automática (JSON)."""
    if not (request.user.is_superuser or getattr(request.user, 'rol', None) == 'admin'):
        return JsonResponse({'error': 'forbidden'}, status=403)
    promocion = get_object_or_404(Promocion, pk=pk)
    return JsonResponse({'es_automatica': bool(promocion.es_automatica)})
