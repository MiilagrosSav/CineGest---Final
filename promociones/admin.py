from django.contrib import admin
from .models.promocion import Promocion
from .models.vinculo_promocional import VinculoPromocional
from .models.politicaPromocion import PoliticaPromocion
from .models.cuponGenerado import CuponGenerado


class VinculoPromocionalInline(admin.TabularInline):
    """
    Inline para gestionar vínculos promocionales directamente desde el admin de Promocion.
    
    Permite vincular la promoción con:
    - Películas específicas (todas sus funciones)
    - Funciones específicas (solo esa proyección)
    """
    model = VinculoPromocional
    extra = 1
    fields = ('pelicula', 'funcion')
    raw_id_fields = ['funcion']  # ✔️ Usa raw_id en vez de autocomplete (Funcion no tiene admin)
    verbose_name = 'Vínculo a Película/Función'
    verbose_name_plural = '🎯 Vínculos Específicos (deja vacío para aplicar universalmente)'
    
    def get_formset(self, request, obj=None, **kwargs):
        """Personaliza el formset para mejorar UX"""
        formset = super().get_formset(request, obj, **kwargs)
        formset.help_texts = {
            'pelicula': 'Aplica a TODAS las funciones de esta película',
            'funcion': 'Aplica SOLO a esta función específica (mayor prioridad que película)',
        }
        return formset


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo_descuento', 'valor_descuento', 'fecha_inicio', 'fecha_fin')
    search_fields = ('codigo', 'nombre', 'descripcion')
    list_filter = ('tipo_descuento', 'fecha_inicio', 'fecha_fin')
    inlines = [VinculoPromocionalInline]  # ✅ AGREGADO: Gestión inline
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo', 'nombre', 'descripcion')
        }),
        ('Descuento', {
            'fields': ('tipo_descuento', 'valor_descuento')
        }),
        ('Vigencia y Restricciones', {
            'fields': ('fecha_inicio', 'fecha_fin', 'dias_semana', 'genero_requerido', 'es_automatica'),
            'description': (
                '⚙️ Sin vínculos específicos: aplica universalmente (según género/días configurados).\n'
                '🎯 Con vínculos: solo aplica a películas/funciones vinculadas abajo.'
            )
        }),
    )


@admin.register(VinculoPromocional)
class VinculoPromocionalAdmin(admin.ModelAdmin):
    """
    Admin separado para gestión avanzada de vínculos.
    Para uso diario, editar desde PromocionAdmin (inline).
    """
    list_display = ('promocion', 'pelicula', 'funcion')
    search_fields = ('promocion__nombre', 'pelicula__titulo', 'funcion__pelicula__titulo')
    list_filter = ('promocion',)
    raw_id_fields = ['funcion']  # ✔️ Usa raw_id en vez de autocomplete (Funcion no tiene admin)
    
    fieldsets = (
        (None, {
            'fields': ('promocion',),
        }),
        ('Vínculo (elegir UNO)', {
            'fields': ('pelicula', 'funcion'),
            'description': (
                '⚠️ Debe elegir PELÍCULA (todas sus funciones) O FUNCIÓN (solo esa proyección).\n'
                'No puede vincular ambas simultáneamente.'
            )
        }),
    )


@admin.register(PoliticaPromocion)
class PoliticaPromocionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa', 'promocion_a_otorgar', 'genero_pelicula', 'hora_inicio_rango', 'hora_fin_rango', 'horas_antes_de_funcion')
    search_fields = ('nombre',)
    list_filter = ('activa', 'genero_pelicula')
    readonly_fields = ()
    fieldsets = (
        (None, {
            'fields': ('nombre', 'activa', 'promocion_a_otorgar')
        }),
        ('Condiciones de Activación', {
            'fields': ('genero_pelicula', 'hora_inicio_rango', 'hora_fin_rango')
        }),
        ('Yield Management', {
            'fields': ('horas_antes_de_funcion',),
            'description': 'Solo enviar promociones si faltan menos de X horas para la función.'
        }),
    )


@admin.register(CuponGenerado)
class CuponGeneradoAdmin(admin.ModelAdmin):
    list_display = ('token', 'cliente', 'politica_origen', 'usado', 'creado_en')
    search_fields = ('token', 'cliente__usuario__username', 'cliente__usuario__email')
    list_filter = ('usado', 'politica_origen')
    readonly_fields = ('token', 'creado_en')
