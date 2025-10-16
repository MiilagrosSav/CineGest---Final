from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Pelicula, Sala
from .forms import PeliculaForm, SalaForm

# --- Mixin de Seguridad para Administradores ---
# Este mixin se asegura de que solo los usuarios con el rol 'administrador'
# puedan acceder a las vistas de gestión.

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Asegura que el usuario esté logueado y sea un administrador.
    """
    def test_func(self):
        # Comprueba si el usuario está autenticado y si su tipo es 'administrador'
        return self.request.user.is_authenticated and self.request.user.is_admin()

    def handle_no_permission(self):
        # Redirige al dashboard si no es administrador
        return redirect('accounts:dashboard')


# --- Vistas del CRUD de Películas ---

# READ: Vista para listar todas las películas
class PeliculaListView(AdminRequiredMixin, ListView):
    model = Pelicula
    template_name = 'cine/pelicula_list.html'  # Template que listará las películas
    context_object_name = 'peliculas'          # Nombre de la variable en el template
    paginate_by = 10                           # Opcional: para paginar la lista

# CREATE: Vista para mostrar el formulario de creación
class PeliculaCreateView(AdminRequiredMixin, CreateView):
    model = Pelicula
    form_class = PeliculaForm  # ✅ USAR FORMULARIO CON VALIDACIONES HTML
    template_name = 'cine/pelicula_form.html'  # Template con el formulario
    success_url = reverse_lazy('cine:pelicula_list') # Redirige aquí tras crear con éxito

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🎬 Añadir Nueva Película'
        context['nombre_boton'] = '✨ Crear Película'
        return context

# UPDATE: Vista para mostrar el formulario de edición
class PeliculaUpdateView(AdminRequiredMixin, UpdateView):
    model = Pelicula
    form_class = PeliculaForm  # ✅ USAR FORMULARIO CON VALIDACIONES HTML
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
    template_name = 'cine/pelicula_confirm_delete.html' # Template de confirmación
    success_url = reverse_lazy('cine:pelicula_list')


# --- Vistas del CRUD de Salas ---

# READ: Vista para listar todas las salas
class SalaListView(AdminRequiredMixin, ListView):
    model = Sala
    template_name = 'cine/sala_list.html'  # Mismo patrón que películas
    context_object_name = 'salas'          # Nombre de la variable en el template
    paginate_by = 10                       # Opcional: para paginar la lista

# CREATE: Vista para mostrar el formulario de creación
class SalaCreateView(AdminRequiredMixin, CreateView):
    model = Sala
    form_class = SalaForm  # ✅ USAR FORMULARIO CON VALIDACIONES HTML
    template_name = 'cine/sala_form.html'  # Template con el formulario
    success_url = reverse_lazy('cine:sala_list') # Redirige aquí tras crear con éxito

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '🏛️ Añadir Nueva Sala'
        context['nombre_boton'] = '✨ Crear Sala'
        return context

# UPDATE: Vista para mostrar el formulario de edición
class SalaUpdateView(AdminRequiredMixin, UpdateView):
    model = Sala
    form_class = SalaForm  # ✅ USAR FORMULARIO CON VALIDACIONES HTML
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
    template_name = 'cine/sala_confirm_delete.html' # Template de confirmación
    success_url = reverse_lazy('cine:sala_list')
