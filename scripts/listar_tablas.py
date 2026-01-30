# scripts/listar_tablas.py
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from django.db import connection

print("=" * 70)
print("LISTADO DE TABLAS EN BASE DE DATOS")
print("=" * 70)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    
    tablas = cursor.fetchall()
    
    # Agrupar por prefijo
    grupos = {}
    for tabla in tablas:
        nombre = tabla[0]
        
        if nombre.startswith('auth_'):
            grupo = '🔐 Django Auth'
        elif nombre.startswith('django_'):
            grupo = '⚙️ Django Core'
        elif nombre.startswith('social_'):
            grupo = '🌐 Social Auth'
        elif nombre.startswith('accounts_'):
            grupo = '👤 Accounts'
        elif nombre.startswith('cine_'):
            grupo = '🎬 Cine'
        elif nombre.startswith('ventas_'):
            grupo = '💰 Ventas'
        elif nombre.startswith('promociones_'):
            grupo = '🎉 Promociones'
        elif nombre.startswith('auditoria_'):
            grupo = '📋 Auditoría'
        elif nombre.startswith('reportes_'):
            grupo = '📊 Reportes'
        elif nombre.startswith('valoraciones_'):
            grupo = '⭐ Valoraciones'
        elif nombre in ['peliculas', 'salas', 'funciones', 'sala', 'formato']:
            grupo = '🎬 Cine (legacy)'
        elif nombre in ['usuarios']:
            grupo = '👤 Accounts (legacy)'
        else:
            grupo = '❓ Otros'
        
        if grupo not in grupos:
            grupos[grupo] = []
        grupos[grupo].append(nombre)
    
    # Imprimir agrupado
    for grupo in sorted(grupos.keys()):
        print(f"\n{grupo} ({len(grupos[grupo])} tablas):")
        for tabla in sorted(grupos[grupo]):
            print(f"  - {tabla}")
    
    print(f"\n{'=' * 70}")
    print(f"📊 TOTAL: {len(tablas)} tablas")
    print("=" * 70)