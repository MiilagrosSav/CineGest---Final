# scripts/verificar_db.py
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from django.db import connection

print("=" * 70)
print("DIAGNÓSTICO DE BASE DE DATOS")
print("=" * 70)

db_config = connection.settings_dict
print(f"\n📊 Motor: {db_config['ENGINE']}")
print(f"📁 Nombre: {db_config['NAME']}")
print(f"👤 Usuario: {db_config['USER']}")
print(f"🏠 Host: {db_config['HOST']}")
print(f"🔌 Puerto: {db_config['PORT']}")

# Verificar conexión
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"\n✅ CONEXIÓN EXITOSA")
        print(f"🎯 Versión: {version[0]}")
        
        # Contar tablas
        if 'postgresql' in db_config['ENGINE']:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
        else:  # SQLite
            cursor.execute("""
                SELECT COUNT(*) 
                FROM sqlite_master 
                WHERE type='table'
            """)
        
        count = cursor.fetchone()[0]
        print(f"📋 Tablas en la base de datos: {count}")
        
except Exception as e:
    print(f"\n❌ ERROR DE CONEXIÓN: {e}")
    print("\n⚠️ POSIBLES CAUSAS:")
    print("   1. PostgreSQL no está corriendo")
    print("   2. Credenciales incorrectas en .env")
    print("   3. Base de datos no existe")
    print("\n💡 SOLUCIONES:")
    print("   - Verificar que PostgreSQL esté activo")
    print("   - Revisar archivo .env")
    print("   - Crear la base de datos: CREATE DATABASE cinegest;")

print("\n" + "=" * 70)