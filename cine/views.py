# En cine/views.py

from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Pelicula, Sala
from .forms import PeliculaForm, SalaForm

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
        return redirect('accounts:dashboard_view') # Recomiendo usar el nombre de la vista (dashboard_view)


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