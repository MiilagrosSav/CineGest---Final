import re
import logging
from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from django.utils import timezone
from simple_history.models import HistoricalRecords
from cine.models.genero import Genero
from core.mixins import SoftDeleteMixin
from cloudinary.models import CloudinaryField
from cine.image_utils import procesar_imagen_hibrida, verificar_conexion_cloudinary

logger = logging.getLogger(__name__)

class Pelicula(SoftDeleteMixin, models.Model):
    """
    Modelo para representar una película en el cine.
    """

    titulo = models.CharField(
        max_length=200,
        blank=False,
        help_text="El título de la película."
    )
    sinopsis = models.TextField(help_text="Una breve descripción de la trama.")
    director = models.ForeignKey(
        'Director',
        on_delete=models.PROTECT,
        related_name='peliculas',
        help_text='Director principal de la pelicula.'
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
    
    # Clasificación por edad - Ahora es FK a modelo Clasificacion
    clasificacion = models.ForeignKey(
        'Clasificacion',
        on_delete=models.PROTECT,
        related_name='peliculas',
        help_text="Clasificación por edad de la película"
    )
    
    # ========================================================================
    # SISTEMA HÍBRIDO DE IMÁGENES (Cloudinary + Local)
    # ========================================================================
    # Campo principal: Cloudinary (almacenamiento en la nube)
    imagen_red = CloudinaryField(
        'imagen',
        folder='peliculas/portadas',
        blank=True,
        null=True,
        help_text="Imagen almacenada en Cloudinary (requiere conexión a internet)"
    )
    
    # Campo de respaldo: Almacenamiento local
    imagen_local = models.ImageField(
        upload_to='portadas_peliculas/', 
        blank=True, 
        null=True,
        help_text="Copia local optimizada de la imagen (respaldo sin internet)"
    )
    
    # Campo legacy para retrocompatibilidad (DEPRECADO - usar get_poster_url)
    imagen_portada = models.ImageField(
        upload_to='portadas_peliculas/', 
        blank=True, 
        default='',
        help_text="[DEPRECADO] Usar imagen_red/imagen_local + get_poster_url"
    )
    
    # Flags de control para promociones
    es_estreno = models.BooleanField(
        default=False,
        
    )
    acepta_promociones = models.BooleanField(
        default=True,
        
    )
    anio_estreno = models.PositiveIntegerField(
        editable=False,
        null=False,
        blank=True,
        help_text="Año de estreno calculado automáticamente desde fecha_estreno"
    )
    
    # Campo para el trailer de YouTube desde TMDB
    youtube_trailer_key = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="ID del video de YouTube del trailer oficial (ej: 'dQw4w9WgXcQ')"
    )

    def __str__(self):
        return self.titulo

    @property
    def get_poster_url(self):
        """
        Devuelve la URL del póster de la película.

        Lógica local-first (optimización de rendimiento):
        1. Usa imagen_local
        2. Si no existe, usa imagen_portada (retrocompatibilidad)
        3. Si no hay ninguna imagen, devuelve placeholder
        
        Returns:
            str: URL de la imagen (Cloudinary, local o placeholder)
        """
        # Fallback 1: Usar imagen local optimizada
        if self.imagen_local:
            try:
                return self.imagen_local.url
            except Exception:
                pass
        
        # Fallback 2: Retrocompatibilidad con imagen_portada legacy
        if self.imagen_portada:
            try:
                return self.imagen_portada.url
            except Exception:
                pass
        
        # Fallback 3: Imagen placeholder
        from django.templatetags.static import static
        return static('img/no-poster.jpg')

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

            if not re.search(r'[a-zA-Z0-9]{1,}', self.titulo):
                raise ValidationError({
                    'titulo': f"El título '{self.titulo}' es demasiado corto o no contiene caracteres válidos."
                })


        # ========================================================================
        # 2. VALIDACIÓN: Fecha de estreno
        # ========================================================================
        if self.fecha_estreno:
            # Validar que el año no sea absurdamente antiguo (antes del cine)
            if self.fecha_estreno.year < 1888:  # Primer película: 1888
                raise ValidationError({
                    'fecha_estreno': f"La fecha de estreno no puede ser anterior a 1888 (invención del cine)."
                })
            
            # Validar que no sea más de 3 años en el futuro
            from datetime import timedelta
            hoy = timezone.now().date()
            fecha_maxima = hoy + timedelta(days=365*3)
            if self.fecha_estreno > fecha_maxima:
                raise ValidationError({
                    'fecha_estreno': f"La fecha de estreno no puede ser más de 3 años en el futuro. "
                                    f"Límite máximo: {fecha_maxima.strftime('%d/%m/%Y')}"
                })

        # ========================================================================
        # 3. VALIDACIÓN: Duración razonable
        # ========================================================================
        if self.duracion and (self.duracion < 30 or self.duracion > 300):
            raise ValidationError({
                'duracion': 'La duración debe estar entre 30 y 300 minutos (5 horas máximo).'
            })

        # ========================================================================
        # 4. VALIDACIÓN: Unicidad de título + año (para mostrar error en formulario)
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
        4. Fecha de estreno debe ser >= 1888
        5. Bloqueo de cambio de título si ya tiene funciones con ventas (validado en clean())
        """

        # ========================================================================
        # 0. NORMALIZACIÓN: Homogeneización de datos (Data Cleaning)
        # ========================================================================
        if self.titulo:
            # Eliminar espacios innecesarios y aplicar Title Case
            self.titulo = self.titulo.strip().title()
            # Corregir letras repetidas 3 o más veces (ej: "Holaaa" -> "Holaa")
            self.titulo = re.sub(r'(.)\1{2,}', r'\1\1', self.titulo)
        

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
        # 1.5 PROCESAMIENTO HÍBRIDO DE IMÁGENES (Cloudinary + Local)
        # ========================================================================
        # Detectar si hay una nueva imagen subida
        imagen_nueva = None
        
        # Verificar si hay una imagen en imagen_portada (campo legacy/formulario)
        if self.imagen_portada and hasattr(self.imagen_portada, 'file'):
            imagen_nueva = self.imagen_portada
        # O si se subió directamente a imagen_local
        elif self.imagen_local and hasattr(self.imagen_local, 'file'):
            imagen_nueva = self.imagen_local
        
        # Procesar la imagen si hay una nueva
        if imagen_nueva:
            try:
                # Procesar imagen con el sistema híbrido
                resultado = procesar_imagen_hibrida(
                    imagen=imagen_nueva,
                    folder='peliculas/portadas',
                    instancia_modelo=self
                )
                
                # Guardar imagen local optimizada
                if resultado.get('imagen_local'):
                    self.imagen_local = resultado['imagen_local']
                
                # Si se subió a Cloudinary, guardar el public_id
                if resultado.get('cloudinary_public_id'):
                    # Cloudinary se encarga automáticamente con CloudinaryField
                    # Solo necesitamos asignar si tenemos el public_id
                    self.imagen_red = resultado['cloudinary_public_id']
                    logger.info(f"Película {self.titulo}: Imagen subida a Cloudinary y guardada localmente")
                else:
                    logger.warning(f"Película {self.titulo}: Solo se guardó imagen local (Cloudinary no disponible)")
                
            except Exception as e:
                logger.error(f"Error al procesar imagen híbrida para película {self.titulo}: {e}")
                # Continuar con el guardado aunque falle el procesamiento de imagen

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


