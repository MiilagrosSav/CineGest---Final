from django.core.management.base import BaseCommand

from ventas.services import liberar_reservas_expiradas


class Command(BaseCommand):
    help = 'Libera entradas reservadas/pendientes que excedieron el tiempo configurado en ConfiguracionCine'

    def handle(self, *args, **options):
        liberadas = liberar_reservas_expiradas()
        if liberadas:
            self.stdout.write(f'Se liberaron {liberadas} entradas expiradas.')
        else:
            self.stdout.write('No se encontraron entradas expiradas para liberar.')
