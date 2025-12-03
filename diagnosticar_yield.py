"""
Diagnóstico: Por qué no llegó email de yield management
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from cine.models import Funcion
from promociones.models.politicaPromocion import PoliticaPromocion
from accounts.models import Cliente
from ventas.models import Venta

print("=" * 70)
print("DIAGNÓSTICO: Yield Management Email")
print("=" * 70)

# 1. Verificar políticas activas con activar_por_ocupacion
politicas = PoliticaPromocion.objects.filter(
    activa=True,
    activar_por_ocupacion=True
)

print(f"\n1️⃣ Políticas de ocupación automática activas: {politicas.count()}")
if politicas.exists():
    for p in politicas:
        print(f"   - {p.nombre}")
        print(f"     Umbral: {p.umbral_ocupacion}%")
        print(f"     Anticipación: {p.horas_anticipacion}h")
        print(f"     Promoción: {p.promocion_a_otorgar.codigo}")
else:
    print("   ⚠️  NO HAY POLÍTICAS ACTIVAS")

# 2. Verificar funciones en ventana de 2 minutos (test mode)
now = timezone.now()
fin_ventana = now + timedelta(minutes=2)

funciones = Funcion.objects.filter(
    fecha_hora__gte=now,
    fecha_hora__lte=fin_ventana
).select_related('pelicula', 'sala')

print(f"\n2️⃣ Funciones en ventana de 2 minutos: {funciones.count()}")
if funciones.exists():
    for f in funciones:
        total = f.sala.capacidad
        vendidas = f.entradas.filter(estado__in=['RESERVADA', 'VENDIDA', 'USADA']).count()
        ocupacion = (vendidas / total * 100) if total > 0 else 0
        
        print(f"   - Función #{f.id}: {f.pelicula.titulo}")
        print(f"     Fecha: {f.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"     Ocupación: {ocupacion:.1f}% ({vendidas}/{total})")
        print(f"     Estado promoción: {f.estado_promocion}")
else:
    print("   ⚠️  NO HAY FUNCIONES EN VENTANA DE 2 MINUTOS")
    print(f"   Crea una función con fecha_hora entre:")
    print(f"   {now.strftime('%Y-%m-%d %H:%M:%S')} y {fin_ventana.strftime('%Y-%m-%d %H:%M:%S')}")

# 3. Verificar clientes disponibles
clientes_activos = Cliente.objects.filter(usuario__is_active=True).count()
print(f"\n3️⃣ Clientes activos en el sistema: {clientes_activos}")

# Verificar si hay clientes con compras recientes
fecha_limite = timezone.now() - timedelta(days=180)
clientes_con_compras = Venta.objects.filter(
    fecha_compra__gte=fecha_limite
).values_list('id_cliente', flat=True).distinct()

print(f"   Clientes con compras en últimos 6 meses: {len(clientes_con_compras)}")

# 4. Verificar configuración SMTP
from django.conf import settings
print(f"\n4️⃣ Configuración SMTP:")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")

# 5. Resumen
print("\n" + "=" * 70)
print("RESUMEN:")
print("=" * 70)

problemas = []
if not politicas.exists():
    problemas.append("❌ No hay políticas de ocupación automática activas")
if not funciones.exists():
    problemas.append("❌ No hay funciones en ventana de 2 minutos")
if clientes_activos == 0:
    problemas.append("❌ No hay clientes activos")
if len(clientes_con_compras) == 0:
    problemas.append("⚠️  No hay clientes con compras recientes (los emails se envían solo a clientes objetivo)")

if problemas:
    for p in problemas:
        print(p)
else:
    print("✅ Configuración correcta. Si el cron ejecutó y no llegó email:")
    print("   1. Verifica que la ocupación sea < umbral configurado")
    print("   2. Revisa los logs del comando con -v 2")
    print("   3. Verifica que MailCrab esté corriendo en localhost:1080")

print("=" * 70)
