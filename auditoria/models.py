from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class AuditEntry(models.Model):
    """Registro consolidado para auditoria cruzada.

    Diccionario rapido de tablas:
    - AuditEntry: resumen de cambios (alta/edicion/baja) desde simple_history.
    - historical_*: detalle historico por modelo con ip y usuario (simple_history).
    - ventas_intercambio: auditoria de intercambios realizados.
    - RegistroAcceso: auditoria de validaciones en puerta.
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
    
    @classmethod
    def cleanup_old_entries(cls, days_to_keep=90):
        """
        Elimina registros de auditoría más antiguos que X días.
        
        Args:
            days_to_keep (int): Días de retención (default: 90)
        
        Returns:
            int: Número de registros eliminados
        """
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        deleted_count, _ = cls.objects.filter(history_date__lt=cutoff_date).delete()
        return deleted_count
    
    @classmethod
    def get_statistics(cls):
        """Retorna estadísticas de uso de la tabla de auditoría."""
        from django.db.models import Count, Q
        from datetime import datetime, timedelta
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        
        stats = {
            'total_entries': cls.objects.count(),
            'entries_last_30_days': cls.objects.filter(history_date__gte=last_30_days).count(),
            'entries_last_7_days': cls.objects.filter(history_date__gte=last_7_days).count(),
            'by_type': cls.objects.values('history_type').annotate(count=Count('id')),
            'by_model': cls.objects.values('model_name').annotate(count=Count('id')).order_by('-count')[:10],
            'oldest_entry': cls.objects.order_by('history_date').first(),
            'newest_entry': cls.objects.order_by('-history_date').first(),
        }
        
        return stats


class AuditConfig(models.Model):
    """
    Configuración de auditoría (Singleton).
    Permite configurar retención y qué modelos auditar.
    """
    # Retención
    retention_days = models.PositiveIntegerField(
        default=90,
        verbose_name='Días de Retención',
        help_text='Días que se conservan los registros de auditoría antes de ser eliminados automáticamente'
    )
    
    auto_cleanup_enabled = models.BooleanField(
        default=False,
        verbose_name='Limpieza Automática Habilitada',
        help_text='Si está activado, los registros antiguos se eliminan automáticamente según retention_days'
    )
    
    # Modelos excluidos de auditoría consolidada (aún tienen historical_*)
    excluded_models = models.TextField(
        blank=True,
        default='',
        verbose_name='Modelos Excluidos',
        help_text='Nombres de modelos separados por comas para excluir de AuditEntry (ej: venta,entrada)'
    )
    
    # Timestamps
    last_cleanup = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Última Limpieza',
        help_text='Fecha y hora de la última limpieza automática'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Configuración de Auditoría'
        verbose_name_plural = 'Configuración de Auditoría'
    
    def save(self, *args, **kwargs):
        """Implementar patrón Singleton"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevenir eliminación"""
        pass
    
    @classmethod
    def load(cls):
        """Cargar o crear configuración"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def __str__(self):
        return f"Auditoría: {self.retention_days} días retención"
    
    def get_excluded_models_list(self):
        """Retorna lista de modelos excluidos"""
        if not self.excluded_models:
            return []
        return [m.strip().lower() for m in self.excluded_models.split(',') if m.strip()]
    
    def is_model_excluded(self, model_name):
        """Verifica si un modelo está excluido"""
        return model_name.lower() in self.get_excluded_models_list()
