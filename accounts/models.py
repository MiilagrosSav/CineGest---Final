from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# 1. Este es el modelo de Usuario principal
# ---------------------------------------------
class Usuario(AbstractUser):
    """
    Modelo de Usuario Personalizado que hereda de AbstractUser.
    AbstractUser ya incluye: username, password, email, first_name, last_name, is_staff, is_active, is_superuser.
    """
    
    # Opciones para el campo 'rol'
    ROL_CHOICES = (
        ('admin', 'Administrador'),
        ('empleado', 'Empleado'),
        ('cliente', 'Cliente'),
    )
    
    # Campos adicionales de tu diagrama
    dni = models.CharField(max_length=20, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='cliente')
    
    # Sobrescribir email para hacerlo único (AbstractUser no lo tiene unique por defecto)
    email = models.EmailField(
        'email address', 
        unique=True,  
        help_text='Dirección de email única para cada usuario'
    )

    def __str__(self):
        return self.username

    def clean(self):
        """
        Validaciones personalizadas del modelo Usuario
        """
        super().clean()
        
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
        Ejecutar validaciones antes de guardar
        """
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "usuarios"  # 👤 Tabla personalizada
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        
        constraints = [
        models.UniqueConstraint(
            fields=['email'], 
            name='email_unico'  # 📧 Nombre que tú elijas
        ),
        models.UniqueConstraint(
            fields=['dni'], 
            name='dni_unico'    # 🆔 Nombre que tú elijas
        ),
    ]

# 2. Estos son los modelos de "Perfil" que extienden al Usuario
# -----------------------------------------------------------
# Usamos OneToOneField para la relación 1 a 1 (la línea con "1" en cada extremo)

class Administrador(models.Model):
    # Esto crea el id_usuario (FK) y lo hace la clave primaria (PK)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    
    # Campos específicos de Administrador
    nivel_acceso = models.CharField(max_length=50)

    def __str__(self):
        return f"Admin: {self.usuario.username}"

    class Meta:
        db_table = "administradores"  # 👨‍💼 Tabla personalizada
        verbose_name = "Administrador"
        verbose_name_plural = "Administradores"

class Empleado(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    
    # Campos específicos de Empleado
    fecha_ingreso = models.DateField()
    cargo = models.CharField(max_length=100)

    def __str__(self):
        return f"Empleado: {self.usuario.username}"

    class Meta:
        db_table = "empleados"  # 👨‍💻 Tabla personalizada
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"

class Cliente(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    
    # Campos específicos de Cliente
    direccion = models.CharField(max_length=255, null=True, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    fecha_registro = models.DateField(auto_now_add=True) # Se pone la fecha actual al crear

    def __str__(self):
        return f"Cliente: {self.usuario.username}"

    class Meta:
        db_table = "clientes"  # 👥 Tabla personalizada
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"