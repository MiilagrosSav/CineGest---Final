import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from django.db import models
from ventas.models import MetodoPago, Venta, Pago

print("=" * 70)
print("VERIFICACIÓN FINAL DE MÉTODOS DE PAGO")
print("=" * 70)

# 1. Métodos existentes
metodos = MetodoPago.objects.all()
print(f"\n✅ Registros en MetodoPago: {metodos.count()}")
for metodo in metodos:
    print(f"  🔹 {metodo.nombre}: {metodo.descripcion}")

# 2. Distribución de pagos
print(f"\n💳 DISTRIBUCIÓN DE PAGOS POR MÉTODO:")
for metodo in metodos:
    count = Pago.objects.filter(id_metodo_pago=metodo).count()
    print(f"  - {metodo.nombre}: {count} pagos")

# Pagos sin método (no debería haber)
pagos_sin_metodo = Pago.objects.filter(id_metodo_pago__isnull=True).count()
if pagos_sin_metodo > 0:
    print(f"  ⚠️  SIN MÉTODO: {pagos_sin_metodo} pagos")
else:
    print(f"  ✅ TODOS los pagos tienen método asignado")

# 3. Ventas por medio_pago
print(f"\n🛒 DISTRIBUCIÓN DE VENTAS POR MEDIO DE PAGO:")
ventas_por_medio = Venta.objects.values('medio_pago').annotate(
    total=models.Count('id_venta')
).order_by('-total')

for item in ventas_por_medio:
    medio = item['medio_pago'] or '(vacío)'
    total = item['total']
    print(f"  - {medio}: {total} ventas")

# 4. Consistencia
print(f"\n🔍 VERIFICACIÓN DE CONSISTENCIA:")

# Total de ventas confirmadas
ventas_confirmadas = Venta.objects.filter(estado='CONFIRMADA').count()
print(f"  - Ventas CONFIRMADAS: {ventas_confirmadas}")

# Total de pagos completados
pagos_completados = Pago.objects.filter(estado='COMPLETADO').count()
print(f"  - Pagos COMPLETADOS: {pagos_completados}")

# Ventas confirmadas SIN pago
ventas_sin_pago = Venta.objects.filter(estado='CONFIRMADA').exclude(
    pago__isnull=False
).count()

if ventas_sin_pago > 0:
    print(f"  ⚠️  {ventas_sin_pago} ventas confirmadas SIN registro de pago")
else:
    print(f"  ✅ Todas las ventas confirmadas tienen registro de pago")

# 5. Métodos usados vs existentes
print(f"\n📊 RESUMEN:")
print(f"  - Métodos de pago configurados: {metodos.count()}")
print(f"  - Métodos usados en pagos: {Pago.objects.values('id_metodo_pago').distinct().count()}")

print("\n" + "=" * 70)
print("✅ VERIFICACIÓN COMPLETADA")
print("=" * 70)
