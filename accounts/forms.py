from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, PasswordResetForm
from django.db import transaction
from .models import Usuario, Cliente, Empleado, DNI_VALIDATOR, TELEFONO_VALIDATOR, USERNAME_ALPHANUMERIC_VALIDATOR, NOMBRE_VALIDATOR
from ventas.models import PoliticaReembolso
from datetime import date
from django.core.exceptions import ValidationError

# ==================== VALIDADORES PERSONALIZADOS ====================

def validar_password_minimo(password):
    """Validador para asegurar que la contraseña tenga mínimo 8 caracteres"""
    if len(password) < 8:
        raise ValidationError(
            'La contraseña debe tener un mínimo de 8 caracteres.',
            code='password_too_short'
        )


def validar_nombre_sin_numeros(nombre):
    """Validador para asegurar que el nombre no contenga números"""
    if any(char.isdigit() for char in nombre):
        raise ValidationError(
            'El nombre no puede contener números.',
            code='nombre_con_numeros'
        )


# ==================== FORMULARIOS ====================
class CustomPasswordResetForm(PasswordResetForm):
    """
    Permite reset para usuarios activos con cuenta Google aunque no tengan password usable.
    """

    def get_users(self, email):
        email = email.strip().lower()
        qs = Usuario.all_objects.filter(email__iexact=email, is_active=True)
        for user in qs:
            if user.has_usable_password() or user.is_google_user:
                yield user


class CustomUserCreationForm(UserCreationForm):
    # Campo marketing del perfil Cliente
    acepta_marketing = forms.BooleanField(
        label='Deseo recibir novedades y promociones exclusivas',
        required=False,
        help_text='Te enviaremos promociones y novedades por correo. Puedes darte de baja en cualquier momento desde tu perfil.',
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'acepta_marketing')

    def clean_username(self):
        """Valida que el username sea alfanumérico y único."""
        username = self.cleaned_data.get('username')
        if username:
            username_normalizado = username.strip().lower()
            # Validar caracteres alfanuméricos
            if not username_normalizado.isalnum():
                raise forms.ValidationError('El nombre de usuario solo puede contener letras y números.')
            if Usuario.objects.filter(username=username_normalizado).exists():
                raise forms.ValidationError('Ya existe un usuario con este nombre de usuario.')
            return username
        return username

    def clean_first_name(self):
        """Valida que el first_name no contenga números"""
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError('El nombre es requerido.')
        validar_nombre_sin_numeros(first_name)
        return first_name

    def clean_last_name(self):
        """Valida que el last_name no contenga números"""
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError('El apellido es requerido.')
        validar_nombre_sin_numeros(last_name)
        return last_name

    def clean_password1(self):
        """Valida que la contraseña tenga mínimo 8 caracteres"""
        password1 = self.cleaned_data.get('password1', '')
        validar_password_minimo(password1)
        return password1

    def clean_email(self):
        """Validación personalizada para email único, considerando baja lógica"""
        email = self.cleaned_data['email'].strip().lower()
        
        # Buscar en todos los usuarios (activos e inactivos)
        usuario_existente = Usuario.all_objects.filter(email=email).first()
        
        if usuario_existente:
            # Si el usuario existe pero está inactivo (baja lógica)
            if not usuario_existente.is_active:
                raise forms.ValidationError(
                    'Este email fue dado de baja. Por favor contacta al soporte para reactivar tu cuenta o usa otro email.'
                )
            # Si el usuario está activo, no permitir el registro
            raise forms.ValidationError('Ya existe un usuario con este email.')
        
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.rol = 'cliente'
        user.is_staff = False
        if commit:
            user.save()
        cliente = Cliente(
            usuario=user,
            acepta_marketing=bool(self.cleaned_data.get('acepta_marketing', False)),
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
        input_formats=['%Y-%m-%d'],  # Acepta formato ISO (YYYY-MM-DD)
        widget=forms.DateInput(
            format='%Y-%m-%d',  # Renderiza en formato ISO para HTML5
            attrs={
                'class': 'form-input',
                'type': 'date',
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

        # Establecer 'hoy' en tiempo de instanciación (no de importación)
        today = date.today()
        self.fields['fecha_ingreso'].initial = today
        self.fields['fecha_ingreso'].widget.attrs['max'] = today.isoformat()

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

    def clean_first_name(self):
        """Valida que el first_name no contenga números"""
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError('El nombre es requerido.')
        validar_nombre_sin_numeros(first_name)
        return first_name

    def clean_last_name(self):
        """Valida que el last_name no contenga números"""
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError('El apellido es requerido.')
        validar_nombre_sin_numeros(last_name)
        return last_name

    def clean_password1(self):
        """Valida que la contraseña tenga mínimo 8 caracteres"""
        password1 = self.cleaned_data.get('password1', '')
        validar_password_minimo(password1)
        return password1

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

# --- Formulario de Login: acepta Username o Email ---
class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario o Email',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu usuario o email',
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


# --- Formulario de Cambio de Contraseña Personalizado ---
class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Formulario para cambio de contraseña con validación de longitud mínima.
    Compatible con usuarios de Google (MAILCREAB).
    """
    
    new_password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Mínimo 8 caracteres',
            'autocomplete': 'new-password',
            'minlength': '8'
        }),
        strip=False,
        help_text='Mínimo 8 caracteres.'
    )
    
    new_password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirma tu nueva contraseña',
            'autocomplete': 'new-password',
            'minlength': '8'
        }),
        strip=False,
    )
    
    old_password = forms.CharField(
        label='Contraseña actual',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu contraseña actual',
            'autocomplete': 'current-password'
        }),
        strip=False,
    )
    
    def clean_new_password1(self):
        """Valida que la nueva contraseña tenga mínimo 8 caracteres"""
        password = self.cleaned_data.get('new_password1')
        if password:
            validar_password_minimo(password)
        return password
    
    def clean_new_password2(self):
        """Valida que la confirmación coincida con la nueva contraseña"""
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    'Las contraseñas no coinciden.',
                    code='password_mismatch'
                )
        return password2


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

    def clean_first_name(self):
        """Valida que el first_name no contenga números"""
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError('El nombre es requerido.')
        validar_nombre_sin_numeros(first_name)
        return first_name

    def clean_last_name(self):
        """Valida que el last_name no contenga números"""
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError('El apellido es requerido.')
        validar_nombre_sin_numeros(last_name)
        return last_name

    def clean_password1(self):
        """Valida que la contraseña tenga mínimo 8 caracteres (si se proporciona)"""
        password1 = self.cleaned_data.get('password1')
        if password1:  # Solo validar si se proporciona una contraseña
            validar_password_minimo(password1)
        return password1

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
    DECISION_MANTENER_ACTUAL = 'mantener_actual'
    DECISION_ACTIVAR_NUEVA = 'activar_nueva'

    
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

    ofrecer_promos_vinculo = forms.BooleanField(
        label='🎯 Ofrecer promociones de vínculo específico',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Si está activo, al elegir la nueva función en un intercambio se pueden aplicar promociones de vínculo específico.'
    )

    permitir_reintercambio = forms.BooleanField(
        label='🔁 Permitir reintercambio',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Permite volver a intercambiar una compra que ya tuvo un intercambio previo.'
    )

    permitir_con_cupon_promocion = forms.BooleanField(
        label='🎟️ Permitir intercambio con cupón/promoción',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Si está activo, las compras hechas con cupón o promociones especiales también pueden intercambiarse.'
    )

    decision_politica_activa = forms.ChoiceField(
        label='⚖️ Política activa a mantener',
        required=False,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        choices=[
            (DECISION_MANTENER_ACTUAL, 'Mantener activa la política actual y crear esta nueva como inactiva'),
            (DECISION_ACTIVAR_NUEVA, 'Activar esta nueva política y desactivar la política actual'),
        ],
        help_text='Ya existe una política activa. Debes elegir cuál quedará activa.'
    )

    class Meta:
        model = PoliticaReembolso
        fields = [
            'nombre',
            'activo',
            'dias_antes_minimo',
            'max_cambios_por_compra',
            'ofrecer_promos_vinculo',
            'permitir_reintercambio',
            'permitir_con_cupon_promocion',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._es_creacion = not bool(self.instance and self.instance.pk)
        self._politica_activa_existente = PoliticaReembolso.all_objects.filter(activo=True).exclude(
            pk=getattr(self.instance, 'pk', None)
        ).first()

        if self._es_creacion:
            # El campo "activo" solo se muestra al modificar.
            self.fields.pop('activo', None)
            if not self._politica_activa_existente:
                self.fields.pop('decision_politica_activa', None)
            else:
                self.fields['decision_politica_activa'].help_text = (
                    f'Actualmente está activa: "{self._politica_activa_existente.nombre}". '
                    'Selecciona cuál política debe mantenerse activa.'
                )
        else:
            self.fields.pop('decision_politica_activa', None)

    def clean(self):
        cleaned_data = super().clean()
        if self._es_creacion and self._politica_activa_existente:
            decision = cleaned_data.get('decision_politica_activa')
            if not decision:
                raise forms.ValidationError(
                    'Ya existe una política activa. Debes indicar cuál política quieres mantener activa.'
                )
        return cleaned_data

    def save(self, commit=True):
        instancia = super().save(commit=False)

        with transaction.atomic():
            if self._es_creacion:
                if self._politica_activa_existente:
                    decision = self.cleaned_data.get('decision_politica_activa')
                    if decision == self.DECISION_MANTENER_ACTUAL:
                        instancia.activo = False
                    else:
                        PoliticaReembolso.all_objects.filter(activo=True).update(activo=False)
                        instancia.activo = True
                else:
                    # Si no hay política previa, la nueva queda activa automáticamente.
                    instancia.activo = True
            else:
                # Si se marca activa en edición, desactivar cualquier otra.
                if self.cleaned_data.get('activo'):
                    PoliticaReembolso.all_objects.filter(activo=True).exclude(pk=instancia.pk).update(activo=False)

            if commit:
                instancia.save()
                self.save_m2m()

        return instancia


# --- Formulario para Editar Perfil de Cliente ---
class ClienteProfileForm(forms.ModelForm):
    """
    Formulario para que clientes editen su perfil.
    - Si el usuario vino por Google: email, first_name, last_name son read-only.
    - Si el usuario de Google ya completó el modal (es_perfil_completo), username también es read-only.
    """
    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        required=False,
        validators=[USERNAME_ALPHANUMERIC_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Solo letras y números'
        }),
        help_text='Solo letras y números, sin espacios. Ej: juan123'
    )
    first_name = forms.CharField(
        label='Nombre',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tu nombre'})
    )
    last_name = forms.CharField(
        label='Apellido',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tu apellido'})
    )
    email = forms.EmailField(
        label='Email',
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'tu@email.com'})
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=False,
        validators=[TELEFONO_VALIDATOR],
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+54 9 11 1234-5678'})
    )
    dni = forms.CharField(
        label='DNI',
        max_length=8,
        required=False,
        validators=[DNI_VALIDATOR],
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '12345678'})
    )
    acepta_marketing = forms.BooleanField(
        label='Deseo recibir novedades y promociones',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Cliente
        fields = ['acepta_marketing']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.usuario:
            usuario = self.instance.usuario
            self.fields['username'].initial = usuario.username
            self.fields['first_name'].initial = usuario.first_name
            self.fields['last_name'].initial = usuario.last_name
            self.fields['email'].initial = usuario.email
            self.fields['telefono'].initial = usuario.telefono
            self.fields['dni'].initial = usuario.dni

            # Bloquear campos para usuarios de Google
            if usuario.is_google_user:
                for campo in ('email', 'first_name', 'last_name'):
                    self.fields[campo].widget.attrs['readonly'] = True
                    self.fields[campo].widget.attrs['class'] = 'form-input readonly-field'
                    self.fields[campo].help_text = 'Campo gestionado por Google, no editable.'

                # Username bloqueado si el perfil ya está completo
                if usuario.es_perfil_completo:
                    self.fields['username'].widget.attrs['readonly'] = True
                    self.fields['username'].widget.attrs['class'] = 'form-input readonly-field'
                    self.fields['username'].help_text = 'Nombre de usuario fijado al completar el perfil.'

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            return self.instance.usuario.username if self.instance else username
        username_norm = username.strip().lower()
        if not username_norm.isalnum():
            raise forms.ValidationError('Solo letras y números, sin espacios.')
        if Usuario.objects.filter(username=username_norm).exclude(pk=self.instance.usuario.pk).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        usuario = self.instance.usuario
        # Si es Google user, preservar email original (no editable)
        if usuario.is_google_user:
            return usuario.email
        # Validar contra usuarios activos e inactivos (baja lógica)
        usuario_existente = Usuario.all_objects.filter(email=email).exclude(pk=usuario.pk).first()
        if usuario_existente:
            if not usuario_existente.is_active:
                raise forms.ValidationError(
                    'Este email fue dado de baja. Por favor contacta al soporte para reactivar tu cuenta o usa otro email.'
                )
            raise forms.ValidationError('Este email ya está en uso.')
        return email

    def clean_first_name(self):
        """Valida que el first_name no contenga números, respetando usuarios de Google"""
        first_name = self.cleaned_data.get('first_name')
        if self.instance.usuario.is_google_user:
            return self.instance.usuario.first_name
        if not first_name:
            raise forms.ValidationError('El nombre es requerido.')
        validar_nombre_sin_numeros(first_name)
        return first_name

    def clean_last_name(self):
        """Valida que el last_name no contenga números, respetando usuarios de Google"""
        last_name = self.cleaned_data.get('last_name')
        if self.instance.usuario.is_google_user:
            return self.instance.usuario.last_name
        if not last_name:
            raise forms.ValidationError('El apellido es requerido.')
        validar_nombre_sin_numeros(last_name)
        return last_name

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if not dni:
            return dni
        if Usuario.objects.filter(dni=dni).exclude(pk=self.instance.usuario.pk).exists():
            raise forms.ValidationError('Este DNI ya está en uso.')
        return dni

    @transaction.atomic
    def save(self, commit=True):
        usuario = self.instance.usuario
        usuario.first_name = self.cleaned_data['first_name']
        usuario.last_name = self.cleaned_data['last_name']
        usuario.email = self.cleaned_data['email']
        usuario.telefono = self.cleaned_data.get('telefono') or ''
        usuario.dni = self.cleaned_data.get('dni') or None
        # Actualizar username solo si no es Google con perfil completo
        new_username = self.cleaned_data.get('username')
        if new_username and not (usuario.is_google_user and usuario.es_perfil_completo):
            usuario.username = new_username.strip().lower()
        if commit:
            usuario.save()
        cliente = super().save(commit=False)
        if commit:
            cliente.save()
        return cliente


# --- Formulario del Modal de Completar Perfil (solo Google users) ---
class CompletarPerfilGoogleForm(forms.Form):
    """Formulario del modal obligatorio para usuarios de Google."""
    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        required=False,
        validators=[USERNAME_ALPHANUMERIC_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Solo letras y números. Ej: juan123',
            'id': 'id_modal_username',
            'autocomplete': 'off'
        }),
        help_text='Opcional. Solo letras y números.'
    )
    dni = forms.CharField(
        label='DNI',
        max_length=8,
        required=True,
        validators=[DNI_VALIDATOR],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 12345678',
            'id': 'id_modal_dni'
        })
    )
    email = forms.EmailField(
        label='Correo de contacto',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'tu@email.com',
            'id': 'id_modal_email',
            'autocomplete': 'email'
        }),
        help_text='Podés corregirlo si querés recibir novedades en otra dirección.'
    )
    acepta_marketing = forms.BooleanField(
        label='Acepto recibir promociones/notificaciones por cupones',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_modal_marketing'
        }),
        error_messages={
            'required': 'Debes aceptar promociones/notificaciones para recibir cupones.'
        }
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user:
            self.fields['username'].initial = user.username
            self.fields['email'].initial = user.email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            # Mantener el existente si no se proporciona uno
            return self._user.username if self._user else ''
        username_norm = username.strip().lower()
        if not username_norm.isalnum():
            raise forms.ValidationError('Solo letras y números, sin espacios.')
        qs = Usuario.objects.filter(username=username_norm)
        if self._user:
            qs = qs.exclude(pk=self._user.pk)
        if qs.exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if dni:
            qs = Usuario.objects.filter(dni=dni)
            if self._user:
                qs = qs.exclude(pk=self._user.pk)
            if qs.exists():
                raise forms.ValidationError('DNI ya registrado.')
        return dni

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            return email
        qs = Usuario.all_objects.filter(email=email)
        if self._user:
            qs = qs.exclude(pk=self._user.pk)
        if qs.exists():
            raise forms.ValidationError('Este email ya está registrado por otro usuario.')
        return email


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
    
    def clean_first_name(self):
        """Valida que el first_name no contenga números"""
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError('El nombre es requerido.')
        validar_nombre_sin_numeros(first_name)
        return first_name

    def clean_last_name(self):
        """Valida que el last_name no contenga números"""
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError('El apellido es requerido.')
        validar_nombre_sin_numeros(last_name)
        return last_name
    
    def clean_email(self):
        email = self.cleaned_data['email']
        usuario_existente = Usuario.all_objects.filter(email=email).exclude(pk=self.instance.pk).first()
        if usuario_existente:
            if not usuario_existente.is_active:
                raise forms.ValidationError(
                    'Este email fue dado de baja. Por favor contacta al soporte para reactivar tu cuenta o usa otro email.'
                )
            raise forms.ValidationError('Este email ya está en uso.')
        return email
    
    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if dni and Usuario.objects.filter(dni=dni).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este DNI ya está en uso.')
        return dni
