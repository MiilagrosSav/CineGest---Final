from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        label='👤 Nombre de usuario',
        help_text='Requerido. 150 caracteres o menos. Letras, números y @/./+/-/_ solamente.',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: miusuario123',
            'required': True,
            'minlength': '3',
            'maxlength': '150',
            'pattern': '^[a-zA-Z0-9@.+_-]+$',
            'title': 'Solo letras, números y los símbolos @.+_-'
        })
    )
    email = forms.EmailField(
        label='📧 Correo electrónico',
        help_text='Requerido. Ingresa una dirección de correo válida.',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'tu@email.com',
            'required': True,
            'autocomplete': 'email'
        })
    )
    first_name = forms.CharField(
        label='👨‍💼 Nombre',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre',
            'maxlength': '150',
            'pattern': '^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\\s]+$',
            'title': 'Solo letras y espacios'
        })
    )
    last_name = forms.CharField(
        label='👥 Apellidos',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tus apellidos',
            'maxlength': '150',
            'pattern': '^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\\s]+$',
            'title': 'Solo letras y espacios'
        })
    )
    password1 = forms.CharField(
        label='🔒 Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Mínimo 8 caracteres',
            'required': True,
            'minlength': '8',
            'autocomplete': 'new-password'
        }),
        help_text='Tu contraseña debe tener al menos 8 caracteres y no puede ser completamente numérica.'
    )
    password2 = forms.CharField(
        label='🔐 Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Repite tu contraseña',
            'required': True,
            'minlength': '8',
            'autocomplete': 'new-password'
        }),
        help_text='Ingresa la misma contraseña que antes, para verificación.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='👤 Usuario',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre de usuario',
            'autofocus': True,
            'required': True,
            'minlength': '1',
            'maxlength': '254',
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
            'minlength': '1',
            'autocomplete': 'current-password'
        })
    )
    
    error_messages = {
        'invalid_login': 'Por favor, ingrese un nombre de usuario y contraseña correctos.',
        'inactive': 'Esta cuenta está inactiva.',
    }
from django import forms

class LoginForm(forms.Form):
    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

class EmployeeCreationForm(UserCreationForm):
    """Formulario para que los administradores creen usuarios empleados"""
    username = forms.CharField(
        label='👨‍💼 Nombre de usuario',
        help_text='Requerido. 150 caracteres o menos. Letras, números y @/./+/-/_ solamente.',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: empleado.juan',
            'required': True,
            'minlength': '3',
            'maxlength': '150',
            'pattern': '^[a-zA-Z0-9@.+_-]+$',
            'title': 'Solo letras, números y los símbolos @.+_-'
        })
    )
    email = forms.EmailField(
        label='📧 Correo electrónico',
        help_text='Requerido. Ingresa una dirección de correo válida.',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'empleado@cinegest.com',
            'required': True,
            'autocomplete': 'email'
        })
    )
    first_name = forms.CharField(
        label='👤 Nombre',
        max_length=150,
        required=True,
        help_text='Nombre del empleado.',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Juan Carlos',
            'required': True,
            'maxlength': '150',
            'pattern': '^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\\s]+$',
            'title': 'Solo letras y espacios'
        })
    )
    last_name = forms.CharField(
        label='👥 Apellidos',
        max_length=150,
        required=True,
        help_text='Apellidos del empleado.',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Pérez González',
            'required': True,
            'maxlength': '150',
            'pattern': '^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\\s]+$',
            'title': 'Solo letras y espacios'
        })
    )
    password1 = forms.CharField(
        label='🔒 Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Mínimo 8 caracteres',
            'required': True,
            'minlength': '8',
            'autocomplete': 'new-password'
        }),
        help_text='La contraseña debe tener al menos 8 caracteres.'
    )
    password2 = forms.CharField(
        label='🔐 Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Repite la contraseña',
            'required': True,
            'minlength': '8',
            'autocomplete': 'new-password'
        }),
        help_text='Ingresa la misma contraseña que antes, para verificación.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')