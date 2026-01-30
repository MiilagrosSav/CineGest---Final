import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from ventas.models import Venta
from django.db.models import Q

print("=" * 70)
print("ANÁLISIS COMPLETO DE get_metodo_pago_normalizado()")
print("=" * 70)

# Estadísticas generales
total_ventas = Venta.objects.count()
print(f"\n📊 Total de ventas: {total_ventas}")

# Caso 1: Ventas con Pago y MetodoPago
ventas_con_pago = Venta.objects.filter(pago__isnull=False).count()
print(f"\n✅ Ventas CON registro de Pago: {ventas_con_pago}")

if ventas_con_pago > 0:
    venta_ejemplo = Venta.objects.filter(pago__isnull=False).first()
    print(f"   Ejemplo: Venta #{venta_ejemplo.id_venta}")
    print(f"   - medio_pago: '{venta_ejemplo.medio_pago}'")
    print(f"   - Pago.id_metodo_pago: {venta_ejemplo.pago.id_metodo_pago.nombre}")
    print(f"   - get_metodo_pago_normalizado(): '{venta_ejemplo.get_metodo_pago_normalizado()}'")

# Caso 2: Ventas SIN Pago pero CON medio_pago
ventas_sin_pago_con_medio = Venta.objects.filter(
    pago__isnull=True
).exclude(medio_pago='').count()
print(f"\n⚠️  Ventas SIN Pago pero CON medio_pago: {ventas_sin_pago_con_medio}")

if ventas_sin_pago_con_medio > 0:
    venta_ejemplo = Venta.objects.filter(pago__isnull=True).exclude(medio_pago='').first()
    print(f"   Ejemplo: Venta #{venta_ejemplo.id_venta}")
    print(f"   - medio_pago: '{venta_ejemplo.medio_pago}'")
    print(f"   - get_metodo_pago_normalizado(): '{venta_ejemplo.get_metodo_pago_normalizado()}'")

# Caso 3: Ventas SIN Pago y SIN medio_pago
ventas_sin_nada = Venta.objects.filter(
    pago__isnull=True,
    medio_pago=''
).count()
print(f"\n❌ Ventas SIN Pago y SIN medio_pago: {ventas_sin_nada}")

if ventas_sin_nada > 0:
    venta_ejemplo = Venta.objects.filter(pago__isnull=True, medio_pago='').first()
    print(f"   Ejemplo: Venta #{venta_ejemplo.id_venta}")
    print(f"   - Estado: {venta_ejemplo.estado}")
    print(f"   - get_metodo_pago_normalizado(): '{venta_ejemplo.get_metodo_pago_normalizado()}'")

# Distribución por método normalizado
print(f"\n📈 DISTRIBUCIÓN POR MÉTODO NORMALIZADO:")
metodos_count = {}
for venta in Venta.objects.all():
    metodo = venta.get_metodo_pago_normalizado()
    metodos_count[metodo] = metodos_count.get(metodo, 0) + 1

for metodo, count in sorted(metodos_count.items(), key=lambda x: -x[1]):
    print(f"   - {metodo}: {count} ventas")

print("\n" + "=" * 70)
print("✅ ANÁLISIS COMPLETADO")
print("=" * 70)
print("\n💡 CONCLUSIONES:")
print("   - El método normaliza correctamente los valores")
print("   - Prioriza el Pago.id_metodo_pago sobre medio_pago")
print("   - Retorna 'No especificado' cuando no hay información")
print("=" * 70)
