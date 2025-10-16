from django import forms
from .models import Pelicula, Sala

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
            'title': 'La fecha de estreno es obligatoria'
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
    
    precio_base = forms.DecimalField(
        label='💰 Precio base',
        min_value=0.01,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 1200.00',
            'required': True,
            'min': '0.01',
            'step': '0.01',
            'title': 'Precio base de entrada'
        }),
        error_messages={
            'required': 'El precio base es obligatorio.',
            'min_value': 'El precio debe ser mayor a 0.'
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
        fields = ['numero', 'nombre', 'capacidad', 'tipo', 'precio_base', 'activa', 'observaciones']

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