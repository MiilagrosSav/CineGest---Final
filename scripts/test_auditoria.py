# scripts/test_auditoria.py
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from auditoria.models import AuditEntry
from cine.models import Pelicula
from datetime import date, timedelta  # ✅ Importar date

print("🧪 Probando sistema de auditoría...")

# Contar registros actuales
count_before = AuditEntry.objects.count()
print(f"📊 Registros antes: {count_before}")

# ✅ Crear una película de prueba con fecha correcta
pelicula = Pelicula.objects.create(
    titulo="Test Auditoría",
    sinopsis="Prueba del sistema",
    director="Test",
    duracion=120,
    fecha_estreno=date.today() + timedelta(days=30)  # ✅ Objeto date
)

# Contar después
count_after = AuditEntry.objects.count()
print(f"📊 Registros después: {count_after}")

if count_after > count_before:
    print("✅ Sistema de auditoría FUNCIONA")
    last_entry = AuditEntry.objects.latest('history_date')
    print(f"📝 Último registro: {last_entry.model_name} - {last_entry.get_history_type_display()}")
else:
    print("❌ Sistema de auditoría NO FUNCIONA")
    print("⚠️ Revisar signals.py y que 'auditoria' esté en INSTALLED_APPS")

# Limpiar
pelicula.delete()
print("\n🧹 Película de prueba eliminada")