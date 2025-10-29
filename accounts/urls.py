from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    # Rutas para gestión de empleados (CRUD completo)
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='create_employee'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='edit_employee'),
    path('employees/<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='delete_employee'),
    
    # ✅ PÁGINAS REQUERIDAS POR GOOGLE OAUTH
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms/', views.terms_of_service_view, name='terms_of_service'),
]