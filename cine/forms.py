from django import forms
from .models import Pelicula, Sala, Funcion, Formato, FuncionFormato, ConfiguracionCine, Genero
from datetime import date, datetime, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone

class PeliculaForm(forms.ModelForm):
    """
    Formulario para crear y editar películas con validaciones HTML completas
    """
    
    titulo = forms.CharField(
        label='🎬 Título de la película',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Avatar: El Camino del Agua',
            'required': True,
            'minlength': '2',
            'maxlength': '200',
            'title': 'El título es obligatorio (2-200 caracteres)'
        }),
        error_messages={
            'required': 'El título de la película es obligatorio.',
            'max_length': 'El título no puede tener más de 200 caracteres.'
        }
    )
    
    sinopsis = forms.CharField(
        label='📝 Sinopsis',
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Describe brevemente la historia de la película...',
            'required': True,
            'minlength': '10',
            'maxlength': '1000',
            'rows': 4,
            'title': 'Describe la película (mínimo 10 caracteres)'
        }),
        error_messages={
            'required': 'La sinopsis es obligatoria.'
        }
    )
    
    director = forms.CharField(
        label='🎭 Director',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: James Cameron',
            'required': True,
            'minlength': '2',
            'maxlength': '100',
            'pattern': '^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\\s.,-]+$',
            'title': 'El director es obligatorio (solo letras, espacios y signos básicos)'
        }),
        error_messages={
            'required': 'El director de la película es obligatorio.',
            'max_length': 'El nombre del director no puede tener más de 100 caracteres.'
        }
    )
    
    generos = forms.ModelMultipleChoiceField(
        label='🎪 Géneros',
        queryset=None,
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'genre-checkboxes'}),
        help_text='Selecciona uno o más géneros para la película',
        error_messages={
            'required': 'Debe seleccionar al menos un género.'
        }
    )
    
    duracion = forms.IntegerField(
        label='⏰ Duración (minutos)',
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 120',
            'required': True,
            'min': '30',
            'max': '300',
            'step': '1',
            'title': 'La duración es obligatoria (30-300 minutos)'
        }),
        error_messages={
            'required': 'La duración de la película es obligatoria.',
            'min_value': 'La duración mínima es de 30 minutos.',
            'max_value': 'La duración máxima es de 300 minutos.'
        }
    )
    
    fecha_estreno = forms.DateField(
        label='📅 Fecha de estreno',
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'required': True,
            'min': date.today().strftime('%Y-%m-%d'),  # No permitir fechas pasadas
            'title': 'La fecha de estreno debe ser hoy o en el futuro'
        }),
        error_messages={
            'required': 'La fecha de estreno es obligatoria.',
            'invalid': 'Ingresa una fecha válida.'
        }
    )
    
    imagen_portada = forms.ImageField(
        label='🖼️ Imagen de portada',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*',
            'title': 'Selecciona una imagen para la portada (opcional)'
        })
    )
    
    class Meta:
        model = Pelicula
        fields = ['titulo', 'sinopsis', 'director', 'generos', 'duracion', 'fecha_estreno', 'clasificacion', 'imagen_portada', 'es_estreno', 'acepta_promociones']
        
    def clean_titulo(self):
        """Validación personalizada para el título"""
        titulo = self.cleaned_data['titulo']
        if len(titulo.strip()) < 2:
            raise forms.ValidationError('El título debe tener al menos 2 caracteres.')
        return titulo.strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicializar queryset de géneros dinámicamente
        try:
            self.fields['generos'].queryset = Genero.objects.all().order_by('nombre')
        except Exception:
            # En entornos donde el modelo no existe aún (migrations) fallamos silenciosamente
            self.fields['generos'].queryset = []
    
    def clean_duracion(self):
        """Validación personalizada para la duración"""
        duracion = self.cleaned_data['duracion']
        if duracion < 30:
            raise forms.ValidationError('La duración mínima es de 30 minutos.')
        if duracion > 300:
            raise forms.ValidationError('La duración máxima es de 300 minutos.')
        return duracion
    
    def clean_fecha_estreno(self):
        """Validación personalizada para la fecha de estreno"""
        fecha_estreno = self.cleaned_data['fecha_estreno']
        if fecha_estreno < date.today():
            raise forms.ValidationError('La fecha de estreno no puede ser anterior a la fecha actual.')
        return fecha_estreno


class SalaForm(forms.ModelForm):
    """
    Formulario para crear y editar salas con validaciones completas
    """
    
    numero = forms.IntegerField(
        label='🔢 Número de sala',
        min_value=1,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 1',
            'required': True,
            'min': '1',
            'max': '100',
            'title': 'Número único de sala (1-100)'
        }),
        error_messages={
            'required': 'El número de sala es obligatorio.',
            'min_value': 'El número debe ser mayor a 0.',
            'max_value': 'El número no puede ser mayor a 100.'
        }
    )
    
    nombre = forms.CharField(
        label='🏛️ Nombre de la sala',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Sala Premium A',
            'required': True,
            'maxlength': '100',
            'title': 'Nombre descriptivo de la sala'
        }),
        error_messages={
            'required': 'El nombre de la sala es obligatorio.',
            'max_length': 'El nombre no puede tener más de 100 caracteres.'
        }
    )
    
    # NOTA: El campo 'capacidad' se calcula automáticamente 
    # contando las butacas, no es un campo del formulario
    
   
    
    activa = forms.BooleanField(
        label='✅ Sala activa',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'title': 'Marca si la sala está disponible para proyecciones'
        })
    )
    
    observaciones = forms.CharField(
        label='📝 Observaciones',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Notas adicionales sobre equipamiento, mantenimiento, etc...',
            'rows': '3',
            'maxlength': '500',
            'title': 'Observaciones opcionales (máx. 500 caracteres)'
        })
    )

    class Meta:
        model = Sala
        # 'tipo' fue eliminado del modelo; no incluirlo en el formulario
        fields = ['numero', 'nombre', 'activa', 'observaciones']

    def clean_numero(self):
        """Validación para número único de sala"""
        numero = self.cleaned_data['numero']
        # Verificar si existe otra sala con el mismo número (excluyendo la actual si es edición)
        queryset = Sala.objects.filter(numero=numero)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise forms.ValidationError(f'Ya existe una sala con el número {numero}.')
        
        return numero
    
    def clean_nombre(self):
        """Validación para nombre de sala"""
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 3:
            raise forms.ValidationError('El nombre debe tener al menos 3 caracteres.')
        return nombre.strip()
    
    # Nota: la capacidad se calcula dinámicamente en el modelo `Sala.capacidad`
    # y no es un campo del formulario, por eso se eliminó la validación clean_capacidad.


class FuncionForm(forms.ModelForm):
    """
    Formulario para crear y editar funciones (proyecciones) con validaciones completas
    """
    
    pelicula = forms.ModelChoiceField(
        label='🎬 Película',
        queryset=Pelicula.objects.all().order_by('titulo'),
        empty_label='Selecciona una película...',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona la película a proyectar'
        }),
        error_messages={
            'required': 'Debes seleccionar una película.',
            'invalid_choice': 'La película seleccionada no es válida.'
        }
    )
    
    sala = forms.ModelChoiceField(
        label='🏛️ Sala',
        queryset=Sala.objects.filter(activa=True).order_by('numero'),
        empty_label='Selecciona una sala...',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona la sala donde se proyectará'
        }),
        error_messages={
            'required': 'Debes seleccionar una sala.',
            'invalid_choice': 'La sala seleccionada no es válida.'
        }
    )
    
    fecha_hora = forms.DateTimeField(
        label='📅 Fecha y hora',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-input',
            'type': 'datetime-local',
            'required': True,
            'min': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'title': 'Selecciona la fecha y hora de la función'
        }),
        error_messages={
            'required': 'La fecha y hora son obligatorias.',
            'invalid': 'Ingresa una fecha y hora válidas.'
        }
    )
    
    # Campo agrupado en categorías: una opción por cada categoría
    formatos_visual = forms.ModelChoiceField(
        label='1. Formato_Visual',
        queryset=Formato.objects.filter(nombre__in=['2D', '3D']).order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato visual.'}
    )

    formatos_pantalla = forms.ModelChoiceField(
        label='2. Formato_Pantalla',
        queryset=Formato.objects.filter(nombre__in=['Pantalla Standard', 'IMAX', 'ScreenX']).order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato de pantalla.'}
    )

    formatos_experiencia = forms.ModelChoiceField(
        label='3. Formato_Experiencia',
        queryset=Formato.objects.filter(nombre__in=['Experiencia Standard', '4DX', 'D-BOX']).order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato de experiencia.'}
    )

    idioma = forms.ChoiceField(
        label='4. Idioma',
        choices=Funcion.IDIOMA_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        initial='DOBLADA',
        error_messages={'required': 'Debes seleccionar un idioma.'}
    )
    
    precio_base = forms.DecimalField(
        label='💰 Precio de entrada',
        min_value=0.01,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 1500.00',
            'required': True,
            'min': '0.01',
            'step': '0.01',
            'title': 'Precio de entrada para esta función'
        }),
        error_messages={
            'required': 'El precio es obligatorio.',
            'min_value': 'El precio debe ser mayor a 0.',
            'invalid': 'Ingresa un precio válido.'
        }
    )

    class Meta:
        model = Funcion
        fields = ['pelicula', 'sala', 'fecha_hora', 'idioma', 'precio_base']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando, cargar los formatos actuales
        if self.instance and self.instance.pk:
            # Cargar los formatos ya asignados
            formatos_actuales = self.instance.formatos_funcion.select_related('formato').all()
            # Inicializar por categoría (tomando el primer formato que coincida con cada categoría)
            visual = formatos_actuales.filter(formato__nombre__in=['2D', '3D']).first()
            pantalla = formatos_actuales.filter(formato__nombre__in=['Pantalla Standard', 'IMAX', 'ScreenX']).first()
            experiencia = formatos_actuales.filter(formato__nombre__in=['Experiencia Standard', '4DX', 'D-BOX']).first()
            if visual:
                self.initial['formatos_visual'] = visual.formato_id
            if pantalla:
                self.initial['formatos_pantalla'] = pantalla.formato_id
            if experiencia:
                self.initial['formatos_experiencia'] = experiencia.formato_id
        else:
            # Si es creación nueva, preseleccionar las opciones 'standard' cuando sea posible
            try:
                visual_default = Formato.objects.filter(nombre__in=['2D', '2D Standard']).first() or Formato.objects.filter(categoria='VISUAL').order_by('nombre').first()
                if visual_default:
                    self.initial.setdefault('formatos_visual', visual_default.id)

                pantalla_default = Formato.objects.filter(nombre__icontains='Standard', categoria='PANTALLA').first() or Formato.objects.filter(categoria='PANTALLA').order_by('nombre').first()
                if pantalla_default:
                    self.initial.setdefault('formatos_pantalla', pantalla_default.id)

                experiencia_default = Formato.objects.filter(nombre__icontains='Standard', categoria='EXPERIENCIA').first() or Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre').first()
                if experiencia_default:
                    self.initial.setdefault('formatos_experiencia', experiencia_default.id)
            except Exception:
                pass
    
    
    
    def clean_fecha_hora(self):
        """Validación para fecha y hora de la función"""
        fecha_hora = self.cleaned_data['fecha_hora']
        
        # Solo validar para nuevas funciones o si se cambió la fecha
        if not self.instance.pk or self.instance.fecha_hora != fecha_hora:
            if fecha_hora < timezone.now():
                raise forms.ValidationError('La fecha y hora no pueden ser en el pasado.')
        
        return fecha_hora
    
    def clean_precio_base(self):
        """Validación para el precio"""
        precio = self.cleaned_data['precio_base']
        if precio <= 0:
            raise forms.ValidationError('El precio debe ser mayor a 0.')
        if precio > 99999.99:
            raise forms.ValidationError('El precio es demasiado alto.')
        return precio
    
    def clean(self):
        """Validaciones que requieren múltiples campos"""
        cleaned_data = super().clean()
        sala = cleaned_data.get('sala')
        pelicula = cleaned_data.get('pelicula')
        fecha_hora = cleaned_data.get('fecha_hora')

        # --- Validación de formatos por categoría (si están presentes en el form) ---
        visual = cleaned_data.get('formatos_visual')
        pantalla = cleaned_data.get('formatos_pantalla')
        experiencia = cleaned_data.get('formatos_experiencia')
        idioma = cleaned_data.get('formatos_idioma')

        formatos_sel = []
        for f in (visual, pantalla, experiencia, idioma):
            if f:
                formatos_sel.append(f.nombre)

        if formatos_sel:
            from cine.models.funcion_formato import FORMATOS_INCOMPATIBLES
            for nombre in formatos_sel:
                if nombre in FORMATOS_INCOMPATIBLES:
                    for incompatible in FORMATOS_INCOMPATIBLES[nombre]:
                        if incompatible in formatos_sel:
                            raise ValidationError(f'No puedes combinar {nombre} con {incompatible}. Son tecnologías mutuamente excluyentes.')
        
        if sala and pelicula and fecha_hora:
            # Verificar que la sala esté activa
            if not sala.activa:
                raise ValidationError({
                    'sala': 'No se pueden programar funciones en salas inactivas.'
                })
            
            # Obtener configuración del cine para los minutos de limpieza
            from cine.models import ConfiguracionCine
            configuracion = ConfiguracionCine.load()
            minutos_limpieza = configuracion.minutos_limpieza
            
            # Verificar solapamiento de funciones
            # Calcular fin de esta función (duración + minutos de limpieza configurados)
            from datetime import timedelta
            duracion_total = timedelta(minutes=pelicula.duracion + minutos_limpieza)
            fin_funcion = fecha_hora + duracion_total
            
            # Buscar funciones que se solapen
            funciones_solapadas = Funcion.objects.filter(
                sala=sala,
                fecha_hora__lt=fin_funcion,
            )
            
            # Si estamos editando, excluir la función actual
            if self.instance.pk:
                funciones_solapadas = funciones_solapadas.exclude(pk=self.instance.pk)
            
            for funcion in funciones_solapadas:
                duracion_otra = timedelta(minutes=funcion.pelicula.duracion + minutos_limpieza)
                fin_otra = funcion.fecha_hora + duracion_otra
                
                # Verificar si hay solapamiento
                if funcion.fecha_hora < fin_funcion and fecha_hora < fin_otra:
                    raise ValidationError({
                        'fecha_hora': f'Esta función se solapa con "{funcion.pelicula.titulo}" '
                                    f'programada a las {funcion.fecha_hora.strftime("%d/%m/%Y %H:%M")} en la misma sala. '
                                    f'Debe haber al menos {minutos_limpieza} minutos de diferencia entre funciones.'
                    })
        
        return cleaned_data
# --- CAMBIO 2: CLASE COMPLETAMENTE NUEVA AÑADIDA AL FINAL ---

class FuncionBatchForm(forms.Form):
    """
    Formulario para CREAR múltiples funciones (lote) en un solo día.
    Reemplaza 'fecha_hora' por 'fecha' y 'horarios' (un string).
    """
    
    # --- Campos copiados de FuncionForm (son los datos que se repiten) ---
    
    pelicula = forms.ModelChoiceField(
        label='Película',
        queryset=Pelicula.objects.all().order_by('titulo'),
        empty_label='Selecciona una película...',
        widget=forms.Select(attrs={
            'class': 'form-select', 'required': True, 
            'title': 'Selecciona la película a proyectar'
        })
    )
    
    sala = forms.ModelChoiceField(
        label='Sala',
        queryset=Sala.objects.filter(activa=True).order_by('numero'),
        empty_label='Selecciona una sala...',
        widget=forms.Select(attrs={
            'class': 'form-select', 'required': True, 
            'title': 'Selecciona la sala donde se proyectará'
        })
    )
    
    formatos_visual = forms.ModelChoiceField(
        label='1. Formato_Visual',
        queryset=Formato.objects.filter(nombre__in=['2D', '3D']).order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato visual.'}
    )

    formatos_pantalla = forms.ModelChoiceField(
        label='2. Formato_Pantalla',
        queryset=Formato.objects.filter(nombre__in=['Pantalla Standard', 'IMAX', 'ScreenX']).order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato de pantalla.'}
    )

    formatos_experiencia = forms.ModelChoiceField(
        label='3. Formato_Experiencia',
        queryset=Formato.objects.filter(nombre__in=['Experiencia Standard', '4DX', 'D-BOX']).order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato de experiencia.'}
    )

    idioma = forms.ChoiceField(
        label='4. Idioma',
        choices=Funcion.IDIOMA_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        initial='DOBLADA',
        error_messages={'required': 'Debes seleccionar un idioma.'}
    )
    
    precio_base = forms.DecimalField(
        label='Precio de entrada',
        min_value=0.01, max_digits=8, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input', 'placeholder': 'Ej: 1500.00',
            'required': True, 'min': '0.01', 'step': '0.01',
            'title': 'Precio de entrada para esta función'
        })
    )
    
    # --- Nuevos campos para la creación por lote ---
    
    fecha = forms.DateField(
        label='Día de las funciones',
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'required': True,
            'min': date.today().strftime('%Y-%m-%d'),
            'title': 'Elige el día para todas las funciones'
        })
    )
    
    horarios = forms.CharField(
        label="Horarios (separados por coma)",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 18:00, 20:15, 22:30',
            'required': True,
            'title': 'Formato HH:MM, separados por comas'
        }),
        help_text="Introduce uno o más horarios en formato HH:MM, separados por comas."
    )

    def clean_horarios(self):
        """
        Valida el string de horarios.
        Convierte el string "18:00, 20:15" en una lista de objetos [time(18,0), time(20,15)]
        """
        horarios_str = self.cleaned_data.get('horarios', '')
        if not horarios_str:
            raise forms.ValidationError('Debes ingresar al menos un horario.')
        
        horarios_lista_str = [h.strip() for h in horarios_str.split(',')]
        horarios_obj_lista = []
        
        for hora_str in horarios_lista_str:
            if not hora_str: continue # Ignora comas dobles (ej: "18:00,,19:00")
            
            try:
                # Intenta convertir el texto (ej: "18:00") a un objeto 'time'
                hora_obj = datetime.strptime(hora_str, '%H:%M').time()
                horarios_obj_lista.append(hora_obj)
            except ValueError:
                # Si el usuario escribió mal un horario (ej: "18:xx" o "banana")
                raise forms.ValidationError(f"El horario '{hora_str}' tiene un formato incorrecto. El formato debe ser HH:MM (ej: 18:00).")
        
        if not horarios_obj_lista:
             raise forms.ValidationError('No se encontraron horarios válidos.')
        
        # Verificar duplicados en la entrada del usuario
        if len(horarios_obj_lista) != len(set(horarios_obj_lista)):
            raise forms.ValidationError('Ingresaste el mismo horario más de una vez.')

        # ¡Éxito! Retornamos la LISTA de objetos 'time' limpios
        return horarios_obj_lista

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure sensible defaults for formatos when creating a new batch
        try:
            # If no initial provided for formatos, pick reasonable 'standard' defaults
            if not self.initial.get('formatos_visual'):
                visual_default = Formato.objects.filter(nombre__in=['2D', '2D Standard', '2D/Standard']).first() or Formato.objects.filter(categoria='VISUAL').order_by('nombre').first()
                if visual_default:
                    self.initial['formatos_visual'] = visual_default.id

            if not self.initial.get('formatos_pantalla'):
                pantalla_default = Formato.objects.filter(nombre__icontains='Standard', categoria='PANTALLA').first() or Formato.objects.filter(categoria='PANTALLA').order_by('nombre').first()
                if pantalla_default:
                    self.initial['formatos_pantalla'] = pantalla_default.id

            if not self.initial.get('formatos_experiencia'):
                experiencia_default = Formato.objects.filter(nombre__icontains='Standard', categoria='EXPERIENCIA').first() or Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre').first()
                if experiencia_default:
                    self.initial['formatos_experiencia'] = experiencia_default.id
        except Exception:
            # Don't fail form construction if DB is not ready; defaults are best-effort
            pass
    
    # NOTE: validations for formats will run inside clean()
    
    def clean(self):
        """
        Validación cruzada para solapamiento de funciones,
        adaptada de la lógica original de FuncionForm.
        """
        cleaned_data = super().clean()
        sala = cleaned_data.get('sala')
        pelicula = cleaned_data.get('pelicula')
        fecha = cleaned_data.get('fecha')
        horarios = cleaned_data.get('horarios') # Esta es la *lista* de objetos 'time' de clean_horarios

        # --- Validación de formatos por categoría ---
        formatos_sel = []
        visual = cleaned_data.get('formatos_visual')
        pantalla = cleaned_data.get('formatos_pantalla')
        experiencia = cleaned_data.get('formatos_experiencia')
        idioma_valor = cleaned_data.get('idioma')  # Este es un string, no un Formato

        if not all([visual, pantalla, experiencia, idioma_valor]):
            raise ValidationError('Debes seleccionar una opción para cada categoría de formato.')

        # Reunir nombres para validación cruzada (solo formatos, no idioma)
        for f in (visual, pantalla, experiencia):
            if f:
                formatos_sel.append(f.nombre)

        # Verificar incompatibilidades (2D vs 3D)
        from cine.models.funcion_formato import FORMATOS_INCOMPATIBLES
        for nombre in formatos_sel:
            if nombre in FORMATOS_INCOMPATIBLES:
                for incompatible in FORMATOS_INCOMPATIBLES[nombre]:
                    if incompatible in formatos_sel:
                        raise ValidationError(f'No puedes combinar {nombre} con {incompatible}. Son tecnologías mutuamente excluyentes.')

        # Si faltan datos básicos, la validación de campos ya falló, no hacemos nada más
        if not all([sala, pelicula, fecha, horarios]):
            return cleaned_data
            
        # Verificar que la sala esté activa
        if not sala.activa:
            raise ValidationError({'sala': 'No se pueden programar funciones en salas inactivas.'})
        
        # Obtener configuración del cine para los minutos de limpieza
        from cine.models import ConfiguracionCine
        configuracion = ConfiguracionCine.load()
        minutos_limpieza = configuracion.minutos_limpieza
        
        # Primero, verificar que los horarios seleccionados no se solapen ENTRE SÍ
        horarios_con_duracion = []
        for hora_obj in horarios:
            try:
                fecha_hora_naive = datetime.combine(fecha, hora_obj)
                current_tz = timezone.get_current_timezone()
                fecha_hora_aware = timezone.make_aware(fecha_hora_naive, current_tz)
                duracion_total = timedelta(minutes=pelicula.duracion + minutos_limpieza)
                fin_funcion = fecha_hora_aware + duracion_total
                horarios_con_duracion.append((fecha_hora_aware, fin_funcion, hora_obj))
            except Exception:
                raise ValidationError(f"No se pudo procesar el horario {hora_obj}.")
        
        # Verificar solapamiento entre los horarios seleccionados
        for i, (inicio_i, fin_i, hora_i) in enumerate(horarios_con_duracion):
            for j, (inicio_j, fin_j, hora_j) in enumerate(horarios_con_duracion):
                if i != j and inicio_i < fin_j and inicio_j < fin_i:
                    raise ValidationError({
                        'horarios': f'Los horarios {hora_i.strftime("%H:%M")} y {hora_j.strftime("%H:%M")} se solapan entre sí. '
                                   f'Cada función dura {pelicula.duracion} min + {minutos_limpieza} min de limpieza.'
                    })
        
        # Iterar sobre cada horario que el usuario quiere crear
        for fecha_hora_propuesta, fin_funcion_propuesta, hora_obj in horarios_con_duracion:
            
            # Validar que no sea en el pasado
            if fecha_hora_propuesta < timezone.now():
                raise ValidationError({'horarios': f'El horario {hora_obj.strftime("%H:%M")} del día {fecha.strftime("%d/%m")} ya pasó.'})
            
            # Buscar SOLO funciones en la misma sala y el MISMO DÍA
            funciones_existentes = Funcion.objects.filter(
                sala=sala,
                fecha_hora__date=fecha  # FILTRO POR DÍA ESPECÍFICO
            ).order_by('fecha_hora')

            # Verificar solapamiento con cada función existente
            for funcion_existente in funciones_existentes:
                inicio_existente = funcion_existente.fecha_hora
                fin_existente = inicio_existente + timedelta(minutes=funcion_existente.pelicula.duracion + minutos_limpieza)
                
                # Condición de solapamiento: 
                # Se solapan si la nueva empieza antes de que termine la existente
                # Y la nueva termina después de que empiece la existente
                if fecha_hora_propuesta < fin_existente and fin_funcion_propuesta > inicio_existente:
                    raise ValidationError({
                        'horarios': f'El horario {hora_obj.strftime("%H:%M")} se solapa con "{funcion_existente.pelicula.titulo}" '
                                    f'programada de {inicio_existente.strftime("%H:%M")} a {fin_existente.strftime("%H:%M")} en la misma sala. '
                                    f'(Se incluyen {minutos_limpieza} min. de limpieza entre funciones).'
                    })

        return cleaned_data


class ConfiguracionCineForm(forms.ModelForm):
    """
    Formulario para editar la configuración del cine
    """
    
    nombre = forms.CharField(
        label='🎬 Nombre del Cine',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Cine CineGest',
            'required': True,
            'title': 'Nombre comercial del cine'
        }),
        error_messages={
            'required': 'El nombre del cine es obligatorio.'
        }
    )
    
    razon_social = forms.CharField(
        label='🏢 Razón Social',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: CineGest S.A.',
            'required': True,
            'title': 'Razón social registrada'
        }),
        error_messages={
            'required': 'La razón social es obligatoria.'
        }
    )
    
    cuil_cuit = forms.CharField(
        label='📋 CUIL/CUIT',
        max_length=13,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'XX-XXXXXXXX-X',
            'required': True,
            'pattern': r'\d{2}-\d{8}-\d{1}',
            'title': 'Formato: XX-XXXXXXXX-X (solo números y guiones)'
        }),
        error_messages={
            'required': 'El CUIL/CUIT es obligatorio.',
            'invalid': 'Formato inválido. Use XX-XXXXXXXX-X'
        }
    )
    
    direccion = forms.CharField(
        label='📍 Dirección',
        max_length=300,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Av. Corrientes 1234, CABA',
            'required': True,
            'title': 'Dirección física del cine'
        }),
        error_messages={
            'required': 'La dirección es obligatoria.'
        }
    )
    
    telefono = forms.CharField(
        label='📞 Teléfono',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+54 11 0000-0000',
            'required': True,
            'type': 'tel',
            'title': 'Número de contacto'
        }),
        error_messages={
            'required': 'El teléfono es obligatorio.'
        }
    )
    
    email = forms.EmailField(
        label='📧 Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'contacto@micine.com',
            'required': True,
            'type': 'email',
            'title': 'Email de contacto'
        }),
        error_messages={
            'required': 'El email es obligatorio.',
            'invalid': 'Ingrese un email válido.'
        }
    )
    
    descripcion = forms.CharField(
        label='📝 Descripción',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Descripción del cine, servicios, características especiales...',
            'rows': 4,
            'title': 'Descripción general del cine'
        })
    )
    
    horario_apertura = forms.TimeField(
        label='🕐 Horario de Apertura',
        widget=forms.TimeInput(attrs={
            'class': 'form-input',
            'type': 'time',
            'required': True,
            'title': 'Hora de apertura del cine'
        }),
        error_messages={
            'required': 'El horario de apertura es obligatorio.',
            'invalid': 'Formato de hora inválido.'
        }
    )
    
    horario_cierre = forms.TimeField(
        label='🕐 Horario de Cierre',
        widget=forms.TimeInput(attrs={
            'class': 'form-input',
            'type': 'time',
            'required': True,
            'title': 'Hora de cierre del cine'
        }),
        error_messages={
            'required': 'El horario de cierre es obligatorio.',
            'invalid': 'Formato de hora inválido.'
        }
    )
    
    minutos_limpieza = forms.IntegerField(
        label='🧹 Minutos de Limpieza',
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '30',
            'required': True,
            'min': '0',
            'max': '120',
            'step': '5',
            'title': 'Tiempo entre funciones para limpieza (0-120 minutos)'
        }),
        help_text='Tiempo entre funciones para limpieza de sala',
        error_messages={
            'required': 'Los minutos de limpieza son obligatorios.',
            'invalid': 'Ingrese un número válido.',
            'min_value': 'El valor mínimo es 0 minutos.',
            'max_value': 'El valor máximo es 120 minutos.'
        }
    )
    
    facebook = forms.URLField(
        label='📘 Facebook',
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-input',
            'placeholder': 'https://facebook.com/micine',
            'type': 'url',
            'title': 'URL de la página de Facebook'
        })
    )
    
    instagram = forms.URLField(
        label='📷 Instagram',
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-input',
            'placeholder': 'https://instagram.com/micine',
            'type': 'url',
            'title': 'URL del perfil de Instagram'
        })
    )
    
    twitter = forms.URLField(
        label='🐦 Twitter/X',
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-input',
            'placeholder': 'https://twitter.com/micine',
            'type': 'url',
            'title': 'URL del perfil de Twitter/X'
        })
    )
    
    logo = forms.ImageField(
        label='🖼️ Logo del Cine',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*',
            'title': 'Seleccione una imagen para el logo'
        })
    )
    
    class Meta:
        model = ConfiguracionCine
        fields = [
            'nombre', 'logo', 'razon_social', 'cuil_cuit', 'descripcion',
            'direccion', 'telefono', 'email',
            'horario_apertura', 'horario_cierre', 'minutos_limpieza',
            'facebook', 'instagram', 'twitter'
        ]
    
    def clean_cuil_cuit(self):
        """Validar formato de CUIL/CUIT"""
        cuil_cuit = self.cleaned_data.get('cuil_cuit')
        if cuil_cuit:
            import re
            if not re.match(r'^\d{2}-\d{8}-\d{1}$', cuil_cuit):
                raise ValidationError('El formato debe ser XX-XXXXXXXX-X (ej: 20-12345678-9)')
        return cuil_cuit
    
    def clean(self):
        """Validar que el horario de cierre sea posterior al de apertura"""
        cleaned_data = super().clean()
        apertura = cleaned_data.get('horario_apertura')
        cierre = cleaned_data.get('horario_cierre')
        
        if apertura and cierre:
            if cierre <= apertura:
                raise ValidationError({
                    'horario_cierre': 'El horario de cierre debe ser posterior al de apertura.'
                })
        
        return cleaned_data