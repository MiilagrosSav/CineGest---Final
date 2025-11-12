from django.db import models



#----------------------------------------------------------------------------------------------
#--------------------------------creamos la clase SALA---------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class Sala(models.Model):
    """
    Modelo para representar una sala de cine.
    Cada sala tiene una capacidad específica y puede proyectar películas.
    """
    # Opciones para el tipo de sala
   

    numero = models.PositiveIntegerField(
        unique=True,
        help_text="Número único de la sala (ej: 1, 2, 3...)"
    )
    
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre descriptivo de la sala (ej: 'Sala Premium A')"
    )
    
    activa = models.BooleanField(
        default=True,
        help_text="Indica si la sala está disponible para proyecciones"
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Notas adicionales sobre la sala (equipamiento, mantenimiento, etc.)"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sala {self.numero} - {self.nombre}"
    
    @property
    def capacidad(self):
        """Calcula la capacidad real contando solo butacas (sin pasillos)"""
        return self.butacas.filter(es_pasillo=False).count()
    
    def get_status_display(self):
        """Retorna el estado de la sala con icono"""
        return "🟢 Activa" if self.activa else "🔴 Inactiva"

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = ['numero']
        db_table = "sala"  # 🏛️ Nombre personalizado de la tabla