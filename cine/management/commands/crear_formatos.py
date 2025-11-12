from django.core.management.base import BaseCommand
from cine.models import Formato


class Command(BaseCommand):
    help = 'Crea los formatos de proyección iniciales organizados por categorías'

    def handle(self, *args, **kwargs):
        formatos_iniciales = [
            # 1. Formato_Visual
            {
                'nombre': '2D',
                'descripcion': 'Proyección en 2 dimensiones estándar',
                'categoria': 'VISUAL'
            },
            {
                'nombre': '3D',
                'descripcion': 'Proyección en 3 dimensiones con gafas especiales',
                'categoria': 'VISUAL'
            },
            # 2. Formato_Pantalla
            {
                'nombre': 'Pantalla Standard',
                'descripcion': 'Pantalla de proyección estándar',
                'categoria': 'PANTALLA'
            },
            {
                'nombre': 'IMAX',
                'descripcion': 'Sistema de proyección de alta resolución en pantalla gigante',
                'categoria': 'PANTALLA'
            },
            {
                'nombre': 'ScreenX',
                'descripcion': 'Proyección panorámica de 270 grados',
                'categoria': 'PANTALLA'
            },
            # 3. Formato_Experiencia
            {
                'nombre': 'Experiencia Standard',
                'descripcion': 'Experiencia de cine estándar sin efectos especiales',
                'categoria': 'EXPERIENCIA'
            },
            {
                'nombre': '4DX',
                'descripcion': 'Experiencia inmersiva con movimiento, efectos ambientales y sensoriales',
                'categoria': 'EXPERIENCIA'
            },
            {
                'nombre': 'D-BOX',
                'descripcion': 'Sistema de asientos con movimiento sincronizado con la película',
                'categoria': 'EXPERIENCIA'
            },
        ]

        for formato_data in formatos_iniciales:
            nombre = formato_data['nombre']
            descripcion = formato_data['descripcion']
            categoria = formato_data['categoria']

            formato, created = Formato.objects.get_or_create(
                nombre=nombre,
                defaults={'descripcion': descripcion, 'categoria': categoria}
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Creado: {formato.nombre} (categoria: {categoria})'))
            else:
                # Si ya existe, actualiza categoria/descripcion si es diferente
                changed = False
                if getattr(formato, 'categoria', None) != categoria:
                    formato.categoria = categoria
                    changed = True
                if getattr(formato, 'descripcion', None) != descripcion:
                    formato.descripcion = descripcion
                    changed = True
                if changed:
                    formato.save()
                    self.stdout.write(self.style.SUCCESS(f'↻ Actualizado: {formato.nombre} (categoria: {categoria})'))
                else:
                    self.stdout.write(self.style.WARNING(f'○ Ya existe: {formato.nombre} (categoria: {formato.categoria})'))

        self.stdout.write(self.style.SUCCESS(f'\n¡Formatos listos! Total: {Formato.objects.count()}'))
