"""Señales que crean `AuditEntry` cuando se generan modelos históricos de simple_history."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from django.db import models
import logging
from .models import AuditEntry, AuditConfig

logger = logging.getLogger(__name__)


@receiver(post_save)
def capture_simple_history(sender, instance, created, **kwargs):
    """Intercepta saves de modelos históricos y crea una fila en AuditEntry.

    Detecta un modelo histórico si la tabla comienza con 'historical_'.
    """
    # Solo procesar modelos históricos
    try:
        db_table = sender._meta.db_table
        model_name = sender._meta.model_name
    except Exception:
        return

    # Detectar modelos históricos (pueden tener prefijo de app: app_historicalmodel o solo historicalmodel)
    if not ('historical' in model_name.lower() or 'historical' in db_table.lower()):
        return

    # Evitar recursión: no procesar AuditEntry ni modelos que no sean históricos
    if model_name in ('auditentry', 'logentry'):
        return
    
    # Verificar que tenga los campos requeridos de simple_history
    if not hasattr(instance, 'history_date') or not hasattr(instance, 'history_type'):
        return

    try:
        # Serializar campos del objeto histórico
        data = {}
        for field in sender._meta.fields:
            name = field.name
            
            # Saltar campos de metadatos de history
            if name.startswith('history_'):
                continue
                
            try:
                value = getattr(instance, name, None)
                
                # Serialización mejorada según tipo de campo
                if value is None:
                    data[name] = None
                elif isinstance(value, (str, int, float, bool)):
                    data[name] = value
                elif isinstance(value, (list, dict)):
                    data[name] = value
                elif isinstance(field, (models.DateField, models.DateTimeField)):
                    data[name] = value.isoformat() if value else None
                elif isinstance(field, models.ForeignKey):
                    # Guardar ID y representación del FK
                    if value:
                        data[name] = {'id': value.pk, 'repr': str(value)}
                    else:
                        data[name] = None
                elif hasattr(value, 'isoformat'):  # Para tipos date/datetime/time
                    data[name] = value.isoformat()
                else:
                    data[name] = str(value)
            except Exception as e:
                logger.warning(f"Error serializando campo {name}: {e}")
                data[name] = None

        # Extraer metadatos del histórico
        history_date = getattr(instance, 'history_date', None)
        history_type = getattr(instance, 'history_type', None)
        history_user = getattr(instance, 'history_user', None)
        history_change_reason = getattr(instance, 'history_change_reason', None)

        # Obtener el objeto original para repr
        try:
            # simple_history crea una propiedad 'instance' que apunta al objeto actual
            original_obj = instance.instance if hasattr(instance, 'instance') else None
            object_repr = str(original_obj) if original_obj else str(data.get('id', 'N/A'))
        except Exception:
            object_repr = str(data.get('id', 'N/A'))

        # Obtener el nombre limpio del modelo (remover historical y prefijo de app si existe)
        clean_model_name = db_table.replace('historical', '').replace('_', '', 1).strip('_')
        if not clean_model_name:
            # Fallback: usar el nombre del modelo
            clean_model_name = model_name.replace('historical', '')
        
        # Verificar si el modelo está excluido en la configuración
        try:
            config = AuditConfig.load()
            if config.is_model_excluded(clean_model_name):
                logger.debug(f"Modelo {clean_model_name} excluido de auditoría consolidada")
                return
        except Exception as e:
            logger.warning(f"Error verificando configuración de auditoría: {e}")
            # Si falla, continuar con la auditoría por seguridad

        # Crear entrada de auditoría
        AuditEntry.objects.create(
            model_name=clean_model_name,
            object_id=str(data.get('id', '') or getattr(instance, instance._meta.pk.attname, '')),
            object_repr=object_repr,
            history_type=history_type or '',
            history_date=history_date,
            history_user=history_user,
            history_change_reason=history_change_reason or None,
            snapshot=data,
        )
        
        logger.debug(f"AuditEntry creada para {clean_model_name} (ID: {data.get('id')})")
        
    except Exception as e:
        logger.error(f"Error creando AuditEntry para {sender}: {e}", exc_info=True)
