# scripts/verificar_uso_funcionpromocion.py
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from promociones.models import FuncionPromocion

count = FuncionPromocion.objects.count()
print(f"📊 Registros en FuncionPromocion: {count}")

if count > 0:
    print("\n✅ LA TABLA SE ESTÁ USANDO")
    print("\nPrimeros 5 registros:")
    for fp in FuncionPromocion.objects.all()[:5]:
        print(f"  - Promo: {fp.promocion.nombre}")
        print(f"    Función: {fp.funcion or 'N/A'}")
        print(f"    Película: {fp.pelicula or 'N/A'}")
else:
    print("\n⚠️ LA TABLA ESTÁ VACÍA")
    print("💡 Considera eliminarla si no planeas usarla")