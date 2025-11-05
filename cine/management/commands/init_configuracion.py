from django.core.management.base import BaseCommand
from cine.models import ConfiguracionCine


class Command(BaseCommand):
    help = 'Inicializa la configuración del cine con valores por defecto'

    def handle(self, *args, **options):
        """
        Crea o obtiene la configuración del cine.
        Si ya existe, no hace nada.
        """
        configuracion = ConfiguracionCine.load()
        
        if configuracion:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Configuración del cine inicializada: {configuracion.nombre}'
                )
            )
            self.stdout.write(f'  - CUIL/CUIT: {configuracion.cuil_cuit}')
            self.stdout.write(f'  - Teléfono: {configuracion.telefono}')
            self.stdout.write(f'  - Email: {configuracion.email}')
        else:
            self.stdout.write(
                self.style.ERROR('✗ Error al inicializar la configuración')
            )
