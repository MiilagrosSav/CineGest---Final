import django.db.models as models
from django.core.exceptions import ValidationError
from django.apps import apps
from simple_history.models import HistoricalRecords

class Promocion(models.Model):
    """
    Modelo Promocion: representa un beneficio genérico que puede aplicarse
    a funciones o películas.
    """
    TIPO_DESCUENTO_CHOICES = [
        ('PORCENTAJE', 'Porcentaje'),
        ('2X1', '2x1'),
        ('MONTO_FIJO', 'Monto fijo'),
    ]

    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default='')
    # Si es True, la promoción se aplica automáticamente cuando la función/película
    # esté vinculada en `FuncionPromocion`. Si es False, requiere código o cupón.
    es_automatica = models.BooleanField(default=False, help_text='Si está marcada, la promoción se aplicará automáticamente a funciones vinculadas.')
    tipo_descuento = models.CharField(max_length=20, choices=TIPO_DESCUENTO_CHOICES)
    valor_descuento = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Porcentaje (0-100) o monto fijo. No se usa para 2x1."
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    
    # Reglas de negocio (Inversión de Control)
    aplica_en_estrenos = models.BooleanField(
        default=False,
        help_text='Si es True, ignora el flag es_estreno de la película.'
    )
    genero_requerido = models.ForeignKey(
        'cine.Genero',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Si es None, aplica a todos los géneros. Si tiene valor, solo aplica a ese género.'
    )
    
    # Días de la semana (solo para promociones automáticas)
    # Almacenado como CSV: "0,2,4" para Lun/Mié/Vie. Vacío = todos los días.
    dias_semana = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Días permitidos como CSV de índices (0=Lunes,..6=Domingo). Ej: "0,2,4". Vacío = todos los días.'
    )

    class Meta:
        db_table = 'promociones_promocion'
        verbose_name = 'Promoción'
        verbose_name_plural = 'Promociones'
        constraints = [
            models.UniqueConstraint(fields=['codigo'], name='UQ_promocion_codigo')
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        """
        Override save para garantizar que 2x1 siempre tenga valor_descuento=50.
        Esto evita errores en cálculos y reportes que esperan un número.
        """
        if self.tipo_descuento == '2X1':
            self.valor_descuento = 50
        super().save(*args, **kwargs)
    
    def clean(self):
        """
        Seguridad: evitar que el campo `codigo` sea modificado si existen
        instancias de `PoliticaPromocion` relacionadas que estén `activa=True`.

        Si esta promoción ya existe en la base y el administrador intenta
        cambiar su `codigo`, se comprobará la existencia de políticas activas
        que referencien la promoción; si existen, se lanzará ValidationError
        para impedir el cambio.
        """
        # Solo aplica si ya existe la instancia en DB
        if not self.pk:
            return

        try:
            original = self.__class__.objects.get(pk=self.pk)
        except self.__class__.DoesNotExist:
            return

        # Si el código no cambia, nada que validar
        if original.codigo == self.codigo:
            return

        # Consultar PoliticaPromocion evitando importaciones circulares
        PoliticaPromocion = apps.get_model('promociones', 'PoliticaPromocion')
        # Buscar políticas activas que referencien esta promoción
        existe_activa = PoliticaPromocion.objects.filter(promocion_a_otorgar=original, activa=True).exists()
        if existe_activa:
            raise ValidationError({'codigo': 'No se puede modificar el código: existen políticas de recuperación activas que dependen de esta promoción. Desactívelas primero o elimínelas antes de cambiar el código.'})
    
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
    
    def obtener_dias_resumen(self):
        """
        Devuelve resumen legible de días:
        - Si vacío: "Todos los días"
        - Si tiene días específicos: lista de nombres cortos ['Lun', 'Mar', ...]
        """
        dias_list = self.get_dias_list()
        if not dias_list:
            return "Todos los días"
        
        nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        return [nombres[d] for d in dias_list if 0 <= d <= 6]
    
    # historial de cambios
    history = HistoricalRecords()