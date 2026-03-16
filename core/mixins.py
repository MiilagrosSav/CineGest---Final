"""
Mixins reutilizables para implementar baja lógica en modelos.

Este módulo proporciona el comportamiento de soft delete que puede ser
heredado por cualquier modelo que requiera baja lógica en lugar de
eliminación física de registros.
"""

from django.db import models
from django.utils import timezone
from core.managers import ActiveManager, AllObjectsManager


class SoftDeleteMixin(models.Model):
    """
    Mixin que agrega funcionalidad de baja lógica a cualquier modelo.
    
    Características:
    - Campo 'activo' para marcar registros como activos/inactivos
    - Managers: objects (solo activos) y all_objects (todos)
    - Método delete() sobrescrito para hacer baja lógica
    - Métodos soft_delete() y restore() explícitos
    - Compatible con simple_history (registra cambios de estado)
    
    Uso:
        class MiModelo(SoftDeleteMixin):
            nombre = models.CharField(max_length=100)
            ...
        
        # Uso normal
        obj = MiModelo.objects.get(id=1)
        obj.delete()  # Baja lógica (activo=False)
        
        # Uso explícito
        obj.soft_delete()  # Baja lógica
        obj.restore()      # Restaurar
        
        # Acceso administrativo
        MiModelo.all_objects.all()  # Incluye inactivos
    """
    
    activo = models.BooleanField(
        default=True,
        db_index=True,  # Índice para optimizar queries con filtro activo=True
        verbose_name='Activo',
        help_text='Indica si el registro está activo o fue dado de baja lógicamente'
    )
    
    fecha_baja = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Baja',
        help_text='Fecha y hora en que el registro fue dado de baja'
    )
    
    # Managers
    objects = ActiveManager()  # Manager por defecto: solo activos
    all_objects = AllObjectsManager()  # Manager para acceso administrativo
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False, hard_delete=False):
        """
        Sobrescribe delete() para hacer baja lógica por defecto.
        
        Args:
            using: Base de datos a usar
            keep_parents: Mantener parents en herencia multi-tabla
            hard_delete: Si True, elimina físicamente el registro
        
        Returns:
            Tupla (num_deleted, dict) si hard_delete=True, sino None
        """
        if hard_delete:
            # Eliminación física real (solo para casos excepcionales)
            return super().delete(using=using, keep_parents=keep_parents)
        else:
            # Baja lógica
            self.soft_delete()
            return None
    
    def soft_delete(self, user=None):
        """
        Realiza baja lógica del registro.
        
        Args:
            user: Usuario que realiza la baja (opcional)
        
        Marca el registro como inactivo y registra la fecha de baja.
        Crea un registro histórico con tipo "-" (ELIMINACIÓN).
        """
        if self.activo:  # Solo si está activo
            self.activo = False
            self.fecha_baja = timezone.now()
            
            # Guardar sin crear historial automático
            self.skip_history_when_saving = True
            try:
                self.save(update_fields=['activo', 'fecha_baja'], skip_clean=True)
            except TypeError:
                self.save(update_fields=['activo', 'fecha_baja'])
            del self.skip_history_when_saving
            
            # Crear registro histórico manual con tipo "-" (eliminación)
            if hasattr(self, 'history'):
                history_data = {field.name: getattr(self, field.name) 
                               for field in self._meta.fields}
                history_data['history_date'] = timezone.now()
                history_data['history_type'] = "-"
                history_data['history_change_reason'] = 'ELIMINACIÓN (baja lógica)'
                history_data['history_user_id'] = user.id if user else None
                self.history.create(**history_data)
    
    def restore(self, user=None):
        """
        Restaura un registro dado de baja lógica.
        
        Args:
            user: Usuario que realiza la restauración (opcional)
        
        Marca el registro como activo nuevamente y limpia la fecha de baja.
        Crea un registro histórico con tipo "+" (creación/restauración).
        """
        if not self.activo:  # Solo si está inactivo
            self.activo = True
            self.fecha_baja = None
            
            # Guardar sin crear historial automático
            self.skip_history_when_saving = True
            try:
                self.save(update_fields=['activo', 'fecha_baja'], skip_clean=True)
            except TypeError:
                self.save(update_fields=['activo', 'fecha_baja'])
            del self.skip_history_when_saving
            
            # Crear registro histórico manual con tipo "+" (creación/restauración)
            if hasattr(self, 'history'):
                history_data = {field.name: getattr(self, field.name) 
                               for field in self._meta.fields}
                history_data['history_date'] = timezone.now()
                history_data['history_type'] = "+"
                history_data['history_change_reason'] = 'RESTAURACIÓN (reactivación)'
                history_data['history_user_id'] = user.id if user else None
                self.history.create(**history_data)
    
    def hard_delete(self):
        """
        Elimina físicamente el registro de la base de datos.
        
        Atención: Esta operación es irreversible.
        Solo usar en casos excepcionales donde se requiera eliminación física.
        """
        return super().delete()
    
    @property
    def esta_activo(self):
        """Propiedad de conveniencia para verificar si está activo"""
        return self.activo
    
    @property
    def esta_dado_de_baja(self):
        """Propiedad de conveniencia para verificar si está dado de baja"""
        return not self.activo
