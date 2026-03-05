from django import forms
from django.db import models
from .models import Pelicula, Sala, Funcion, Formato, FuncionFormato, ConfiguracionCine, Genero, ExcepcionHorario
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
        input_formats=['%Y-%m-%d'],  # Formato ISO para HTML5
        widget=forms.DateInput(
            format='%Y-%m-%d',  # Formato de salida
            attrs={
                'class': 'form-input',
                'type': 'date',
                'required': True,
                'title': 'La fecha de estreno es obligatoria'
            }
        ),
        error_messages={
            'required': 'La fecha de estreno es obligatoria.',
            'invalid': 'Ingresa una fecha válida.'
        }
    )
    
    clasificacion = forms.ChoiceField(
        label='🔞 Clasificación',
        choices=[
            ('ATP', 'Apta para todo público'),
            ('+13', 'Mayores de 13 años'),
            ('+16', 'Mayores de 16 años'),
            ('+18', 'Mayores de 18 años'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona la clasificación por edad de la película'
        }),
        error_messages={
            'required': 'La clasificación es obligatoria.'
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
        """Validación y normalización del título"""
        titulo = self.cleaned_data.get('titulo', '')
        titulo = titulo.strip()
        if len(titulo) < 2:
            raise forms.ValidationError('El título debe tener al menos 2 caracteres.')
        # Normalizar: Title Case
        return titulo.title()
    
    def clean_director(self):
        """Validación y normalización del director"""
        director = self.cleaned_data.get('director', '')
        director = director.strip()
        if len(director) < 2:
            raise forms.ValidationError('El nombre del director debe tener al menos 2 caracteres.')
        # Normalizar: Title Case
        return director.title()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicializar queryset de géneros dinámicamente
        try:
            self.fields['generos'].queryset = Genero.objects.all().order_by('nombre')
        except Exception:
            # En entornos donde el modelo no existe aún (migrations) fallamos silenciosamente
            self.fields['generos'].queryset = []

        # ========================================================================
        # CONFIGURACIÓN DE WIDGET DE FECHA
        # ========================================================================
        # NO agregamos 'min' al widget HTML5 porque puede causar problemas con zonas horarias
        # Las validaciones se manejan en el servidor (clean_fecha_estreno y modelo)
        # Esto evita que el navegador rechace fechas válidas debido a diferencias de zona horaria

        # ========================================================================
        # PROTECCIÓN DE DATOS: Bloqueo de campos si hay entradas vendidas
        # ========================================================================
        # Si estamos editando una película existente, verificar si tiene ventas
        if self.instance and self.instance.pk:
            try:
                # Verificar si la película tiene funciones con entradas vendidas
                if self.instance.tiene_entradas_vendidas():
                    # Deshabilitar título y fecha de estreno en la interfaz
                    self.fields['titulo'].disabled = True
                    self.fields['titulo'].widget.attrs['readonly'] = True
                    self.fields['titulo'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['titulo'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['titulo'].help_text = (
                        '⚠️ El título no puede modificarse porque esta película tiene funciones con entradas vendidas. '
                        'Por contrato con el cliente, esta información es INMUTABLE.'
                    )

                    self.fields['fecha_estreno'].disabled = True
                    self.fields['fecha_estreno'].widget.attrs['readonly'] = True
                    self.fields['fecha_estreno'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['fecha_estreno'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['fecha_estreno'].help_text = (
                        '⚠️ La fecha de estreno no puede modificarse porque esta película tiene funciones con entradas vendidas. '
                        'Por contrato con el cliente, esta información es INMUTABLE.'
                    )
                    
                    # Bloquear también otros campos críticos relacionados con las ventas
                    self.fields['director'].disabled = True
                    self.fields['director'].widget.attrs['readonly'] = True
                    self.fields['director'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['director'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['director'].help_text = '⚠️ No puede modificarse porque hay funciones con entradas vendidas.'
                    
                    self.fields['duracion'].disabled = True
                    self.fields['duracion'].widget.attrs['readonly'] = True
                    self.fields['duracion'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['duracion'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['duracion'].help_text = '⚠️ No puede modificarse porque hay funciones con entradas vendidas.'
                    
                    self.fields['clasificacion'].disabled = True
                    self.fields['clasificacion'].widget.attrs['class'] = 'form-select input-disabled'
                    self.fields['clasificacion'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['clasificacion'].help_text = '⚠️ No puede modificarse porque hay funciones con entradas vendidas.'
            except Exception:
                # Si hay algún error al verificar, seguir adelante sin bloquear
                # La validación en clean() del modelo seguirá protegiéndolo
                pass
    
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
        fecha_estreno = self.cleaned_data.get('fecha_estreno')
        if not fecha_estreno:
            return fecha_estreno
            
        # Solo validar "no pasado" para películas NUEVAS
        # PERMITIDO: Hoy y futuro
        # BLOQUEADO: Solo fechas anteriores a hoy (pasado)
        if not self.instance.pk:  # Si es creación
            hoy = timezone.now().date()
            if fecha_estreno < hoy:  # Menor que HOY (no incluye hoy)
                raise forms.ValidationError(
                    f'La fecha de estreno no puede ser anterior al día de hoy ({hoy.strftime("%d/%m/%Y")}). '
                    f'Puedes seleccionar hoy o cualquier fecha futura.'
                )
        
        return fecha_estreno
    
    def clean(self):
        """Validación global del formulario que captura errores del modelo"""
        cleaned_data = super().clean()
        
        # Verificar duplicados de título + año antes de llegar al modelo
        titulo = cleaned_data.get('titulo')
        fecha_estreno = cleaned_data.get('fecha_estreno')
        
        if titulo and fecha_estreno:
            anio = fecha_estreno.year
            
            # Buscar películas con el mismo título y año
            peliculas_existentes = Pelicula.objects.filter(
                titulo=titulo,
                anio_estreno=anio
            )
            
            # Si estamos editando, excluir la película actual
            if self.instance.pk:
                peliculas_existentes = peliculas_existentes.exclude(pk=self.instance.pk)
            
            # Si existe otra película con el mismo título y año, lanzar error
            if peliculas_existentes.exists():
                self.add_error('titulo', 
                    f"Esta película ya está registrada con esa fecha de estreno ({anio}). "
                    f"Por favor, verifica el título o selecciona otro año."
                )
        
        return cleaned_data


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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando (instance existe), deshabilitar el campo número
        if self.instance.pk:
            self.fields['numero'].disabled = True
            self.fields['numero'].widget.attrs['readonly'] = True
            self.fields['numero'].help_text = 'El número de sala no puede modificarse una vez creada.'
        else:
            # Si estamos creando, sugerir el siguiente número disponible
            ultimo_numero = Sala.objects.aggregate(models.Max('numero'))['numero__max']
            siguiente_numero = (ultimo_numero or 0) + 1
            self.fields['numero'].initial = siguiente_numero
            self.fields['numero'].help_text = f'Siguiente número sugerido: {siguiente_numero}'
            
            # 🆕 OCULTAR campo 'activo' al crear una sala nueva
            # (las salas nuevas siempre son activas por defecto)
            self.fields['activo'].widget = forms.HiddenInput()
            self.fields['activo'].initial = True
    
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
    
   
    
    activo = forms.BooleanField(
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
        fields = ['numero', 'nombre', 'activo', 'observaciones']

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
            'class': 'form-select combobox-select',
            'required': True,
            'title': 'Selecciona o busca la película a proyectar',
            'data-searchable': 'true'
        }),
        error_messages={
            'required': 'Debes seleccionar una película.',
            'invalid_choice': 'La película seleccionada no es válida.'
        }
    )
    
    sala = forms.ModelChoiceField(
        label='🏛️ Sala',
        queryset=Sala.objects.none(),  # Se inicializa en __init__
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
    
    estado = forms.ChoiceField(
        label='5. Estado',
        choices=[('ACTIVA', 'Activa'), ('PREVENTA', 'Preventa')],
        widget=forms.RadioSelect,
        required=True,
        initial='ACTIVA',
        error_messages={'required': 'Debes seleccionar un estado.'}
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
        fields = ['pelicula', 'sala', 'fecha_hora', 'idioma', 'estado', 'precio_base']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Inicializar flag de protección
        self._tiene_entradas_vendidas = False
        
        # 🛡️ FILTRAR SALAS: Solo salas activas CON butacas configuradas
        from django.db.models import Count
        salas_con_butacas = Sala.objects.filter(
            activo=True
        ).annotate(
            num_butacas=Count('butacas')
        ).filter(
            num_butacas__gt=0
        ).order_by('numero')
        
        self.fields['sala'].queryset = salas_con_butacas
        
        if salas_con_butacas.count() == 0:
            self.fields['sala'].help_text = (
                '⚠️ No hay salas disponibles con butacas configuradas. '
                'Por favor, configura la distribución de asientos en al menos una sala.'
            )
        
        # Si estamos editando, cargar los formatos actuales
        if self.instance and self.instance.pk:
            # ========================================================================
            # PROTECCIÓN DE DATOS: Bloqueo de campos si hay entradas vendidas
            # ========================================================================
            try:
                # Verificar si la función tiene entradas vendidas
                tiene_entradas_vendidas = self.instance.entradas.filter(
                    estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
                ).exists()

                if tiene_entradas_vendidas:
                    # 🔒 BLOQUEO VISUAL: Solo readonly para mostrar pero NO disabled
                    # (disabled=True hace que los campos no se envíen en el POST)
                    for field_name in self.fields:
                        self.fields[field_name].widget.attrs['readonly'] = True
                        self.fields[field_name].widget.attrs['class'] = self.fields[field_name].widget.attrs.get('class', '') + ' input-disabled'
                        self.fields[field_name].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed; pointer-events: none;'
                        self.fields[field_name].widget.attrs['tabindex'] = '-1'
                    
                    # Mensaje de advertencia general
                    self.fields['pelicula'].help_text = (
                        '🔒 FUNCIÓN BLOQUEADA: Esta función tiene entradas vendidas. '
                        'Por contrato con el cliente, NO se permite ninguna modificación. '
                        'Si necesitas cambiar algo, debes contactar al cliente y ofrecer un reembolso.'
                    )
                    
                    # Marcar que esta instancia tiene ventas (para save())
                    self._tiene_entradas_vendidas = True
            except Exception:
                # Si hay algún error al verificar, seguir adelante sin bloquear
                # La validación en clean() del modelo seguirá protegiéndolo
                pass

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
            ahora = timezone.now()
            if fecha_hora < ahora:
                raise forms.ValidationError('La fecha y hora no pueden ser en el pasado.')
            
            # 🛡️ VALIDACIÓN: No permitir funciones a más de 1 año en el futuro
            limite_futuro = ahora + timedelta(days=365)
            if fecha_hora > limite_futuro:
                raise forms.ValidationError(
                    f'No se pueden crear funciones a más de 1 año en el futuro. '
                    f'Límite: {limite_futuro.strftime("%d/%m/%Y %H:%M")}'
                )
        
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
            if not sala.activo:
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

    def save(self, commit=True):
        """
        🔒 PROTECCIÓN: Si la función tiene entradas vendidas, NO permitir NINGUNA modificación.
        """
        # Verificar si se marcó como bloqueada en __init__
        if hasattr(self, '_tiene_entradas_vendidas') and self._tiene_entradas_vendidas:
            # Retornar la instancia original sin cambios
            return self.instance
        
        # Si no hay entradas vendidas, guardar normalmente
        return super().save(commit=commit)

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
        queryset=Sala.objects.none(),  # Se inicializa en __init__
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
    
    estado = forms.ChoiceField(
        label='5. Estado',
        choices=[('ACTIVA', 'Activa'), ('PREVENTA', 'Preventa')],
        widget=forms.RadioSelect,
        required=True,
        initial='ACTIVA',
        error_messages={'required': 'Debes seleccionar un estado.'}
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

    def clean_fecha(self):
        """Validación para la fecha de las funciones"""
        fecha = self.cleaned_data.get('fecha')
        
        if not fecha:
            raise forms.ValidationError('Debes seleccionar una fecha.')
        
        # Validar que no sea en el pasado
        hoy = timezone.now().date()
        if fecha < hoy:
            raise forms.ValidationError(
                f'La fecha no puede ser en el pasado. '
                f'Hoy es {hoy.strftime("%d/%m/%Y")}.'
            )
        
        # 🛡️ VALIDACIÓN: No permitir funciones a más de 1 año en el futuro
        limite_futuro = hoy + timedelta(days=365)
        if fecha > limite_futuro:
            raise forms.ValidationError(
                f'❌ No se pueden crear funciones a más de 1 año en el futuro. '
                f'Límite máximo: {limite_futuro.strftime("%d/%m/%Y")}'
            )
        
        return fecha

    def __init__(self, *args, **kwargs):
        # ✅ Extraer la función si es edición
        funcion = kwargs.pop('funcion', None)
        super().__init__(*args, **kwargs)
        
        # Inicializar flag de protección
        self._tiene_entradas_vendidas = False
        self._funcion = funcion
        
        # 🔒 PROTECCIÓN: Bloqueo de campos si hay entradas vendidas
        if funcion and funcion.pk:
            try:
                tiene_entradas_vendidas = funcion.entradas.filter(
                    estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
                ).exists()
                
                if tiene_entradas_vendidas:
                    # Bloquear TODOS los campos visualmente
                    for field_name in self.fields:
                        self.fields[field_name].widget.attrs['readonly'] = True
                        self.fields[field_name].widget.attrs['class'] = self.fields[field_name].widget.attrs.get('class', '') + ' input-disabled'
                        self.fields[field_name].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed; pointer-events: none;'
                        self.fields[field_name].widget.attrs['tabindex'] = '-1'
                    
                    self.fields['pelicula'].help_text = (
                        '🔒 FUNCIÓN BLOQUEADA: Esta función tiene entradas vendidas. '
                        'Por contrato con el cliente, NO se permite ninguna modificación.'
                    )
                    
                    self._tiene_entradas_vendidas = True
            except Exception:
                pass
        
        # 🛡️ FILTRAR SALAS: Solo salas activas CON butacas configuradas
        from django.db.models import Count
        salas_con_butacas = Sala.objects.filter(
            activo=True
        ).annotate(
            num_butacas=Count('butacas')
        ).filter(
            num_butacas__gt=0
        ).order_by('numero')
        
        self.fields['sala'].queryset = salas_con_butacas
        
        if salas_con_butacas.count() == 0:
            self.fields['sala'].help_text = (
                '⚠️ No hay salas disponibles con butacas configuradas. '
                'Por favor, configura la distribución de asientos en al menos una sala.'
            )
        
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
        if not sala.activo:
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
            
            # ✅ Si estamos EDITANDO una función, excluirla de la validación
            if hasattr(self, '_funcion') and self._funcion and self._funcion.pk:
                funciones_existentes = funciones_existentes.exclude(pk=self._funcion.pk)

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
    
    # NOTA: Los horarios de apertura/cierre ahora se gestionan con HorarioAtencion
    # Ver gestión de horarios en la vista dedicada
    
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
    
    reserva_tiempo_espera = forms.IntegerField(
        label='⏰ Tiempo de Espera para Reservas (minutos)',
        min_value=1,
        max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '10',
            'required': True,
            'min': '1',
            'max': '60',
            'step': '1',
            'title': 'Tiempo que el cliente tiene para completar la compra después de seleccionar butacas (1-60 minutos)'
        }),
        help_text='Tiempo máximo que un cliente tiene para completar su compra después de seleccionar butacas',
        error_messages={
            'required': 'El tiempo de espera para reservas es obligatorio.',
            'invalid': 'Ingrese un número válido.',
            'min_value': 'El valor mínimo es 1 minuto.',
            'max_value': 'El valor máximo es 60 minutos.'
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
            'minutos_limpieza',
            'reserva_tiempo_espera',
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
    
    # Nota: La validación de horarios ahora se maneja en HorarioAtencion
    # No es necesario el método clean() aquí


# ============================================================================
# FORMULARIOS PARA HORARIOS DE ATENCIÓN (Sistema Flexible por Día)
# ============================================================================

class HorarioAtencionForm(forms.ModelForm):
    """
    Formulario para crear/editar un rango horario de atención.
    Cada instancia representa un rango para un día específico.
    """
    
    dia_semana = forms.ChoiceField(
        label='📅 Día de la Semana',
        choices=[
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
            (5, 'Sábado'),
            (6, 'Domingo'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-input',
            'required': True
        })
    )
    
    hora_apertura = forms.TimeField(
        label='🕐 Hora de Apertura',
        widget=forms.TimeInput(attrs={
            'class': 'form-input',
            'type': 'time',
            'required': True,
            'title': 'Hora de inicio del rango'
        }),
        error_messages={
            'required': 'La hora de apertura es obligatoria.',
            'invalid': 'Formato de hora inválido.'
        }
    )
    
    hora_cierre = forms.TimeField(
        label='🕐 Hora de Cierre',
        widget=forms.TimeInput(attrs={
            'class': 'form-input',
            'type': 'time',
            'required': True,
            'title': 'Hora de fin del rango'
        }),
        error_messages={
            'required': 'La hora de cierre es obligatoria.',
            'invalid': 'Formato de hora inválido.'
        }
    )
    
    activo = forms.BooleanField(
        label='✅ Activo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'title': 'Desmarcar para deshabilitar temporalmente este horario'
        }),
        help_text='Desmarcar para deshabilitar temporalmente sin eliminar'
    )
    
    orden = forms.IntegerField(
        label='📊 Orden',
        required=False,
        initial=0,
        min_value=0,
        max_value=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'min': '0',
            'max': '10',
            'title': 'Orden de visualización (0, 1, 2...)'
        }),
        help_text='Orden para múltiples rangos del mismo día'
    )
    
    class Meta:
        from .models import HorarioAtencion
        model = HorarioAtencion
        fields = ['dia_semana', 'hora_apertura', 'hora_cierre', 'activo', 'orden']
    
    def clean(self):
        """Validar que cierre > apertura"""
        cleaned_data = super().clean()
        apertura = cleaned_data.get('hora_apertura')
        cierre = cleaned_data.get('hora_cierre')
        
        if apertura and cierre:
            if cierre <= apertura:
                raise ValidationError({
                    'hora_cierre': 'El horario de cierre debe ser posterior al de apertura.'
                })
        
        return cleaned_data


# Formset para gestionar múltiples horarios
from django.forms import modelformset_factory, inlineformset_factory
from .models import HorarioAtencion

HorarioAtencionFormSet = modelformset_factory(
    HorarioAtencion,
    form=HorarioAtencionForm,
    extra=0,  # No mostrar formularios extra vacíos (evita errores al solo eliminar)
    can_delete=True,  # Permitir eliminar horarios
    min_num=0,  # Permitir 0 horarios (todos eliminados)
    validate_min=False,  # No validar el mínimo
    max_num=21,  # Máximo 3 rangos por día × 7 días = 21 total
    validate_max=True
)


# FormSet inline para editar horarios de un día específico
HorarioAtencionInlineFormSet = inlineformset_factory(
    ConfiguracionCine,
    HorarioAtencion,
    form=HorarioAtencionForm,
    extra=1,
    can_delete=True,
    max_num=5,  # Máximo 5 rangos por día (razonable)
    validate_max=True
)


# ============================================================================
# FORM: EXCEPCIÓN DE HORARIO
# ============================================================================

class ExcepcionHorarioForm(forms.ModelForm):
    """
    Formulario para crear y editar excepciones de horario.
    
    Casos de uso:
    - Días cerrados: cerrado=True, sin horarios
    - Días con horario modificado: cerrado=False, con horarios específicos
    
    Validaciones:
    - Si cerrado=True → hora_apertura y hora_cierre deben estar vacíos
    - Si cerrado=False → hora_apertura y hora_cierre son obligatorios
    - hora_cierre > hora_apertura
    """
    
    class Meta:
        model = ExcepcionHorario
        fields = ['fecha', 'fecha_fin', 'cerrado', 'hora_apertura', 'hora_cierre', 'descripcion']
        widgets = {
            'fecha': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input',
                'placeholder': 'Seleccionar fecha de inicio'
            }),
            'fecha_fin': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input',
                'placeholder': 'Opcional: Fecha de fin del rango'
            }),
            'cerrado': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'id': 'id_cerrado',
                'onchange': 'toggleHorarios()'  # JavaScript para mostrar/ocultar horarios
            }),
            'hora_apertura': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-input',
                'id': 'id_hora_apertura',
                'placeholder': 'HH:MM'
            }),
            'hora_cierre': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-input',
                'id': 'id_hora_cierre',
                'placeholder': 'HH:MM'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Navidad, Nochebuena, Mantenimiento',
                'maxlength': 200
            }),
        }
        labels = {
            'fecha': '📅 Fecha de Inicio',
            'fecha_fin': '📅 Fecha de Fin (Opcional)',
            'cerrado': '🚫 Cine cerrado este día',
            'hora_apertura': '🕐 Hora de apertura',
            'hora_cierre': '🕐 Hora de cierre',
            'descripcion': '📝 Descripción / Motivo',
        }
        help_texts = {
            'fecha': 'Selecciona la fecha de inicio de la excepción',
            'fecha_fin': 'Dejar vacío para excepción de un solo día. Completar para rango de días consecutivos.',
            'cerrado': 'Marcar si el cine estará completamente cerrado',
            'hora_apertura': 'Solo si el cine NO está cerrado (horario modificado)',
            'hora_cierre': 'Solo si el cine NO está cerrado (horario modificado)',
            'descripcion': 'Breve explicación del motivo (ej: "Navidad", "Mantenimiento programado")',
        }
    
    def __init__(self, *args, **kwargs):
        """Inicializar form y configurar campos opcionales según contexto"""
        super().__init__(*args, **kwargs)
        
        # Si es POST y cerrado=True, los campos de horario NO son requeridos
        # Usar self.data que ya está disponible después de super().__init__()
        if self.data and self.data.get('cerrado') in ['on', 'true', True, '1', 1]:
            self.fields['hora_apertura'].required = False
            self.fields['hora_cierre'].required = False
        
        # Si es edición y está cerrado, deshabilitar horarios en el cliente
        if self.instance.pk and self.instance.cerrado:
            self.fields['hora_apertura'].widget.attrs['disabled'] = True
            self.fields['hora_cierre'].widget.attrs['disabled'] = True
            self.fields['hora_apertura'].required = False
            self.fields['hora_cierre'].required = False
    
    def clean(self):
        """
        Validaciones customizadas del formulario.
        
        Complementa las validaciones del modelo para mejor UX.
        """
        cleaned_data = super().clean()
        
        # IMPORTANTE: Usar self.data para detectar checkbox marcado
        # Los checkboxes vienen como 'on' en POST, pero pueden ser None in cleaned_data
        cerrado = self.data.get('cerrado') in ['on', 'true', True, '1', 1]
        
        hora_apertura = cleaned_data.get('hora_apertura')
        hora_cierre = cleaned_data.get('hora_cierre')
        fecha = cleaned_data.get('fecha')
        fecha_fin = cleaned_data.get('fecha_fin')
        
        # Validar coherencia de rango de fechas
        if fecha_fin and fecha and fecha_fin < fecha:
            self.add_error('fecha_fin', 'La fecha de fin debe ser igual o posterior a la fecha de inicio.')
        
        # Validar coherencia entre cerrado y horarios
        if cerrado:
            # Si está cerrado, limpiar horarios (ignorar lo que haya en el form)
            cleaned_data['cerrado'] = True  # Asegurar que esté en cleaned_data
            cleaned_data['hora_apertura'] = None
            cleaned_data['hora_cierre'] = None
            
            # Limpiar errores de horarios si existen (Django los valida antes de este clean)
            if 'hora_apertura' in self.errors:
                del self.errors['hora_apertura']
            if 'hora_cierre' in self.errors:
                del self.errors['hora_cierre']
            
            # VALIDACIÓN CRÍTICA: Verificar ventas confirmadas antes de permitir cierre
            if fecha:
                from ventas.models import Venta
                
                # Determinar rango de fechas a verificar
                fecha_inicio = fecha
                fecha_final = fecha_fin if fecha_fin else fecha
                
                # Buscar ventas confirmadas para funciones en ese rango
                ventas_comprometidas = Venta.objects.filter(
                    entradas__id_funcion__fecha_hora__date__gte=fecha_inicio,
                    entradas__id_funcion__fecha_hora__date__lte=fecha_final,
                    estado__in=['CONFIRMADA', 'PENDIENTE_PAGO', 'PENDIENTE']
                ).distinct()
                
                if ventas_comprometidas.exists():
                    # Contar ventas y entradas
                    total_ventas = ventas_comprometidas.count()
                    total_entradas = 0
                    
                    for venta in ventas_comprometidas:
                        total_entradas += venta.entradas.filter(
                            id_funcion__fecha_hora__date__gte=fecha_inicio,
                            id_funcion__fecha_hora__date__lte=fecha_final
                        ).count()
                    
                    # Formatear mensaje según rango o día único
                    if fecha_final != fecha_inicio:
                        fecha_str = f"del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_final.strftime('%d/%m/%Y')}"
                    else:
                        fecha_str = f"el día {fecha_inicio.strftime('%d/%m/%Y')}"
                    
                    entrada_plural = "s" if total_entradas != 1 else ""
                    vendida_plural = "s" if total_entradas != 1 else ""
                    venta_plural = "s" if total_ventas != 1 else ""
                    
                    self.add_error('cerrado', 
                        f'No es posible cerrar el cine {fecha_str}: '
                        f'Existen {total_entradas} entrada{entrada_plural} ya vendida{vendida_plural} '
                        f'({total_ventas} venta{venta_plural}). '
                    )
                    # No continuar validando horarios si hay error de ventas
                    return cleaned_data
        else:
            # Si NO está cerrado, los horarios son obligatorios
            if not hora_apertura:
                self.add_error('hora_apertura', 'Este campo es obligatorio cuando el cine NO está cerrado.')
            
            if not hora_cierre:
                self.add_error('hora_cierre', 'Este campo es obligatorio cuando el cine NO está cerrado.')
            
            # Validar que cierre > apertura
            if hora_apertura and hora_cierre:
                if hora_cierre <= hora_apertura:
                    self.add_error('hora_cierre', 'La hora de cierre debe ser posterior a la hora de apertura.')
        
        # Validar que la fecha no sea en el pasado (opcional, depende de lógica de negocio)
        if fecha:
            hoy = timezone.now().date()
            if fecha < hoy:
                # Advertencia: Permitir editar excepciones pasadas pero avisar
                # No es un error crítico, solo informativo
                pass  # Puedes agregar warning si lo deseas
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Guardar excepción asignando configuracion_cine automáticamente.
        """
        excepcion = super().save(commit=False)
        
        # Asignar configuración del cine (Singleton)
        if not excepcion.configuracion_cine_id:
            excepcion.configuracion_cine = ConfiguracionCine.load()
        
        if commit:
            excepcion.save()
        
        return excepcion