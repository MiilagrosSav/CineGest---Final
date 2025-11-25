#!/usr/bin/env python
"""
Test del flujo completo de descuentos en selección de butacas
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from promociones.models.promocion import Promocion
from promociones.services import calcular_precio_final
from cine.models import Funcion
from decimal import Decimal

print("=" * 70)
print("TEST: Flujo de Descuentos en Selección de Butacas")
print("=" * 70)

# Obtener una función de prueba
funcion = Funcion.objects.first()
if not funcion:
    print("❌ No hay funciones disponibles para probar")
    exit(1)

print(f"\n✓ Función: {funcion.pelicula.titulo}")
print(f"✓ Precio base: ${funcion.precio_base}")

# Obtener una promoción 2x1
promo_2x1 = Promocion.objects.filter(tipo_descuento='2X1').first()
if not promo_2x1:
    print("\n❌ No hay promociones 2x1 disponibles")
    exit(1)

print(f"\n✓ Promoción 2x1: {promo_2x1.codigo}")
print(f"✓ Valor descuento: {promo_2x1.valor_descuento}%")

# Simular cálculo para diferentes cantidades
print("\n" + "-" * 70)
print("Simulación de cálculos de precio:")
print("-" * 70)

for cantidad in [1, 2, 3, 4]:
    total, promo_aplicada, detalle = calcular_precio_final(funcion, cantidad)
    
    print(f"\n{cantidad} entrada(s):")
    if promo_aplicada and promo_aplicada.tipo_descuento == '2X1':
        entradas_pagar = (cantidad // 2) + (cantidad % 2)
        print(f"  - Con 2x1: Pagás {entradas_pagar} entrada(s)")
        print(f"  - Total: ${total}")
        print(f"  - Ahorro: ${funcion.precio_base * cantidad - total}")
    else:
        print(f"  - Sin descuento: ${total}")

# Verificar que calcular_precio_final devuelve la promo correcta
print("\n" + "-" * 70)
print("Verificación de retorno de calcular_precio_final:")
print("-" * 70)

total, promo_ret, detalle = calcular_precio_final(funcion, 2)
if promo_ret:
    print(f"✓ Promoción retornada: {promo_ret.codigo}")
    print(f"✓ Tipo: {promo_ret.tipo_descuento}")
    print(f"✓ Total para 2 entradas: ${total}")
else:
    print("⚠️  No se retornó promoción (verificar FuncionPromocion)")

print("\n" + "=" * 70)
print("✅ TEST COMPLETADO")
print("=" * 70)
print("\nPasos siguientes:")
print("1. Activa una promoción 2x1 desde un link de email")
print("2. Ve a seleccionar butacas")
print("3. Deberías ver:")
print("   - Banner verde con nombre de promoción")
print("   - Descripción del descuento")
print("   - Precio final correcto")
print("   - Total calculado con 2x1")
