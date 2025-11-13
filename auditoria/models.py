from django.db import models
from django.conf import settings
from django.utils import timezone


class AuditEntry(models.Model):
    """Registro consolidado para entradas históricas generadas por django-simple-history.

    Este modelo se alimenta automáticamente desde las señales cuando un modelo histórico
    (tabla `historical_*`) es creado por simple_history.
    """
    # Información del modelo y objeto
    model_name = models.CharField(max_length=200, db_index=True, help_text="Nombre de la tabla del modelo")
    object_id = models.CharField(max_length=255, null=True, blank=True, db_index=True, help_text="ID del objeto auditado")
    object_repr = models.CharField(max_length=500, null=True, blank=True, help_text="Representación en texto del objeto")

    # Información del cambio
    history_type = models.CharField(
        max_length=1,
        choices=[
            ('+', 'Creación'),
            ('~', 'Actualización'),
            ('-', 'Eliminación'),
        ],
        db_index=True,
        help_text="Tipo de operación realizada"
    )
    history_date = models.DateTimeField(db_index=True, help_text="Fecha y hora del cambio")
    history_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_entries',
        db_index=True,
        help_text="Usuario que realizó el cambio"
    )
    history_change_reason = models.TextField(null=True, blank=True, help_text="Razón del cambio (opcional)")

    # Datos del cambio
    snapshot = models.JSONField(null=True, blank=True, help_text="Snapshot completo del objeto en ese momento")
    
    # Timestamp de creación del registro de auditoría
    created_at = models.DateTimeField(auto_now_add=True, help_text="Fecha de creación de esta entrada de auditoría")

    class Meta:
        ordering = ['-history_date', '-created_at']
        verbose_name = 'Entrada de Auditoría'
        verbose_name_plural = 'Entradas de Auditoría'
        indexes = [
            models.Index(fields=['-history_date', 'model_name']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['history_user', '-history_date']),
        ]

    def __str__(self):
        return f"{self.get_history_type_display()} {self.model_name} {self.object_repr} @ {self.history_date}"

    def get_history_type_display(self):
        """Retorna una representación legible del tipo de cambio."""
        display_map = {
            '+': 'Creación',
            '~': 'Actualización',
            '-': 'Eliminación'
        }
        return display_map.get(self.history_type, self.history_type)
