import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from ventas.models import MetodoPago

print("=" * 70)
print("CREANDO MÉTODOS DE PAGO COMPLETOS")
print("=" * 70)

# Definir los 3 métodos principales
metodos = [
    {
        'nombre': 'Efectivo',
        'descripcion': 'Pago en efectivo en taquilla presencial'
    },
    {
        'nombre': 'Mercado Pago',
        'descripcion': 'Pago online con Mercado Pago (QR, tarjeta, débito)'
    },
    {
        'nombre': 'Tarjeta',
        'descripcion': 'Pago con tarjeta de crédito/débito en taquilla'
    },
]

print("\n🔧 Creando/Verificando métodos de pago...\n")

for metodo_data in metodos:
    metodo, created = MetodoPago.objects.get_or_create(
        nombre=metodo_data['nombre'],
        defaults={'descripcion': metodo_data['descripcion']}
    )
    
    if created:
        print(f"✅ Creado: {metodo.nombre}")
    else:
        print(f"⏭️  Ya existe: {metodo.nombre}")
        # Actualizar descripción si cambió
        if metodo.descripcion != metodo_data['descripcion']:
            metodo.descripcion = metodo_data['descripcion']
            metodo.save()
            print(f"   📝 Descripción actualizada")

print("\n" + "=" * 70)
print("📊 MÉTODOS DE PAGO ACTUALES:")
print("=" * 70)

for m in MetodoPago.objects.all():
    print(f"\n🔹 {m.nombre}")
    print(f"   {m.descripcion}")

print("\n" + "=" * 70)
print("✅ PROCESO COMPLETADO")
print("=" * 70)
