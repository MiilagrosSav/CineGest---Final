from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import UpdateView, DeleteView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import CustomUserCreationForm, CustomAuthenticationForm, EmployeeCreationForm
from .models import User

# Mixin de administración para vistas basadas en clases
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

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Establecer siempre el tipo de usuario como CLIENTE
            user.user_type = User.CLIENTE
            user.save()
            messages.success(request, 'Registro exitoso. Ya puedes iniciar sesión como cliente.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Corrige los errores en el formulario.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form, 'user_type': 'cliente'})

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)  # establece la sesión
            messages.success(request, f'Bienvenido, {user.username}!')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión.')
    return redirect('accounts:login')

@login_required
def dashboard_view(request):
    """
    Redirige al dashboard correspondiente según el tipo de usuario
    """
    user = request.user
    if user.is_admin():
        return render(request, 'accounts/dashboard_admin.html')
    elif user.is_employee():
        return render(request, 'accounts/dashboard_empleado.html')
    else:
        return render(request, 'accounts/dashboard_cliente.html')

# Vista para eliminar empleados
class EmployeeDeleteView(AdminRequiredMixin, DeleteView):
    """Vista para eliminar un empleado"""
    model = User
    template_name = 'accounts/employee_confirm_delete.html'
    success_url = reverse_lazy('accounts:employee_list')
    
    def get_queryset(self):
        # Solo permitir eliminar empleados, no otros tipos de usuario
        return User.objects.filter(user_type=User.EMPLEADO)
    
    def delete(self, request, *args, **kwargs):
        employee = self.get_object()
        messages.success(request, f'Empleado {employee.username} eliminado correctamente.')
        return super().delete(request, *args, **kwargs)

# Decorador de ejemplo para proteger vistas específicas
def admin_required(view_func):
    decorated = user_passes_test(lambda u: u.is_authenticated and u.is_admin(), login_url='accounts:login')(view_func)
    return decorated

# Ejemplo de vista solo para administradores
@admin_required
def admin_only_view(request):
    return render(request, 'accounts/admin_only.html')

# Vista para crear empleados (con clase)
class EmployeeCreateView(AdminRequiredMixin, CreateView):
    """Vista para que los administradores creen usuarios empleados"""
    model = User
    form_class = EmployeeCreationForm
    template_name = 'accounts/employee_form.html'
    success_url = reverse_lazy('accounts:employee_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Crear Nuevo Empleado'
        context['nombre_boton'] = 'Crear Empleado'
        return context
    
    def form_valid(self, form):
        employee = form.save(commit=False)
        employee.user_type = User.EMPLEADO  # Establecer tipo como EMPLEADO
        messages.success(self.request, f'Empleado {employee.username} creado exitosamente.')
        return super().form_valid(form)

# Vista para listar empleados
class EmployeeListView(AdminRequiredMixin, ListView):
    """Vista para mostrar la lista de empleados"""
    model = User
    template_name = 'accounts/employee_list.html'
    context_object_name = 'employees'
    
    def get_queryset(self):
        return User.objects.filter(user_type=User.EMPLEADO)

# Vista para editar empleados
class EmployeeUpdateView(AdminRequiredMixin, UpdateView):
    """Vista para actualizar los datos de un empleado"""
    model = User
    template_name = 'accounts/employee_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
    success_url = reverse_lazy('accounts:employee_list')
    
    def get_queryset(self):
        # Solo permitir editar empleados, no otros tipos de usuario
        return User.objects.filter(user_type=User.EMPLEADO)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar Empleado'
        context['nombre_boton'] = 'Guardar Cambios'
        return context
        
    def form_valid(self, form):
        messages.success(self.request, f'Empleado {form.instance.username} actualizado correctamente.')
        return super().form_valid(form)

# ✅ VISTAS PARA PÁGINAS REQUERIDAS POR GOOGLE OAUTH
def privacy_policy_view(request):
    """
    Vista para mostrar la política de privacidad.
    Google requiere esta página para aplicaciones OAuth.
    """
    return render(request, 'accounts/privacy_policy.html')

def terms_of_service_view(request):
    """
    Vista para mostrar los términos de servicio.
    Google requiere esta página para aplicaciones OAuth.
    """
    return render(request, 'accounts/terms_of_service.html')