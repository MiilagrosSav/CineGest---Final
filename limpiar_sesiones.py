#!/usr/bin/env python
"""
Script para limpiar todas las sesiones y empezar de cero
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from django.contrib.sessions.models import Session

print("=" * 60)
print("LIMPIEZA DE SESIONES")
print("=" * 60)

# Contar sesiones actuales
count = Session.objects.count()
print(f"\n📊 Sesiones actuales: {count}")

if count > 0:
    respuesta = input("\n¿Deseas eliminar TODAS las sesiones? (s/n): ")
    if respuesta.lower() == 's':
        Session.objects.all().delete()
        print("\n✅ Todas las sesiones eliminadas")
        print("\n🔄 Ahora todas las promociones en sesión se han limpiado")
        print("🎯 Compras normales NO mostrarán promociones")
        print("📧 Solo al activar link de email verás promociones")
    else:
        print("\n❌ Operación cancelada")
else:
    print("\n✅ No hay sesiones para limpiar")

print("\n" + "=" * 60)
