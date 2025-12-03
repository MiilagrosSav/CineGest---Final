"""
Comando para mostrar estadísticas de la auditoría.

Uso:
    python manage.py audit_stats
"""

from django.core.management.base import BaseCommand
from auditoria.models import AuditEntry, AuditConfig


class Command(BaseCommand):
    help = 'Muestra estadísticas de uso de la auditoría'

    def handle(self, *args, **options):
        stats = AuditEntry.get_statistics()
        config = AuditConfig.load()
        
        self.stdout.write(self.style.SUCCESS('\n📊 ESTADÍSTICAS DE AUDITORÍA\n'))
        
        # Resumen general
        self.stdout.write(self.style.WARNING('📈 Resumen General:'))
        self.stdout.write(f'  • Total de registros: {stats["total_entries"]:,}')
        self.stdout.write(f'  • Últimos 30 días: {stats["entries_last_30_days"]:,}')
        self.stdout.write(f'  • Últimos 7 días: {stats["entries_last_7_days"]:,}')
        
        # Rango de fechas
        if stats['oldest_entry'] and stats['newest_entry']:
            self.stdout.write(f'\n  • Registro más antiguo: {stats["oldest_entry"].history_date.strftime("%d/%m/%Y %H:%M")}')
            self.stdout.write(f'  • Registro más reciente: {stats["newest_entry"].history_date.strftime("%d/%m/%Y %H:%M")}')
        
        # Por tipo de operación
        self.stdout.write(self.style.WARNING('\n🔄 Por Tipo de Operación:'))
        type_names = {'+': 'Creaciones', '~': 'Actualizaciones', '-': 'Eliminaciones'}
        for item in stats['by_type']:
            type_display = type_names.get(item['history_type'], item['history_type'])
            self.stdout.write(f'  • {type_display}: {item["count"]:,}')
        
        # Por modelo
        self.stdout.write(self.style.WARNING('\n📦 Top 10 Modelos (más auditados):'))
        for idx, item in enumerate(stats['by_model'], 1):
            self.stdout.write(f'  {idx}. {item["model_name"]}: {item["count"]:,} registros')
        
        # Configuración
        self.stdout.write(self.style.WARNING('\n⚙️  Configuración:'))
        self.stdout.write(f'  • Retención: {config.retention_days} días')
        self.stdout.write(f'  • Limpieza automática: {"✅ Habilitada" if config.auto_cleanup_enabled else "❌ Deshabilitada"}')
        if config.last_cleanup:
            self.stdout.write(f'  • Última limpieza: {config.last_cleanup.strftime("%d/%m/%Y %H:%M")}')
        
        if config.excluded_models:
            self.stdout.write(f'  • Modelos excluidos: {config.excluded_models}')
        
        # Recomendaciones
        if stats['total_entries'] > 100000:
            self.stdout.write(self.style.ERROR('\n⚠️  ADVERTENCIA: Más de 100K registros.'))
            self.stdout.write('  Considera ejecutar: python manage.py cleanup_audit')
        
        self.stdout.write('\n')
