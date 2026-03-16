from django.contrib import admin
from .models import Valoracion, NotificacionValoracion, Resena


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'pelicula', 'calificacion', 'comentario_preview', 'fecha_creacion')
    list_filter = ('calificacion', 'fecha_creacion', 'pelicula')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'pelicula__titulo', 'comentario')
    readonly_fields = ('fecha_creacion',)
    ordering = ('-fecha_creacion',)
    list_per_page = 20

    def comentario_preview(self, obj):
        if obj.comentario:
            return obj.comentario[:80] + '…' if len(obj.comentario) > 80 else obj.comentario
        return '(Sin comentario)'
    comentario_preview.short_description = 'Comentario'


@admin.register(Valoracion)
class ValoracionAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'pelicula', 'puntuacion', 'comentario_preview', 'fecha_creacion')
    list_filter = ('puntuacion', 'fecha_creacion', 'pelicula')
    search_fields = ('cliente__usuario__username', 'pelicula__titulo', 'comentario')
    readonly_fields = ('fecha_creacion',)
    ordering = ('-fecha_creacion',)
    list_per_page = 20
    
    def comentario_preview(self, obj):
        """Muestra un preview del comentario en la lista"""
        if obj.comentario:
            return obj.comentario[:80] + '...' if len(obj.comentario) > 80 else obj.comentario
        return '(Sin comentario)'
    comentario_preview.short_description = 'Comentario'


@admin.register(NotificacionValoracion)
class NotificacionValoracionAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'funcion', 'leido', 'fecha_creacion')
    list_filter = ('leido', 'fecha_creacion')
    search_fields = ('cliente__usuario__username', 'funcion__pelicula__titulo', 'mensaje')
    readonly_fields = ('fecha_creacion',)
    ordering = ('-fecha_creacion',)
    
    actions = ['marcar_como_leidas']
    
    def marcar_como_leidas(self, request, queryset):
        count = queryset.update(leido=True)
        self.message_user(request, f'{count} notificaciones marcadas como leídas.')
    marcar_como_leidas.short_description = 'Marcar seleccionadas como leídas'

