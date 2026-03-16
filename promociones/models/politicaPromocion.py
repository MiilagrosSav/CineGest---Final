import django.db.models as models
from core.mixins import SoftDeleteMixin
from .promocion import Promocion
from django.utils import timezone
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


class PoliticaPromocion(SoftDeleteMixin, models.Model):
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
        default=1,
        help_text='Prioridad de la política: 1 = máxima prioridad, números más altos = menor prioridad. Valor por defecto=100 (baja prioridad)'
    )

    # Minutos de validez del cupón generado
    minutos_validez = models.PositiveIntegerField(
        default=60, 
        help_text='Tiempo en minutos que el cupón será válido desde que se envía al cliente'
    )
    
    # Ventana de urgencia: horas antes de la función para disparar envío
    # Se usa también para análisis automático de ocupación (ventana de búsqueda)
    horas_antes_de_funcion = models.PositiveIntegerField(
        default=24,
        null=False,
        help_text='Horas antes de la función para disparar envío. También se usa como ventana de búsqueda para análisis de ocupación automática (ej: 24 = enviar/analizar si faltan <= 24 horas)'
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

    class Meta:
        db_table = 'promociones_politicapromocion'
        verbose_name = 'Política de Promoción'
        verbose_name_plural = 'Políticas de Promoción'

    # Campos que definen condiciones financieras/operativas y no pueden
    # modificarse si la política ya fue usada en ventas y está vencida.
    CAMPOS_CRITICOS = [
        'promocion_a_otorgar_id', 'hora_inicio_rango', 'hora_fin_rango',
        'genero_pelicula_id', 'dias_semana', 'umbral_ocupacion',
        'horas_antes_de_funcion', 'prioridad',
        'minutos_validez', 'activar_por_ocupacion',
    ]

    # ------------------------------------------------------------------ #
    # Properties de estado                                                 #
    # ------------------------------------------------------------------ #

    @property
    def esta_vigente(self):
        """
        True si la política está activa Y la promoción asociada también está
        activa y dentro de su rango de fechas.
        """
        if not self.activa:
            return False
        promo = self.promocion_a_otorgar
        if not promo.activo:
            return False
        if promo.fecha_fin < timezone.now().date():
            return False
        return True

    @property
    def esta_bloqueada(self):
        """
        True si la política está vencida/inactiva Y ya fue usada en al menos
        una venta real (cupón marcado como usado). En ese caso, sus campos
        críticos no pueden modificarse por integridad contable.
        """
        if self.esta_vigente:
            return False
        if not self.pk:
            return False  # objeto nuevo, sin historial
        from promociones.models.cuponGenerado import CuponGenerado
        return CuponGenerado.objects.filter(
            politica_origen_id=self.pk, usado=True
        ).exists()

    # ------------------------------------------------------------------ #
    # Validación de formulario                                            #
    # ------------------------------------------------------------------ #

    def clean(self):
        super().clean()
        import re

        nombre_limpio = (self.nombre or '').strip()
        if len(nombre_limpio) < 3:
            raise ValidationError({'nombre': 'El nombre debe tener al menos 3 caracteres.'})
        if not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', nombre_limpio):
            raise ValidationError({'nombre': 'El nombre debe contener letras.'})
        if self.pk and self.esta_bloqueada:
            raise ValidationError(
                'Esta política ya cuenta con ventas registradas y ha vencido. '
                'No puede ser modificada por razones de integridad contable.'
            )

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
        # Sin selección O los 7 días seleccionados → sin restricción
        if not l or set(l) >= {0, 1, 2, 3, 4, 5, 6}:
            return 'TODOS'
        return ', '.join([nombres[d] for d in sorted(l) if 0 <= d <= 6])
    
    def save(self, *args, **kwargs):
        """
        1. Normalización de datos antes de guardar.
        2. Bloqueo de inmutabilidad: si la política está bloqueada (vencida +
           ventas reales), impide cambiar campos críticos.
        """
        import re

        # ------ Bloqueo de inmutabilidad (solo en edición) ------
        if self.pk and self.esta_bloqueada:
            try:
                original = PoliticaPromocion.objects.get(pk=self.pk)
                for campo in self.CAMPOS_CRITICOS:
                    if getattr(self, campo) != getattr(original, campo):
                        raise ValidationError(
                            'Esta política ya cuenta con ventas registradas y ha vencido. '
                            'No puede ser modificada por razones de integridad contable.'
                        )
            except PoliticaPromocion.DoesNotExist:
                pass  # objeto recién creado en esta transacción

        # ------ Normalización de nombre ------
        if self.nombre:
            self.nombre = self.nombre.strip().title()
            self.nombre = re.sub(r'(.)\1{2,}', r'\1\1', self.nombre)

        super().save(*args, **kwargs)
    
    # historial de cambios
    history = HistoricalRecords()