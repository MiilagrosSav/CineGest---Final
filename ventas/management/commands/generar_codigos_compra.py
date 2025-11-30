"""
Management command para generar códigos de compra para ventas existentes
"""
from django.core.management.base import BaseCommand
from ventas.models import Venta
import random
import string


class Command(BaseCommand):
    help = 'Genera códigos de compra para ventas ONLINE existentes que no tienen código'

    def handle(self, *args, **options):
        ventas_sin_codigo = Venta.objects.filter(
            tipo_venta='ONLINE',
            codigo_compra__isnull=True
        )
        
        total = ventas_sin_codigo.count()
        self.stdout.write(f'Encontradas {total} ventas sin código de compra')
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay ventas para procesar'))
            return
        
        generados = 0
        for venta in ventas_sin_codigo:
            # Generar código único
            while True:
                parte1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                parte2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                codigo = f"CG-{parte1}-{parte2}"
                
                # Verificar que no exista
                if not Venta.objects.filter(codigo_compra=codigo).exists():
                    venta.codigo_compra = codigo
                    venta.save(update_fields=['codigo_compra'])
                    generados += 1
                    break
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {generados} códigos de compra generados exitosamente')
        )
