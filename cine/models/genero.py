import django.db.models as models
from core.mixins import SoftDeleteMixin

class Genero(SoftDeleteMixin, models.Model):
    """Modelo para representar un género cinematográfico (ej: Acción, Comedia)."""
    nombre = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Género'
        verbose_name_plural = 'Géneros'
        ordering = ['nombre']
        db_table = 'generos'
        constraints = [
            models.UniqueConstraint(fields=['nombre'], name='UQ_genero_nombre')
        ]

    def save(self, *args, **kwargs):
        """Normalizar nombre del género a Title Case"""
        if self.nombre:
            self.nombre = self.nombre.strip().title()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.nombre