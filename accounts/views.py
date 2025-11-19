from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import UpdateView, DeleteView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import CustomUserCreationForm, CustomAuthenticationForm, EmployeeCreationForm, EmployeeUpdateForm
from core.services import notificacion_service
from .models import Empleado # Importamos Empleado para la lista

# Obtenemos nuestro modelo de Usuario personalizado
Usuario = get_user_model()

# --- Mixin de Permisos Actualizado ---
class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Asegura que el usuario esté logueado y tenga el rol de 'admin' o sea superusuario.
    """
    def test_func(self):
        return (self.request.user.is_authenticated and 
                (self.request.user.is_superuser or self.request.user.rol == 'admin'))

    def handle_no_permission(self):
        return redirect('accounts:dashboard')

# --- Vista de Registro (Actualizada con redirección si ya está autenticado) ---
def register_view(request):
    # Si el usuario ya está autenticado, redirigir al dashboard
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # El método .save() del form ahora crea el Usuario Y el Cliente
            usuario = form.save()
            # Enviar email de bienvenida (no bloquear el flujo por errores de email)
            try:
                notificacion_service.enviar_bienvenida(usuario)
            except Exception:
                # Logging opcional ya que el servicio maneja logs
                pass
            messages.success(request, 'Registro exitoso. Ya puedes iniciar sesión.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Corrige los errores en el formulario.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form, 'user_type': 'cliente'})

# --- Vista de Login (Actualizada con redirección si ya está autenticado) ---
def login_view(request):
    # Si el usuario ya está autenticado, redirigir al dashboard
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bienvenido, {user.username}!')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

# --- Vista de Logout (Sin cambios) ---
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión.')
    return redirect('accounts:login')

# --- Vista de Dashboard (Actualizada) ---
@login_required
def dashboard_view(request):
    """
    Redirige al dashboard correspondiente según el rol del usuario
    """
    user = request.user
    
    if user.is_superuser or user.rol == 'admin':
        return render(request, 'accounts/dashboard_admin.html')
    elif user.rol == 'empleado':
        return render(request, 'accounts/dashboard_empleado.html')
    else: # user.rol == 'cliente'
        # Redirigir clientes directamente a la cartelera pública
        return redirect('cine:cartelera')

# --- Vista para Crear Empleados (Actualizada) ---
class EmployeeCreateView(AdminRequiredMixin, CreateView):
    model = Usuario
    form_class = EmployeeCreationForm
    template_name = 'accounts/employee_form.html'
    success_url = reverse_lazy('accounts:employee_list')
    paginate_by = 5
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Crear Nuevo Empleado'
        context['nombre_boton'] = 'Crear Empleado'
        return context
    
    def form_valid(self, form):
        # El .save() del form ya crea el Usuario Y el Empleado
        employee = form.save() 
        messages.success(self.request, f'Empleado {employee.username} creado exitosamente.')
        # Usamos super().form_valid() pero llamándolo con el form
        # ya que el objeto se creó en form.save()
        super().form_valid(form)
        return redirect(self.success_url)


# --- Vista para Listar Empleados (Actualizada) ---
class EmployeeListView(AdminRequiredMixin, ListView):
    model = Usuario
    template_name = 'accounts/employee_list.html'
    context_object_name = 'employees'
    
    def get_queryset(self):
        # Obtenemos todos los usuarios con rol 'empleado'
        # Usamos select_related('empleado') para traer el perfil de Empleado
        return Usuario.objects.filter(rol='empleado').select_related('empleado')

# --- Vista para Editar Empleados (Actualizada) ---
class EmployeeUpdateView(AdminRequiredMixin, UpdateView):
    model = Usuario
    form_class = EmployeeUpdateForm
    template_name = 'accounts/employee_form.html'
    success_url = reverse_lazy('accounts:employee_list')
    
    def get_queryset(self):
        # Solo permitir editar usuarios que tengan el rol 'empleado'
        return Usuario.objects.filter(rol='empleado')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = '✏️ Editar Empleado'
        context['nombre_boton'] = '💾 Guardar Cambios'
        return context
        
    def form_valid(self, form):
        messages.success(self.request, f'Empleado {form.instance.username} actualizado correctamente.')
        return super().form_valid(form)

# --- Vista para Eliminar Empleados (Actualizada) ---
class EmployeeDeleteView(AdminRequiredMixin, DeleteView):
    model = Usuario # <-- El modelo base es Usuario
    template_name = 'accounts/employee_confirm_delete.html'
    success_url = reverse_lazy('accounts:employee_list')
    
    def get_queryset(self):
        # Solo permitir eliminar usuarios con rol 'empleado'
        return Usuario.objects.filter(rol='empleado')
    
    def delete(self, request, *args, **kwargs):
        employee = self.get_object()
        messages.success(request, f'Empleado {employee.username} eliminado correctamente.')
        # Al borrar el Usuario, el perfil Empleado se borra por 'on_delete=CASCADE'
        return super().delete(request, *args, **kwargs)

# --- Vistas de Google (Sin cambios) ---
def privacy_policy_view(request):
    return render(request, 'accounts/privacy_policy.html')

def terms_of_service_view(request):
    return render(request, 'accounts/terms_of_service.html')