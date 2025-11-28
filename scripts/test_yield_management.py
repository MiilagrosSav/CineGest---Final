"""
Script de prueba para el comando de Yield Management.

Uso:
    python scripts/test_yield_management.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    print('=== Test: Yield Management (DRY RUN) ===\n')
    
    # Ejecutar en modo dry-run con verbosity alta
    call_command('ejecutar_yield_management', '--dry-run', '--verbosity=2')
    
    print('\n=== Test completado ===')
    print('Para ejecutar en modo real (con envíos): python manage.py ejecutar_yield_management')
