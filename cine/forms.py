from django import forms
from .models import Pelicula, Sala, Funcion
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
    
    genero = forms.ChoiceField(
        label='🎪 Género',
        choices=[('', 'Selecciona un género...')] + Pelicula.GENERO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Debes seleccionar un género'
        }),
        error_messages={
            'required': 'Debes seleccionar un género para la película.'
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
        fields = ['titulo', 'sinopsis', 'director', 'genero', 'duracion', 'fecha_estreno', 'imagen_portada']
        
    def clean_titulo(self):
        """Validación personalizada para el título"""
        titulo = self.cleaned_data['titulo']
        if len(titulo.strip()) < 2:
            raise forms.ValidationError('El título debe tener al menos 2 caracteres.')
        return titulo.strip()
    
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
    
    capacidad = forms.IntegerField(
        label='👥 Capacidad (asientos)',
        min_value=10,
        max_value=500,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 150',
            'required': True,
            'min': '10',
            'max': '500',
            'title': 'Número total de asientos (10-500)'
        }),
        error_messages={
            'required': 'La capacidad es obligatoria.',
            'min_value': 'La capacidad mínima es de 10 asientos.',
            'max_value': 'La capacidad máxima es de 500 asientos.'
        }
    )
    
    tipo = forms.ChoiceField(
        label='🎭 Tipo de sala',
        choices=[('', 'Selecciona un tipo de sala...')] + Sala.TIPO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona el tipo de experiencia'
        }),
        error_messages={
            'required': 'Debes seleccionar un tipo de sala.'
        }
    )
    
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
        fields = ['numero', 'nombre', 'capacidad', 'tipo', 'activa', 'observaciones']

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
    
    def clean_capacidad(self):
        """Validación adicional para capacidad"""
        capacidad = self.cleaned_data['capacidad']
        if capacidad < 10:
            raise forms.ValidationError('La capacidad mínima es de 10 asientos.')
        if capacidad > 500:
            raise forms.ValidationError('La capacidad máxima es de 500 asientos.')
        return capacidad


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
    
    formato_proyeccion = forms.ChoiceField(
        label='🎞️ Formato de proyección',
        choices=Funcion.FORMATO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'title': 'Selecciona el formato en que se proyectará'
        }),
        error_messages={
            'required': 'Debes seleccionar un formato de proyección.'
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
        fields = ['pelicula', 'sala', 'fecha_hora', 'formato_proyeccion', 'precio_base']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando, actualizar el min de fecha_hora dinámicamente
        if self.instance and self.instance.pk:
            # Para ediciones, permitir mantener la fecha actual si ya está programada
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
        
        if sala and pelicula and fecha_hora:
            # Verificar que la sala esté activa
            if not sala.activa:
                raise ValidationError({
                    'sala': 'No se pueden programar funciones en salas inactivas.'
                })
            
            # Verificar solapamiento de funciones
            # Calcular fin de esta función (duración + 30 min de limpieza)
            from datetime import timedelta
            duracion_total = timedelta(minutes=pelicula.duracion + 30)
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
                duracion_otra = timedelta(minutes=funcion.pelicula.duracion + 30)
                fin_otra = funcion.fecha_hora + duracion_otra
                
                # Verificar si hay solapamiento
                if funcion.fecha_hora < fin_funcion and fecha_hora < fin_otra:
                    raise ValidationError({
                        'fecha_hora': f'Esta función se solapa con "{funcion.pelicula.titulo}" '
                                    f'programada a las {funcion.fecha_hora.strftime("%d/%m/%Y %H:%M")} en la misma sala. '
                                    f'Debe haber al menos 30 minutos de diferencia entre funciones.'
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
    
    formato_proyeccion = forms.ChoiceField(
        label='Formato de proyección',
        choices=Funcion.FORMATO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select', 'required': True,
            'title': 'Selecciona el formato en que se proyectará'
        })
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

        # Si faltan datos básicos, la validación de campos ya falló, no hacemos nada más
        if not all([sala, pelicula, fecha, horarios]):
            return cleaned_data
            
        # Verificar que la sala esté activa
        if not sala.activa:
            raise ValidationError({'sala': 'No se pueden programar funciones en salas inactivas.'})
        
        # Iterar sobre cada horario que el usuario quiere crear
        for hora_obj in horarios:
            
            # Combinar la fecha y hora propuestas
            # Usamos 'datetime.combine' para juntar el Date y el Time
            try:
                # 1. Crear el datetime "naive" (sin zona horaria)
                fecha_hora_naive = datetime.combine(fecha, hora_obj)
            
                # 2. OBTENER LA ZONA HORARIA ACTUAL
                current_tz = timezone.get_current_timezone()
            
                # 3. CONVERTIRLO A "AWARE" (con zona horaria)
                fecha_hora_propuesta = timezone.make_aware(fecha_hora_naive, current_tz)

            except Exception:
                raise ValidationError(f"No se pudo combinar la fecha y hora para {hora_obj}.")

            # Validar que no sea en el pasado
            # (Ahora ambos son "aware" y la comparación funciona)
            if fecha_hora_propuesta < timezone.now():
                raise ValidationError({'horarios': f'El horario {hora_obj.strftime("%H:%M")} del día {fecha.strftime("%d/%m")} ya pasó.'})
            # --- Lógica de solapamiento (adaptada de tu FuncionForm) ---
            
            # Calcular fin de esta función (duración + 30 min de limpieza)
            duracion_total = timedelta(minutes=pelicula.duracion + 30)
            fin_funcion_propuesta = fecha_hora_propuesta + duracion_total
            
            # [start_A, end_A] es el rango de nuestra función propuesta
            start_A = fecha_hora_propuesta
            end_A = fin_funcion_propuesta
            
            # Buscar funciones existentes (B) que se solapen
            # Un solapamiento existe si (start_A < end_B) Y (start_B < end_A)
            
            # 1. Buscamos funciones en la misma sala que empiecen ANTES de que la nuestra TERMINE
            funciones_conflictivas = Funcion.objects.filter(
                sala=sala,
                fecha_hora__lt=end_A
            )

            # 2. Revisamos cada una para ver si terminan DESPUÉS de que la nuestra EMPIECE
            for funcion_b in funciones_conflictivas:
                start_B = funcion_b.fecha_hora
                end_B = funcion_b.fecha_hora + timedelta(minutes=funcion_b.pelicula.duracion + 30)
                
                # La condición de solapamiento
                if start_B < end_A and start_A < end_B:
                    raise ValidationError({
                        'horarios': f'El horario {hora_obj.strftime("%H:%M")} se solapa con "{funcion_b.pelicula.titulo}" '
                                    f'programada de {start_B.strftime("%H:%M")} a {end_B.strftime("%H:%M")} en la misma sala.'
                                    f' (Se incluyen 30 min. de limpieza entre funciones).'
                    })

        return cleaned_data