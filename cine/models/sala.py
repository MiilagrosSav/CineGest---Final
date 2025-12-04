from django.db import models
from simple_history.models import HistoricalRecords
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


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
        help_text="Número único de la sala (ej: 1, 2, 3...)"
    )
    
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre descriptivo de la sala (ej: 'Sala Premium A')"
    )
    capacidad_total = models.PositiveIntegerField(default=0, editable=False)
    activa = models.BooleanField(
        default=True,
        help_text="Indica si la sala está disponible para proyecciones"
    )
    
    observaciones = models.TextField(
        blank=True,
        default='',
        help_text="Notas adicionales sobre la sala (equipamiento, mantenimiento, etc.)"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sala {self.numero} - {self.nombre} ({self.capacidad_total} butacas)"  
      
    @property
    def capacidad(self):
        """
        OPTIMIZACIÓN: Ahora leemos el campo guardado en lugar de contar en la BD cada vez.
        Esto hace que tu sistema vuele de rápido.
        """
        return self.capacidad_total
    
    def get_status_display(self):
        """Retorna el estado de la sala con icono"""
        return "🟢 Activa" if self.activa else "🔴 Inactiva"
    
    def tiene_butacas_vendidas(self):
        """
        Verifica si la sala tiene butacas vendidas en alguna función.
        Retorna True si hay entradas vendidas, False en caso contrario.
        """
        from ventas.models import Entrada
        return Entrada.objects.filter(
            id_sala=self,
            estado__in=['VENDIDA', 'ENTREGADA', 'USADA']
        ).exists()

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = ['numero']
        db_table = "sala"  # 🏛️ Nombre personalizado de la tabla
        constraints = [
            models.UniqueConstraint(fields=['numero'], name='UQ_sala_numero')
        ]

    # historial de cambios
    history = HistoricalRecords()


# -------------------------------------------------------------------------
# AUTOMATIZACIÓN: La Señal (Signal)
# -------------------------------------------------------------------------
# Esto va fuera de la clase, al final del archivo.
# Se ejecuta cada vez que tocas una Butaca en el sistema.

@receiver([post_save, post_delete], sender='cine.Butaca')
def actualizar_capacidad_sala(sender, instance, **kwargs):
    """
    Calcula la capacidad real (sin pasillos) y actualiza la Sala.
    """
    sala = instance.sala
    
    # Contamos SOLO las butacas que NO son pasillo (respetando tu lógica de negocio)
    cantidad_real = sala.butacas.filter(es_pasillo=False).count()
    
    # Solo guardamos si el número cambió (para no gastar recursos)
    if sala.capacidad_total != cantidad_real:
        sala.capacidad_total = cantidad_real
        # update_fields es vital para no sobreescribir otros datos por error
        sala.save(update_fields=['capacidad_total'])