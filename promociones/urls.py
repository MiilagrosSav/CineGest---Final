from django.urls import path
from . import views

app_name = 'promociones'

urlpatterns = [
    path('dashboard/', views.dashboard_promociones, name='dashboard'),
    
    # Políticas de Promoción
    path('politicas/', views.PoliticaPromocionListView.as_view(), name='politica_list'),
    path('politicas/crear/', views.PoliticaPromocionCreateView.as_view(), name='politica_create'),
    path('politicas/<int:pk>/editar/', views.PoliticaPromocionUpdateView.as_view(), name='politica_update'),
    path('politicas/<int:pk>/eliminar/', views.PoliticaPromocionDeleteView.as_view(), name='politica_delete'),
    
    # Promociones
    path('promociones/', views.PromocionListView.as_view(), name='promocion_list'),
    path('promociones/crear/', views.PromocionCreateView.as_view(), name='promocion_create'),
    path('promociones/<int:pk>/editar/', views.PromocionUpdateView.as_view(), name='promocion_update'),
    path('promociones/<int:pk>/eliminar/', views.PromocionDeleteView.as_view(), name='promocion_delete'),
    path('promocion/<int:pk>/is_automatica/', views.promocion_is_automatica, name='promocion_is_automatica'),
    
    # Redeem link público (token UUID)
    path('redeem/<uuid:token>/', views.redeem_cupon, name='promocion_redeem'),
    path('activar/<uuid:token>/', views.activar_promocion_por_link, name='activar_promo'),
    
    # Verificación manual de ocupación
    path('verificar-ocupacion/', views.verificar_ocupacion_salas, name='verificar_ocupacion'),
]
