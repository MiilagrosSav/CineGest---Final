from django import forms
from django.db import models
from .models import Pelicula, Sala, Funcion, Formato, FuncionFormato, ConfiguracionCine, Genero, Clasificacion, ExcepcionHorario, Director
from datetime import date, datetime, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone

class PeliculaForm(forms.ModelForm):
    """
    Formulario profesionalizado para Pelicula con director normalizado (FK).
    Soporta:
    - Seleccion de director existente
    - Alta manual de director (modal -> campos ocultos)
    - Reuso/get_or_create para evitar duplicados
    """

    titulo = forms.CharField(
        label='Titulo de la pelicula',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Avatar: El Camino del Agua',
            'required': True,
            'minlength': '1',
            'maxlength': '200',
            'title': 'El titulo es obligatorio (1-200 caracteres). Puede ser numerico.'
        }),
        error_messages={
            'required': 'El titulo de la pelicula es obligatorio.',
            'max_length': 'El titulo no puede tener mas de 200 caracteres.'
        }
    )

    sinopsis = forms.CharField(
        label='Sinopsis',
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Describe brevemente la historia de la pelicula...',
            'required': True,
            'minlength': '10',
            'maxlength': '1000',
            'rows': 4,
            'title': 'Describe la pelicula (minimo 10 caracteres)'
        }),
        error_messages={
            'required': 'La sinopsis es obligatoria.'
        }
    )

    director = forms.ModelChoiceField(
        label='Director',
        queryset=Director.objects.all().order_by('apellido', 'nombre'),
        required=False,
        empty_label='Selecciona un director existente...',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'title': 'Selecciona un director existente o crea uno nuevo'
        }),
        error_messages={
            'invalid_choice': 'Selecciona un director valido.'
        },
        help_text='Puedes seleccionar uno existente o crear uno nuevo desde el boton "Nuevo director".'
    )

    # Campos ocultos para alta manual desde modal
    director_usar_manual = forms.CharField(required=False, widget=forms.HiddenInput())
    director_nombre_manual = forms.CharField(required=False, max_length=100, widget=forms.HiddenInput())
    director_apellido_manual = forms.CharField(required=False, max_length=100, widget=forms.HiddenInput())
    director_fecha_nacimiento_manual = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.HiddenInput()
    )
    director_biografia_manual = forms.CharField(required=False, widget=forms.HiddenInput())
    director_tmdb_id_manual = forms.IntegerField(required=False, widget=forms.HiddenInput())

    generos = forms.ModelMultipleChoiceField(
        label='Generos',
        queryset=None,
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'genre-checkboxes'}),
        help_text='Selecciona uno o mas generos para la pelicula',
        error_messages={
            'required': 'Debe seleccionar al menos un genero.'
        }
    )

    duracion = forms.IntegerField(
        label='Duracion (minutos)',
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 120',
            'required': True,
            'min': '30',
            'max': '300',
            'step': '1',
            'title': 'La duracion es obligatoria (30-300 minutos)'
        }),
        error_messages={
            'required': 'La duracion de la pelicula es obligatoria.',
            'min_value': 'La duracion minima es de 30 minutos.',
            'max_value': 'La duracion maxima es de 300 minutos.'
        }
    )

    fecha_estreno = forms.DateField(
        label='Fecha de estreno',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={
                'class': 'form-input',
                'type': 'date',
                'required': True,
                'title': 'La fecha de estreno es obligatoria'
            }
        ),
        error_messages={
            'required': 'La fecha de estreno es obligatoria.',
            'invalid': 'Ingresa una fecha valida.'
        }
    )

    clasificacion = forms.ModelChoiceField(
        label='Clasificacion',
        queryset=Clasificacion.objects.filter(activo=True).order_by('edad_minima', 'nombre'),
        empty_label='Selecciona una clasificacion',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona la clasificacion por edad de la pelicula'
        }),
        error_messages={
            'required': 'La clasificacion es obligatoria.',
            'invalid_choice': 'Selecciona una clasificacion valida.'
        },
        help_text='Clasificacion por edad segun normativa vigente'
    )

    imagen_portada = forms.ImageField(
        label='Imagen de portada (opcional si usas TMDB)',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*',
            'title': 'Selecciona una imagen para la portada (opcional si buscas en TMDB)'
        }),
        help_text='Si importas desde TMDB, el poster se descarga automaticamente. Tambien puedes subirlo manualmente aqui.'
    )

    youtube_trailer_key = forms.CharField(
        label='Trailer de YouTube (ID)',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: dQw4w9WgXcQ',
            'title': 'ID del video de YouTube del trailer oficial (se autocompleta desde TMDB)'
        }),
        help_text='Se autocompleta desde TMDB. Tambien puedes pegar manualmente el ID del video de YouTube.'
    )

    desactivar = forms.BooleanField(
        label='Desactivar pelicula',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox'
        }),
        help_text='Dar de baja logica la pelicula (no elimina registros).'
    )

    class Meta:
        model = Pelicula
        fields = [
            'titulo', 'sinopsis', 'director', 'generos', 'duracion',
            'fecha_estreno', 'clasificacion', 'imagen_portada',
            'youtube_trailer_key', 'es_estreno', 'acepta_promociones'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.director_warning_message = None
        self._director_manual_payload = None
        self._desactivar_permitido = True

        try:
            self.fields['generos'].queryset = Genero.objects.all().order_by('nombre')
        except Exception:
            self.fields['generos'].queryset = []

        self.fields['director'].queryset = Director.objects.all().order_by('apellido', 'nombre')

        if self.instance and self.instance.pk:
            # Determinar si se permite desactivar la pelicula
            try:
                funciones_activas = self.instance.funciones.filter(
                    activo=True,
                    fecha_hora__gte=timezone.now(),
                ).exclude(estado='INACTIVA').exists()
                self._desactivar_permitido = not funciones_activas
            except Exception:
                self._desactivar_permitido = True

            if not self._desactivar_permitido:
                self.fields['desactivar'].disabled = True
                self.fields['desactivar'].help_text = (
                    'No se puede desactivar porque existen funciones activas asociadas.'
                )
        else:
            # No mostrar desactivar al crear
            self.fields.pop('desactivar', None)

        if self.instance and self.instance.pk:
            try:
                if self.instance.tiene_entradas_vendidas():
                    self.fields['titulo'].disabled = True
                    self.fields['titulo'].widget.attrs['readonly'] = True
                    self.fields['titulo'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['titulo'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['titulo'].help_text = (
                        'No se puede modificar porque esta pelicula tiene funciones con entradas vendidas.'
                    )

                    self.fields['fecha_estreno'].disabled = True
                    self.fields['fecha_estreno'].widget.attrs['readonly'] = True
                    self.fields['fecha_estreno'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['fecha_estreno'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['fecha_estreno'].help_text = (
                        'No se puede modificar porque esta pelicula tiene funciones con entradas vendidas.'
                    )

                    self.fields['director'].disabled = True
                    self.fields['director'].widget.attrs['class'] = 'form-select input-disabled'
                    self.fields['director'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['director'].help_text = 'No puede modificarse porque hay funciones con entradas vendidas.'

                    self.fields['duracion'].disabled = True
                    self.fields['duracion'].widget.attrs['readonly'] = True
                    self.fields['duracion'].widget.attrs['class'] = 'form-input input-disabled'
                    self.fields['duracion'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['duracion'].help_text = 'No puede modificarse porque hay funciones con entradas vendidas.'

                    self.fields['clasificacion'].disabled = True
                    self.fields['clasificacion'].widget.attrs['class'] = 'form-select input-disabled'
                    self.fields['clasificacion'].widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                    self.fields['clasificacion'].help_text = 'No puede modificarse porque hay funciones con entradas vendidas.'
            except Exception:
                pass

    def _normalizar_texto(self, valor):
        return ' '.join((valor or '').strip().split())

    def _to_bool(self, valor):
        return str(valor).strip().lower() in {'1', 'true', 'on', 'si', 'yes'}

    def _resolver_director_manual(self, *, nombre, apellido, fecha_nacimiento=None, biografia='', tmdb_id=None):
        nombre = self._normalizar_texto(nombre).title()
        apellido = self._normalizar_texto(apellido).title()
        biografia = (biografia or '').strip()

        if tmdb_id:
            # Buscar por tmdb_id primero
            director = Director.objects.filter(tmdb_id=tmdb_id).first()
            if not director:
                # Buscar por nombre (manual previo sin tmdb_id)
                director = Director.objects.filter(
                    nombre__iexact=nombre,
                    apellido__iexact=apellido,
                    tmdb_id__isnull=True,
                ).first()
                if director:
                    director.tmdb_id = tmdb_id
                    director.save(update_fields=['tmdb_id'])
                else:
                    director = Director.objects.create(
                        tmdb_id=tmdb_id,
                        nombre=nombre,
                        apellido=apellido,
                        fecha_nacimiento=fecha_nacimiento,
                        biografia=biografia,
                    )
        else:
            director = Director.objects.filter(
                nombre__iexact=nombre,
                apellido__iexact=apellido,
            ).first()
            if not director:
                director = Director.objects.create(
                    nombre=nombre,
                    apellido=apellido,
                    fecha_nacimiento=fecha_nacimiento,
                    biografia=biografia,
                )

        cambios = []
        if tmdb_id and not director.tmdb_id:
            director.tmdb_id = tmdb_id
            cambios.append('tmdb_id')
        if fecha_nacimiento and not director.fecha_nacimiento:
            director.fecha_nacimiento = fecha_nacimiento
            cambios.append('fecha_nacimiento')
        if biografia and not director.biografia:
            director.biografia = biografia
            cambios.append('biografia')

        if cambios:
            director.save(update_fields=cambios)

        return director

    def _build_director_warning(self, director):
        if director and director.fecha_nacimiento:
            return (
                f'Ya existe un director con este nombre nacido el '
                f'{director.fecha_nacimiento.strftime("%d/%m/%Y")}. ¿Es la misma persona?'
            )
        return 'Ya existe un director con este nombre en la base. ¿Es la misma persona?'

    def clean_titulo(self):
        titulo = self._normalizar_texto(self.cleaned_data.get('titulo', ''))
        if len(titulo) < 1:
            raise forms.ValidationError('El titulo debe tener al menos 1 caracter.')
        return titulo.title()

    def clean_duracion(self):
        duracion = self.cleaned_data['duracion']
        if duracion < 30:
            raise forms.ValidationError('La duracion minima es de 30 minutos.')
        if duracion > 300:
            raise forms.ValidationError('La duracion maxima es de 300 minutos.')
        return duracion

    def clean_fecha_estreno(self):
        return self.cleaned_data.get('fecha_estreno')

    def clean(self):
        cleaned_data = super().clean()
        # Si el usuario quiere desactivar, validar permiso
        if cleaned_data.get('desactivar') and not self._desactivar_permitido:
            self.add_error('desactivar', 'No se puede desactivar porque hay funciones activas.')

        titulo = cleaned_data.get('titulo')
        fecha_estreno = cleaned_data.get('fecha_estreno')
        director_obj = cleaned_data.get('director')
        self._director_manual_payload = None
        self.director_warning_message = None

        # Si campos criticos estan deshabilitados, usar valores actuales de la instancia
        if self.instance and self.instance.pk:
            if self.fields.get('titulo') and self.fields['titulo'].disabled and not titulo:
                titulo = self.instance.titulo
                cleaned_data['titulo'] = titulo
            if self.fields.get('fecha_estreno') and self.fields['fecha_estreno'].disabled and not fecha_estreno:
                fecha_estreno = self.instance.fecha_estreno
                cleaned_data['fecha_estreno'] = fecha_estreno
            if self.fields.get('director') and self.fields['director'].disabled and not director_obj:
                director_obj = self.instance.director
                cleaned_data['director'] = director_obj

        usar_manual = self._to_bool(cleaned_data.get('director_usar_manual'))
        if usar_manual:
            nombre = self._normalizar_texto(cleaned_data.get('director_nombre_manual'))
            apellido = self._normalizar_texto(cleaned_data.get('director_apellido_manual'))
            fecha_nac = cleaned_data.get('director_fecha_nacimiento_manual')  # opcional
            biografia = (cleaned_data.get('director_biografia_manual') or '').strip()
            tmdb_id = cleaned_data.get('director_tmdb_id_manual')

            if not nombre or not apellido:
                self.add_error('director', 'Debes completar nombre y apellido del nuevo director en el modal.')

            if nombre and apellido:
                nombre_normalizado = nombre.title()
                apellido_normalizado = apellido.title()

                self._director_manual_payload = {
                    'nombre': nombre_normalizado,
                    'apellido': apellido_normalizado,
                    'fecha_nacimiento': fecha_nac,
                    'biografia': biografia,
                    'tmdb_id': tmdb_id,
                }

                if not tmdb_id:
                    director_existente = Director.objects.filter(
                        nombre__iexact=nombre_normalizado,
                        apellido__iexact=apellido_normalizado,
                    ).order_by('pk').first()
                    if director_existente:
                        self.director_warning_message = self._build_director_warning(director_existente)

        if not director_obj:
            if not self._director_manual_payload:
                self.add_error('director', 'Debes seleccionar un director o crear uno nuevo.')

        if titulo and fecha_estreno:
            anio = fecha_estreno.year
            peliculas_existentes = Pelicula.objects.filter(
                titulo=titulo,
                anio_estreno=anio
            )
            if self.instance.pk:
                peliculas_existentes = peliculas_existentes.exclude(pk=self.instance.pk)
            if peliculas_existentes.exists():
                self.add_error(
                    'titulo',
                    (
                        f'Esta pelicula ya esta registrada con esa fecha de estreno ({anio}). '
                        f'Por favor, verifica el titulo o selecciona otro año.'
                    )
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        payload = self._director_manual_payload
        if payload:
            director_obj = self._resolver_director_manual(**payload)
            if not self.director_warning_message and not payload.get('tmdb_id'):
                self.director_warning_message = self._build_director_warning(director_obj)
            instance.director = director_obj
        elif self.cleaned_data.get('director'):
            instance.director = self.cleaned_data['director']

        if commit:
            instance.save()
            self.save_m2m()

        return instance


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
        label='1. Formato Visual',
        queryset=Formato.objects.filter(categoria='VISUAL').order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato visual.'}
    )

    formatos_pantalla = forms.ModelChoiceField(
        label='2. Formato Pantalla',
        queryset=Formato.objects.filter(categoria='PANTALLA').order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato de pantalla.'}
    )

    formatos_experiencia = forms.ModelChoiceField(
        label='3. Formato Experiencia',
        queryset=Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre'),
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
    
    fecha_activacion = forms.DateField(
        label='📅 Fecha de activación automática',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'title': 'Fecha en que la función pasará automáticamente de PREVENTA a ACTIVA a las 00:00'
        }, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
        help_text='Solo para funciones en PREVENTA. La función se activará automáticamente a las 00:00 de esta fecha.',
        error_messages={
            'invalid': 'Ingresa una fecha válida.'
        }
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
        fields = ['pelicula', 'sala', 'fecha_hora', 'idioma', 'estado', 'fecha_activacion', 'precio_base']
    
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
                entradas_vendidas_count = self.instance.entradas.filter(
                    estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
                ).count()

                if entradas_vendidas_count > 0:
                    # 🔒 BLOQUEO: Deshabilitar todos los campos
                    # Usamos disabled para que funcione con todos los tipos (text, select, radio, etc.)
                    for field_name in self.fields:
                        field = self.fields[field_name]
                        field.disabled = True
                        field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' input-disabled'
                        field.widget.attrs['style'] = 'background-color: #f0f0f0; cursor: not-allowed;'
                        field.widget.attrs['title'] = f'Este campo está bloqueado porque hay {entradas_vendidas_count} entrada(s) vendida(s)'
                    
                    # Mensaje de advertencia general
                    self.fields['pelicula'].help_text = (
                        f'🔒 FUNCIÓN BLOQUEADA: Esta función tiene {entradas_vendidas_count} entrada(s) vendida(s). '
                        f'Por contrato con el cliente, NO se permite ninguna modificación. '
                        f'Si necesitas cambiar algo, debes contactar al cliente y ofrecer un reembolso.'
                    )
                    
                    # Marcar que esta instancia tiene ventas (para save())
                    self._tiene_entradas_vendidas = True
            except Exception as e:
                # Si hay algún error al verificar, seguir adelante sin bloquear
                # La validación en clean() del modelo seguirá protegiéndolo
                pass

            # Cargar los formatos ya asignados
            formatos_actuales = self.instance.formatos_funcion.select_related('formato').all()
            # Inicializar por categoría (tomando el primer formato que coincida con cada categoría)
            visual = formatos_actuales.filter(formato__nombre__in=['2D', '3D']).first()
            pantalla = formatos_actuales.filter(formato__nombre__in=['Pantalla estándar', 'IMAX', 'ScreenX']).first()
            experiencia = formatos_actuales.filter(formato__nombre__in=['Experiencia estándar', '4D', 'D-BOX']).first()
            if visual:
                self.initial['formatos_visual'] = visual.formato_id
            if pantalla:
                self.initial['formatos_pantalla'] = pantalla.formato_id
            if experiencia:
                self.initial['formatos_experiencia'] = experiencia.formato_id
        else:
            # Si es creación nueva, preseleccionar las opciones 'standard' por defecto
            try:
                visual_default = Formato.objects.filter(nombre='2D').first() or Formato.objects.filter(categoria='VISUAL').order_by('nombre').first()
                if visual_default:
                    self.initial.setdefault('formatos_visual', visual_default.id)

                pantalla_default = Formato.objects.filter(nombre__icontains='standard', categoria='PANTALLA').first() or Formato.objects.filter(categoria='PANTALLA').order_by('nombre').first()
                if pantalla_default:
                    self.initial.setdefault('formatos_pantalla', pantalla_default.id)

                experiencia_default = Formato.objects.filter(nombre__icontains='standard', categoria='EXPERIENCIA').first() or Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre').first()
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
        
        # 🛡️ VALIDACIÓN: No permitir funciones para películas que aún no se han estrenado
        if pelicula and fecha_hora:
            fecha_funcion = fecha_hora.date()
            if pelicula.fecha_estreno > fecha_funcion:
                raise ValidationError({
                    'pelicula': f'No se pueden programar funciones antes del estreno de la película. '
                                f'Esta película se estrena el {pelicula.fecha_estreno.strftime("%d/%m/%Y")}. '
                                f'Estás intentando crear una función para el {fecha_funcion.strftime("%d/%m/%Y")}.'
                })
        
        if sala and pelicula and fecha_hora:
            # Verificar que la sala esté activa
            if not sala.activo:
                raise ValidationError({
                    'sala': 'No se pueden programar funciones en salas inactivas.'
                })

            requiere_4d = Funcion.requiere_4d_en_formatos([visual, pantalla, experiencia])
            if requiere_4d is not None:
                tiene_4d, tiene_estandar = Funcion.sala_tiene_butacas_para(sala)
                if requiere_4d and not tiene_4d:
                    raise ValidationError({
                        'sala': 'La sala no tiene butacas 4D para una funcion con formato 4D o D-BOX.'
                    })
                if requiere_4d is False and not tiene_estandar:
                    raise ValidationError({
                        'sala': 'La sala no tiene butacas estandar para funciones sin 4D.'
                    })
            else:
                tiene_4d, tiene_estandar = Funcion.sala_tiene_butacas_para(sala)
            
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
                fecha_hora__date=fecha_hora.date(),
                fecha_hora__lt=fin_funcion,
                fecha_hora__gte=timezone.now(),
            )
            
            # Si estamos editando, excluir la función actual
            if self.instance.pk:
                funciones_solapadas = funciones_solapadas.exclude(pk=self.instance.pk)

            funciones_solapadas = funciones_solapadas.prefetch_related('formatos_funcion__formato')
            
            for funcion in funciones_solapadas:
                duracion_otra = timedelta(minutes=funcion.pelicula.duracion + minutos_limpieza)
                fin_otra = funcion.fecha_hora + duracion_otra
                
                # Verificar si hay solapamiento
                if funcion.fecha_hora < fin_funcion and fecha_hora < fin_otra:
                    requiere_4d_otra = Funcion.requiere_4d_en_formatos(funcion.formatos_funcion.all())
                    if funcion.fecha_hora != fecha_hora:
                        raise ValidationError({
                            'fecha_hora': (
                                f'Esta función se solapa con "{funcion.pelicula.titulo}" '
                                f'programada a las {funcion.fecha_hora.strftime("%d/%m/%Y %H:%M")} en la misma sala.'
                            )
                        })

                    if funcion.pelicula_id != pelicula.id:
                        raise ValidationError({
                            'fecha_hora': (
                                f'Conflicto de Proyección: La sala {sala.nombre} ya tiene '
                                f'programada la película "{funcion.pelicula.titulo}" en este horario.'
                            )
                        })
                    if Funcion.permite_solape_bisala(requiere_4d, requiere_4d_otra, tiene_4d, tiene_estandar):
                        continue
                    if requiere_4d is None or requiere_4d_otra is None:
                        detalle_bisala = 'No se puede solapar sin definir formato de experiencia (4D o estandar).'
                    elif requiere_4d and requiere_4d_otra:
                        detalle_bisala = 'Ambas funciones requieren butacas 4D. El solape solo se permite cuando una es 4D y la otra estandar.'
                    else:
                        detalle_bisala = 'Ambas funciones son estandar. El solape solo se permite cuando una es 4D y la otra estandar.'
                    raise ValidationError({
                        'fecha_hora': f'Esta función se solapa con "{funcion.pelicula.titulo}" '
                                    f'programada a las {funcion.fecha_hora.strftime("%d/%m/%Y %H:%M")} en la misma sala. '
                                    f'{detalle_bisala}'
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
    Formulario para crear funciones en lote por rango de fechas y dias de semana.
    """

    DIAS_SEMANA_CHOICES = [
        ('0', 'Lunes'),
        ('1', 'Martes'),
        ('2', 'Miercoles'),
        ('3', 'Jueves'),
        ('4', 'Viernes'),
        ('5', 'Sabado'),
        ('6', 'Domingo'),
    ]

    pelicula = forms.ModelChoiceField(
        label='Pelicula',
        queryset=Pelicula.objects.all().order_by('titulo'),
        empty_label='Selecciona una película...',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona la película a proyectar'
        })
    )

    sala = forms.ModelChoiceField(
        label='Sala',
        queryset=Sala.objects.none(),
        empty_label='Selecciona una sala...',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona la sala donde se proyectará'
        })
    )

    formatos_visual = forms.ModelChoiceField(
        label='1. Formato Visual',
        queryset=Formato.objects.filter(categoria='VISUAL').order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato visual.'}
    )

    formatos_pantalla = forms.ModelChoiceField(
        label='2. Formato Pantalla',
        queryset=Formato.objects.filter(categoria='PANTALLA').order_by('nombre'),
        widget=forms.RadioSelect,
        required=True,
        empty_label=None,
        error_messages={'required': 'Debes seleccionar un formato de pantalla.'}
    )

    formatos_experiencia = forms.ModelChoiceField(
        label='3. Formato Experiencia',
        queryset=Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre'),
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
    
    fecha_activacion = forms.DateField(
        label='Fecha de activacion automatica',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'title': 'Fecha en que la función pasará automáticamente de PREVENTA a ACTIVA a las 00:00'
        }, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
        help_text='Solo para funciones en PREVENTA. Se activara automaticamente a las 00:00 de esta fecha.',
        error_messages={
            'invalid': 'Ingresa una fecha válida.'
        }
    )

    precio_base = forms.DecimalField(
        label='Precio de entrada',
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
        })
    )

    fecha_inicio = forms.DateField(
        label='Fecha inicio',
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'required': True,
            'title': 'Primer dia del rango'
        }, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d']
    )

    fecha_fin = forms.DateField(
        label='Fecha fin (opcional)',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'title': 'Ultimo dia del rango (opcional)'
        }, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
        help_text='Si no completas fecha fin, se programa solo para la fecha de inicio.'
    )

    dias_semana = forms.MultipleChoiceField(
        label='Dias de la semana',
        choices=DIAS_SEMANA_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'btn-check dia-semana-input'
        }),
        help_text='Selecciona los dias sobre los que se repetiran los horarios.'
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

    def _validar_limite_fecha(self, fecha_valor):
        hoy = timezone.now().date()
        if fecha_valor < hoy:
            raise forms.ValidationError(
                f'La fecha no puede ser en el pasado. Hoy es {hoy.strftime("%d/%m/%Y")}.'
            )

        limite_futuro = hoy + timedelta(days=365)
        if fecha_valor > limite_futuro:
            raise forms.ValidationError(
                f'No se pueden crear funciones a mas de 1 ano en el futuro. '
                f'Limite maximo: {limite_futuro.strftime("%d/%m/%Y")}.'
            )
        return fecha_valor

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

    def clean_fecha_inicio(self):
        fecha_inicio = self.cleaned_data.get('fecha_inicio')
        if not fecha_inicio:
            raise forms.ValidationError('Debes seleccionar la fecha de inicio.')
        return self._validar_limite_fecha(fecha_inicio)

    def clean_fecha_fin(self):
        fecha_fin = self.cleaned_data.get('fecha_fin')
        if not fecha_fin:
            return None
        return self._validar_limite_fecha(fecha_fin)

    def clean_dias_semana(self):
        dias_semana = self.cleaned_data.get('dias_semana', [])
        if not dias_semana:
            return []

        dias_limpios = []
        for dia in dias_semana:
            try:
                dia_int = int(dia)
            except (TypeError, ValueError):
                raise forms.ValidationError('Seleccion de dias invalida.')
            if dia_int < 0 or dia_int > 6:
                raise forms.ValidationError('Seleccion de dias invalida.')
            dias_limpios.append(dia_int)

        return sorted(set(dias_limpios))

    def _generar_fechas_objetivo(self, fecha_inicio, fecha_fin, dias_semana):
        fechas_objetivo = []
        dias_set = set(dias_semana)
        fecha_cursor = fecha_inicio
        while fecha_cursor <= fecha_fin:
            if fecha_cursor.weekday() in dias_set:
                fechas_objetivo.append(fecha_cursor)
            fecha_cursor += timedelta(days=1)
        return fechas_objetivo

    def __init__(self, *args, **kwargs):
        funcion = kwargs.pop('funcion', None)
        super().__init__(*args, **kwargs)

        self._tiene_entradas_vendidas = False
        self._funcion = funcion

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
                        'FUNCION BLOQUEADA: esta funcion tiene entradas vendidas y no puede editarse.'
                    )

                    self._tiene_entradas_vendidas = True
            except Exception:
                pass

        if funcion and funcion.fecha_hora:
            fecha_funcion_local = timezone.localtime(funcion.fecha_hora).date() if timezone.is_aware(funcion.fecha_hora) else funcion.fecha_hora.date()
            self.initial.setdefault('fecha_inicio', fecha_funcion_local)
            self.initial.setdefault('fecha_fin', fecha_funcion_local)
            self.initial.setdefault('dias_semana', [str(fecha_funcion_local.weekday())])

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

        try:
            if not self.initial.get('formatos_visual'):
                visual_default = Formato.objects.filter(nombre='2D').first() or Formato.objects.filter(categoria='VISUAL').order_by('nombre').first()
                if visual_default:
                    self.initial['formatos_visual'] = visual_default.id

            if not self.initial.get('formatos_pantalla'):
                pantalla_default = Formato.objects.filter(nombre__icontains='standard', categoria='PANTALLA').first() or Formato.objects.filter(categoria='PANTALLA').order_by('nombre').first()
                if pantalla_default:
                    self.initial['formatos_pantalla'] = pantalla_default.id

            if not self.initial.get('formatos_experiencia'):
                experiencia_default = Formato.objects.filter(nombre__icontains='standard', categoria='EXPERIENCIA').first() or Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre').first()
                if experiencia_default:
                    self.initial['formatos_experiencia'] = experiencia_default.id
        except Exception:
            pass

    def clean(self):
        """
        Validacion cruzada para:
        - coherencia de rango
        - horarios validos dentro de horario de atencion/excepciones
        - solapamiento entre horarios propuestos y funciones existentes
        """
        cleaned_data = super().clean()
        sala = cleaned_data.get('sala')
        pelicula = cleaned_data.get('pelicula')
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        dias_semana = cleaned_data.get('dias_semana')
        horarios = cleaned_data.get('horarios')

        formatos_sel = []
        visual = cleaned_data.get('formatos_visual')
        pantalla = cleaned_data.get('formatos_pantalla')
        experiencia = cleaned_data.get('formatos_experiencia')
        idioma_valor = cleaned_data.get('idioma')

        if not all([visual, pantalla, experiencia, idioma_valor]):
            raise ValidationError('Debes seleccionar una opcion para cada categoria de formato.')

        for f in (visual, pantalla, experiencia):
            if f:
                formatos_sel.append(f.nombre)

        from cine.models.funcion_formato import FORMATOS_INCOMPATIBLES
        for nombre in formatos_sel:
            if nombre in FORMATOS_INCOMPATIBLES:
                for incompatible in FORMATOS_INCOMPATIBLES[nombre]:
                    if incompatible in formatos_sel:
                        raise ValidationError(f'No puedes combinar {nombre} con {incompatible}. Son tecnologias mutuamente excluyentes.')

        if not all([sala, pelicula, fecha_inicio, horarios]):
            return cleaned_data

        # Flujo de dia unico (sin fecha_fin)
        if not fecha_fin:
            cleaned_data['fechas_objetivo'] = [fecha_inicio]
            cleaned_data['dias_semana'] = [fecha_inicio.weekday()]
        else:
            if fecha_fin < fecha_inicio:
                raise ValidationError({
                    'fecha_fin': 'La fecha de fin debe ser igual o posterior a la fecha de inicio.'
                })

            if not dias_semana:
                raise ValidationError({
                    'dias_semana': 'Debes seleccionar al menos un dia cuando completas la fecha fin.'
                })

            fechas_objetivo = self._generar_fechas_objetivo(fecha_inicio, fecha_fin, dias_semana)
            if not fechas_objetivo:
                raise ValidationError({
                    'dias_semana': 'El rango seleccionado no contiene dias coincidentes con los dias elegidos.'
                })
            cleaned_data['fechas_objetivo'] = fechas_objetivo

        if not sala.activo:
            raise ValidationError({'sala': 'No se pueden programar funciones en salas inactivas.'})

        requiere_4d = Funcion.requiere_4d_en_formatos([visual, pantalla, experiencia])
        if requiere_4d is not None:
            tiene_4d, tiene_estandar = Funcion.sala_tiene_butacas_para(sala)
            if requiere_4d and not tiene_4d:
                raise ValidationError({'sala': 'La sala no tiene butacas 4D para una funcion con formato 4D o D-BOX.'})
            if requiere_4d is False and not tiene_estandar:
                raise ValidationError({'sala': 'La sala no tiene butacas estandar para funciones sin 4D.'})

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

    fecha_inicio_actividad = forms.DateField(
        label='📅 Fecha de Inicio de Actividad',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={
                'class': 'form-input',
                'type': 'date',
                'title': 'Fecha en que el cine inició sus actividades (para comprobantes fiscales)'
            }
        ),
        help_text='Aparece en comprobantes de pago y correos de confirmación.',
        error_messages={'invalid': 'Ingresá una fecha válida.'}
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
            'nombre', 'logo', 'razon_social', 'cuil_cuit', 'fecha_inicio_actividad', 'descripcion',
            'direccion', 'telefono', 'email',
            'minutos_limpieza',
            'reserva_tiempo_espera',
            'facebook', 'instagram', 'twitter'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Evita selección de fechas futuras desde el datepicker.
        self.fields['fecha_inicio_actividad'].widget.attrs['max'] = timezone.localdate().isoformat()
    
    def clean_cuil_cuit(self):
        """Validar formato de CUIL/CUIT"""
        cuil_cuit = self.cleaned_data.get('cuil_cuit')
        if cuil_cuit:
            import re
            if not re.match(r'^\d{2}-\d{8}-\d{1}$', cuil_cuit):
                raise ValidationError('El formato debe ser XX-XXXXXXXX-X (ej: 20-12345678-9)')
        return cuil_cuit

    def clean_fecha_inicio_actividad(self):
        """No permitir fechas de inicio de actividad en el futuro."""
        fecha = self.cleaned_data.get('fecha_inicio_actividad')
        if fecha and fecha > timezone.localdate():
            raise ValidationError('La fecha de inicio de actividad no puede ser futura.')
        return fecha
    
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


class ClasificacionForm(forms.ModelForm):
    """
    Formulario para crear y editar clasificaciones de edad.
    """
    nombre = forms.CharField(
        label='Nombre',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: ATP, +13, +16, +18',
            'required': True,
            'maxlength': '10',
            'title': 'Nombre de la clasificación (máximo 10 caracteres)'
        }),
        error_messages={
            'required': 'El nombre de la clasificación es obligatorio.',
            'max_length': 'El nombre no puede tener más de 10 caracteres.'
        }
    )
    
    descripcion = forms.CharField(
        label='Descripción',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Apta para todo público',
            'required': True,
            'maxlength': '200',
            'title': 'Descripción de la clasificación'
        }),
        error_messages={
            'required': 'La descripción es obligatoria.',
            'max_length': 'La descripción no puede tener más de 200 caracteres.'
        }
    )
    
    edad_minima = forms.IntegerField(
        label='Edad Mínima',
        min_value=0,
        max_value=99,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0',
            'required': True,
            'min': '0',
            'max': '99',
            'title': 'Edad mínima requerida (0-99 años)'
        }),
        error_messages={
            'required': 'La edad mínima es obligatoria.',
            'min_value': 'La edad mínima no puede ser negativa.',
            'max_value': 'La edad mínima no puede ser mayor a 99 años.'
        }
    )
    
    class Meta:
        model = Clasificacion
        fields = ['nombre', 'descripcion', 'edad_minima', 'activo']
        widgets = {
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }
    
    def __init__(self, *args, **kwargs):
        """
        Personalizar el formulario según si es creación o edición.
        - Si is_creation=True, se oculta el campo 'activo' (será True por defecto).
        - Si is_creation=False (edición), solo se puede modificar 'descripcion', el resto es de solo lectura.
        """
        is_creation = kwargs.pop('is_creation', False)
        super().__init__(*args, **kwargs)
        
        if is_creation:
            # En creación, eliminar el campo activo (se establecerá automáticamente en True)
            self.fields.pop('activo', None)
        else:
            # En edición, hacer solo lectura todos los campos excepto 'descripcion'
            if 'nombre' in self.fields:
                self.fields['nombre'].disabled = True
                self.fields['nombre'].widget.attrs['readonly'] = 'readonly'
            if 'edad_minima' in self.fields:
                self.fields['edad_minima'].disabled = True
                self.fields['edad_minima'].widget.attrs['readonly'] = 'readonly'
            if 'activo' in self.fields:
                self.fields['activo'].disabled = True
                self.fields['activo'].widget.attrs['readonly'] = 'readonly'
    
    def clean_nombre(self):
        """
        Validar que el nombre de la clasificación sea único (ignorando mayúsculas/minúsculas).
        """
        nombre = self.cleaned_data.get('nombre', '').strip()
        
        if not nombre:
            raise ValidationError('El nombre no puede estar vacío.')
        
        # Verificar unicidad (el modelo ya normaliza a mayúsculas en save())
        nombre_normalizado = nombre.upper()
        
        # Excluir la instancia actual en caso de edición
        qs = Clasificacion.all_objects.filter(nombre__iexact=nombre_normalizado)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError(
                f'Ya existe una clasificación con el nombre "{nombre_normalizado}".'
            )
        
        return nombre
    
    def clean(self):
        """
        Validaciones adicionales del formulario.
        """
        cleaned_data = super().clean()
        edad_minima = cleaned_data.get('edad_minima')
        nombre = cleaned_data.get('nombre')
        
        # Validar coherencia edad_minima con nombre (advertencia, no error)
        if edad_minima is not None and nombre:
            nombre_norm = nombre.upper().strip()
            if '+' in nombre_norm:
                try:
                    # Intentar extraer el número del nombre (ej: "+13" → 13)
                    edad_en_nombre = int(nombre_norm.replace('+', '').replace('A', '').strip())
                    if edad_minima != edad_en_nombre:
                        self.add_error(
                            'edad_minima',
                            f'La edad mínima ({edad_minima}) no coincide con el número en el nombre ({edad_en_nombre}).'
                        )
                except (ValueError, AttributeError):
                    pass  # Si no se puede extraer número, ignorar validación
        
        return cleaned_data


class DirectorForm(forms.ModelForm):
    """
    Formulario para editar directores desde Configuración del Cine.
    """

    class Meta:
        model = Director
        fields = ['nombre', 'apellido', 'fecha_nacimiento']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-input',
                'maxlength': 100,
                'placeholder': 'Ej: Christopher',
            }),
            'apellido': forms.TextInput(attrs={
                'class': 'form-input',
                'maxlength': 100,
                'placeholder': 'Ej: Nolan',
            }),
            'fecha_nacimiento': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
        }
        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'fecha_nacimiento': 'Fecha de nacimiento',
        }

    @staticmethod
    def _normalizar(valor):
        return ' '.join((valor or '').strip().split())

    def clean_nombre(self):
        nombre = self._normalizar(self.cleaned_data.get('nombre'))
        if not nombre:
            raise ValidationError('El nombre del director es obligatorio.')
        return nombre.title()

    def clean_apellido(self):
        apellido = self._normalizar(self.cleaned_data.get('apellido'))
        return apellido.title()

