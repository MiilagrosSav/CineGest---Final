"""
Comando para limpiar registros antiguos de auditoría.

Uso:
    python manage.py cleanup_audit                    # Usa configuración por defecto (90 días)
    python manage.py cleanup_audit --days 30          # Elimina registros mayores a 30 días
    python manage.py cleanup_audit --dry-run          # Simula sin eliminar
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db import models
from auditoria.models import AuditEntry, AuditConfig


class Command(BaseCommand):
    help = 'Limpia registros antiguos de auditoría según política de retención'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            help='Días de retención (por defecto usa AuditConfig.retention_days)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la operación sin eliminar registros',
        )

    def handle(self, *args, **options):
        # Obtener configuración
        config = AuditConfig.load()
        days_to_keep = options.get('days') or config.retention_days
        dry_run = options.get('dry_run', False)
        
        # Calcular fecha de corte
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Contar registros a eliminar
        old_entries = AuditEntry.objects.filter(history_date__lt=cutoff_date)
        count = old_entries.count()
        
        self.stdout.write(self.style.WARNING(f'\n📊 Resumen de Limpieza de Auditoría'))
        self.stdout.write(f'  • Política de retención: {days_to_keep} días')
        self.stdout.write(f'  • Fecha de corte: {cutoff_date.strftime("%d/%m/%Y %H:%M")}')
        self.stdout.write(f'  • Registros totales: {AuditEntry.objects.count()}')
        self.stdout.write(f'  • Registros a eliminar: {count}')
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No hay registros antiguos para eliminar.'))
            return
        
        # Mostrar distribución por modelo
        models_distribution = old_entries.values('model_name').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        if models_distribution:
            self.stdout.write('\n  Modelos más afectados:')
            for item in models_distribution:
                self.stdout.write(f'    - {item["model_name"]}: {item["count"]} registros')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  Modo DRY-RUN: No se eliminarán registros.'))
            return
        
        # Confirmar eliminación
        self.stdout.write(self.style.WARNING(f'\n⚠️  Se eliminarán {count} registros.'))
        confirm = input('¿Continuar? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('❌ Operación cancelada.'))
            return
        
        # Eliminar registros
        self.stdout.write('🔄 Eliminando registros...')
        deleted_count = AuditEntry.cleanup_old_entries(days_to_keep)
        
        # Actualizar configuración
        config.last_cleanup = timezone.now()
        config.save()
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Limpieza completada: {deleted_count} registros eliminados.'))
        self.stdout.write(f'  • Registros restantes: {AuditEntry.objects.count()}')
