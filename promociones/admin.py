from django.contrib import admin
from django.utils.html import format_html
from .models.promocion import Promocion
from .models.vinculo_promocional import VinculoPromocional
from .models.politicaPromocion import PoliticaPromocion
from .models.cuponGenerado import CuponGenerado


# ------------------------------------------------------------------ #
# Filtros con selección predeterminada "Solo activas"                  #
# ------------------------------------------------------------------ #

class ActivePoliticaFilter(admin.SimpleListFilter):
    title = 'Estado'
    parameter_name = 'estado_politica'

    def lookups(self, request, model_admin):
        return [
            ('activas', 'Solo activas'),
            ('inactivas', 'Solo inactivas'),
            ('todas', 'Todas'),
        ]

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == lookup or (
                    lookup == 'activas' and self.value() is None
                ),
                'query_string': changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                'display': title,
            }

    def queryset(self, request, queryset):
        if self.value() == 'inactivas':
            return queryset.filter(activa=False)
        if self.value() == 'todas':
            return queryset.all()
        # Default (None) y 'activas' → solo activa=True
        return queryset.filter(activa=True)


class ActivePromocionFilter(admin.SimpleListFilter):
    title = 'Estado'
    parameter_name = 'estado_promo'

    def lookups(self, request, model_admin):
        return [
            ('activas', 'Solo activas'),
            ('inactivas', 'Solo inactivas'),
            ('todas', 'Todas'),
        ]

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == lookup or (
                    lookup == 'activas' and self.value() is None
                ),
                'query_string': changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                'display': title,
            }

    def queryset(self, request, queryset):
        if self.value() == 'inactivas':
            return queryset.filter(activo=False)
        if self.value() == 'todas':
            return queryset.all()
        return queryset.filter(activo=True)


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
    list_filter = (ActivePromocionFilter, 'tipo_descuento', 'fecha_inicio', 'fecha_fin')
    inlines = [VinculoPromocionalInline]  # ✅ AGREGADO: Gestión inline
    
    def get_fieldsets(self, request, obj=None):
        """
        Ocultar el campo 'activo' al crear, mostrarlo solo al editar.
        """
        # Fieldsets base para creación (sin 'activo')
        fieldsets_base = (
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
        
        # Si está editando (obj existe), agregar campo 'activo'
        if obj:
            return (
                ('Información Básica', {
                    'fields': ('codigo', 'nombre', 'descripcion', 'activo')
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
        
        return fieldsets_base


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
    list_display = (
        'nombre', 'activa', 'estado_vigencia', 'bloqueada_icon',
        'promocion_a_otorgar', 'prioridad', 'genero_pelicula',
        'hora_inicio_rango', 'hora_fin_rango', 'horas_antes_de_funcion',
    )
    search_fields = ('nombre',)
    list_filter = (ActivePoliticaFilter, 'genero_pelicula')
    readonly_fields = ()

    @admin.display(description='Vigencia', boolean=False)
    def estado_vigencia(self, obj):
        if obj.esta_vigente:
            return format_html('<span style="color:green;font-weight:bold;">✔ Vigente</span>')
        return format_html('<span style="color:red;">✘ Inactiva/Vencida</span>')

    @admin.display(description='Bloqueada', boolean=True)
    def bloqueada_icon(self, obj):
        return obj.esta_bloqueada

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'promocion_a_otorgar':
            from django.utils import timezone as tz
            from .models.promocion import Promocion
            today = tz.now().date()
            kwargs['queryset'] = Promocion.objects.filter(
                activo=True,
                fecha_fin__gte=today,
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    
    def get_fieldsets(self, request, obj=None):
        """
        Ocultar el campo 'activa' al crear, mostrarlo solo al editar.
        """
        # Fieldsets base para creación (sin 'activa')
        fieldsets_base = (
            (None, {
                'fields': ('nombre', 'promocion_a_otorgar')
            }),
            ('Condiciones de Activación', {
                'fields': ('genero_pelicula', 'hora_inicio_rango', 'hora_fin_rango', 'dias_semana')
            }),
            ('⏰ Ventana de Urgencia', {
                'fields': ('horas_antes_de_funcion',),
                'description': 'Solo enviar promociones si faltan menos de X horas para la función.'
            }),
            ('⚡ Análisis Automático de Ocupación', {
                'fields': ('activar_por_ocupacion', 'umbral_ocupacion'),
                'description': 'Configuración para activar automáticamente promociones cuando la ocupación de las salas sea baja.'
            }),
            ('🏆 Prioridad y validez', {
                'fields': ('prioridad', 'minutos_validez'),
                'description': 'Prioridad: 1 = máxima prioridad (primer lugar), valores más altos = menor prioridad. '
                               'Cuando varias políticas compiten por la misma función, gana la de menor número.'
            }),
        )
        
        # Si está editando (obj existe), agregar campo 'activa'
        if obj:
            return (
                (None, {
                    'fields': ('nombre', 'activa', 'promocion_a_otorgar')
                }),
                ('Condiciones de Activación', {
                    'fields': ('genero_pelicula', 'hora_inicio_rango', 'hora_fin_rango', 'dias_semana')
                }),
                ('⏰ Ventana de Urgencia', {
                    'fields': ('horas_antes_de_funcion',),
                    'description': 'Solo enviar promociones si faltan menos de X horas para la función.'
                }),
                ('⚡ Análisis Automático de Ocupación', {
                    'fields': ('activar_por_ocupacion', 'umbral_ocupacion'),
                    'description': 'Configuración para activar automáticamente promociones cuando la ocupación de las salas sea baja.'
                }),
                ('🏆 Prioridad y validez', {
                    'fields': ('prioridad', 'minutos_validez'),
                    'description': 'Prioridad: 1 = máxima prioridad (primer lugar), valores más altos = menor prioridad. '
                                   'Cuando varias políticas compiten por la misma función, gana la de menor número.'
                }),
            )
        
        return fieldsets_base


@admin.register(CuponGenerado)
class CuponGeneradoAdmin(admin.ModelAdmin):
    list_display = ('token', 'cliente', 'politica_origen', 'usado', 'creado_en')
    search_fields = ('token', 'cliente__usuario__username', 'cliente__usuario__email')
    list_filter = ('usado', 'politica_origen')
    readonly_fields = ('token', 'creado_en')
