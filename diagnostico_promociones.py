"""
Script de diagnóstico para verificar promociones y vínculos.
Ejecutar con: python manage.py shell < diagnostico_promociones.py
"""

from promociones.models import Promocion
from promociones.models.vinculo_promocional import VinculoPromocional
from django.utils import timezone

print("\n" + "="*80)
print("DIAGNÓSTICO DE PROMOCIONES Y VÍNCULOS")
print("="*80 + "\n")

# 1. Promociones automáticas activas
print("1. PROMOCIONES AUTOMÁTICAS ACTIVAS")
print("-" * 80)
promos_automaticas = Promocion.objects.filter(
    es_automatica=True,
    activo=True,
    fecha_baja__isnull=True
)
print(f"Total: {promos_automaticas.count()}\n")

for promo in promos_automaticas:
    print(f"\n📋 {promo.codigo} - {promo.nombre}")
    print(f"   ID: {promo.pk}")
    print(f"   Tipo: {promo.tipo_descuento} | Valor: {promo.valor_descuento}")
    print(f"   Vigencia: {promo.fecha_inicio} hasta {promo.fecha_fin}")
    print(f"   Días semana: {promo.dias_semana or 'Todos'}")
    print(f"   Activo: {promo.activo} | Fecha baja: {promo.fecha_baja}")
    
    # Verificar vínculos
    vinculos = VinculoPromocional.objects.filter(promocion=promo).select_related('funcion', 'pelicula')
    if vinculos.exists():
        print(f"   🎯 TIENE {vinculos.count()} VÍNCULO(S) ESPECÍFICO(S):")
        for v in vinculos:
            if v.funcion:
                print(f"      → Función #{v.funcion.pk}: {v.funcion.pelicula.titulo} - "
                      f"{v.funcion.fecha_hora.strftime('%d/%m/%Y %H:%M')} - "
                      f"Sala: {v.funcion.sala.nombre} - Estado: {v.funcion.estado}")
            if v.pelicula:
                print(f"      → Película: {v.pelicula.titulo} (ID={v.pelicula.pk})")
    else:
        print(f"   ✨ SIN VÍNCULOS (aplica universalmente)")

# 2. Promociones problemáticas
print("\n\n2. POSIBLES PROBLEMAS")
print("-" * 80)

# 2a. Promociones activas pero con fecha_baja
promos_problema_1 = Promocion.all_objects.filter(
    es_automatica=True,
    activo=True,
    fecha_baja__isnull=False
)
if promos_problema_1.exists():
    print(f"\n⚠️ PROMOCIONES ACTIVAS CON FECHA_BAJA (inconsistencia): {promos_problema_1.count()}")
    for p in promos_problema_1:
        print(f"   - {p.codigo} (ID={p.pk}): activo={p.activo}, fecha_baja={p.fecha_baja}")
else:
    print("\n✅ No hay promociones activas con fecha_baja")

# 2b. Vínculos a funciones/películas inactivas
print("\n\nVERIFICANDO VÍNCULOS A ENTIDADES INACTIVAS...")
vinculos_problema = []
todos_vinculos = VinculoPromocional.objects.all().select_related('promocion', 'funcion', 'pelicula')

for v in todos_vinculos:
    if v.funcion and not v.funcion.activo:
        vinculos_problema.append(f"Vínculo #{v.pk}: Promoción '{v.promocion.codigo}' → Función INACTIVA #{v.funcion.pk}")
    if v.pelicula and not v.pelicula.activo:
        vinculos_problema.append(f"Vínculo #{v.pk}: Promoción '{v.promocion.codigo}' → Película INACTIVA '{v.pelicula.titulo}'")

if vinculos_problema:
    print(f"\n⚠️ VÍNCULOS A ENTIDADES INACTIVAS: {len(vinculos_problema)}")
    for msg in vinculos_problema[:10]:  # Mostrar máximo 10
        print(f"   - {msg}")
    if len(vinculos_problema) > 10:
        print(f"   ... y {len(vinculos_problema) - 10} más")
else:
    print("\n✅ Todos los vínculos apuntan a entidades activas")

# 3. Resumen
print("\n\n3. RESUMEN")
print("-" * 80)
total_promos_activas = Promocion.objects.filter(activo=True, fecha_baja__isnull=True).count()
total_promos_con_vinculos = Promocion.objects.filter(
    activo=True,
    fecha_baja__isnull=True,
    vinculos__isnull=False
).distinct().count()
total_promos_sin_vinculos = total_promos_activas - total_promos_con_vinculos

print(f"Total promociones activas: {total_promos_activas}")
print(f"  - Con vínculos específicos: {total_promos_con_vinculos}")
print(f"  - Sin vínculos (universales): {total_promos_sin_vinculos}")
print(f"Total vínculos activos: {VinculoPromocional.objects.count()}")

print("\n" + "="*80)
print("FIN DEL DIAGNÓSTICO")
print("="*80 + "\n")
