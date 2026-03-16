from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import UpdateView, DeleteView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_POST
from .forms import CustomUserCreationForm, CustomAuthenticationForm, EmployeeCreationForm, EmployeeUpdateForm, ClienteProfileForm, AdminProfileForm, CompletarPerfilGoogleForm, CustomPasswordChangeForm
from core.services import notificacion_service
from .models import Empleado # Importamos Empleado para la lista
from django.http import JsonResponse, HttpResponseForbidden
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
            is_first_login = user.last_login is None
            login(request, user)
            # Si es cliente y no aceptó marketing, activar prompt en sesión (no intrusivo)
            try:
                if getattr(user, 'rol', None) == 'cliente':
                    cliente = getattr(user, 'cliente', None)
                    acepta_marketing = bool(getattr(cliente, 'acepta_marketing', False))
                    tiene_dni = bool(getattr(user, 'dni', None))

                    if cliente and not acepta_marketing:
                        # Solo mostrar una vez por sesión
                        if not request.session.get('marketing_prompt_dismissed'):
                            request.session['show_marketing_optin'] = True

                    # Primer inicio de sesión post-registro: mostrar modal de completar perfil
                    # si falta DNI o consentimiento para cupones.
                    if is_first_login and (not tiene_dni or not acepta_marketing):
                        request.session.pop('dismiss_modal_completar_perfil', None)
                        request.session['mostrar_modal_completar_perfil'] = True
                        request.session['forzar_modal_completar_perfil_primera_sesion'] = True
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


@login_required
@require_POST
def dismiss_completar_perfil_prompt(request):
    """Cierra el modal de completar perfil solo por la sesión actual."""
    if getattr(request.user, 'rol', None) != 'cliente':
        return HttpResponseForbidden()

    request.session['dismiss_modal_completar_perfil'] = True
    request.session.pop('mostrar_modal_completar_perfil', None)
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
        context['is_google_user'] = self.request.user.is_google_user
        context['es_perfil_completo'] = self.request.user.es_perfil_completo
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
    form_class = CustomPasswordChangeForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar información sobre usuarios de Google
        user = self.request.user
        context['is_google_user'] = user.is_google_user if hasattr(user, 'is_google_user') else False
        return context
    
    def form_valid(self, form):
        """Superpone para agregar mensaje de éxito personalizado"""
        response = super().form_valid(form)
        messages.success(self.request, '✓ Tu contraseña ha sido cambiada exitosamente.')
        return response


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
                from django.core.mail import send_mail
                from django.conf import settings as django_settings
                pwd = secrets.token_urlsafe(8)
                employee.set_password(pwd)
                employee.save()
                send_mail(
                    subject='Acceso al sistema CineGest',
                    message=(
                        f'Hola {employee.get_full_name() or employee.username},\n\n'
                        f'Tu cuenta de empleado ha sido creada.\n'
                        f'Usuario: {employee.username}\n'
                        f'Contraseña temporal: {pwd}\n\n'
                        f'Por seguridad, cambia tu contraseña en el primer inicio de sesión.'
                    ),
                    from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[employee.email],
                    fail_silently=True,
                )
                messages.info(self.request, f'Se envió la contraseña temporal al email de {employee.username}.')
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
        employee.soft_delete(user=request.user)
        messages.success(request, f'Empleado {employee.username} dado de baja correctamente.')
        return redirect(self.success_url)

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
    
    # Baja lógica usando el método centralizado del modelo
    usuario.soft_delete(user=usuario)

    # Registrar en auditoría como ELIMINACIÓN (baja lógica = eliminación)
    try:
        fecha_baja = usuario.fecha_baja or timezone.now()
        snapshot = {
            'username': usuario.username,
            'email': usuario.email,
            'nombre': usuario.first_name,
            'apellido': usuario.last_name,
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


# --- AJAX: Verificar disponibilidad de email en tiempo real ---
def check_email_disponible(request):
    """
    Devuelve JSON indicando si el email está disponible.
    GET /accounts/check-email/?email=tu@email.com
    """
    email = request.GET.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'disponible': False, 'mensaje': 'Ingresa un email.'})

    from django.core.validators import validate_email as django_validate_email
    from django.core.exceptions import ValidationError as DjangoValidationError
    try:
        django_validate_email(email)
    except DjangoValidationError:
        return JsonResponse({'disponible': False, 'mensaje': 'Formato de email no válido.'})

    exclude_pk = request.user.pk if request.user.is_authenticated else None
    qs = Usuario.all_objects.filter(email=email)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    if qs.exists():
        return JsonResponse({'disponible': False, 'mensaje': 'Email ya registrado por otro usuario.'})

    return JsonResponse({'disponible': True, 'mensaje': 'Email disponible.'})


# --- AJAX: Verificar disponibilidad de username en tiempo real ---
def check_username_disponible(request):
    """
    Devuelve JSON indicando si el username está disponible.
    GET /accounts/check-username/?username=juan123
    """
    username = request.GET.get('username', '').strip().lower()
    if not username:
        return JsonResponse({'disponible': False, 'mensaje': 'Ingresa un nombre de usuario.'})

    if not username.isalnum():
        return JsonResponse({'disponible': False, 'mensaje': 'Solo letras y números, sin espacios.'})

    exclude_pk = request.user.pk if request.user.is_authenticated else None
    qs = Usuario.all_objects.filter(username=username)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    if qs.exists():
        return JsonResponse({'disponible': False, 'mensaje': 'Nombre de usuario no disponible.'})

    return JsonResponse({'disponible': True, 'mensaje': 'Nombre de usuario disponible.'})


# --- Vista: Guardar datos del modal de completar perfil (clientes) ---
@login_required
@require_POST
def completar_perfil_google(request):
    """
    Procesa el formulario del modal de completar perfil para clientes.
    Guarda DNI, username (opcional), email y aceptación de marketing.
    Requisito para promociones por cupones: DNI + acepta_marketing=True.
    """
    if getattr(request.user, 'rol', None) != 'cliente':
        return JsonResponse({'ok': False, 'error': 'Solo disponible para clientes.'}, status=403)

    form = CompletarPerfilGoogleForm(request.POST, user=request.user)
    if form.is_valid():
        if not form.cleaned_data.get('acepta_marketing', False):
            return JsonResponse(
                {
                    'ok': False,
                    'errores': {
                        'acepta_marketing': 'Debes aceptar promociones/notificaciones para recibir cupones.'
                    }
                },
                status=400,
            )
        from django.db import transaction as db_transaction
        try:
            with db_transaction.atomic():
                usuario = request.user
                usuario.dni = form.cleaned_data['dni']
                new_username = form.cleaned_data.get('username')
                if new_username:
                    usuario.username = new_username.strip().lower()
                new_email = form.cleaned_data.get('email')
                if new_email:
                    usuario.email = new_email
                usuario.save(update_fields=['dni', 'username', 'email'])

                # Actualizar acepta_marketing en el perfil de cliente
                if hasattr(usuario, 'cliente'):
                    usuario.cliente.acepta_marketing = form.cleaned_data.get('acepta_marketing', False)
                    usuario.cliente.save(update_fields=['acepta_marketing'])

            request.session.pop('mostrar_modal_completar_perfil', None)
            request.session.pop('forzar_modal_completar_perfil_primera_sesion', None)
            return JsonResponse({'ok': True})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': 'Error al guardar. Intenta de nuevo.'}, status=500)
    else:
        # Retornar errores del formulario como JSON
        errores = {field: errs[0] for field, errs in form.errors.items()}
        return JsonResponse({'ok': False, 'errores': errores}, status=400)