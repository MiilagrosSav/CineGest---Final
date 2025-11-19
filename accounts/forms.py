from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import transaction
from .models import Usuario, Cliente, Empleado
from ventas.models import PoliticaReembolso

# --- Formulario de Registro de Clientes ---
class CustomUserCreationForm(UserCreationForm):
    # Campos del perfil Cliente
    direccion = forms.CharField(
        label='🏠 Dirección', 
        max_length=255, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tu dirección'})
    )
    fecha_nacimiento = forms.DateField(
        label='🎂 Fecha de Nacimiento', 
        required=False, 
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    
    # Campos del Usuario (puedes añadir dni, telefono si quieres pedirlos en el registro)
    dni = forms.CharField(label='DNI', max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tu DNI'}))
    telefono = forms.CharField(label='Teléfono', max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tu teléfono'}))

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'dni', 'telefono') # Campos del Usuario

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
            direccion=self.cleaned_data.get('direccion'),
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
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 12345678'
        })
    )
    
    telefono = forms.CharField(
        label='📱 Teléfono',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: +54 9 11 1234-5678'
        })
    )
    
    # Campos del perfil Empleado
    fecha_ingreso = forms.DateField(
        label='🗓️ Fecha de Ingreso', 
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date'
        })
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
        self.fields['username'].label = '👤 Nombre de usuario'
        self.fields['username'].widget.attrs['placeholder'] = 'Ej: jperez'
        
        self.fields['email'].label = '📧 Email address'
        self.fields['email'].widget.attrs['placeholder'] = 'Ej: empleado@cinegest.com'
        
        self.fields['first_name'].label = '📝 Nombre'
        self.fields['first_name'].widget.attrs['placeholder'] = 'Ej: Juan'
        
        self.fields['last_name'].label = '📝 Apellidos'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Ej: Pérez'
        
        self.fields['password1'].label = '🔒 Contraseña'
        self.fields['password1'].widget.attrs['placeholder'] = '••••••••'
        
        self.fields['password2'].label = '🔒 Confirmar contraseña'
        self.fields['password2'].widget.attrs['placeholder'] = '••••••••'

    def clean_dni(self):
        """Validar que el DNI sea único"""
        dni = self.cleaned_data['dni']
        if Usuario.objects.filter(dni=dni).exists():
            raise forms.ValidationError('Ya existe un usuario con este DNI.')
        return dni

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
                'placeholder': 'DNI'
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

# --- Formulario para Politica de Reembolso (Admin) ---
class PoliticaReembolsoForm(forms.ModelForm):
    class Meta:
        model = PoliticaReembolso
        fields = ['nombre', 'permitir_intercambio', 'dias_antes_minimo', 'penalidad_percent', 'max_cambios_por_compra', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'permitir_intercambio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dias_antes_minimo': forms.NumberInput(attrs={'class': 'form-control'}),
            'penalidad_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_cambios_por_compra': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre de la Política',
            'permitir_intercambio': 'Permitir intercambio',
            'dias_antes_minimo': 'Días mínimos antes del evento',
            'penalidad_percent': 'Penalidad (%)',
            'max_cambios_por_compra': 'Máximo de cambios por compra (0 = ilimitado)',
            'activo': 'Activa',
        }
