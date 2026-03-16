"""
Comando de limpieza para el modelo Director.

Realiza dos operaciones:
1. Normaliza nombres y apellidos de todos los directores (title-case, sin espacios extra).
2. Detecta y fusiona registros duplicados (mismo nombre+apellido).
   Al fusionar, si uno tiene tmdb_id y el otro no, conserva el que tiene tmdb_id
   y reasigna todas las películas del duplicado.

Uso:
    python manage.py limpiar_directores_duplicados [--dry-run]
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from cine.models import Director

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Normaliza y deduplica el modelo Director'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué cambios se harían sin aplicarlos',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        v = options['verbosity']

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No se realizarán cambios'))

        # --- Paso 1: normalizar nombres ---
        normalizados = 0
        for director in Director.objects.all():
            nombre_norm = ' '.join((director.nombre or '').strip().split()).title()
            apellido_norm = ' '.join((director.apellido or '').strip().split()).title()
            if director.nombre != nombre_norm or director.apellido != apellido_norm:
                if v >= 2:
                    self.stdout.write(
                        f'  Normalizar: [{director.pk}] "{director.nombre} {director.apellido}" '
                        f'→ "{nombre_norm} {apellido_norm}"'
                    )
                if not dry_run:
                    Director.objects.filter(pk=director.pk).update(
                        nombre=nombre_norm, apellido=apellido_norm
                    )
                normalizados += 1

        self.stdout.write(f'Directores normalizados: {normalizados}')

        # --- Paso 2: detectar duplicados (mismo nombre+apellido, cualquier combinación de tmdb_id) ---
        grupos_dup = (
            Director.objects.values('nombre', 'apellido')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
        )

        fusiones = 0
        for grupo in grupos_dup:
            nombre = grupo['nombre']
            apellido = grupo['apellido']
            registros = list(
                Director.objects.filter(nombre=nombre, apellido=apellido).order_by('pk')
            )
            # Preferir el registro que ya tiene tmdb_id como "principal"
            con_tmdb = [d for d in registros if d.tmdb_id]
            sin_tmdb = [d for d in registros if not d.tmdb_id]
            if con_tmdb:
                principal = con_tmdb[0]
                duplicados = sin_tmdb + con_tmdb[1:]
            else:
                principal = registros[0]
                duplicados = registros[1:]

            self.stdout.write(
                f'Duplicado encontrado: "{nombre} {apellido}" — '
                f'conservar pk={principal.pk}, eliminar {[d.pk for d in duplicados]}'
            )

            if not dry_run:
                with transaction.atomic():
                    for dup in duplicados:
                        # Reasignar películas que apuntan al duplicado
                        peliculas_reasignadas = dup.peliculas.all()
                        count_peliculas = peliculas_reasignadas.count()
                        peliculas_reasignadas.update(director=principal)
                        if count_peliculas and v >= 2:
                            self.stdout.write(
                                f'  Reasignadas {count_peliculas} película(s) de pk={dup.pk} → pk={principal.pk}'
                            )
                        # Copiar tmdb_id si el principal no lo tiene
                        if dup.tmdb_id and not principal.tmdb_id:
                            principal.tmdb_id = dup.tmdb_id
                            principal.save(update_fields=['tmdb_id'])
                        dup.delete()
                fusiones += 1

        self.stdout.write(f'Grupos fusionados: {fusiones}')
        self.stdout.write(self.style.SUCCESS('=== Limpieza completada ==='))
