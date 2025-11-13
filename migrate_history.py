#!/usr/bin/env python
"""Script para migrar registros históricos existentes a AuditEntry."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from django.apps import apps
from auditoria.models import AuditEntry

print('=== Migración de Registros Históricos Existentes ===\n')

total_migrated = 0

for model in apps.get_models():
    if not hasattr(model, 'history'):
        continue
    
    model_name = model._meta.model_name
    historical_count = model.history.count()
    
    if historical_count == 0:
        continue
    
    print(f'Procesando {model_name}... ({historical_count} registros)')
    
    for h in model.history.all():
        # Verificar si ya existe (por si se ejecuta dos veces)
        db_table = h._meta.db_table
        clean_name = db_table.replace('historical', '').replace('_', '', 1).strip('_')
        
        # Construir snapshot
        snapshot = {}
        for field in h._meta.fields:
            fname = field.name
            if fname.startswith('history_'):
                continue
            try:
                val = getattr(h, fname, None)
                if val is None or isinstance(val, (str, int, float, bool, list, dict)):
                    snapshot[fname] = val
                else:
                    snapshot[fname] = str(val)
            except:
                snapshot[fname] = None
        
        # Crear AuditEntry si no existe
        AuditEntry.objects.get_or_create(
            model_name=clean_name,
            object_id=str(snapshot.get('id', '')),
            history_date=h.history_date,
            history_type=h.history_type,
            defaults={
                'object_repr': str(getattr(h, 'instance', snapshot.get('id', 'N/A'))),
                'history_user': h.history_user,
                'history_change_reason': h.history_change_reason,
                'snapshot': snapshot,
            }
        )
    
    migrated = AuditEntry.objects.filter(model_name=clean_name).count()
    print(f'  ✅ {migrated} entradas en AuditEntry')
    total_migrated += migrated

print(f'\n=== Migración Completa ===')
print(f'Total de entradas en AuditEntry: {AuditEntry.objects.count()}')
