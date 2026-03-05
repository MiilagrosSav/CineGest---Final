from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import transaction
from django.core.validators import RegexValidator
from .models import Usuario, Cliente, Empleado
from ventas.models import PoliticaReembolso
from datetime import date

# Validador de DNI (7-8 dígitos numéricos)
DNI_VALIDATOR = RegexValidator(
    regex=r'^\d{7,8}$',
    message='El DNI debe contener entre 7 y 8 dígitos numéricos, sin letras ni espacios.'
)

# Validador de Teléfono (7-15 dígitos)
TELEFONO_VALIDATOR = RegexValidator(
    regex=r'^\+?\d{7,15}$',
    message='El teléfono debe contener entre 7 y 15 dígitos numéricos. Puede incluir + al inicio.',
    code='telefono_invalido'
)

# --- Formulario de Registro de Clientes ---
class CustomUserCreationForm(UserCreationForm):
    # Campos del perfil Cliente
    acepta_marketing = forms.BooleanField(
        label='Deseo recibir novedades y promociones exclusivas',
        required=False,
        help_text='Te enviaremos promociones y novedades por correo. Puedes darte de baja en cualquier momento desde tu perfil.',
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    fecha_nacimiento = forms.DateField(
        label='Fecha de Nacimiento', 
        required=False, 
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    
    # Campos del Usuario (puedes añadir dni, telefono si quieres pedirlos en el registro)
    dni = forms.CharField(
        label='DNI', 
        max_length=8, 
        required=False, 
        validators=[DNI_VALIDATOR],
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: 12345678'})
    )
    telefono = forms.CharField(
        label='Teléfono', 
        max_length=20, 
        required=False,
        validators=[TELEFONO_VALIDATOR],
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+54 9 11 1234-5678'})
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'dni', 'telefono', 'acepta_marketing') # Campos del Usuario

    def clean_username(self):
        """Validación personalizada para username único (considerando normalización a minúsculas)"""
        username = self.cleaned_data.get('username')
        if username:
            # Normalizar a minúsculas como lo hace el modelo
            username_normalizado = username.strip().lower()
            if Usuario.objects.filter(username=username_normalizado).exists():
                raise forms.ValidationError('Ya existe un usuario con este nombre de usuario.')
            return username
        return username

    def clean_email(self):
        """Validación personalizada para email único"""
        email = self.cleaned_data['email']
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe un usuario con este email.')
        return email

    def clean_dni(self):
        """Validación personalizada para DNI único"""
        dni = self.cleaned_data.get('dni')
        if dni and Usuario.objects.filter(dni=dni).exists():
            raise forms.ValidationError('Ya existe un usuario con este DNI.')
        return dni

    def clean_fecha_nacimiento(self):
        """Validación personalizada para fecha de nacimiento"""
        fecha_nac = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nac:
            if fecha_nac > date.today():
                raise forms.ValidationError('La fecha de nacimiento no puede ser posterior al día de hoy.')
            if fecha_nac < date(1900, 1, 1):
                raise forms.ValidationError('La fecha de nacimiento no puede ser anterior al 1 de enero de 1900.')
        return fecha_nac

    @transaction.atomic # Asegura que o se crean los dos (Usuario y Cliente) o ninguno
    def save(self, commit=True):
        # 1. Guarda el objeto Usuario
        user = super().save(commit=False) # No guarda en BD todavía
        user.rol = 'cliente' # Asigna el rol de cliente
        user.is_staff = False
        
        # 2. Guarda los campos extra del Usuario
        user.dni = self.cleaned_data.get('dni')
        user.telefono = self.cleaned_data.get('telefono')
        
        if commit:
            user.save() # Ahora sí, guarda el Usuario
        
        # 3. Crea y guarda el objeto Cliente enlazado
        cliente = Cliente(
            usuario=user,
            acepta_marketing=bool(self.cleaned_data.get('acepta_marketing', False)),
            fecha_nacimiento=self.cleaned_data.get('fecha_nacimiento')
        )
        if commit:
            cliente.save()
            
        return user

# --- Formulario de Creación de Empleados (para Admins) ---
class EmployeeCreationForm(UserCreationForm):
    # Campos adicionales del Usuario
    dni = forms.CharField(
        label='🆔 DNI',
        max_length=8,
        required=True,
        validators=[DNI_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 12345678'
        })
    )
    
    telefono = forms.CharField(
        label='📱 Teléfono',
        max_length=20,
        required=False,
        validators=[TELEFONO_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: +54 9 11 1234-5678'
        })
    )
    
    # Campos del perfil Empleado
    fecha_ingreso = forms.DateField(
        label='🗓️ Fecha de Ingreso', 
        initial=date.today(),  # Valor por defecto: fecha de hoy
        input_formats=['%Y-%m-%d'],  # Acepta formato ISO (YYYY-MM-DD)
        widget=forms.DateInput(
            format='%Y-%m-%d',  # Renderiza en formato ISO para HTML5
            attrs={
                'class': 'form-input',
                'type': 'date',
                'max': date.today().isoformat()  # Bloquea fechas futuras en el calendario del navegador
            }
        ),
        help_text='La fecha de ingreso no puede ser posterior al día de hoy.'
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'dni', 'telefono')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agregar clase form-input a todos los campos heredados
        for field_name in self.fields:
            if field_name not in ['dni', 'telefono', 'fecha_ingreso']:
                self.fields[field_name].widget.attrs['class'] = 'form-input'
        
        # Personalizar labels y placeholders
        self.fields['username'].label = 'Nombre de usuario'
        self.fields['username'].widget.attrs['placeholder'] = 'Ej: jperez'
        
        self.fields['email'].label = 'Email'
        self.fields['email'].widget.attrs['placeholder'] = 'Ej: empleado@cinegest.com'
        
        self.fields['first_name'].label = 'Nombre*'
        self.fields['first_name'].widget.attrs['placeholder'] = 'Ej: Juan'
        
        self.fields['last_name'].label = 'Apellido*'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Ej: Pérez'
        
        self.fields['password1'].label = 'Contraseña'
        self.fields['password1'].widget.attrs['placeholder'] = '••••••••'
        
        self.fields['password2'].label = 'Confirmar contraseña'
        self.fields['password2'].widget.attrs['placeholder'] = '••••••••'

    def clean_username(self):
        """Validar que el username sea único (considerando normalización a minúsculas)"""
        username = self.cleaned_data.get('username')
        if username:
            # Normalizar a minúsculas como lo hace el modelo
            username_normalizado = username.strip().lower()
            if Usuario.objects.filter(username=username_normalizado).exists():
                raise forms.ValidationError('Ya existe un usuario con este nombre de usuario.')
            return username
        return username

    def clean_dni(self):
        """Validar que el DNI sea único"""
        dni = self.cleaned_data['dni']
        if Usuario.objects.filter(dni=dni).exists():
            raise forms.ValidationError('Ya existe un usuario con este DNI.')
        return dni

    def clean_email(self):
        """Validar que el email sea único"""
        email = self.cleaned_data.get('email')
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe un usuario con este email.')
        return email

    def clean_fecha_ingreso(self):
        """
        Validación personalizada para fecha_ingreso.
        Verificar que no sea posterior al día de hoy.
        """
        fecha_ingreso = self.cleaned_data.get('fecha_ingreso')
        if fecha_ingreso and fecha_ingreso > date.today():
            raise forms.ValidationError(
                'La fecha de ingreso no puede ser posterior al día de hoy.'
            )
        return fecha_ingreso

    @transaction.atomic
    def save(self, commit=True):
        # 1. Guarda el objeto Usuario
        user = super().save(commit=False)
        user.rol = 'empleado' # Asigna el rol de empleado
        user.is_staff = False # Los empleados no entran al admin
        user.dni = self.cleaned_data.get('dni')
        user.telefono = self.cleaned_data.get('telefono')
        
        if commit:
            user.save()
            
        # 2. Crea y guarda el objeto Empleado enlazado
        empleado = Empleado(
            usuario=user,
            fecha_ingreso=self.cleaned_data.get('fecha_ingreso')
        )
        if commit:
            empleado.save()
            
        return user

# --- Formulario de Login (Sin cambios, estaba bien) ---
class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='👤 Usuario',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre de usuario',
            'autofocus': True,
            'required': True,
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        label='🔒 Contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu contraseña secreta',
            'required': True,
            'autocomplete': 'current-password'
        })
    )
    
    error_messages = {
        'invalid_login': 'Por favor, ingrese un nombre de usuario y contraseña correctos.',
        'inactive': 'Esta cuenta está inactiva.',
    }


# --- Formulario de Edición de Empleados ---
class EmployeeUpdateForm(forms.ModelForm):
    """
    Formulario para editar empleados existentes
    """
    password1 = forms.CharField(
        label='Contraseña nueva',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Dejar en blanco para no cambiar'
        })
    )
    password2 = forms.CharField(
        label='Confirmar contraseña nueva',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Reingresá la contraseña'
        })
    )
    class Meta:
        model = Usuario
        fields = ['username', 'email', 'first_name', 'last_name', 'dni', 'telefono', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nombre de usuario'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Email'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Apellidos'
            }),
            'dni': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'DNI (7-8 dígitos)'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Teléfono'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }
        labels = {
            'username': '👤 Nombre de usuario',
            'email': '📧 Email',
            'first_name': '📝 Nombre',
            'last_name': '📝 Apellidos',
            'dni': '🆔 DNI',
            'telefono': '📱 Teléfono',
            'is_active': '✅ Usuario activo'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dni'].validators = [DNI_VALIDATOR]
        self.fields['dni'].max_length = 8
        self.fields['telefono'].validators = [TELEFONO_VALIDATOR]

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('password1')
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user

# --- Formulario para Politica de Reembolso (Admin) ---
class PoliticaReembolsoForm(forms.ModelForm):
    
    nombre = forms.CharField(
        label='📝 Nombre de la Política',
        max_length=140,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: Política de Intercambio 2025',
            'required': True
        })
    )
    
    activo = forms.BooleanField(
        label='🟢 Política activa',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Si está activa, esta política permite intercambios. Solo una política puede estar activa a la vez.'
    )
    
    dias_antes_minimo = forms.IntegerField(
        label='📅 Días mínimos antes del evento',
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '1',
            'required': True,
            'min': '0'
        }),
        help_text='Número mínimo de días de anticipación requeridos para realizar un intercambio.'
    )
    
    max_cambios_por_compra = forms.IntegerField(
        label='🔄 Máximo de cambios por compra',
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '1',
            'required': True,
            'min': '0'
        }),
        help_text='Número máximo de intercambios permitidos por compra (0 = ilimitado).'
    )
    
    activo = forms.BooleanField(
        label='🟢 Política activa',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Si está activa, esta política permite intercambios. Solo una política puede estar activa a la vez.'
    )
    
    class Meta:
        model = PoliticaReembolso
        fields = ['nombre', 'activo', 'dias_antes_minimo', 'max_cambios_por_compra']


# --- Formulario para Editar Perfil de Cliente ---
class ClienteProfileForm(forms.ModelForm):
    """Formulario para que clientes editen su perfil"""
    first_name = forms.CharField(
        label='Nombre',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre'
        })
    )
    last_name = forms.CharField(
        label='Apellido',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu apellido'
        })
    )
    email = forms.EmailField(
        label='Email',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'tu@email.com'
        })
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=False,
        validators=[TELEFONO_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+54 9 11 1234-5678'
        })
    )
    dni = forms.CharField(
        label='DNI',
        max_length=8,
        required=False,
        validators=[DNI_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '12345678'
        })
    )
    fecha_nacimiento = forms.DateField(
        label='Fecha de Nacimiento',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
            'min': '1900-01-01',
            'max': date.today().isoformat()
        }),
        help_text='Debe ser una fecha entre el 1/1/1900 y hoy'
    )
    acepta_marketing = forms.BooleanField(
        label='Deseo recibir novedades y promociones',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Cliente
        fields = ['fecha_nacimiento', 'acepta_marketing']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicializar campos del usuario
        if self.instance and self.instance.usuario:
            self.fields['first_name'].initial = self.instance.usuario.first_name
            self.fields['last_name'].initial = self.instance.usuario.last_name
            self.fields['email'].initial = self.instance.usuario.email
            self.fields['telefono'].initial = self.instance.usuario.telefono
            self.fields['dni'].initial = self.instance.usuario.dni
    
    def clean_email(self):
        email = self.cleaned_data['email']
        # Verificar que el email no esté en uso por otro usuario
        if Usuario.objects.filter(email=email).exclude(pk=self.instance.usuario.pk).exists():
            raise forms.ValidationError('Este email ya está en uso.')
        return email
    
    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if dni and Usuario.objects.filter(dni=dni).exclude(pk=self.instance.usuario.pk).exists():
            raise forms.ValidationError('Este DNI ya está en uso.')
        return dni

    def clean_fecha_nacimiento(self):
        """Validación personalizada para fecha de nacimiento"""
        fecha_nac = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nac:
            if fecha_nac > date.today():
                raise forms.ValidationError('La fecha de nacimiento no puede ser posterior al día de hoy.')
            if fecha_nac < date(1900, 1, 1):
                raise forms.ValidationError('La fecha de nacimiento no puede ser anterior al 1 de enero de 1900.')
        return fecha_nac
    
    @transaction.atomic
    def save(self, commit=True):
        # Actualizar datos del usuario
        usuario = self.instance.usuario
        usuario.first_name = self.cleaned_data['first_name']
        usuario.last_name = self.cleaned_data['last_name']
        usuario.email = self.cleaned_data['email']
        usuario.telefono = self.cleaned_data.get('telefono', '')
        usuario.dni = self.cleaned_data.get('dni', '')
        if commit:
            usuario.save()
        
        # Actualizar datos del cliente
        cliente = super().save(commit=False)
        if commit:
            cliente.save()
        return cliente


# --- Formulario para Editar Perfil de Administrador ---
class AdminProfileForm(forms.ModelForm):
    """Formulario para que administradores editen su perfil"""
    first_name = forms.CharField(
        label='Nombre',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre'
        })
    )
    last_name = forms.CharField(
        label='Apellido',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu apellido'
        })
    )
    email = forms.EmailField(
        label='Email',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'admin@cinegest.com'
        })
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=False,
        validators=[TELEFONO_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+54 9 11 1234-5678'
        })
    )
    dni = forms.CharField(
        label='DNI',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '12345678'
        })
    )
    
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'dni']
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este email ya está en uso.')
        return email
    
    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if dni and Usuario.objects.filter(dni=dni).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este DNI ya está en uso.')
        return dni
