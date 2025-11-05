from django.core.management.base import BaseCommand
from cine.models import Formato


class Command(BaseCommand):
    help = 'Crea los formatos de proyección iniciales organizados por categorías'

    def handle(self, *args, **kwargs):
        formatos_iniciales = [
            # 1. Formato_Visual
            {
                'nombre': '2D',
                'descripcion': 'Proyección en 2 dimensiones estándar'
            },
            {
                'nombre': '3D',
                'descripcion': 'Proyección en 3 dimensiones con gafas especiales'
            },
            # 2. Formato_Pantalla
            {
                'nombre': 'Pantalla Standard',
                'descripcion': 'Pantalla de proyección estándar'
            },
            {
                'nombre': 'IMAX',
                'descripcion': 'Sistema de proyección de alta resolución en pantalla gigante'
            },
            {
                'nombre': 'ScreenX',
                'descripcion': 'Proyección panorámica de 270 grados'
            },
            # 3. Formato_Experiencia
            {
                'nombre': 'Experiencia Standard',
                'descripcion': 'Experiencia de cine estándar sin efectos especiales'
            },
            {
                'nombre': '4DX',
                'descripcion': 'Experiencia inmersiva con movimiento, efectos ambientales y sensoriales'
            },
            {
                'nombre': 'D-BOX',
                'descripcion': 'Sistema de asientos con movimiento sincronizado con la película'
            },
            # 4. Formato_Idioma
            {
                'nombre': 'Doblada',
                'descripcion': 'Audio en español doblado'
            },
            {
                'nombre': 'Subtitulada',
                'descripcion': 'Audio original con subtítulos en español'
            },
            {
                'nombre': 'Original',
                'descripcion': 'Audio original sin subtítulos'
            },
        ]

        for formato_data in formatos_iniciales:
            formato, created = Formato.objects.get_or_create(
                nombre=formato_data['nombre'],
                defaults={'descripcion': formato_data['descripcion']}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creado: {formato.nombre}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'○ Ya existe: {formato.nombre}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n¡Formatos listos! Total: {Formato.objects.count()}')
        )
