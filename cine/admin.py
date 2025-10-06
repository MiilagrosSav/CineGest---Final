from django.contrib import admin
from .models import Pelicula

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

