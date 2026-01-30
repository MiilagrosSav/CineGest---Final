# scripts/verificar_archivos_sensibles.py
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

print("=" * 70)
print("VERIFICACIÓN DE ARCHIVOS SENSIBLES")
print("=" * 70)

# Archivos que NO deben versionarse
archivos_sensibles = [
    '.env',
    'db.sqlite3',
    '*.pyc',
    '__pycache__/',
    'staticfiles/',
    'media/uploads/',
    'logs/*.log',
    '*.sqlite3',
    'venv/',
    '.vscode/',
]

# Verificar .gitignore
gitignore_path = ROOT / '.gitignore'

if not gitignore_path.exists():
    print("\n❌ ERROR: .gitignore no existe")
    print("   Crear archivo .gitignore con las siguientes entradas:")
    for archivo in archivos_sensibles:
        print(f"   {archivo}")
else:
    gitignore_content = gitignore_path.read_text(encoding='utf-8')
    
    print("\n🔍 Verificando .gitignore...")
    
    faltantes = []
    for patron in archivos_sensibles:
        if patron not in gitignore_content:
            faltantes.append(patron)
    
    if faltantes:
        print("\n⚠️  Entradas faltantes en .gitignore:")
        for f in faltantes:
            print(f"   - {f}")
    else:
        print("\n✅ .gitignore está completo")

# Verificar archivos que existen pero no deberían versionarse
print("\n🔍 Archivos sensibles existentes:")

archivos_encontrados = []

# .env
if (ROOT / '.env').exists():
    archivos_encontrados.append('.env')
    print("   ⚠️  .env (contiene secretos)")

# db.sqlite3
if (ROOT / 'db.sqlite3').exists():
    archivos_encontrados.append('db.sqlite3')
    print("   ⚠️  db.sqlite3 (base de datos local)")

# staticfiles
if (ROOT / 'staticfiles').exists():
    archivos_encontrados.append('staticfiles/')
    print("   ⚠️  staticfiles/ (archivos generados)")

# __pycache__
pycache_dirs = list(ROOT.rglob('__pycache__'))
if pycache_dirs:
    print(f"   ⚠️  {len(pycache_dirs)} directorios __pycache__")

# .pyc files
pyc_files = list(ROOT.rglob('*.pyc'))
if pyc_files:
    print(f"   ⚠️  {len(pyc_files)} archivos .pyc")

# logs
log_files = list((ROOT / 'logs').glob('*.log')) if (ROOT / 'logs').exists() else []
if log_files:
    print(f"   ⚠️  {len(log_files)} archivos .log")

if not archivos_encontrados and not pycache_dirs and not pyc_files and not log_files:
    print("   ✅ No se encontraron archivos sensibles")

print("\n" + "=" * 70)