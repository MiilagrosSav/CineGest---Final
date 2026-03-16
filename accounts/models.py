from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from simple_history.models import HistoricalRecords
from django.utils import timezone
from datetime import date, datetime

# Validador de DNI (7-8 dígitos numéricos)
DNI_VALIDATOR = RegexValidator(
    regex=r'^\d{7,8}$',
    message='El DNI debe contener entre 7 y 8 dígitos numéricos, sin letras ni espacios.'
)

# Validador de teléfono (7-15 dígitos)
TELEFONO_VALIDATOR = RegexValidator(
    regex=r'^\+?\d{7,15}$',
    message='El teléfono debe contener entre 7 y 15 dígitos numéricos. Puede incluir + al inicio.',
    code='telefono_invalido'
)

# Validador de username alfanumérico
USERNAME_ALPHANUMERIC_VALIDATOR = RegexValidator(
    regex=r'^[a-zA-Z0-9]+$',
    message='El nombre de usuario solo puede contener letras y números, sin espacios ni caracteres especiales.',
    code='username_invalido'
)

# Validador para nombres y apellidos (sin números)
NOMBRE_VALIDATOR = RegexValidator(
    regex=r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s\-\.]+$',
    message='El nombre no puede contener números.',
    code='nombre_invalido'
)


# Managers personalizados para Usuario
class ActiveUserManager(UserManager):
    """
    Manager que solo devuelve usuarios activos.
    ✅ CORREGIDO: Hereda de UserManager para tener get_by_natural_key() y otros métodos de autenticación.
    """
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class AllUsersManager(UserManager):
    """
    Manager que devuelve todos los usuarios (activos e inactivos).
    ✅ CORREGIDO: Hereda de UserManager para compatibilidad con el sistema de autenticación.
    """
    def get_queryset(self):
        return super().get_queryset()


# 1. Este es el modelo de Usuario principal
# ---------------------------------------------
class Usuario(AbstractUser):
    """
    Modelo de Usuario Personalizado que hereda de AbstractUser.
    AbstractUser ya incluye: username, password, email, first_name, last_name, is_staff, is_active, is_superuser.
    
    Nota: El campo 'is_active' de Django se usa para baja lógica.
    - is_active=True: Usuario activo
    - is_active=False: Usuario dado de baja (soft delete)
    """
    
    # Opciones para el campo 'rol'
    ROL_CHOICES = (
        ('admin', 'Administrador'),
        ('empleado', 'Empleado'),
        ('cliente', 'Cliente'),
    )
    
    # Sobreescribir username para restringir a caracteres alfanuméricos
    username = models.CharField(
        'nombre de usuario',
        max_length=150,
        unique=True,
        help_text='150 caracteres o menos. Solo letras y números.',
        validators=[USERNAME_ALPHANUMERIC_VALIDATOR],
        error_messages={
            'unique': 'Ya existe un usuario con ese nombre de usuario.',
        },
    )

    # Campos adicionales de tu diagrama
    dni = models.CharField(max_length=20, unique=True, null=True, blank=True, validators=[DNI_VALIDATOR])
    telefono = models.CharField(
        max_length=20, 
        null=True, 
        blank=True,
        validators=[TELEFONO_VALIDATOR],
        help_text='Formato: +54 9 11 1234-5678 o 1112345678 (7-15 dígitos)'
    )
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='cliente')
    
    # Campo para baja lógica
    fecha_baja = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Baja',
        help_text='Fecha y hora en que el usuario fue dado de baja'
    )
    
    # Sobrescribir email para hacerlo único (AbstractUser no lo tiene unique por defecto)
    email = models.EmailField(
        'Correo Electrónico', 
        unique=True,  
        help_text='Dirección de email única'
    )
    
    # Managers
    objects = ActiveUserManager()  # Manager por defecto: solo usuarios activos
    all_objects = AllUsersManager()  # Manager para acceso administrativo: todos los usuarios

    def __str__(self):
        return self.username

    def clean(self):
        """
        Validaciones personalizadas del modelo Usuario
        """
        super().clean()
        
        # Validar unicidad de username (considerando normalización a minúsculas)
        if self.username:
            username_normalizado = self.username.strip().lower()
            existing_username = Usuario.all_objects.filter(username=username_normalizado).exclude(pk=self.pk)
            if existing_username.exists():
                raise ValidationError({
                    'username': 'Ya existe un usuario con este nombre de usuario.'
                })
        
        # Validar unicidad de email (doble verificación)
        if self.email:
            existing_email = Usuario.objects.filter(email=self.email).exclude(pk=self.pk)
            if existing_email.exists():
                raise ValidationError({
                    'email': 'Ya existe un usuario con este email.'
                })
        
        # Validar unicidad de DNI (doble verificación)
        if self.dni:
            existing_dni = Usuario.objects.filter(dni=self.dni).exclude(pk=self.pk)
            if existing_dni.exists():
                raise ValidationError({
                    'dni': 'Ya existe un usuario con este DNI.'
                })

    def save(self, *args, **kwargs):
        """
        Ejecutar validaciones antes de guardar y gestionar permisos según rol.
        """
        
        # Normalizar username a minúsculas (estándar para nombres de usuario)
        if self.username:
            self.username = self.username.strip().lower()
        
        # Normalizar first_name y last_name a formato título
        if self.first_name:
            self.first_name = self.first_name.strip().title()
        if self.last_name:
            self.last_name = self.last_name.strip().title()
        
        # Normalizar email a minúsculas
        if self.email:
            self.email = self.email.strip().lower()
        
        # Gestionar is_staff según el rol
        if self.rol == 'admin':
            self.is_staff = True
        elif self.rol in ['empleado', 'cliente'] and not self.is_superuser:
            # Solo quitar is_staff si no es superuser
            self.is_staff = False

        # Guardar primero para que el usuario tenga PK
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Asignar permisos de auditoría solo si es admin y no es la primera creación
        # (en la primera creación las migraciones podrían no estar completas)
        if not is_new and self.rol == 'admin':
            try:
                from django.contrib.auth.models import Permission
                from django.contrib.contenttypes.models import ContentType
                
                # Intentar obtener el permiso de auditoría
                ct = ContentType.objects.filter(app_label='auditoria', model='auditentry').first()
                if ct:
                    perm = Permission.objects.filter(content_type=ct, codename='view_auditentry').first()
                    if perm and not self.user_permissions.filter(pk=perm.pk).exists():
                        self.user_permissions.add(perm)
            except Exception:
                # Silenciar errores de permisos (ej: durante migraciones iniciales)
                pass
    
    def soft_delete(self, user=None):
        """
        Realiza baja lógica del usuario.
        
        Args:
            user: Usuario que realiza la baja (opcional, para auditoría)
        
        Marca is_active=False y registra fecha de baja.
        Django automáticamente impedirá el login de usuarios con is_active=False.
        """
        if self.is_active:  # Solo si está activo
            self.is_active = False
            self.fecha_baja = timezone.now()
            
            # Guardar sin crear historial automático
            self.skip_history_when_saving = True
            self.save(update_fields=['is_active', 'fecha_baja'])
            del self.skip_history_when_saving
            
            # Crear registro histórico manual con tipo "-" (eliminación)
            if hasattr(self, 'history'):
                history_data = {field.name: getattr(self, field.name) 
                               for field in self._meta.fields}
                history_data['history_date'] = timezone.now()
                history_data['history_type'] = "-"
                history_data['history_change_reason'] = 'ELIMINACIÓN (baja lógica de usuario)'
                history_data['history_user_id'] = user.id if user else None
                self.history.create(**history_data)
    
    def restore(self, user=None):
        """
        Restaura un usuario dado de baja lógica.
        
        Args:
            user: Usuario que realiza la restauración (opcional, para auditoría)
        
        Marca is_active=True y limpia la fecha de baja.
        """
        if not self.is_active:  # Solo si está inactivo
            self.is_active = True
            self.fecha_baja = None
            
            # Guardar sin crear historial automático
            self.skip_history_when_saving = True
            self.save(update_fields=['is_active', 'fecha_baja'])
            del self.skip_history_when_saving
            
            # Crear registro histórico manual con tipo "+" (restauración)
            if hasattr(self, 'history'):
                history_data = {field.name: getattr(self, field.name) 
                               for field in self._meta.fields}
                history_data['history_date'] = timezone.now()
                history_data['history_type'] = "+"
                history_data['history_change_reason'] = 'RESTAURACIÓN (reactivación de usuario)'
                history_data['history_user_id'] = user.id if user else None
                self.history.create(**history_data)
    
    @property
    def esta_activo(self):
        """Propiedad de conveniencia para verificar si está activo"""
        return self.is_active
    
    @property
    def esta_dado_de_baja(self):
        """Propiedad de conveniencia para verificar si está dado de baja"""
        return not self.is_active

    @property
    def es_perfil_completo(self):
        """Verifica si el usuario tiene DNI y username definidos."""
        return bool(self.dni) and bool(self.username)

    @property
    def is_google_user(self):
        """Verifica si el usuario se autenticó con Google."""
        try:
            return self.social_auth.filter(provider='google-oauth2').exists()
        except Exception:
            return False
    
    def is_admin(self):
        """
        Verifica si el usuario tiene rol de administrador.
        
        Returns:
            bool: True si el usuario es administrador o superusuario, False en caso contrario
        """
        return self.is_superuser or self.rol == 'admin'
    
    def is_empleado(self):
        """
        Verifica si el usuario tiene rol de empleado.
        
        Returns:
            bool: True si el usuario es empleado, admin o superusuario
        """
        return self.is_superuser or self.rol in ['admin', 'empleado']
    
    def is_cliente(self):
        """
        Verifica si el usuario tiene rol de cliente.
        
        Returns:
            bool: True si el usuario es cliente (y no admin/empleado)
        """
        return self.rol == 'cliente' and not self.is_superuser

    # historial de cambios
    history = HistoricalRecords()

    class Meta:
        db_table = "usuarios"  # 👤 Tabla personalizada
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        
        # Las constraints de unicidad de email y dni ya están garantizadas
        # por unique=True en los campos. No se duplican aquí.

# 2. Estos son los modelos de "Perfil" que extienden al Usuario
# -----------------------------------------------------------
# Usamos OneToOneField para la relación 1 a 1 (la línea con "1" en cada extremo)

class Administrador(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return f"Admin: {self.usuario.username}"

    class Meta:
        db_table = "administradores"
        verbose_name = "Administrador"
        verbose_name_plural = "Administradores"


def validar_fecha_ingreso_no_futura(value):
    """
    Validador personalizado para asegurar que la fecha de ingreso
    no sea posterior al día de hoy.
    """
    if value > date.today():
        raise ValidationError(
            'La fecha de ingreso no puede ser posterior al día de hoy.'
        )


class Empleado(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    
    # Campos específicos de Empleado
    fecha_ingreso = models.DateField(
        validators=[validar_fecha_ingreso_no_futura],
        help_text='La fecha de ingreso no puede ser posterior al día de hoy.'
    )

    def __str__(self):
        return f"Empleado: {self.usuario.username}"

    class Meta:
        db_table = "empleados"  # 👨‍💻 Tabla personalizada
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"

class Cliente(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    
    # Campos específicos de Cliente
    acepta_marketing = models.BooleanField(default=False, verbose_name='Acepta marketing', help_text='Opt-in para recibir novedades y ofertas')
    fecha_registro = models.DateField(default=date.today) # Se pone la fecha actual al crear

    def save(self, *args, **kwargs):
        """Asegurar que fecha_registro siempre tenga un valor"""
        if not self.fecha_registro:
            self.fecha_registro = date.today()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cliente: {self.usuario.username}"

    class Meta:
        db_table = "clientes"  # 👥 Tabla personalizada
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"