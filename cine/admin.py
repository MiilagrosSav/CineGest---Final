from django.contrib import admin
from .models import Pelicula, Sala

@admin.register(Pelicula)
class PeliculaAdmin(admin.ModelAdmin):
    """
    Configuración personalizada para el modelo Pelicula en el panel de admin.
    """
    list_display = ('titulo', 'genero', 'director', 'fecha_estreno', 'duracion')
    list_filter = ('genero', 'fecha_estreno')
    search_fields = ('titulo', 'director', 'sinopsis')
    ordering = ('-fecha_estreno',)
    
    fieldsets = (
        (None, {
            'fields': ('titulo', 'sinopsis', 'imagen_portada')
        }),
        ('Detalles de Producción', {
            'fields': ('director', 'genero', 'duracion', 'fecha_estreno')
        }),
    )


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    """
    Configuración personalizada para el modelo Sala en el panel de admin.
    """
    list_display = ('numero', 'nombre', 'tipo', 'capacidad', 'get_status_display')
    list_filter = ('tipo', 'activa', 'fecha_creacion')
    search_fields = ('numero', 'nombre', 'observaciones')
    ordering = ('numero',)
    
    # Campos de solo lectura
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('numero', 'nombre', 'tipo')
        }),
        ('Capacidad', {
            'fields': ('capacidad',)
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

