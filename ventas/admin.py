"""
Configuración del admin para los modelos de ventas
"""

from django.contrib import admin
from ventas.models import Venta, Entrada, MetodoPago, Pago, Intercambio
from ventas.models import PoliticaReembolso
from simple_history.admin import SimpleHistoryAdmin


@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ['id_metodo_pago', 'nombre', 'descripcion']
    search_fields = ['nombre']


class EntradaInline(admin.TabularInline):
    model = Entrada
    extra = 0
    readonly_fields = ['id_funcion', 'id_sala', 'id_butaca', 'id_pelicula']
    fields = ['id_funcion', 'id_sala', 'id_butaca', 'id_pelicula', 'estado']


class PagoInline(admin.StackedInline):
    model = Pago
    extra = 0
    readonly_fields = ['fecha_pago']


@admin.register(Venta)
class VentaAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    list_display = ['id_venta', 'id_cliente', 'fecha_compra', 'tipo_venta', 'estado', 'cantidad_entradas', 'calcular_total']
    list_filter = ['estado', 'tipo_venta', 'fecha_compra']
    search_fields = ['id_venta', 'id_cliente__usuario__username', 'id_cliente__usuario__email']
    readonly_fields = ['fecha_compra', 'calcular_total']
    inlines = [EntradaInline, PagoInline]
    
    fieldsets = (
        ('Información de la Venta', {
            'fields': ('id_cliente', 'id_empleado', 'fecha_compra', 'tipo_venta', 'estado')
        }),
        ('Totales', {
            'fields': ('calcular_total',)
        }),
    )
class PoliticaReembolsoAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'permitir_intercambio', 'dias_antes_minimo', 'penalidad_percent', 'activo']
    list_filter = ['activo', 'permitir_intercambio']
    search_fields = ['nombre']
    readonly_fields = ['created_at', 'updated_at']


# Registrar el admin sólo si no está ya registrado (evita errores en autoreload)
try:
    if PoliticaReembolso not in admin.site._registry:
        admin.site.register(PoliticaReembolso, PoliticaReembolsoAdmin)
except Exception:
    # En entornos de autoreload durante desarrollo puede fallar; ignoramos
    pass


@admin.register(Entrada)
class EntradaAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    list_display = ['id_entrada', 'id_venta', 'id_pelicula', 'id_funcion', 'id_sala', 'id_butaca', 'estado']
    list_filter = ['estado', 'id_pelicula', 'id_sala']
    search_fields = ['id_entrada', 'id_venta__id_venta']
    readonly_fields = ['id_venta', 'id_funcion', 'id_sala', 'id_butaca', 'id_pelicula']


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ['id_pago', 'id_venta', 'monto', 'fecha_pago', 'estado', 'id_metodo_pago', 'nro_transaccion']
    list_filter = ['estado', 'id_metodo_pago', 'fecha_pago']
    search_fields = ['id_pago', 'id_venta__id_venta', 'nro_transaccion']
    readonly_fields = ['fecha_pago']


@admin.register(Intercambio)
class IntercambioAdmin(admin.ModelAdmin):
    """Admin para el modelo de auditoría de Intercambios"""
    list_display = [
        'id_intercambio',
        'venta',
        'funcion_origen',
        'funcion_destino',
        'fecha_intercambio',
        'cantidad_entradas',
        'estado',
        'motivo'
    ]
    list_filter = ['estado', 'motivo', 'fecha_intercambio']
    search_fields = [
        'id_intercambio',
        'venta__id_venta',
        'usuario_email',
        'funcion_origen__pelicula__titulo',
        'funcion_destino__pelicula__titulo'
    ]
    readonly_fields = [
        'id_intercambio',
        'venta',
        'funcion_origen',
        'funcion_destino',
        'fecha_intercambio',
        'cantidad_entradas',
        'usuario_email',
        'ip_address',
        'user_agent',
        'dias_anticipacion_origen'
    ]
    
    fieldsets = (
        ('Información del Intercambio', {
            'fields': (
                'id_intercambio',
                'venta',
                'fecha_intercambio',
                'estado',
                'motivo'
            )
        }),
        ('Funciones', {
            'fields': (
                'funcion_origen',
                'funcion_destino',
                'cantidad_entradas'
            )
        }),
        ('Detalles Financieros', {
            'fields': (
                'penalidad_aplicada',
            )
        }),
        ('Auditoría', {
            'fields': (
                'usuario_email',
                'ip_address',
                'user_agent',
                'dias_anticipacion_origen'
            ),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notas',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Los intercambios solo se crean a través del flujo de la aplicación
        return False
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar registros de auditoría
        return False


# Reembolso model and admin registration removed as refund functionality
# was deprecated and replaced by the 'Intercambio de Entradas' flow.
