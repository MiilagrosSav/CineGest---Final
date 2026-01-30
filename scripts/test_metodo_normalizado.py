import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from ventas.models import Venta

print("=" * 70)
print("PRUEBA DEL MÉTODO get_metodo_pago_normalizado()")
print("=" * 70)

# Probar con las primeras 5 ventas
ventas = Venta.objects.all()[:5]

for venta in ventas:
    print(f"\n📦 Venta #{venta.id_venta}")
    print(f"   Estado: {venta.estado}")
    print(f"   medio_pago (campo CharField): '{venta.medio_pago}'")
    
    # Verificar si tiene pago
    try:
        if hasattr(venta, 'pago') and venta.pago:
            print(f"   Pago.id_metodo_pago: {venta.pago.id_metodo_pago.nombre}")
        else:
            print(f"   Pago: No tiene registro de Pago")
    except Exception as e:
        print(f"   Pago: Error - {e}")
    
    # Probar el método normalizado
    metodo_normalizado = venta.get_metodo_pago_normalizado()
    print(f"   ✅ get_metodo_pago_normalizado(): '{metodo_normalizado}'")

print("\n" + "=" * 70)
print("✅ PRUEBA COMPLETADA")
print("=" * 70)
