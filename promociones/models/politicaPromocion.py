import django.db.models as models
from .promocion import Promocion
from django.utils import timezone
from simple_history.models import HistoricalRecords


class PoliticaPromocion(models.Model):
    """
    Política que define cuándo disparar correos automáticos al liberarse butacas.
    
    - genero_pelicula: Si se especifica, solo se activa para películas de ese género
                       (ej: "Terror", "Comedia"). Útil para marketing dirigido.
    - hora_inicio_rango/hora_fin_rango: Rango horario de funciones que activan esta política
    """
    
    nombre = models.CharField(max_length=200)
    activa = models.BooleanField(default=True)
    promocion_a_otorgar = models.ForeignKey(Promocion, on_delete=models.PROTECT, related_name='+')

    # ahora referenciamos al modelo `Genero` de la app `cine` para soportar múltiples géneros
    genero_pelicula = models.ForeignKey(
        'cine.Genero',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='politicas',
        help_text='Género de película que activa esta política (opcional)'
    )
    hora_inicio_rango = models.TimeField(help_text="Hora de inicio del rango (ej: 18:00)")
    hora_fin_rango = models.TimeField(help_text="Hora de fin del rango (ej: 23:00)")

    # Nuevo: días de la semana usando django-multiselectfield (valores '0'..'6')
    WEEKDAY_CHOICES = [
        ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
        ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo')
    ]

    # días de la semana como CSV de enteros 0..6. Vacío o '*' = todos los días
    dias_semana = models.CharField(max_length=32, blank=True, default='',
                                  help_text='Días permitidos como CSV de índices (0=Lunes,..6=Domingo). Ej: "0,2,4"')

    # Prioridad: 1 = máxima prioridad, números más altos = menor prioridad
    prioridad = models.PositiveIntegerField(
        default=100,
        help_text='Prioridad de la política: 1 = máxima prioridad, números más altos = menor prioridad. Valor por defecto=100 (baja prioridad)'
    )

    # Minutos de validez del cupón generado
    minutos_validez = models.PositiveIntegerField(
        default=60, 
        help_text='Tiempo en minutos que el cupón será válido desde que se envía al cliente'
    )
    
    # Ventana de urgencia: horas antes de la función para disparar envío
    horas_antes_de_funcion = models.PositiveIntegerField(
        default=24,
        null=False,
        help_text='Mínimo de horas antes de la función para disparar el envío de cupones'
    )
        
    # Análisis Automático: activación por ocupación baja
    activar_por_ocupacion = models.BooleanField(
        default=False,
        help_text='⚡ Habilitar análisis automático: el sistema escaneará funciones futuras y disparará promociones cuando la ocupación sea baja'
    )
    umbral_ocupacion = models.PositiveIntegerField(
        default=30,
        help_text='Activar promoción si ocupación < X%. Ejemplo: 30 = activar cuando ocupación sea menor a 30%'
    )
    horas_anticipacion = models.PositiveIntegerField(
        default=24,
        help_text='Ventana de tiempo: analizar funciones que ocurran en las próximas X horas desde ahora'
    )

    class Meta:
        db_table = 'promociones_politicapromocion'
        verbose_name = 'Política de Promoción'
        verbose_name_plural = 'Políticas de Promoción'

    def __str__(self):
        return self.nombre

    def get_dias_list(self):
        """Devuelve la lista de días como enteros. Si vacío -> todos los días ([])"""
        raw = (self.dias_semana or '').strip()
        if raw == '' or raw == '*' or raw.lower() == 'todos':
            return []
        try:
            parts = [p for p in [x.strip() for x in raw.split(',')] if p != '']
            return [int(p) for p in parts]
        except Exception:
            return []

    def get_dias_display(self):
        l = self.get_dias_list()
        nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        if not l:
            return 'Todos'
        return ','.join([nombres[d] for d in l if 0 <= d <= 6])
    
    def save(self, *args, **kwargs):
        """
        Normalización de datos antes de guardar.
        """
        import re
        
        # Normalizar nombre de la política
        if self.nombre:
            # Eliminar espacios innecesarios y aplicar Title Case
            self.nombre = self.nombre.strip().title()
            # Corregir letras repetidas 3 o más veces
            self.nombre = re.sub(r'(.)\1{2,}', r'\1\1', self.nombre)
        
        super().save(*args, **kwargs)
    
    # historial de cambios
    history = HistoricalRecords()