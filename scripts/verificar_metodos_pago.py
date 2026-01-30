# scripts/verificar_metodos_pago.py
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from django.db import models  # ✅ AGREGAR ESTA LÍNEA
from ventas.models import MetodoPago, Venta, Pago

print("=" * 70)
print("ANÁLISIS DE MÉTODOS DE PAGO")
print("=" * 70)

# 1. ¿Cuántos MetodoPago existen?
metodos = MetodoPago.objects.all()
print(f"\n📋 Registros en MetodoPago: {metodos.count()}")
for metodo in metodos:
    print(f"  - {metodo.nombre}")

# 2. ¿Cuántos Pagos usan MetodoPago?
pagos_con_metodo = Pago.objects.exclude(id_metodo_pago__isnull=True).count()
pagos_sin_metodo = Pago.objects.filter(id_metodo_pago__isnull=True).count()
print(f"\n💳 Pagos CON método asignado: {pagos_con_metodo}")
print(f"⚠️  Pagos SIN método asignado: {pagos_sin_metodo}")

# 3. ¿Qué valores tiene Venta.medio_pago?
ventas_por_medio = Venta.objects.values('medio_pago').annotate(
    total=models.Count('id_venta')  # ✅ Ahora funciona
).order_by('-total')

print(f"\n🛒 Distribución de Venta.medio_pago:")
for item in ventas_por_medio:
    medio = item['medio_pago'] or '(vacío)'
    total = item['total']
    print(f"  - {medio}: {total} ventas")

# 4. ¿Hay inconsistencias?
print(f"\n⚠️  INCONSISTENCIAS:")
ventas_mp = Venta.objects.filter(medio_pago='MERCADOPAGO').count()
metodo_mp = MetodoPago.objects.filter(nombre='Mercado Pago').exists()

print(f"  - Ventas con medio_pago='MERCADOPAGO': {ventas_mp}")
print(f"  - Existe MetodoPago 'Mercado Pago': {'✅ Sí' if metodo_mp else '❌ No'}")

if ventas_mp > 0 and not metodo_mp:
    print("  ❌ PROBLEMA: Hay ventas de Mercado Pago pero no existe el registro en MetodoPago")

print("\n" + "=" * 70)