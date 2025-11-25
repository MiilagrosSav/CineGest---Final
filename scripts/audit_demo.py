#!/usr/bin/env python
"""Script para probar el sistema de auditoría (demo, no recogido por test runner)."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from cine.models import Pelicula
from datetime import date, timedelta
from auditoria.models import AuditEntry

print('=== Test Sistema de Auditoría (demo) ===')
print(f'AuditEntry antes: {AuditEntry.objects.count()}')
print(f'Películas history antes: {Pelicula.history.count()}')

# Crear película de prueba
p = Pelicula.objects.create(
    titulo='Test Auditoría Final',
    sinopsis='Película de prueba para auditoría',
    director='Director Test',
    duracion=100,
    fecha_estreno=date.today() + timedelta(days=60),
    clasificacion='+13'
)

print(f'\nPelícula creada - ID: {p.id}, Título: {p.titulo}')
print(f'AuditEntry después: {AuditEntry.objects.count()}')
print(f'Películas history después: {Pelicula.history.count()}')

if AuditEntry.objects.exists():
    print('\n✅ ¡FUNCIONA! Últimas 3 entradas:')
    for e in AuditEntry.objects.all()[:3]:
        print(f'  - {e.history_date.strftime("%Y-%m-%d %H:%M:%S")} | {e.get_history_type_display()} | {e.model_name} | {e.object_repr}')
else:
    print('\n❌ NO FUNCIONA - No se crearon entradas en AuditEntry')
    print('\nDEBUG: Verificando último registro histórico...')
    if Pelicula.history.exists():
        h = Pelicula.history.first()
        print(f'  Table: {h._meta.db_table}')
        print(f'  Model: {h._meta.model_name}')
        print(f'  Tipo: {h.history_type}')
