from django.contrib import admin
from .models.promocion import Promocion
from .models.funcionPromocion import FuncionPromocion
from .models.politicaPromocion import PoliticaPromocion
from .models.cuponGenerado import CuponGenerado


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo_descuento', 'valor_descuento', 'fecha_inicio', 'fecha_fin')
    search_fields = ('codigo', 'nombre', 'descripcion')
    list_filter = ('tipo_descuento', 'fecha_inicio', 'fecha_fin')


@admin.register(FuncionPromocion)
class FuncionPromocionAdmin(admin.ModelAdmin):
    list_display = ('promocion', 'funcion', 'pelicula')
    search_fields = ('promocion__nombre', 'pelicula__titulo')
    list_filter = ('promocion',)


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
