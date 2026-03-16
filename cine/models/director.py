from django.db import models
from core.mixins import SoftDeleteMixin


class Director(SoftDeleteMixin, models.Model):
    """
    Entidad normalizada de directores para evitar duplicados y permitir
    enriquecimiento de datos desde TMDB.
    """

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True, default='')
    fecha_nacimiento = models.DateField(blank=True, null=True)
    biografia = models.TextField(blank=True, default='')
    tmdb_id = models.PositiveIntegerField(blank=True, null=True, unique=True)

    class Meta:
        verbose_name = 'Director'
        verbose_name_plural = 'Directores'
        ordering = ['apellido', 'nombre']
        db_table = 'directores'
        constraints = [
            # Evita duplicados para directores sin tmdb_id (creados manualmente).
            # Directores con tmdb_id distinto pueden compartir nombre (homónimos reales).
            models.UniqueConstraint(
                fields=['nombre', 'apellido'],
                condition=models.Q(tmdb_id__isnull=True),
                name='unique_director_nombre_apellido_sin_tmdb',
            ),
        ]

    def _normalizar(self, valor):
        return ' '.join((valor or '').strip().split()).title()

    def save(self, *args, **kwargs):
        self.nombre = self._normalizar(self.nombre)
        self.apellido = self._normalizar(self.apellido)
        super().save(*args, **kwargs)

    def __str__(self):
        nombre_completo = f'{self.nombre} {self.apellido}'.strip()
        return nombre_completo or 'Director sin nombre'
