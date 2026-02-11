import re
import logging
from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from simple_history.models import HistoricalRecords
from cine.models.genero import Genero

logger = logging.getLogger(__name__)

class Pelicula(models.Model):
    """
    Modelo para representar una película en el cine.
    """
    # Opciones para clasificación
    CLASIFICACION_CHOICES = [
        ('ATP', 'Apta para todo público'),
        ('+13', 'Mayores de 13 años'),
        ('+16', 'Mayores de 16 años'),
        ('+18', 'Mayores de 18 años'),
    ]

    titulo = models.CharField(
        max_length=200,
        blank=False,
        help_text="El título de la película."
    )
    sinopsis = models.TextField(help_text="Una breve descripción de la trama.")
    director = models.CharField(
        max_length=100,
        blank=False,
        help_text="El director de la película."
    )
    # Ahora soportamos múltiples géneros por película
    generos = models.ManyToManyField(Genero, related_name='peliculas', blank=True)
    duracion = models.PositiveIntegerField(
        blank=False,
        help_text="La duración en minutos."
    )
    fecha_estreno = models.DateField(
        null=False,
        blank=False,
        help_text="La fecha de estreno en cines."
    )
    
    # Clasificación por edad
    clasificacion = models.CharField(
        max_length=10,
        choices=CLASIFICACION_CHOICES,
        default='ATP',
        help_text="Clasificación por edad de la película."
    )
    
    # Campo para la imagen de portada
    imagen_portada = models.ImageField(
        upload_to='portadas_peliculas/', 
        blank=True, 
        default='', 
        help_text="La imagen de portada o póster de la película."
    )
    
    # Flags de control para promociones
    es_estreno = models.BooleanField(
        default=False,
        help_text="Indica si es un lanzamiento reciente."
    )
    acepta_promociones = models.BooleanField(
        default=True,
        help_text="si lo presiona bloquea cualquier descuento."
    )
    anio_estreno = models.PositiveIntegerField(
        editable=False,
        null=False,
        blank=True,
        help_text="Año de estreno calculado automáticamente desde fecha_estreno"
    )

    def __str__(self):
        return self.titulo

    def get_genero_display(self):
        """Compatibilidad con plantillas: devuelve géneros como cadena separada por comas."""
        try:
            return ', '.join([g.nombre for g in self.generos.all()])
        except Exception:
            return ''

    def tiene_entradas_vendidas(self):
        """
        Verifica si esta película tiene funciones con entradas vendidas.

        Returns:
            bool: True si tiene entradas vendidas, False si no
        """
        return self.funciones.filter(
            entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA', 'RESERVADA']
        ).exists()

    def clean(self):
        """
        Validaciones de integridad y normalización de datos.
        """
        super().clean()  # ✅ CORREGIDO: Con paréntesis

        # ========================================================================
        # 0. VALIDACIÓN: Bloqueo de cambio de título si tiene ventas (MOVIDO AQUÍ)
        # ========================================================================
        if self.pk:  # Solo si es una edición
            try:
                pelicula_original = Pelicula.objects.get(pk=self.pk)

                # Si el título cambió
                if pelicula_original.titulo != self.titulo:
                    # Verificar si tiene funciones con entradas vendidas
                    if self.tiene_entradas_vendidas():
                        # ❌ BLOQUEO: No permitir cambio de título
                        raise ValidationError({
                            'titulo': f"PROHIBIDO: No se puede cambiar el título de la película "
                                     f"'{pelicula_original.titulo}' porque ya tiene funciones con entradas vendidas. "
                                     f"Por contrato con el cliente, esta información es INMUTABLE."
                        })

                    # Si tiene funciones pero sin ventas, solo registrar advertencia en log
                    elif self.funciones.exists():
                        logger.warning(
                            f"[PELICULA] Título modificado: '{pelicula_original.titulo}' → '{self.titulo}' "
                            f"(ID: {self.pk}). La película tiene funciones programadas pero sin ventas aún."
                        )

            except Pelicula.DoesNotExist:
                pass

        # ========================================================================
        # 1. NORMALIZACIÓN: Limpieza de espacios
        # ========================================================================
        if self.titulo:
            self.titulo = " ".join(self.titulo.split())

            if re.search(r'[<>{}\[\]\\]', self.titulo):
                raise ValidationError({'titulo': "El título contiene caracteres no permitidos por seguridad."})

            if not re.search(r'[a-zA-Z0-9]{2,}', self.titulo):
                raise ValidationError({
                    'titulo': f"El título '{self.titulo}' es demasiado corto o no contiene caracteres válidos."
                })

        if self.director:
            # Limpieza de espacios
            self.director = " ".join(self.director.split())

            # Regex: Mínimo 2 caracteres alfanuméricos para el nombre del director
            if re.search(r'\d', self.director):
                raise ValidationError({
                    'director': f"PROHIBIDO: El nombre del director '{self.director}' no puede contener números."
                })

            # B. Regex: Mínimo 2 letras (evita ".", "x", "-")
            # Usamos [a-zA-ZáéíóúÁÉÍÓÚñÑ] para permitir tildes y eñes
            if not re.search(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]{2,}', self.director):
                raise ValidationError({
                    'director': f"El nombre del director '{self.director}' es demasiado corto o inválido."
                })

        # ========================================================================
        # 2. VALIDACIÓN: Títulos y Directores no pueden ser puramente numéricos
        # ========================================================================
        def es_numero_puro(texto):
            try:
                float(texto.strip())
                return True
            except ValueError:
                return False

        if self.titulo and es_numero_puro(self.titulo):
            raise ValidationError({
                'titulo': f"PROHIBIDO: El título '{self.titulo}' no puede ser solo un número. "
                          "Debe ser un nombre descriptivo."
            })

        if self.director and es_numero_puro(self.director):
            raise ValidationError({
                'director': f"PROHIBIDO: El nombre del director '{self.director}' no puede ser un número."
            })

        # ========================================================================
        # 3. VALIDACIÓN: Fecha de estreno
        # ========================================================================
        if self.fecha_estreno:
            # Validar que el año no sea absurdamente antiguo (antes del cine)
            if self.fecha_estreno.year < 1888:  # Primer película: 1888
                raise ValidationError({
                    'fecha_estreno': f"La fecha de estreno no puede ser anterior a 1888 (invención del cine)."
                })

            # Solo validar "no pasado" para películas NUEVAS
            # Permitir editar películas antiguas sin error
            if not self.pk and self.fecha_estreno < date.today():
                raise ValidationError({
                    'fecha_estreno': f"La fecha de estreno {self.fecha_estreno} no puede ser anterior a hoy "
                                    "para películas nuevas."
                })

        # ========================================================================
        # 4. VALIDACIÓN: Duración razonable
        # ========================================================================
        if self.duracion and (self.duracion < 30 or self.duracion > 300):
            raise ValidationError({
                'duracion': 'La duración debe estar entre 30 y 300 minutos (5 horas máximo).'
            })

        # ========================================================================
        # 5. VALIDACIÓN: Unicidad de título + año (para mostrar error en formulario)
        # ========================================================================
        # Calcular el año para la validación de unicidad
        if self.fecha_estreno:
            anio_a_validar = self.fecha_estreno.year

            # Buscar películas con el mismo título y año
            peliculas_existentes = Pelicula.objects.filter(
                titulo=self.titulo,
                anio_estreno=anio_a_validar
            )

            # Si estamos editando, excluir la película actual
            if self.pk:
                peliculas_existentes = peliculas_existentes.exclude(pk=self.pk)

            # Si existe otra película con el mismo título y año, lanzar error
            if peliculas_existentes.exists():
                raise ValidationError({
                    'titulo': f"Ya existe una película con el título '{self.titulo}' estrenada en {anio_a_validar}. "
                             f"Por favor, verifica el título o selecciona otro año de estreno."
                })

    def save(self, *args, **kwargs):
        """
        Ejecutar validaciones CRÍTICAS y sincronización de campos antes de guardar.

        ✅ ARQUITECTURA DE SOFTWARE - Validaciones implementadas:
        1. Sincronización automática de anio_estreno desde fecha_estreno
        2. Validaciones completas mediante full_clean()
        3. Título no puede ser un número (validado en clean())
        4. Director no puede ser un número (validado en clean())
        5. Fecha de estreno debe ser >= 1888
        6. Bloqueo de cambio de título si ya tiene funciones con ventas (validado en clean())
        """

        # ========================================================================
        # 1. SINCRONIZACIÓN: Calcular anio_estreno desde fecha_estreno
        # ========================================================================
        # CRÍTICO: Este campo DEBE tener valor para la UniqueConstraint
        if self.fecha_estreno:
            self.anio_estreno = self.fecha_estreno.year
        else:
            # Si por alguna razón fecha_estreno es None (aunque no debería),
            # evitar que anio_estreno quede como None
            raise ValidationError({
                'fecha_estreno': 'La fecha de estreno es obligatoria.'
            })

        # ========================================================================
        # 2. VALIDACIÓN COMPLETA: Ejecutar clean() y validaciones de constraints
        # ========================================================================
        # full_clean() ejecuta:
        # - clean_fields(): Valida cada campo individualmente
        # - clean(): Nuestras validaciones personalizadas (incluyendo bloqueo de título)
        # - validate_unique(): Verifica UniqueConstraints
        self.full_clean()

        # ========================================================================
        # 3. GUARDAR EN BASE DE DATOS
        # ========================================================================
        super().save(*args, **kwargs)

    def get_valoraciones_stats(self):
        """
        Devuelve estadísticas de valoraciones para esta película.
        Returns: dict con 'promedio', 'total', 'estrellas_llenas', 'estrellas_vacias'
        """
        from django.db.models import Avg, Count
        from valoraciones.models import Valoracion
        
        stats = Valoracion.objects.filter(pelicula=self).aggregate(
            promedio=Avg('puntuacion'),
            total=Count('id')
        )
        
        promedio = stats['promedio'] or 0
        total = stats['total'] or 0
        
        # Calcular estrellas para display (truncar al entero, no redondear)
        # Usar int() en lugar de round() para evitar 6 estrellas totales
        estrellas_llenas = int(promedio) if promedio > 0 else 0
        estrellas_vacias = 5 - estrellas_llenas
        
        return {
            'promedio': round(promedio, 1),
            'total': total,
            'estrellas_llenas': estrellas_llenas,
            'estrellas_vacias': estrellas_vacias,
        }

    @property
    def promedio_calificacion(self):
        """
        Retorna el promedio de las valoraciones (puntuacion) asociadas a esta película.
        Devuelve un float redondeado a una cifra (ej: 4.5) o 0 si no hay valoraciones.
        """
        from django.db.models import Avg
        from valoraciones.models import Valoracion

        stats = Valoracion.objects.filter(pelicula=self).aggregate(promedio=Avg('puntuacion'))
        promedio = stats.get('promedio') or 0
        try:
            return round(float(promedio), 1)
        except Exception:
            return 0.0

    # historial de cambios
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Película"
        verbose_name_plural = "Películas"
        ordering = ['-fecha_estreno', 'titulo']
        db_table = "peliculas"  # 🎬 Nombre personalizado de la tabla

        # ✅ DBA: Restricciones a nivel de base de datos para blindar integridad
        constraints = [
            models.UniqueConstraint(
                fields=['titulo', 'anio_estreno'],
                name='unique_pelicula_titulo_anio',
                violation_error_message='Ya existe una película con este título en el mismo año'
            )
        ]
