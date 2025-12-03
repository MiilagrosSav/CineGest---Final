"""
Crear función de prueba para yield management
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from cine.models import Funcion, Pelicula, Sala

print("=" * 70)
print("CREAR FUNCIÓN DE PRUEBA PARA YIELD MANAGEMENT")
print("=" * 70)

# Obtener película y sala existentes
pelicula = Pelicula.objects.first()
sala = Sala.objects.first()

if not pelicula or not sala:
    print("❌ No hay películas o salas en el sistema")
    print("   Crea al menos una película y una sala primero")
    exit(1)

# Crear función en 1.5 minutos (dentro de ventana de 2 min)
fecha_hora = timezone.now() + timedelta(seconds=90)

print(f"\n📅 Creando función de prueba:")
print(f"   Película: {pelicula.titulo}")
print(f"   Sala: {sala.nombre} (Capacidad: {sala.capacidad})")
print(f"   Fecha/Hora: {fecha_hora.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Precio base: $100")

funcion = Funcion.objects.create(
    pelicula=pelicula,
    sala=sala,
    fecha_hora=fecha_hora,
    precio_base=100.00,
    estado_promocion='NORMAL'
)

print(f"\n✅ Función creada: ID #{funcion.id}")
print(f"\n💡 Ahora ejecuta el cron y debería:")
print(f"   1. Detectar esta función (ocupación: 0%)")
print(f"   2. Activar promoción (umbral: 30%)")
print(f"   3. Enviar emails a clientes objetivo")
print(f"\n⏰ La función estará en ventana por ~90 segundos")
print("=" * 70)
