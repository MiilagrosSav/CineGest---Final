from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class PoliticaReembolso(models.Model):
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre de la Política',
        help_text='Nombre identificador de la política (ej. "Corta antelación").',
    )

    horas_minimas_antes_evento = models.PositiveIntegerField(
        unique=True,
        verbose_name="Horas Mínimas Antes del Evento",
    )

    porcentaje_reembolso = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Porcentaje a Reembolsar (%)",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Indica si esta política está habilitada',
    )

    class Meta:
        ordering = ['-horas_minimas_antes_evento']
        verbose_name = 'Política de Reembolso'
        verbose_name_plural = 'Políticas de Reembolso'

    def __str__(self):
        if getattr(self, 'nombre', None):
            return f"{self.nombre} ({self.horas_minimas_antes_evento}h → {self.porcentaje_reembolso}%)"
        return f"{self.horas_minimas_antes_evento}h antes → {self.porcentaje_reembolso}%"
