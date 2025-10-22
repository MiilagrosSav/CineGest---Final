from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import transaction
from .models import Usuario, Cliente, Empleado

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
    # Campos del perfil Empleado
    cargo = forms.CharField(
        label='📋 Cargo', 
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: Vendedor'})
    )
    fecha_ingreso = forms.DateField(
        label='🗓️ Fecha de Ingreso', 
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name') # Campos del Usuario

    @transaction.atomic
    def save(self, commit=True):
        # 1. Guarda el objeto Usuario
        user = super().save(commit=False)
        user.rol = 'empleado' # Asigna el rol de empleado
        user.is_staff = False # Los empleados no entran al admin
        
        if commit:
            user.save()
            
        # 2. Crea y guarda el objeto Empleado enlazado
        empleado = Empleado(
            usuario=user,
            cargo=self.cleaned_data.get('cargo'),
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
