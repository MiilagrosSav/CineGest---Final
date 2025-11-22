import django.db.models as models

class Genero(models.Model):
    """Modelo para representar un género cinematográfico (ej: Acción, Comedia)."""
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Género'
        verbose_name_plural = 'Géneros'
        ordering = ['nombre']
        db_table = 'generos'

    def __str__(self):
        return self.nombre