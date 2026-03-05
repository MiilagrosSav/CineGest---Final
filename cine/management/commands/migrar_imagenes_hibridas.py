"""
Comando de Django para migrar imágenes existentes al sistema híbrido.

Este comando procesa todas las películas y configuraciones que tienen imágenes
en los campos legacy (imagen_portada, logo) y las migra al sistema híbrido
(imagen_red + imagen_local).

Uso:
    python manage.py migrar_imagenes_hibridas
    python manage.py migrar_imagenes_hibridas --solo-peliculas
    python manage.py migrar_imagenes_hibridas --solo-configuracion
    python manage.py migrar_imagenes_hibridas --forzar  # Reemplazar imágenes existentes
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from cine.models import Pelicula, ConfiguracionCine
from cine.image_utils import procesar_imagen_hibrida
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migra imágenes existentes del sistema legacy al sistema híbrido (Cloudinary + Local)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-peliculas',
            action='store_true',
            help='Migrar solo las imágenes de películas',
        )
        parser.add_argument(
            '--solo-configuracion',
            action='store_true',
            help='Migrar solo el logo de la configuración del cine',
        )
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Forzar migración incluso si ya existe imagen_red o imagen_local',
        )
        parser.add_argument(
            '--skip-cloudinary',
            action='store_true',
            help='Migrar solo a almacenamiento local, sin intentar subir a Cloudinary',
        )

    def handle(self, *args, **options):
        solo_peliculas = options['solo_peliculas']
        solo_configuracion = options['solo_configuracion']
        forzar = options['forzar']
        skip_cloudinary = options['skip_cloudinary']

        # Si se especifican ambos o ninguno, migrar todo
        migrar_peliculas = solo_peliculas or not solo_configuracion
        migrar_configuracion = solo_configuracion or not solo_peliculas

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('MIGRACIÓN DE IMÁGENES AL SISTEMA HÍBRIDO'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if skip_cloudinary:
            self.stdout.write(self.style.WARNING('⚠️  Modo solo local: No se subirá a Cloudinary'))
        
        total_peliculas_migradas = 0
        total_peliculas_saltadas = 0
        configuracion_migrada = False

        # ====================================================================
        # MIGRAR PELÍCULAS
        # ====================================================================
        if migrar_peliculas:
            self.stdout.write('\n' + self.style.MIGRATE_HEADING('📽️  Migrando imágenes de películas...'))
            
            peliculas = Pelicula.objects.all()
            total_peliculas = peliculas.count()
            
            if total_peliculas == 0:
                self.stdout.write(self.style.WARNING('   No hay películas para migrar.'))
            else:
                for idx, pelicula in enumerate(peliculas, 1):
                    self.stdout.write(f'\n   [{idx}/{total_peliculas}] {pelicula.titulo}')
                    
                    # Determinar si debemos procesar esta película
                    tiene_imagen_legacy = bool(pelicula.imagen_portada)
                    tiene_imagen_red = bool(pelicula.imagen_red)
                    tiene_imagen_local = bool(pelicula.imagen_local)
                    
                    # Saltar si no hay imagen legacy
                    if not tiene_imagen_legacy:
                        self.stdout.write(self.style.WARNING('      ⊘ Sin imagen legacy, saltando...'))
                        total_peliculas_saltadas += 1
                        continue
                    
                    # Saltar si ya tiene imágenes híbridas y no se forzó
                    if (tiene_imagen_red or tiene_imagen_local) and not forzar:
                        self.stdout.write(self.style.WARNING(
                            '      ⊘ Ya tiene imágenes híbridas, saltando... (usa --forzar para reemplazar)'
                        ))
                        total_peliculas_saltadas += 1
                        continue
                    
                    # Procesar la imagen
                    try:
                        with transaction.atomic():
                            # Abrir el archivo de la imagen legacy
                            pelicula.imagen_portada.open('rb')
                            
                            # Procesar con el sistema híbrido
                            if skip_cloudinary:
                                # Solo optimizar y guardar local
                                from cine.image_utils import optimizar_imagen
                                imagen_optimizada = optimizar_imagen(pelicula.imagen_portada.file)
                                pelicula.imagen_local = imagen_optimizada
                                self.stdout.write(self.style.SUCCESS('      ✓ Guardado en local'))
                            else:
                                resultado = procesar_imagen_hibrida(
                                    imagen=pelicula.imagen_portada.file,
                                    folder='peliculas/portadas',
                                    instancia_modelo=pelicula
                                )
                                
                                # Asignar resultados
                                if resultado.get('imagen_local'):
                                    pelicula.imagen_local = resultado['imagen_local']
                                    self.stdout.write(self.style.SUCCESS('      ✓ Guardado en local'))
                                
                                if resultado.get('cloudinary_public_id'):
                                    pelicula.imagen_red = resultado['cloudinary_public_id']
                                    self.stdout.write(self.style.SUCCESS('      ✓ Subido a Cloudinary'))
                                elif not skip_cloudinary:
                                    self.stdout.write(self.style.WARNING('      ⚠ Cloudinary no disponible'))
                            
                            # Guardar los cambios
                            # Usar update_fields para evitar ejecutar el procesamiento de nuevo
                            pelicula.save(update_fields=['imagen_local', 'imagen_red'])
                            
                            total_peliculas_migradas += 1
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'      ✗ Error: {str(e)}'))
                        logger.error(f'Error al migrar película {pelicula.pk}: {e}', exc_info=True)

        # ====================================================================
        # MIGRAR CONFIGURACIÓN DEL CINE
        # ====================================================================
        if migrar_configuracion:
            self.stdout.write('\n' + self.style.MIGRATE_HEADING('🏢  Migrando logo de configuración del cine...'))
            
            try:
                config = ConfiguracionCine.load()
                
                # Determinar si debemos procesar
                tiene_logo_legacy = bool(config.logo)
                tiene_logo_red = bool(config.logo_red)
                tiene_logo_local = bool(config.logo_local)
                
                if not tiene_logo_legacy:
                    self.stdout.write(self.style.WARNING('   ⊘ Sin logo legacy, saltando...'))
                elif (tiene_logo_red or tiene_logo_local) and not forzar:
                    self.stdout.write(self.style.WARNING(
                        '   ⊘ Ya tiene logo híbrido, saltando... (usa --forzar para reemplazar)'
                    ))
                else:
                    # Procesar el logo
                    try:
                        with transaction.atomic():
                            # Abrir el archivo del logo legacy
                            config.logo.open('rb')
                            
                            # Procesar con el sistema híbrido
                            if skip_cloudinary:
                                from cine.image_utils import optimizar_imagen
                                logo_optimizado = optimizar_imagen(config.logo.file)
                                config.logo_local = logo_optimizado
                                self.stdout.write(self.style.SUCCESS('   ✓ Guardado en local'))
                            else:
                                resultado = procesar_imagen_hibrida(
                                    imagen=config.logo.file,
                                    folder='cine/logos',
                                    instancia_modelo=config
                                )
                                
                                # Asignar resultados
                                if resultado.get('imagen_local'):
                                    config.logo_local = resultado['imagen_local']
                                    self.stdout.write(self.style.SUCCESS('   ✓ Guardado en local'))
                                
                                if resultado.get('cloudinary_public_id'):
                                    config.logo_red = resultado['cloudinary_public_id']
                                    self.stdout.write(self.style.SUCCESS('   ✓ Subido a Cloudinary'))
                                elif not skip_cloudinary:
                                    self.stdout.write(self.style.WARNING('   ⚠ Cloudinary no disponible'))
                            
                            # Guardar los cambios
                            config.save(update_fields=['logo_local', 'logo_red'])
                            configuracion_migrada = True
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'   ✗ Error: {str(e)}'))
                        logger.error(f'Error al migrar logo de configuración: {e}', exc_info=True)
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ✗ Error al cargar configuración: {str(e)}'))

        # ====================================================================
        # RESUMEN FINAL
        # ====================================================================
        self.stdout.write('\n' + self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('RESUMEN DE MIGRACIÓN'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if migrar_peliculas:
            self.stdout.write(f'📽️  Películas migradas: {total_peliculas_migradas}')
            self.stdout.write(f'   Películas saltadas: {total_peliculas_saltadas}')
        
        if migrar_configuracion:
            status = '✓ Migrado' if configuracion_migrada else '⊘ No migrado'
            self.stdout.write(f'🏢  Logo de configuración: {status}')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Migración completada exitosamente'))
