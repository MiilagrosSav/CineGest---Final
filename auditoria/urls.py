from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('', views.audit_list, name='list'),
    path('<int:pk>/', views.audit_detail, name='detail'),
    path('updates/', views.audit_updates, name='updates'),
]
