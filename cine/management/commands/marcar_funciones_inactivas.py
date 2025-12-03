"""
Management command para marcar funciones pasadas como inactivas.
Ejecutar con: python manage.py marcar_funciones_inactivas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from cine.models.funcion import Funcion


class Command(BaseCommand):
    help = 'Marca funciones pasadas como inactivas automáticamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué funciones se marcarían como inactivas sin hacer cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        ahora = timezone.now()
        
        # Buscar funciones cuya fecha_hora ya pasó y no están marcadas como INACTIVA
        funciones_pasadas = Funcion.objects.filter(
            fecha_hora__lt=ahora
        ).exclude(estado='INACTIVA')
        
        total = funciones_pasadas.count()
        
        if total == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ No hay funciones pasadas que necesiten marcarse como inactivas.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY RUN] Se marcarían {total} funciones como inactivas:')
            )
            for funcion in funciones_pasadas[:10]:  # Mostrar solo las primeras 10
                self.stdout.write(f'  - {funcion}')
            if total > 10:
                self.stdout.write(f'  ... y {total - 10} más')
        else:
            # Actualizar en lote
            funciones_pasadas.update(estado='INACTIVA')
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ {total} funciones marcadas como inactivas exitosamente.')
            )
