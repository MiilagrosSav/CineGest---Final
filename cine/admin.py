from django.contrib import admin
from .models import Pelicula, Sala, Butaca, Formato, FuncionFormato, ConfiguracionCine, HorarioAtencion
from .forms import PeliculaForm
from simple_history.admin import SimpleHistoryAdmin

@admin.register(Pelicula)
class PeliculaAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    """
    Configuración personalizada para el modelo Pelicula en el panel de admin.
    """
    form = PeliculaForm  # Usar formulario personalizado con protección de campos
    list_display = ('titulo', 'get_generos_display', 'director', 'fecha_estreno', 'duracion')
    list_filter = ('fecha_estreno',)
    search_fields = ('titulo', 'director', 'sinopsis')
    ordering = ('-fecha_estreno',)
    filter_horizontal = ('generos',)  # widget mejorado para M2M

    fieldsets = (
        (None, {
            'fields': ('titulo', 'sinopsis', 'imagen_portada')
        }),
        ('Detalles de Producción', {
            'fields': ('director', 'generos', 'duracion', 'fecha_estreno')
        }),
    )

    def get_generos_display(self, obj):
        """Mostrar géneros separados por coma"""
        return ', '.join([g.nombre for g in obj.generos.all()])
    get_generos_display.short_description = 'Géneros'


@admin.register(Sala)
class SalaAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    """
    Configuración personalizada para el modelo Sala en el panel de admin.
    """
    list_display = ('numero', 'nombre', 'get_status_display')
    list_filter = ('activa', 'fecha_creacion')
    search_fields = ('numero', 'nombre', 'observaciones')
    ordering = ('numero',)
    
    # Campos de solo lectura
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('numero', 'nombre')
        }),
        ('Estado y Configuración', {
            'fields': ('activa', 'observaciones')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    # Filtros en la barra lateral
    list_per_page = 20
    
    def get_status_display(self, obj):
        """Mostrar estado con icono en la lista"""
        return obj.get_status_display()
    get_status_display.short_description = 'Estado'


@admin.register(Formato)
class FormatoAdmin(admin.ModelAdmin):
    """
    Administración para el modelo Formato
    """
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(FuncionFormato)
class FuncionFormatoAdmin(admin.ModelAdmin):
    """
    Administración para la tabla intermedia Funcion-Formato
    """
    list_display = ('funcion', 'formato')
    list_filter = ('formato',)
    search_fields = ('funcion__pelicula__titulo', 'formato__nombre')
    ordering = ('funcion', 'formato')


@admin.register(Butaca)
class ButacaAdmin(admin.ModelAdmin):
    """
    Administración básica para el modelo Butaca
    """
    list_display = ('__str__', 'sala', 'fila', 'numero', 'tipo')
    list_filter = ('tipo', 'sala')
    search_fields = ('fila', 'numero', 'sala__nombre')
    ordering = ('sala', 'fila', 'numero')


@admin.register(ConfiguracionCine)
class ConfiguracionCineAdmin(admin.ModelAdmin):
    """
    Administración para la configuración del cine (Singleton)
    """
    list_display = ('nombre', 'cuil_cuit', 'telefono', 'email')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'logo', 'razon_social', 'cuil_cuit', 'descripcion')
        }),
        ('Información de Contacto', {
            'fields': ('direccion', 'telefono', 'email')
        }),
        ('Configuración Operativa', {
            'fields': ('minutos_limpieza', 'reserva_tiempo_espera'),
            'description': 'Los horarios de atención ahora se gestionan por día de la semana en la interfaz web.'
        }),
        ('Redes Sociales', {
            'fields': ('facebook', 'instagram', 'twitter'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Solo permitir agregar si no existe ninguna configuración
        return not ConfiguracionCine.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar la configuración
        return False


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    """
    Administración para Horarios de Atención por Día de la Semana
    """
    list_display = ('dia_semana_display', 'hora_apertura', 'hora_cierre', 'activo', 'orden')
    list_filter = ('dia_semana', 'activo')
    search_fields = ('configuracion_cine__nombre',)
    ordering = ['dia_semana', 'orden', 'hora_apertura']
    
    fieldsets = (
        ('Configuración del Horario', {
            'fields': ('configuracion_cine', 'dia_semana', 'hora_apertura', 'hora_cierre', 'activo', 'orden')
        }),
    )
    
    def dia_semana_display(self, obj):
        """Mostrar nombre del día en vez del número"""
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return dias[obj.dia_semana]
    dia_semana_display.short_description = 'Día'

