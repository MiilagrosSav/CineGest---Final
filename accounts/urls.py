from django.urls import path
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from django.conf import settings
from urllib.parse import urlparse
from . import views
from .forms import CustomPasswordResetForm
from .politicas_views import (
    PoliticaReembolsoListView,
    PoliticaReembolsoCreateView,
    PoliticaReembolsoUpdateView,
    PoliticaReembolsoDeleteView,
)

app_name = 'accounts'

_site_base_url = getattr(settings, 'SITE_BASE_URL', '')
_parsed_site_url = urlparse(_site_base_url) if _site_base_url else None
_reset_email_context = {}
if _parsed_site_url and _parsed_site_url.netloc:
    _reset_email_context = {
        'domain': _parsed_site_url.netloc,
        'protocol': _parsed_site_url.scheme or 'http',
    }

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    # Marketing opt-in endpoints (AJAX)
    path('marketing/optin/', views.set_marketing_optin, name='marketing_optin'),
    path('marketing/dismiss/', views.dismiss_marketing_prompt, name='marketing_dismiss'),
    # Perfil y contraseña
    path('perfil/editar/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('perfil/empleado/editar/', views.EmployeeProfileUpdateView.as_view(), name='edit_employee_profile'),
    path('perfil/password/', views.MyPasswordChangeView.as_view(), name='password_change'),
    path('perfil/password/done/', views.MyPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('perfil/dar-de-baja/', views.dar_de_baja_cliente, name='dar_de_baja_cliente'),
    # Recupero de contraseña
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            form_class=CustomPasswordResetForm,
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.txt',
            html_email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            extra_email_context=_reset_email_context,
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    # Rutas para gestión de empleados (CRUD completo)
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='create_employee'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='edit_employee'),
    path('employees/<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='delete_employee'),
    # Rutas para gestión de políticas de reembolso
    path('politicas/', PoliticaReembolsoListView.as_view(), name='lista_politicas'),
    path('politicas/crear/', PoliticaReembolsoCreateView.as_view(), name='crear_politica'),
    path('politicas/<int:pk>/editar/', PoliticaReembolsoUpdateView.as_view(), name='editar_politica'),
    path('politicas/<int:pk>/eliminar/', PoliticaReembolsoDeleteView.as_view(), name='eliminar_politica'),

    # Modal de completar perfil (Google users)
    path('completar-perfil/', views.completar_perfil_google, name='completar_perfil_google'),
    path('completar-perfil/dismiss/', views.dismiss_completar_perfil_prompt, name='dismiss_completar_perfil_prompt'),
    path('check-username/', views.check_username_disponible, name='check_username'),
    path('check-email/', views.check_email_disponible, name='check_email'),

    # ✅ PÁGINAS REQUERIDAS POR GOOGLE OAUTH
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms/', views.terms_of_service_view, name='terms_of_service'),
]