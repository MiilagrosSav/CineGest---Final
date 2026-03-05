from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import UpdateView, DeleteView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_POST
from .forms import CustomUserCreationForm, CustomAuthenticationForm, EmployeeCreationForm, EmployeeUpdateForm, ClienteProfileForm, AdminProfileForm
from core.services import notificacion_service
from .models import Empleado # Importamos Empleado para la lista
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic.edit import UpdateView
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.utils import timezone
from .models import Cliente
from auditoria.models import AuditEntry
from django.core.serializers import serialize
import json

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
            # Si es cliente y no aceptó marketing, activar prompt en sesión (no intrusivo)
            try:
                if getattr(user, 'rol', None) == 'cliente':
                    cliente = getattr(user, 'cliente', None)
                    if cliente and not getattr(cliente, 'acepta_marketing', False):
                        # Solo mostrar una vez por sesión
                        if not request.session.get('marketing_prompt_dismissed'):
                            request.session['show_marketing_optin'] = True
            except Exception:
                pass

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


@login_required
def set_marketing_optin(request):
    if request.method != 'POST':
        return HttpResponseForbidden()
    user = request.user
    if getattr(user, 'rol', None) != 'cliente':
        return HttpResponseForbidden()
    try:
        cliente = user.cliente
        cliente.acepta_marketing = True
        cliente.save()
        # clear session prompt
        request.session.pop('show_marketing_optin', None)
        request.session['marketing_prompt_dismissed'] = True
        return JsonResponse({'ok': True})
    except Exception:
        return JsonResponse({'ok': False}, status=500)


@login_required
def dismiss_marketing_prompt(request):
    if request.method != 'POST':
        return HttpResponseForbidden()
    # Mark as dismissed for this session only
    request.session['marketing_prompt_dismissed'] = True
    request.session.pop('show_marketing_optin', None)
    return JsonResponse({'ok': True})


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para editar perfil - detecta automáticamente si es cliente o admin"""
    template_name = 'accounts/profile_form.html'
    success_url = reverse_lazy('accounts:dashboard')

    def get_object(self, queryset=None):
        user = self.request.user
        # Si es cliente y tiene perfil de cliente, retornar el objeto Cliente
        if user.rol == 'cliente' and hasattr(user, 'cliente'):
            return user.cliente
        # Si es admin o empleado (o cliente sin perfil), retornar el Usuario
        return user
    
    def get_form_class(self):
        # Determinar qué formulario usar según el rol
        if self.request.user.rol == 'cliente' and hasattr(self.request.user, 'cliente'):
            return ClienteProfileForm
        return AdminProfileForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Perfil'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '✓ Perfil actualizado correctamente')
        return super().form_valid(form)


class EmployeeProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para que empleados editen su propio perfil"""
    model = Usuario
    template_name = 'accounts/employee_profile_form.html'
    fields = ['first_name', 'last_name', 'email', 'telefono']
    success_url = reverse_lazy('accounts:dashboard')

    def get_object(self, queryset=None):
        # Solo permite editar su propio perfil
        return self.request.user
    
    def dispatch(self, request, *args, **kwargs):
        # Verificar que sea empleado
        if not (hasattr(request.user, 'rol') and request.user.rol == 'empleado'):
            messages.error(request, 'Acceso restringido.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Mi Perfil'
        # Agregar info del empleado si existe
        if hasattr(self.request.user, 'empleado'):
            context['empleado'] = self.request.user.empleado
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '✓ Tu perfil ha sido actualizado correctamente')
        return super().form_valid(form)


class MyPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change_form.html'
    success_url = reverse_lazy('accounts:password_change_done')


class MyPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'

# --- Vista para Crear Empleados (Actualizada) ---
class EmployeeCreateView(AdminRequiredMixin, CreateView):
    model = Usuario
    form_class = EmployeeCreationForm
    template_name = 'accounts/employee_form.html'
    success_url = reverse_lazy('accounts:employee_list')
    paginate_by = 5
    
    def get_initial(self):
        """
        Establece valores iniciales para el formulario.
        La fecha de ingreso se establece automáticamente a hoy.
        """
        initial = super().get_initial()
        initial['fecha_ingreso'] = timezone.now().date()
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Crear Nuevo Empleado'
        context['nombre_boton'] = 'Crear Empleado'
        return context
    
    def form_valid(self, form):
        # El .save() del form ya crea el Usuario Y el Empleado
        employee = form.save()
        # Si no se proporcionó contraseña (por ejemplo creación vía admin UI),
        # generamos una contraseña temporal y la asignamos para que el empleado
        # pueda iniciar sesión. Recomendamos cambiarla luego.
        try:
            if not employee.has_usable_password():
                import secrets
                pwd = secrets.token_urlsafe(8)
                employee.set_password(pwd)
                employee.save()
                messages.info(self.request, f'Contraseña temporal generada para {employee.username}: {pwd}')

        except Exception:
            # No bloquear creación por errores en generación de contraseña
            pass

        messages.success(self.request, f'Empleado {employee.username} creado exitosamente.')
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


# --- Vista para Dar de Baja Cuenta de Cliente ---
@login_required
@require_POST
def dar_de_baja_cliente(request):
    """
    Permite al cliente darse de baja (baja lógica).
    Solo accesible por usuarios autenticados mediante POST.
    """
    usuario = request.user
    
    # Verificar que sea un cliente
    if usuario.rol != 'cliente':
        messages.error(request, '❌ Esta acción solo está disponible para clientes.')
        return redirect('accounts:dashboard')
    
    # Realizar baja lógica usando is_active (campo estándar de Django)
    usuario.is_active = False
    usuario.save()
    
    # Nota: Si el modelo Cliente tiene un campo fecha_baja, descomentar estas líneas:
    # if hasattr(usuario, 'cliente'):
    #     usuario.cliente.fecha_baja = timezone.now()
    #     usuario.cliente.save()
    
    # Registrar en auditoría como ELIMINACIÓN (baja lógica = eliminación)
    try:
        fecha_baja = timezone.now()
        snapshot = {
            'username': usuario.username,
            'email': usuario.email,
            'nombre': usuario.nombre,
            'apellido': usuario.apellido,
            'rol': usuario.rol,
            'is_active': False,
            'fecha_baja': fecha_baja.isoformat(),
        }
        
        AuditEntry.objects.create(
            model_name='accountsusuario',
            object_id=str(usuario.pk),
            object_repr=str(usuario),
            history_type='-',  # ELIMINACIÓN
            history_date=fecha_baja,
            history_user=usuario,  # Auto-eliminación
            history_change_reason='Baja voluntaria de cuenta por parte del cliente',
            snapshot=snapshot
        )
    except Exception as e:
        # Si falla el registro de auditoría, continuar con la baja
        pass
    
    # Cerrar sesión
    logout(request)
    
    # Mensaje de despedida y redirección
    messages.info(
        request, 
        '👋 Tu cuenta ha sido dada de baja exitosamente. '
    )
    
    return redirect('cine:index')  # Redirigir a la página principal del cine