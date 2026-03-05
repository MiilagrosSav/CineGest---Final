"""
Comando para marcar automáticamente como CANCELADA las entradas de funciones que ya pasaron.
Esto aplica a entradas que están en estado VENDIDA o ENTREGADA pero cuya función ya empezó.
Las entradas vencidas (función pasada sin uso) se consideran canceladas automáticamente.

Ejecutar manualmente:
    python manage.py marcar_funciones_pasadas

O configurar como tarea cron (cada 1 hora):
    0 * * * * cd /ruta/proyecto && python manage.py marcar_funciones_pasadas
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.models import Entrada


class Command(BaseCommand):
    help = 'Marca como CANCELADA las entradas de funciones que ya pasaron (sin uso)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué entradas se marcarían sin aplicar cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Obtener fecha/hora actual
        ahora = timezone.now()
        
        # Buscar entradas en estado VENDIDA/ENTREGADA de funciones que ya empezaron
        # Si la función ya empezó y la entrada no fue usada, se considera CANCELADA (expiró)
        entradas_a_cancelar = Entrada.objects.filter(
            estado__in=['VENDIDA', 'ENTREGADA'],
            id_funcion__fecha_hora__lt=ahora  # Función ya empezó
        ).select_related('id_funcion', 'id_pelicula', 'id_venta')
        
        cantidad = entradas_a_cancelar.count()
        
        if cantidad == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ No hay entradas vencidas para cancelar')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'🔍 DRY RUN: Se cancelarían {cantidad} entrada(s) vencida(s):')
            )
            for entrada in entradas_a_cancelar[:10]:  # Mostrar solo primeras 10
                self.stdout.write(
                    f'  - Entrada #{entrada.id_entrada} ({entrada.id_pelicula.titulo}) '
                    f'Función: {entrada.id_funcion.fecha_hora:%d/%m/%Y %H:%M} '
                    f'Estado actual: {entrada.estado}'
                )
            if cantidad > 10:
                self.stdout.write(f'  ... y {cantidad - 10} más')
        else:
            # Marcar todas como CANCELADA
            entradas_actualizadas = 0
            for entrada in entradas_a_cancelar:
                entrada.estado = 'CANCELADA'
                entrada.save()
                entradas_actualizadas += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ {entradas_actualizadas} entrada(s) cancelada(s) automáticamente '
                    f'(funciones que ya empezaron y entradas no usadas)'
                )
            )
