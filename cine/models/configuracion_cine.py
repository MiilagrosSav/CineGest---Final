from django.db import models
from django.core.validators import RegexValidator
from simple_history.models import HistoricalRecords


class ConfiguracionCine(models.Model):
    """
    Modelo Singleton para la configuración general del cine.
    Solo puede existir una instancia de este modelo.
    """
    
    # Información básica
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Cine",
        help_text="Nombre comercial del establecimiento"
    )
    
    logo = models.ImageField(
        upload_to='cine/logos/',
        blank=True,
        default='',
        verbose_name="Logo del Cine",
        help_text="Logo o imagen corporativa (opcional)"
    )
    
    # Información fiscal
    cuil_cuit = models.CharField(
        max_length=13,
        verbose_name="CUIL/CUIT",
        validators=[
            RegexValidator(
                regex=r'^\d{2}-\d{8}-\d{1}$',
                message='Formato inválido. Use: XX-XXXXXXXX-X'
            )
        ],
        help_text="Formato: 20-12345678-9"
    )
    
    razon_social = models.CharField(
        max_length=200,
        verbose_name="Razón Social",
        help_text="Nombre legal de la empresa"
    )
    
    # Datos de contacto
    direccion = models.CharField(
        max_length=300,
        verbose_name="Dirección",
        help_text="Dirección completa del cine"
    )
    
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono",
        help_text="Número de contacto principal"
    )
    
    email = models.EmailField(
        verbose_name="Email de Contacto",
        help_text="Correo electrónico para consultas"
    )
    
    # Horarios
    horario_apertura = models.TimeField(
        verbose_name="Horario de Apertura",
        help_text="Hora de apertura del cine"
    )
    
    horario_cierre = models.TimeField(
        verbose_name="Horario de Cierre",
        help_text="Hora de cierre del cine"
    )
    
    # Configuración operativa
    minutos_limpieza = models.PositiveIntegerField(
        default=30,
        verbose_name="Minutos de Limpieza",
        help_text="Tiempo entre funciones para limpieza de sala (en minutos)"
    )

    reserva_tiempo_espera = models.PositiveIntegerField(
        default=10,
        verbose_name="Tiempo de Reserva (min)",
        help_text="Minutos que una butaca permanece reservada antes de liberarse automáticamente si no se completa el pago."
    )
    
    # Redes sociales (opcionales)
    facebook = models.URLField(
        blank=True,
        default='',
        verbose_name="Facebook",
        help_text="URL completa del perfil"
    )
    
    instagram = models.URLField(
        blank=True,
        default='',
        verbose_name="Instagram",
        help_text="URL completa del perfil"
    )
    
    twitter = models.URLField(
        blank=True,
        default='',
        verbose_name="Twitter/X",
        help_text="URL completa del perfil"
    )
    
    # Información adicional
    descripcion = models.TextField(
        blank=True,
        default='',
        verbose_name="Descripción",
        help_text="Descripción breve del cine (para mostrar en el sitio)"
    )
    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'configuracion_cine'
        verbose_name = 'Configuración del Cine'
        verbose_name_plural = 'Configuración del Cine'
    

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        
        # 1. Validación de Minutos de Limpieza (Evita -1 o valores nulos)
        if self.minutos_limpieza is not None and self.minutos_limpieza < 0:
            raise ValidationError({
                'minutos_limpieza': "El tiempo de limpieza no puede ser un valor negativo."
            })
        if self.minutos_limpieza > 240: # 4 horas máximo como límite lógico
            raise ValidationError({
                'minutos_limpieza': "El tiempo de limpieza parece excesivo. Máximo permitido: 240 min."
            })

        # 2. Validación de Tiempo de Reserva (Evita -1)
        if self.reserva_tiempo_espera is not None and self.reserva_tiempo_espera < 1:
            raise ValidationError({
                'reserva_tiempo_espera': "El tiempo de reserva debe ser de al menos 1 minuto."
            })
        if self.reserva_tiempo_espera > 60:
            raise ValidationError({
                'reserva_tiempo_espera': "El tiempo de reserva no puede superar los 60 minutos."
            })

        # 3. Validación de Horarios (Cierre no puede ser antes de Apertura)
        if self.horario_apertura and self.horario_cierre:
            if self.horario_cierre <= self.horario_apertura:
                raise ValidationError({
                    'horario_cierre': "El horario de cierre debe ser posterior al de apertura."
                })


    def save(self, *args, **kwargs):
        """
        Override save para implementar patrón Singleton.
        Solo puede existir una configuración.
        """
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevenir eliminación de la configuración"""
        pass
    
    @classmethod
    def load(cls):
        """
        Método de clase para cargar la configuración.
        Si no existe, crea una instancia por defecto.
        """
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'nombre': 'Mi Cine',
                'cuil_cuit': '20-00000000-0',
                'razon_social': 'Cine S.A.',
                'direccion': 'Av. Principal 123',
                'telefono': '+54 11 0000-0000',
                'email': 'contacto@micine.com',
                'horario_apertura': '10:00',
                'horario_cierre': '23:00',
                'minutos_limpieza': 30,
                'reserva_tiempo_espera': 10,
            }
        )
        return obj
    
    def __str__(self):
        return self.nombre
    
    # historial de cambios
    history = HistoricalRecords()
