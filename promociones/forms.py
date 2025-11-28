from django import forms
from .models.politicaPromocion import PoliticaPromocion
from .models.promocion import Promocion


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
        fields = ['codigo', 'nombre', 'descripcion', 'tipo_descuento', 'valor_descuento', 'fecha_inicio', 'fecha_fin', 'aplica_en_estrenos', 'es_automatica', 'dias_semana', 'genero_requerido']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: VERANO2025'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'es_automatica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_descuento': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo_descuento'}),
            'valor_descuento': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_valor_descuento', 'step': '0.01'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'aplica_en_estrenos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'genero_requerido': forms.Select(attrs={'class': 'form-control'}),
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
        }
        help_texts = {
            'valor_descuento': 'Para Porcentaje: 0-100. Para Monto fijo: valor en pesos. No se usa para 2x1.',
            'es_automatica': 'Marcar para que esta promoción se aplique automáticamente a funciones/películas vinculadas (sin código ni cupones).',
            'aplica_en_estrenos': 'Si se marca, la promoción aplicará también a películas marcadas como estreno.',
            'genero_requerido': 'Si se especifica, la promoción solo aplicará a películas de ese género. Dejar vacío para aplicar a todos los géneros.',
            'dias_semana': 'Solo para promociones automáticas. Selecciona los días aplicables. Vacío = todos los días.',
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
