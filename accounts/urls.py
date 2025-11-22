from django.urls import path
from . import views
from .politicas_views import (
    PoliticaReembolsoListView,
    PoliticaReembolsoCreateView,
    PoliticaReembolsoUpdateView,
    PoliticaReembolsoDeleteView,
)

app_name = 'accounts'

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
    path('perfil/password/', views.MyPasswordChangeView.as_view(), name='password_change'),
    path('perfil/password/done/', views.MyPasswordChangeDoneView.as_view(), name='password_change_done'),
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
    
    # ✅ PÁGINAS REQUERIDAS POR GOOGLE OAUTH
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms/', views.terms_of_service_view, name='terms_of_service'),
]