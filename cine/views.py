# En cine/views.py

from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Pelicula, Sala, Funcion, Butaca
from .forms import PeliculaForm, SalaForm, FuncionForm
import json

# --- Mixin de Seguridad para Administradores (CORREGIDO) ---
# Este mixin se asegura de que solo los usuarios con el rol 'administrador'
# o los superusuarios puedan acceder a las vistas de gestión.

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Asegura que el usuario esté logueado y sea un administrador o superusuario.
    """
    def test_func(self):
        # ✅ ESTA ES LA LÓGICA CORREGIDA
        # Comprueba si el usuario está autenticado Y si es superusuario O su rol es 'admin'
        if not self.request.user.is_authenticated:
            return False
        return self.request.user.is_superuser or self.request.user.rol == 'admin'

    def handle_no_permission(self):
        # Redirige al dashboard (el dashboard_view se encargará de mandarlo
        # al dashboard de cliente si es que no tiene permisos)
        return redirect('accounts:dashboard') # Usa el nombre correcto de la URL


# --- Vistas del CRUD de Películas ---
# (El resto de tu código estaba perfecto, no necesita cambios)

# READ: Vista para listar todas las películas
class PeliculaListView(AdminRequiredMixin, ListView):
    model = Pelicula
    template_name = 'cine/pelicula_list.html'
    context_object_name = 'peliculas'
    paginate_by = 10 

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


# --- Vistas del CRUD de Salas ---

# READ: Vista para listar todas las salas
class SalaListView(AdminRequiredMixin, ListView):
    model = Sala
    template_name = 'cine/sala_list.html'
    context_object_name = 'salas'
    paginate_by = 10

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
class FuncionCreateView(AdminRequiredMixin, CreateView):
    model = Funcion
    form_class = FuncionForm
    template_name = 'cine/funcion_form.html'
    success_url = reverse_lazy('cine:funcion_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🎭 Programar Nueva Función'
        context['nombre_boton'] = '✨ Crear Función'
        return context

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


# --- Vistas para el Diseñador de Butacas ---
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
import json
from .models import Butaca


# Función auxiliar para verificar si es admin
def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.rol == 'admin')


@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def disenar_layout_sala(request, sala_id):
    """
    Muestra la página del diseñador visual para una sala específica.
    Solo accesible para administradores.
    """
    sala = get_object_or_404(Sala, id=sala_id)
    butacas = list(sala.butacas.all().order_by('fila', 'numero').values('fila', 'numero', 'tipo'))
    context = {
        'sala': sala,
        'butacas_existentes': butacas
    }
    return render(request, 'cine/disenar_layout.html', context)


@require_http_methods(["POST"])
@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def api_guardar_layout_sala(request, sala_id):
    """
    Recibe un JSON con el nuevo layout, borra las butacas antiguas
    y crea las nuevas. Solo accesible para administradores.
    """
    try:
        sala = get_object_or_404(Sala, id=sala_id)
        data = json.loads(request.body)

        # Borrar butacas antiguas
        sala.butacas.all().delete()

        # Preparar nuevas
        nuevas = []
        for item in data:
            fila = item.get('fila')
            num = item.get('num')
            tipo = item.get('tipo', 'GENERAL')
            if not fila or not num:
                continue
            nuevas.append(Butaca(sala=sala, fila=fila, numero=num, tipo=tipo))

        if nuevas:
            Butaca.objects.bulk_create(nuevas)

        sala.capacidad = sala.butacas.count()
        sala.save()

        return JsonResponse({'status': 'ok', 'butacas_creadas': len(nuevas), 'capacidad': sala.capacidad})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)