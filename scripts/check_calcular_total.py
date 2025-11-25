# Script de diagnóstico: imprime totales originales y con sesión para las primeras 5 ventas
import sys
import django
import json
from decimal import Decimal
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from ventas.models import Venta

results = []
qs = Venta.objects.all()[:5]
for v in qs:
    try:
        orig = v.calcular_total(None)
    except Exception as e:
        orig = f'ERROR: {e}'
    try:
        # Simular request con sesión vacía
        class DummyRequest:
            session = {}
        disc = v.calcular_total(DummyRequest())
    except Exception as e:
        disc = f'ERROR: {e}'
    results.append({'venta_id': v.id_venta, 'original_total': str(orig), 'discounted_total': str(disc)})

print(json.dumps(results, indent=2, ensure_ascii=False))
