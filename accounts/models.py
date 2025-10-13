from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Definimos tipos de usuario
    ADMINISTRADOR = 'ADMINISTRADOR'
    CLIENTE = 'CLIENTE'
    EMPLEADO = 'EMPLEADO'
    USER_TYPE_CHOICES = [
        (ADMINISTRADOR, 'Administrador'),
        (CLIENTE, 'Cliente'),
        (EMPLEADO, 'Empleado'),
    ]

    # ✅ HACER EMAIL ÚNICO PARA EVITAR DUPLICADOS
    email = models.EmailField(unique=True, blank=False, null=False)

    user_type = models.CharField(
        max_length=15,
        choices=USER_TYPE_CHOICES,
        default=CLIENTE,
        help_text="Tipo de usuario: ADMINISTRADOR / CLIENTE / EMPLEADO"
    )

    def save(self, *args, **kwargs):
        # SOLO cambiar a ADMINISTRADOR si es superusuario Y se está creando por primera vez
        # Y NO es un usuario de OAuth (que tienen email de proveedores externos)
        if (self.is_superuser and 
            self.user_type == self.CLIENTE and 
            not hasattr(self, '_oauth_user')):  # Flag para usuarios OAuth
            self.user_type = self.ADMINISTRADOR
        super().save(*args, **kwargs)

    def is_admin(self):
        return self.user_type == self.ADMINISTRADOR or self.is_superuser

    def is_client(self):
        return self.user_type == self.CLIENTE

    def is_employee(self):
        return self.user_type == self.EMPLEADO

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
