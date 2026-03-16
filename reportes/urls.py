from django.urls import path
from django.views.generic.base import RedirectView
from .views import reporte_financiero_view, reporte_ocupacion_view, buscar_peliculas_ajax
from .views.exports import (
    exportar_financiero_pdf,
    exportar_financiero_excel,
    exportar_operativo_pdf,
    exportar_operativo_excel
)

app_name = 'reportes'

urlpatterns = [
    # backward compatibility: redirect old single-dashboard route to the new financiero view
    path('dashboard/', RedirectView.as_view(pattern_name='reportes:financiero', permanent=False), name='dashboard'),
    path('financiero/', reporte_financiero_view, name='financiero'),
    path('ocupacion/', reporte_ocupacion_view, name='ocupacion'),
    path('ajax/peliculas/', buscar_peliculas_ajax, name='ajax_peliculas'),
    path('exportar/financiero/pdf/', exportar_financiero_pdf, name='exportar_financiero_pdf'),
    path('exportar/financiero/excel/', exportar_financiero_excel, name='exportar_financiero_excel'),
    path('exportar/operativo/pdf/', exportar_operativo_pdf, name='exportar_operativo_pdf'),
    path('exportar/operativo/excel/', exportar_operativo_excel, name='exportar_operativo_excel'),
]
