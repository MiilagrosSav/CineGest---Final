from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from promociones.models.promocion import Promocion


class Command(BaseCommand):
    help = 'Herramienta para auditar y corregir promociones activas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--listar',
            action='store_true',
            help='Listar todas las promociones automáticas vigentes hoy'
        )
        parser.add_argument(
            '--desactivar-todas',
            action='store_true',
            help='Desactivar TODAS las promociones automáticas cambiando su fecha_fin a ayer'
        )
        parser.add_argument(
            '--desactivar',
            type=str,
            help='Desactivar una promoción específica por código (ej: --desactivar automatic)'
        )

    def handle(self, *args, **options):
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        if options['listar']:
            self.stdout.write(self.style.SUCCESS('\n=== PROMOCIONES AUTOMÁTICAS VIGENTES HOY ==='))
            promos = Promocion.objects.filter(
                es_automatica=True,
                fecha_inicio__lte=hoy,
                fecha_fin__gte=hoy
            )
            
            if not promos.exists():
                self.stdout.write(self.style.SUCCESS('✓ No hay promociones automáticas vigentes hoy'))
                return
            
            for p in promos:
                self.stdout.write(f'\n  Código: {p.codigo}')
                self.stdout.write(f'  Nombre: {p.nombre}')
                self.stdout.write(f'  Tipo: {p.tipo_descuento} ({p.valor_descuento})')
                self.stdout.write(f'  Vigencia: {p.fecha_inicio} a {p.fecha_fin}')
                self.stdout.write(f'  Días: "{p.dias_semana}"')
                self.stdout.write(f'  Género req: {p.genero_requerido or "Ninguno"}')
                self.stdout.write(self.style.WARNING(f'  ⚠️ ACTIVA Y APLICÁNDOSE'))
            
            self.stdout.write(f'\n  Total: {promos.count()} promociones activas')
            return

        if options['desactivar_todas']:
            promos = Promocion.objects.filter(es_automatica=True, fecha_fin__gte=hoy)
            count = promos.count()
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('✓ No hay promociones automáticas activas para desactivar'))
                return
            
            self.stdout.write(self.style.WARNING(f'Se van a desactivar {count} promociones:'))
            for p in promos:
                self.stdout.write(f'  - {p.codigo} ({p.nombre})')
            
            confirm = input('\n¿Confirmar desactivación? (escribir "SI" para confirmar): ')
            if confirm != 'SI':
                self.stdout.write(self.style.ERROR('Operación cancelada'))
                return
            
            updated = promos.update(fecha_fin=ayer)
            self.stdout.write(self.style.SUCCESS(f'✓ {updated} promociones desactivadas (fecha_fin cambiada a {ayer})'))
            return

        if options['desactivar']:
            codigo = options['desactivar']
            try:
                promo = Promocion.objects.get(codigo=codigo, es_automatica=True)
                
                if promo.fecha_fin < hoy:
                    self.stdout.write(self.style.WARNING(f'La promoción {codigo} ya está vencida (hasta {promo.fecha_fin})'))
                    return
                
                self.stdout.write(f'\nPromoción a desactivar:')
                self.stdout.write(f'  Código: {promo.codigo}')
                self.stdout.write(f'  Nombre: {promo.nombre}')
                self.stdout.write(f'  Vigencia actual: {promo.fecha_inicio} a {promo.fecha_fin}')
                
                confirm = input(f'\n¿Desactivar "{codigo}" cambiando fecha_fin a {ayer}? (SI/NO): ')
                if confirm != 'SI':
                    self.stdout.write(self.style.ERROR('Operación cancelada'))
                    return
                
                promo.fecha_fin = ayer
                promo.save()
                
                self.stdout.write(self.style.SUCCESS(f'✓ Promoción {codigo} desactivada (fecha_fin = {ayer})'))
                
            except Promocion.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'✗ No se encontró promoción automática con código "{codigo}"'))
                return

        # Si no se pasó ningún argumento, mostrar ayuda
        if not any([options['listar'], options['desactivar_todas'], options['desactivar']]):
            self.stdout.write(self.style.WARNING('\nUso:'))
            self.stdout.write('  python manage.py auditar_promociones --listar')
            self.stdout.write('  python manage.py auditar_promociones --desactivar-todas')
            self.stdout.write('  python manage.py auditar_promociones --desactivar automatic')
