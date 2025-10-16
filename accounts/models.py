from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Hacer el email único
    email = models.EmailField(unique=True, blank=False, null=False)
    
    # Definimos tipos de usuario
    ADMINISTRADOR = 'ADMINISTRADOR'
    CLIENTE = 'CLIENTE'
    EMPLEADO = 'EMPLEADO'
    USER_TYPE_CHOICES = [
        (ADMINISTRADOR, 'Administrador'),
        (CLIENTE, 'Cliente'),
        (EMPLEADO, 'Empleado'),
    ]

    user_type = models.CharField(
        max_length=15,
        choices=USER_TYPE_CHOICES,
        default=CLIENTE,
        help_text="Tipo de usuario: ADMINISTRADOR / CLIENTE / EMPLEADO",
        blank=True,
        null=True
    )

    def is_admin(self):
        return self.user_type == self.ADMINISTRADOR

    def is_client(self):
        return self.user_type == self.CLIENTE

    def is_employee(self):
        return self.user_type == self.EMPLEADO

    def save(self, *args, **kwargs):
        # Si es superusuario, asignar tipo ADMINISTRADOR automáticamente
        if self.is_superuser and not self.user_type:
            self.user_type = self.ADMINISTRADOR
        # Si no tiene tipo asignado y no es superusuario, asignar CLIENTE por defecto
        elif not self.user_type:
            self.user_type = self.CLIENTE
        super().save(*args, **kwargs)

    def __str__(self):
        if self.is_superuser:
            return f"{self.username} (Superadmin)"
        return f"{self.username} ({self.get_user_type_display()})"
