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

    user_type = models.CharField(
        max_length=15,
        choices=USER_TYPE_CHOICES,
        default=CLIENTE,
        help_text="Tipo de usuario: ADMINISTRADOR / CLIENTE / EMPLEADO"
    )

    def is_admin(self):
        return self.user_type == self.ADMINISTRADOR

    def is_client(self):
        return self.user_type == self.CLIENTE

    def is_employee(self):
        return self.user_type == self.EMPLEADO

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
