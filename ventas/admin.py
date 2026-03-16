"""
Configuración del admin para los modelos de ventas
"""

from django.contrib import admin
from ventas.models import Venta, Entrada, MetodoPago, Pago, Intercambio, RegistroAcceso
from ventas.models import PoliticaReembolso, CajaSesion
from simple_history.admin import SimpleHistoryAdmin
from ventas.forms import PoliticaReembolsoAdminForm


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
    form = PoliticaReembolsoAdminForm
    list_display = [
        'id',
        'nombre',
        'activo',
        'dias_antes_minimo',
        'max_cambios_por_compra',
        'ofrecer_promos_vinculo',
        'permitir_reintercambio',
        'permitir_con_cupon_promocion',
    ]
    list_filter = ['activo']
    search_fields = ['nombre']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Reglas Base de Intercambio', {
            'fields': ('nombre', 'activo', 'dias_antes_minimo', 'max_cambios_por_compra')
        }),
        ('Reglas de Promociones y Retorno', {
            'fields': (
                'ofrecer_promos_vinculo',
                'permitir_reintercambio',
                'permitir_con_cupon_promocion',
            )
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


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
        'dias_anticipacion_origen',
        'get_ip_auditoria',
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
        ('Auditoría', {
            'fields': (
                'usuario_email',
                'dias_anticipacion_origen',
                'get_ip_auditoria',
            ),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notas',),
            'classes': ('collapse',)
        }),
    )
    
    def get_ip_auditoria(self, obj):
        """
        Obtiene la IP desde django-simple-history para mostrar en el admin.
        
        Este método consulta el historial del intercambio para obtener la IP
        capturada automáticamente por HistoryRequestMiddleware.
        """
        if obj and obj.pk:
            # Buscar el registro de creación en el historial
            history = obj.history.filter(history_type='+').first()
            if history and hasattr(history, '_request_ip'):
                return history._request_ip
        return '(no disponible)'
    get_ip_auditoria.short_description = 'IP de Creación'
    
    def has_add_permission(self, request):
        # Los intercambios solo se crean a través del flujo de la aplicación
        return False
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar registros de auditoría
        return False


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    """Admin para auditoría de validaciones de acceso en puerta"""
    list_display = [
        'id',
        'entrada',
        'resultado',
        'tipo_validacion',
        'empleado_validador',
        'fecha_hora_intento',
        'motivo_rechazo'
    ]
    list_filter = [
        'resultado',
        'tipo_validacion',
        'fecha_hora_intento',
        'empleado_validador'
    ]
    search_fields = [
        'entrada__id_entrada',
        'entrada__codigo_entrada',
        'codigo_buscado',
        'empleado_validador__username',
        'empleado_validador__first_name',
        'empleado_validador__last_name'
    ]
    readonly_fields = [
        'entrada',
        'empleado_validador',
        'fecha_hora_intento',
        'tipo_validacion',
        'resultado',
        'codigo_buscado',
        'motivo_rechazo',
        'ip_origen'
    ]
    
    fieldsets = (
        ('Información del Acceso', {
            'fields': (
                'entrada',
                'resultado',
                'fecha_hora_intento',
                'tipo_validacion'
            )
        }),
        ('Validador', {
            'fields': (
                'empleado_validador',
                'ip_origen'
            )
        }),
        ('Detalles', {
            'fields': (
                'codigo_buscado',
                'motivo_rechazo'
            )
        }),
    )
    
    def has_add_permission(self, request):
        # Los registros solo se crean automáticamente desde las vistas
        return False
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar registros de auditoría
        return False


# Reembolso model and admin registration removed as refund functionality
# was deprecated and replaced by the 'Intercambio de Entradas' flow.


@admin.register(CajaSesion)
class CajaSesionAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    """Admin para trazabilidad de sesiones de caja (Apertura / Cierre / Arqueo)."""
    list_display = [
        'id', 'empleado', 'estado', 'fecha_apertura', 'fecha_cierre',
        'fondo_inicial', 'total_efectivo_cerrado', 'total_qr_cerrado',
        'monto_esperado', 'monto_real_declarado', 'diferencia',
    ]
    list_filter = ['estado', 'fecha_apertura', 'empleado']
    search_fields = ['empleado__username', 'empleado__first_name', 'empleado__last_name']
    readonly_fields = [
        'fecha_apertura', 'fecha_cierre',
        'total_efectivo_cerrado', 'total_qr_cerrado', 'total_ventas_cerrado',
        'monto_esperado', 'monto_real_declarado', 'diferencia',
    ]
    ordering = ['-fecha_apertura']

    fieldsets = (
        ('Sesión', {
            'fields': ('empleado', 'estado', 'fecha_apertura', 'fecha_cierre'),
        }),
        ('Fondo', {
            'fields': ('fondo_inicial',),
        }),
        ('Arqueo de Cierre', {
            'fields': (
                'total_efectivo_cerrado', 'total_qr_cerrado', 'total_ventas_cerrado',
                'monto_esperado', 'monto_real_declarado', 'diferencia',
            ),
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return False  # Solo se crea desde la boletería

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Solo superadmin puede eliminar
