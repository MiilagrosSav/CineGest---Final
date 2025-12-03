"""
Script de prueba para verificar el constraint parcial de codigo_compra
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from ventas.models import Venta
from accounts.models import Cliente
from django.contrib.auth import get_user_model

User = get_user_model()

# Buscar un cliente existente
cliente = Cliente.objects.first()

if not cliente:
    print("❌ No hay clientes en la base de datos")
else:
    print(f"✅ Usando cliente: {cliente.usuario.username}")
    
    # Probar crear múltiples ventas PRESENCIALES con codigo_compra vacío
    print("\n🔍 Prueba 1: Crear 3 ventas presenciales (codigo_compra vacío)")
    try:
        for i in range(3):
            venta = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='PRESENCIAL',
                estado='CONFIRMADA',
                medio_pago='EFECTIVO',
                codigo_compra=''  # Explícitamente vacío
            )
            print(f"  ✅ Venta presencial #{venta.id_venta} creada (codigo_compra='{venta.codigo_compra}')")
        print("✅ ÉXITO: Múltiples ventas presenciales con codigo_compra vacío permitidas")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Probar crear ventas ONLINE con códigos únicos
    print("\n🔍 Prueba 2: Crear 2 ventas online (código auto-generado)")
    try:
        for i in range(2):
            venta = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='ONLINE',
                estado='CONFIRMADA',
                medio_pago='MERCADOPAGO'
                # codigo_compra se genera automáticamente
            )
            print(f"  ✅ Venta online #{venta.id_venta} creada (codigo_compra='{venta.codigo_compra}')")
        print("✅ ÉXITO: Ventas online con códigos únicos generados automáticamente")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Probar duplicar un código (debe fallar)
    print("\n🔍 Prueba 3: Intentar duplicar código de compra (debe fallar)")
    try:
        venta1 = Venta.objects.create(
            id_cliente=cliente,
            tipo_venta='ONLINE',
            estado='CONFIRMADA',
            medio_pago='MERCADOPAGO',
            codigo_compra='TEST-DUPLICADO'
        )
        print(f"  ✅ Primera venta con TEST-DUPLICADO creada (ID: {venta1.id_venta})")
        
        venta2 = Venta.objects.create(
            id_cliente=cliente,
            tipo_venta='ONLINE',
            estado='CONFIRMADA',
            medio_pago='MERCADOPAGO',
            codigo_compra='TEST-DUPLICADO'
        )
        print(f"  ❌ PROBLEMA: Se permitió duplicar el código (ID: {venta2.id_venta})")
    except Exception as e:
        print(f"  ✅ CORRECTO: Duplicate key error detectado - {str(e)[:100]}")
    
    print("\n" + "="*70)
    print("🎉 PRUEBAS COMPLETADAS")
    print("="*70)
