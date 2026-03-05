from django import forms
from django.forms import inlineformset_factory
from .models.politicaPromocion import PoliticaPromocion
from .models.promocion import Promocion
from .models.vinculo_promocional import VinculoPromocional
from cine.models.formato import Formato


class PromocionForm(forms.ModelForm):
    WEEKDAY_CHOICES = [
        ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
        ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo')
    ]
    
    dias_semana = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Días de la semana'
    )
    
    formatos_aplicables = forms.ModelMultipleChoiceField(
        queryset=Formato.objects.all().order_by('categoria', 'nombre'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Formatos aplicables',
        help_text='Selecciona los formatos a los que aplica la promoción. Vacío = todos los formatos.'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando una promoción existente, sólo bloquear el campo `codigo`
        # si existen políticas activas que dependan de esta promoción. Si no existen
        # políticas activas, permitir la edición del código.
        if self.instance and getattr(self.instance, 'pk', None):
            try:
                # Evitar import circular: PoliticaPromocion fue importado al módulo
                if hasattr(self, 'initial'):
                    pass
                from .models import PoliticaPromocion
                tiene_politicas_activas = PoliticaPromocion.objects.filter(promocion_a_otorgar=self.instance, activa=True).exists()
            except Exception:
                tiene_politicas_activas = False

            if tiene_politicas_activas:
                # marcar el campo como disabled (será mostrado pero no enviado)
                self.fields['codigo'].disabled = True
                # y agregar atributo visual readonly/disabled al widget
                self.fields['codigo'].widget.attrs.update({'readonly': 'readonly', 'disabled': 'disabled'})
            else:
                # Asegurarse que el campo esté habilitado si no hay políticas activas
                self.fields['codigo'].disabled = False
                self.fields['codigo'].widget.attrs.pop('disabled', None)
                self.fields['codigo'].widget.attrs.pop('readonly', None)
        else:
            # ✅ Nueva promoción: marcar 'activo' como True por defecto
            self.initial['activo'] = True
            # Ocultar campo 'activo' al crear (solo mostrar al editar)
            if 'activo' in self.fields:
                self.fields.pop('activo')
        
        # ✅ Formatear fechas en formato ISO para input type="date"
        if self.instance.pk and self.instance.fecha_inicio:
            self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime('%Y-%m-%d')
        if self.instance.pk and self.instance.fecha_fin:
            self.initial['fecha_fin'] = self.instance.fecha_fin.strftime('%Y-%m-%d')
        
        # Inicializar dias_semana con los valores guardados (CSV en el modelo)
        if self.instance and getattr(self.instance, 'dias_semana', None):
            try:
                raw = (self.instance.dias_semana or '').strip()
                if raw == '' or raw == '*' or raw.lower() == 'todos':
                    self.initial['dias_semana'] = []
                else:
                    self.initial['dias_semana'] = [str(d) for d in [x for x in raw.split(',') if x.strip() != '']]
            except Exception:
                self.initial['dias_semana'] = []

    class Meta:
        model = Promocion
        fields = ['codigo', 'nombre', 'descripcion', 'tipo_descuento', 'valor_descuento', 'fecha_inicio', 'fecha_fin', 'aplica_en_estrenos', 'es_automatica', 'dias_semana', 'formatos_aplicables', 'genero_requerido', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: VERANO2025'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'es_automatica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_descuento': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo_descuento'}),
            'valor_descuento': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_valor_descuento', 'step': '0.01'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'aplica_en_estrenos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'genero_requerido': forms.Select(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre',
            'descripcion': 'Descripción',
            'es_automatica': 'Aplicación automática',
            'tipo_descuento': 'Tipo de Descuento',
            'valor_descuento': 'Valor del Descuento',
            'fecha_inicio': 'Fecha de Inicio',
            'fecha_fin': 'Fecha de Fin',
            'aplica_en_estrenos': 'Aplica en estrenos',
            'genero_requerido': 'Género requerido',
            'dias_semana': 'Días de la semana',
            'formatos_aplicables': 'Formatos aplicables',
            'activo': 'Promoción activa',
        }
        help_texts = {
            'valor_descuento': 'Para Porcentaje: 0-100. Para Monto fijo: valor en pesos. No se usa para 2x1.',
            'es_automatica': 'Marcar para que esta promoción se aplique automáticamente a funciones/películas vinculadas (sin código ni cupones).',
            'aplica_en_estrenos': 'Si se marca, la promoción aplicará también a películas marcadas como estreno.',
            'genero_requerido': 'Si se especifica, la promoción solo aplicará a películas de ese género. Dejar vacío para aplicar a todos los géneros.',
            'dias_semana': 'Solo para promociones automáticas. Selecciona los días aplicables. Vacío = todos los días.',
            'formatos_aplicables': 'Solo para promociones automáticas. Selecciona los formatos aplicables. Vacío = todos los formatos.',
            'activo': 'Desmarca para desactivar temporalmente esta promoción sin eliminarla.',
        }
    
    def clean_dias_semana(self):
        """Convierte la lista de días seleccionados en CSV para guardar en el modelo."""
        val = self.cleaned_data.get('dias_semana') or []
        es_automatica = self.cleaned_data.get('es_automatica', False)
        if not es_automatica:
            # Si no es automática, vaciar los días
            return ''
        if not val:
            return ''  # Vacío = todos los días
        return ','.join(sorted(val))
    
    def clean_formatos_aplicables(self):
        """Limpia formatos aplicables. Si no es automática, devuelve lista vacía."""
        val = self.cleaned_data.get('formatos_aplicables') or []
        es_automatica = self.data.get('es_automatica')  # Usar self.data para obtener el valor crudo
        if not es_automatica:
            # Si no es automática, vaciar los formatos
            return []
        return val
    
    def clean(self):
        """
        ✅ CORRECCIÓN: Marcar flag temporal si el usuario está intentando crear vínculos.
        Esto permite que model.clean() sepa que habrá vínculos específicos incluso antes
        de guardarlos en la BD.
        """
        cleaned_data = super().clean()
        
        # Verificar si hay un flag temporal pasado desde la vista
        if hasattr(self, '_tiene_vinculos_pendientes'):
            self.instance._tiene_vinculos_pendientes = self._tiene_vinculos_pendientes
        
        # ✅ Validar que no se reactive una promoción vencida
        if self.instance.pk and cleaned_data.get('activo'):
            from django.utils import timezone
            fecha_fin = cleaned_data.get('fecha_fin') or self.instance.fecha_fin
            if fecha_fin and fecha_fin < timezone.now().date():
                self.add_error('activo', 'No se puede activar una promoción cuya fecha de fin ya pasó.')
        
        return cleaned_data


class PoliticaPromocionForm(forms.ModelForm):
    WEEKDAY_CHOICES = [
        ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
        ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo')
    ]

    dias_semana = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Días de la semana'
    )

    class Meta:
        model = PoliticaPromocion
        fields = [
            'nombre', 'activa', 'promocion_a_otorgar', 'genero_pelicula', 
            'hora_inicio_rango', 'hora_fin_rango', 'dias_semana', 
            'prioridad', 'minutos_validez', 'horas_antes_de_funcion',
            'activar_por_ocupacion', 'umbral_ocupacion', 'horas_anticipacion'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'promocion_a_otorgar': forms.Select(attrs={'class': 'form-control'}),
            'genero_pelicula': forms.Select(attrs={'class': 'form-control'}),
            'hora_inicio_rango': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin_rango': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'prioridad': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'minutos_validez': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'horas_antes_de_funcion': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'dias_semana': forms.CheckboxSelectMultiple(),
            'activar_por_ocupacion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'umbral_ocupacion': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'horas_anticipacion': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'nombre': 'Nombre de la Política',
            'activa': 'Activa',
            'promocion_a_otorgar': 'Promoción a otorgar',
            'genero_pelicula': 'Género de Película',
            'hora_inicio_rango': 'Hora inicio (rango)',
            'hora_fin_rango': 'Hora fin (rango)',
            'prioridad': 'Prioridad',
            'minutos_validez': 'Minutos de validez',
            'horas_antes_de_funcion': 'Horas antes de función',
            'activar_por_ocupacion': 'Ocupación Inteligente',
            'umbral_ocupacion': 'Umbral de ocupación (%)',
            'horas_anticipacion': 'Ventana de anticipación (horas)',
        }
        help_texts = {
            'horas_antes_de_funcion': 'Opcional: Solo enviar promoción si faltan menos de X horas para la función. Dejar vacío para enviar siempre.',
            'activar_por_ocupacion': 'Activar para que el sistema escanee automáticamente funciones con baja ocupación y dispare promociones.',
            'umbral_ocupacion': 'Disparar promoción si la ocupación es menor a este porcentaje (ej: 30 = disparar si < 30%).',
            'horas_anticipacion': 'Escanear funciones que ocurran dentro de X horas desde ahora (ej: 24 = verificar funciones en las próximas 24 horas).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar promociones para mostrar solo las NO automáticas (cupones)
        from .models.promocion import Promocion
        self.fields['promocion_a_otorgar'].queryset = Promocion.objects.filter(es_automatica=False).order_by('nombre')
        
        # Ocultar campo 'activa' al crear nueva política (solo mostrar al editar)
        if not self.instance.pk:
            self.initial['activa'] = True
            if 'activa' in self.fields:
                self.fields.pop('activa')
        
        # Inicializar dias_semana con los valores guardados (CSV en el modelo)
        if self.instance and getattr(self.instance, 'dias_semana', None):
            try:
                raw = (self.instance.dias_semana or '').strip()
                if raw == '' or raw == '*' or raw.lower() == 'todos':
                    self.initial['dias_semana'] = []
                else:
                    self.initial['dias_semana'] = [str(d) for d in [x for x in raw.split(',') if x.strip() != '']]
            except Exception:
                self.initial['dias_semana'] = []

    def clean_dias_semana(self):
        val = self.cleaned_data.get('dias_semana') or []
        if not val:
            return ''
        vals = [str(int(x)) for x in val]
        return ','.join(vals)


# ============================================
# Formset para Vínculos Promocionales
# ============================================

class VinculoPromocionalForm(forms.ModelForm):
    """
    Formulario para gestionar vínculos específicos de promoción a películas/funciones.
    Se usa en formset inline dentro de PromocionForm.
    
    ✅ MEJORAS:
    - Filtra opciones ya vinculadas (evita duplicados en UI)
    - Usa TomSelect para búsqueda rápida
    - Restaura opciones al eliminar vínculos
    """
    class Meta:
        model = VinculoPromocional
        fields = ['pelicula', 'funcion']
        widgets = {
            'pelicula': forms.Select(attrs={
                'class': 'form-control vinculo-select-pelicula tomselect-input',
                'data-type': 'pelicula',
                'data-placeholder': 'Buscar película...'
            }),
            'funcion': forms.Select(attrs={
                'class': 'form-control vinculo-select-funcion tomselect-input',
                'data-type': 'funcion',
                'data-placeholder': 'Buscar función...'
            }),
        }
        labels = {
            'pelicula': 'Película (todas sus funciones)',
            'funcion': 'Función específica (solo esa proyección)',
        }
        help_texts = {
            'pelicula': 'Aplica la promoción a TODAS las funciones de esta película',
            'funcion': 'Aplica la promoción SOLO a esta función específica',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from cine.models import Pelicula, Funcion
        from django.utils import timezone
        
        # ✅ OPTIMIZACIÓN: select_related para evitar N+1
        peliculas_base = Pelicula.objects.filter(
            acepta_promociones=True
        ).order_by('titulo')
        
        funciones_base = Funcion.objects.filter(
            fecha_hora__gte=timezone.now(),
            estado='ACTIVA'
        ).select_related('pelicula', 'sala').order_by('fecha_hora')
        
        # ✅ FILTRADO EXCLUYENTE: Excluir películas/funciones ya vinculadas
        # Obtener promoción desde el parent del formset (si estamos en edición)
        promocion = None
        if hasattr(self, 'parent') and self.parent and hasattr(self.parent, 'instance'):
            promocion = self.parent.instance
        elif hasattr(self, 'instance') and self.instance and self.instance.pk:
            # Si estamos editando un vínculo existente
            promocion = self.instance.promocion
        
        if promocion and promocion.pk:
            # Obtener IDs de películas ya vinculadas (excepto la actual si estamos editando)
            vinculos_existentes = VinculoPromocional.objects.filter(promocion=promocion)
            if self.instance and self.instance.pk:
                vinculos_existentes = vinculos_existentes.exclude(pk=self.instance.pk)
            
            peliculas_vinculadas_ids = vinculos_existentes.filter(
                pelicula__isnull=False
            ).values_list('pelicula_id', flat=True)
            
            funciones_vinculadas_ids = vinculos_existentes.filter(
                funcion__isnull=False
            ).values_list('funcion_id', flat=True)
            
            # Excluir las ya vinculadas
            peliculas_base = peliculas_base.exclude(id__in=peliculas_vinculadas_ids)
            funciones_base = funciones_base.exclude(id__in=funciones_vinculadas_ids)
        
        self.fields['pelicula'].queryset = peliculas_base
        self.fields['funcion'].queryset = funciones_base
        
        # Hacer ambos campos opcionales (el clean validará que haya exactamente uno)
        self.fields['pelicula'].required = False
        self.fields['funcion'].required = False

    def clean(self):
        cleaned_data = super().clean()
        pelicula = cleaned_data.get('pelicula')
        funcion = cleaned_data.get('funcion')

        # Validar que haya exactamente UNO (no ambos, no ninguno)
        if not pelicula and not funcion:
            raise forms.ValidationError(
                'Debe seleccionar una PELÍCULA o una FUNCIÓN (no puede dejar ambos vacíos).'
            )
        
        if pelicula and funcion:
            raise forms.ValidationError(
                'Debe seleccionar SOLO una PELÍCULA o SOLO una FUNCIÓN (no ambas).'
            )
        
        return cleaned_data

        return cleaned_data


# Formset factory para gestionar múltiples vínculos
VinculoPromocionalFormSet = inlineformset_factory(
    Promocion,
    VinculoPromocional,
    form=VinculoPromocionalForm,
    extra=1,  # Mostrar 1 formulario vacío por defecto
    can_delete=True,  # Permitir eliminar vínculos
    min_num=0,  # Mínimo 0 vínculos (pueden no tener vínculos específicos)
    validate_min=True,
)
