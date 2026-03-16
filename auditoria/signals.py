"""Señales que crean `AuditEntry` cuando se generan modelos históricos de simple_history."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from decimal import Decimal, InvalidOperation
import logging
from .models import AuditEntry, AuditConfig

logger = logging.getLogger(__name__)

NOISY_FIELDS = {
    'updated_at',
    'modified_at',
    'last_login',
    'last_seen',
    'last_access',
    'last_activity',
    'last_request',
    'fecha_modificacion',
    'fecha_actualizacion',
    'fecha_actualizado',
    'updated',
}

NOISY_FIELDS_BY_MODEL = {
    'usuario': {'last_login'},
    'cliente': {'last_login'},
    'empleado': {'last_login'},
}


def _serialize_history_instance(sender, instance):
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

    return data


def _resolve_original_pk(sender, instance):
    original_pk = None
    original_pk_field = None

    original_obj = getattr(instance, 'instance', None)
    if original_obj is not None:
        original_pk = original_obj.pk
        original_pk_field = original_obj._meta.pk.attname
        return original_pk, original_pk_field

    # Fallback: intentar encontrar un campo de ID del modelo original
    for field in sender._meta.fields:
        if field.name.startswith('history_') or field.primary_key:
            continue
        if field.name == 'id':
            original_pk = getattr(instance, field.name, None)
            original_pk_field = field.name
            return original_pk, original_pk_field

    for field in sender._meta.fields:
        if field.name.startswith('history_') or field.primary_key:
            continue
        if field.name.startswith('id_'):
            original_pk = getattr(instance, field.name, None)
            original_pk_field = field.name
            return original_pk, original_pk_field

    return original_pk, original_pk_field


def _get_previous_history(sender, instance, original_pk, original_pk_field):
    if not original_pk_field or original_pk is None:
        return None

    try:
        return (
            sender.objects
            .filter(**{original_pk_field: original_pk}, history_date__lt=instance.history_date)
            .order_by('-history_date')
            .first()
        )
    except Exception:
        return None


def _diff_snapshots(current_data, prev_data, ignored_fields):
    if not prev_data:
        return {}

    diff = {}
    keys = set(current_data.keys()) | set(prev_data.keys())
    for key in keys:
        if key in ignored_fields:
            continue
        current_value = current_data.get(key)
        prev_value = prev_data.get(key)
        if _normalize_for_compare(current_value) != _normalize_for_compare(prev_value):
            diff[key] = {'antes': prev_value, 'despues': current_value}

    return diff


def _parse_decimal(value):
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, int):
        return Decimal(value)

    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, str):
        raw = value.strip().replace(',', '.')
        if not raw:
            return None
        try:
            return Decimal(raw)
        except (InvalidOperation, ValueError):
            return None

    return None


def _normalize_for_compare(value):
    """Normaliza valores para evitar falsos positivos en el diff."""
    if isinstance(value, dict):
        return tuple(sorted((k, _normalize_for_compare(v)) for k, v in value.items()))

    if isinstance(value, list):
        return tuple(_normalize_for_compare(v) for v in value)

    decimal_value = _parse_decimal(value)
    if decimal_value is not None:
        return decimal_value.quantize(Decimal('0.01'))

    if isinstance(value, str):
        return value.strip()

    return value


def _build_change_reason(diff, max_items=4):
    if not diff:
        return None

    parts = []
    for idx, (key, values) in enumerate(diff.items()):
        if idx >= max_items:
            parts.append('...')
            break
        parts.append(f"{key}: {values.get('antes')} -> {values.get('despues')}")

    return "Cambios: " + ", ".join(parts)


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
        data = _serialize_history_instance(sender, instance)

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

        original_pk, original_pk_field = _resolve_original_pk(sender, instance)

        # Si es update, detectar cambios y descartar ruido
        if history_type == '~':
            prev_instance = _get_previous_history(sender, instance, original_pk, original_pk_field)
            prev_data = _serialize_history_instance(sender, prev_instance) if prev_instance else {}
            ignored_fields = set(NOISY_FIELDS)
            ignored_fields.update(NOISY_FIELDS_BY_MODEL.get(clean_model_name.lower(), set()))
            diff = _diff_snapshots(data, prev_data, ignored_fields)
            if not diff:
                logger.debug("Update sin cambios relevantes; auditoría omitida")
                return
            if not history_change_reason:
                history_change_reason = _build_change_reason(diff)
        
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
            object_id=str(original_pk or data.get('id', '') or getattr(instance, instance._meta.pk.attname, '')),
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
