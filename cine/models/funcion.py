
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from cine.models.pelicula import Pelicula
from cine.models.sala import Sala
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
from core.mixins import SoftDeleteMixin
import logging

logger = logging.getLogger(__name__)
#----------------------------------------------------------------------------------------------
#--------------------------------creamos la clase FUNCION---------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class Funcion(SoftDeleteMixin, models.Model):
    """
    Modelo para representar una función (proyección) de una película en una sala.
    Una función es la combinación de una película, una sala y un horario específico.
    """
    
    # Opciones para el formato de proyección
    FORMATO_CHOICES = [
        ('2D', '2D'),
        ('3D', '3D'),
        ('4D', '4D'),
        ('IMAX', 'IMAX'),
        ('2D_3D', '2D + 3D'),  # Función mixta con asientos 2D y 3D
        ('2D_4D', '2D + 4D'),  # Función mixta con asientos 2D y 4D
        ('3D_4D', '3D + 4D'),  # Función mixta con asientos 3D y 4D
    ]
    
    # Opciones para el idioma/audio
    IDIOMA_CHOICES = [
        ('DOBLADA', 'Doblada'),
        ('SUBTITULADA', 'Subtitulada'),
        ('NATIVA', 'Idioma Original'),
    ]
    
    pelicula = models.ForeignKey(
        Pelicula,
        on_delete=models.PROTECT,  # Proteger película si tiene funciones
        related_name='funciones',
        help_text="La película que se proyectará en esta función"
    )
    
    sala = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,  # Proteger sala si tiene funciones
        related_name='funciones',
        help_text="La sala donde se proyectará la función"
    )
    
    fecha_hora = models.DateTimeField(
        help_text="Fecha y hora de inicio de la función"
    )
    
    precio_base = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Precio base de la entrada para esta función (puede variar del precio de la sala)"
    )
    
    idioma = models.CharField(
        max_length=20,
        choices=IDIOMA_CHOICES,
        default='DOBLADA',
        help_text="Idioma/audio de la función"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # Yield Management: Control de promociones automáticas
    ESTADO_PROMOCION_CHOICES = [
        ('NORMAL', 'Normal'),
        ('OFERTA_ACTIVA', 'Oferta Activa'),
    ]
    estado_promocion = models.CharField(
        max_length=20,
        choices=ESTADO_PROMOCION_CHOICES,
        default='NORMAL',
        help_text='Estado de promoción automática para esta función'
    )

    # Estado de la función
    ESTADO_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('PREVENTA', 'Preventa'),
        ('AGOTADA', 'Agotada'),
        ('INACTIVA', 'Inactiva'),
    ]
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='ACTIVA',
        help_text='Estado actual de la función'
    )
    
    # Fecha de activación automática (solo para funciones en PREVENTA)
    fecha_activacion = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Fecha y hora en que la función pasará automáticamente de PREVENTA a ACTIVA'
    )

    def __str__(self):
        formatos = self.get_formatos_destacados()
        return f"{self.pelicula.titulo} [{formatos}] - Sala {self.sala.numero} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"

    @staticmethod
    def requiere_4d_en_formatos(formatos):
        if formatos is None:
            return None

        formatos_list = [f for f in formatos if f]
        if not formatos_list:
            return None

        for item in formatos_list:
            formato = getattr(item, 'formato', item)
            if not formato:
                continue
            nombre = (formato.nombre or '').upper()
            if formato.categoria == 'EXPERIENCIA' and ('4D' in nombre or 'D-BOX' in nombre):
                return True

        return False

    @staticmethod
    def sala_tiene_butacas_para(sala):
        if not sala:
            return False, False
        tiene_4d = sala.butacas.filter(tipo='4D').exists()
        tiene_estandar = sala.butacas.filter(tipo__in=['GENERAL', 'DISCAPACITADO']).exists()
        return tiene_4d, tiene_estandar

    @staticmethod
    def permite_solape_bisala(requiere_4d_nueva, requiere_4d_otra, tiene_4d, tiene_estandar):
        if requiere_4d_nueva is None or requiere_4d_otra is None:
            return False
        if requiere_4d_nueva == requiere_4d_otra:
            return False
        return tiene_4d and tiene_estandar

    def _formatos_para_validacion(self):
        if hasattr(self, '_formatos_seleccionados') and self._formatos_seleccionados:
            return self._formatos_seleccionados
        return self.formatos_funcion.select_related('formato').all()

    def requiere_butacas_4d(self):
        return self.requiere_4d_en_formatos(self._formatos_para_validacion())
    
    def clean(self):
        """
        BÚNKER DE INTEGRIDAD - Cine El Artesano
        Centraliza todas las validaciones de negocio e integridad de datos.
        """
        super().clean()
        ahora = timezone.now()

        # 1. VALIDACIÓN DE PRECIO (Cero tolerancia a números negativos)
        if self.precio_base is not None and self.precio_base < 0:
            raise ValidationError({'precio_base': "El precio no puede ser un número negativo."})

        # 2. VALIDACIONES PARA EDICIÓN (Cuando el registro ya existe en la BD)
        if self.pk:
            try:
                original = Funcion.objects.get(pk=self.pk)

                # A. INMUTABILIDAD DE AUDITORÍA: La fecha de creación no se toca
                if self.fecha_creacion != original.fecha_creacion:
                    raise ValidationError({'fecha_creacion': "La fecha de creación es inmutable por seguridad del sistema."})

                # B. BLOQUEO POR VENTAS: Protección de contrato con el cliente
                # Verificamos entradas en estados: RESERVADA, VENDIDA, ENTREGADA, USADA
                tiene_ventas = self.entradas.filter(
                    estado__in=['RESERVADA', 'VENDIDA', 'ENTREGADA', 'USADA']
                ).exists()

                if tiene_ventas:
                    errores = {}
                    if original.pelicula_id != self.pelicula_id:
                        errores['pelicula'] = "No se puede cambiar la película con entradas vendidas."
                    if original.sala_id != self.sala_id:
                        errores['sala'] = "No se puede cambiar la sala con entradas vendidas."
                    if original.fecha_hora != self.fecha_hora:
                        errores['fecha_hora'] = "No se puede cambiar el horario con entradas vendidas."
                    if original.precio_base != self.precio_base:
                        errores['precio_base'] = "El precio base es inmutable si ya hay ventas."
                    
                    if errores:
                        raise ValidationError(errores)
            except Funcion.DoesNotExist:
                pass

        # 3. VALIDACIÓN TEMPORAL (No permitir funciones en el pasado)
        if self.fecha_hora:
            # Si es nueva o si cambiaron la fecha en una edición
            if not self.pk or (self.pk and original.fecha_hora != self.fecha_hora):
                if self.fecha_hora < ahora:
                    raise ValidationError({'fecha_hora': 'La fecha y hora de la función no puede ser en el pasado.'})

        # 4. SANEAMIENTO DE ESTADOS (Evita inyección de valores no permitidos o basura)
        if self.estado_promocion not in dict(self.ESTADO_PROMOCION_CHOICES):
            raise ValidationError({'estado_promocion': f"El valor '{self.estado_promocion}' no es un estado de promoción válido."})
        
        if self.estado not in dict(self.ESTADO_CHOICES):
            raise ValidationError({'estado': f"El valor '{self.estado}' no es un estado de función válido."})

        # 5. INTEGRIDAD FÍSICA Y SOLAPAMIENTO
        # Validar que la sala esté operativa
        if self.sala and not self.sala.activo:
            raise ValidationError({'sala': 'No se pueden programar funciones en salas que figuran como inactivas.'})

        # 6. VALIDACIÓN DE HORARIOS DE ATENCIÓN (Respeta horarios del cine y excepciones)
        if self.pelicula and self.fecha_hora:
            from datetime import timedelta
            from cine.models import ConfiguracionCine
            
            config = ConfiguracionCine.load()
            
            # Calcular hora de inicio y fin de la función (incluye limpieza)
            duracion_total = self.pelicula.duracion + config.minutos_limpieza
            fecha_hora_fin = self.fecha_hora + timedelta(minutes=duracion_total)
            
            # Validar que el rango completo esté dentro de un horario de atención
            es_valido, mensaje_error = config.validar_rango_horario(
                self.fecha_hora, 
                fecha_hora_fin
            )
            
            if not es_valido:
                raise ValidationError({'fecha_hora': mensaje_error})

        # 7. VALIDACIÓN DE SOLAPAMIENTO EN SALA (Evita conflictos físicos)
        if self.sala and self.pelicula and self.fecha_hora:
            from datetime import timedelta
            from cine.models import ConfiguracionCine
            
            # ✅ CORRECCIÓN: Usar minutos_limpieza de la configuración (no hardcodear 30)
            config = ConfiguracionCine.load()
            duracion_total = timedelta(minutes=self.pelicula.duracion + config.minutos_limpieza)
            fin_funcion = self.fecha_hora + duracion_total

            requiere_4d = self.requiere_butacas_4d()
            if requiere_4d is not None:
                tiene_4d, tiene_estandar = self.sala_tiene_butacas_para(self.sala)
                if requiere_4d and not tiene_4d:
                    raise ValidationError({
                        'sala': 'La sala no tiene butacas 4D para una funcion con formato 4D o D-BOX.'
                    })
                if requiere_4d is False and not tiene_estandar:
                    raise ValidationError({
                        'sala': 'La sala no tiene butacas estandar para funciones sin 4D.'
                    })
            else:
                tiene_4d, tiene_estandar = self.sala_tiene_butacas_para(self.sala)

            # ✅ CORRECCIÓN CRÍTICA: Filtrar SOLO funciones del mismo día y futuras
            # El bug anterior buscaba en TODAS las fechas del pasado causando falsos conflictos
            funciones_solapadas = Funcion.objects.filter(
                sala=self.sala,
                fecha_hora__date=self.fecha_hora.date(),  # ✅ Solo funciones del mismo día
                fecha_hora__gte=timezone.now()  # ✅ Solo funciones futuras (excluir inactivas del pasado)
            ).exclude(pk=self.pk if self.pk else None).prefetch_related('formatos_funcion__formato')

            for f in funciones_solapadas:
                duracion_otra = timedelta(minutes=f.pelicula.duracion + config.minutos_limpieza)
                fin_otra = f.fecha_hora + duracion_otra
                
                # Verificar solapamiento real: la nueva función empieza antes de que termine la existente
                # Y la existente empieza antes de que termine la nueva
                if f.fecha_hora < fin_funcion and self.fecha_hora < fin_otra:
                    requiere_4d_otra = self.requiere_4d_en_formatos(f.formatos_funcion.all())
                    if f.fecha_hora != self.fecha_hora:
                        raise ValidationError({
                            'fecha_hora': (
                                f'Conflicto de horario: La sala ya está ocupada por "{f.pelicula.titulo}" '
                                f'({f.fecha_hora.strftime("%H:%M")}).'
                            )
                        })

                    if f.pelicula_id != self.pelicula_id:
                        raise ValidationError({
                            'fecha_hora': (
                                f'Conflicto de Proyección: La sala {self.sala.nombre} ya tiene '
                                f'programada la película "{f.pelicula.titulo}" en este horario.'
                            )
                        })
                    if self.permite_solape_bisala(requiere_4d, requiere_4d_otra, tiene_4d, tiene_estandar):
                        continue
                    if requiere_4d is None or requiere_4d_otra is None:
                        detalle_bisala = 'No se puede solapar sin definir formato de experiencia (4D o estandar).'
                    elif requiere_4d and requiere_4d_otra:
                        detalle_bisala = 'Ambas funciones requieren butacas 4D. El solape solo se permite cuando una es 4D y la otra estandar.'
                    else:
                        detalle_bisala = 'Ambas funciones son estandar. El solape solo se permite cuando una es 4D y la otra estandar.'
                    raise ValidationError({
                        'fecha_hora': (
                            f'Conflicto de horario: La sala ya está ocupada por "{f.pelicula.titulo}" '
                            f'({f.fecha_hora.strftime("%H:%M")}). {detalle_bisala}'
                        )
                    })
    
    def save(self, *args, **kwargs):
        """
        Ejecutar validaciones antes de guardar
        """
        skip_clean = kwargs.pop('skip_clean', False)
        if not skip_clean:
            self.clean()
        super().save(*args, **kwargs)
    
    def get_hora_fin(self):
        """Retorna la hora de finalización estimada de la función"""
        from datetime import timedelta
        if self.pelicula and self.fecha_hora:
            return self.fecha_hora + timedelta(minutes=self.pelicula.duracion)
        return None
    
    def get_valoraciones_stats(self):
        """
        Devuelve estadísticas de valoraciones específicas para ESTA función.
        Usa agregación a nivel de DB (Avg + Count) para evitar cargar objetos en memoria.
        Returns: dict con 'promedio', 'total', 'estrellas_llenas', 'estrellas_vacias'
        """
        from django.db.models import Avg, Count
        try:
            from valoraciones.models import Valoracion

            stats = Valoracion.objects.filter(funcion=self).aggregate(
                promedio=Avg('puntuacion'),
                total=Count('id')
            )

            promedio = stats['promedio'] or 0
            total = stats['total'] or 0

            # DEBUG: descomentar para diagnosticar valoraciones faltantes
            # logger.debug(
            #     "[get_valoraciones_stats] funcion_id=%s pelicula='%s' total=%s promedio=%s",
            #     self.pk, self.pelicula.titulo, total, promedio
            # )
            # print(f"[DEBUG get_valoraciones_stats] funcion_id={self.pk} "
            #       f"pelicula='{self.pelicula.titulo}' total={total} promedio={promedio}")

            # Truncar al entero (int), no redondear (round), para no superar 5 estrellas
            estrellas_llenas = int(promedio) if promedio > 0 else 0
            estrellas_vacias = 5 - estrellas_llenas

            return {
                'promedio': round(promedio, 1),
                'total': total,
                'estrellas_llenas': estrellas_llenas,
                'estrellas_vacias': estrellas_vacias,
            }
        except Exception:
            logger.exception("[get_valoraciones_stats] Error calculando stats para funcion_id=%s", self.pk)
            return {
                'promedio': 0,
                'total': 0,
                'estrellas_llenas': 0,
                'estrellas_vacias': 5,
            }
    
    def get_asientos_disponibles(self):
        """Retorna el número de asientos disponibles para esta función"""
        # Por ahora retorna la capacidad total de la sala
        # En el futuro, aquí se restaría el número de entradas vendidas
        return self.sala.capacidad

    def get_asientos_disponibles_reales(self):
        """Retorna asientos disponibles considerando ocupadas y mantenimiento."""
        from ventas.constants import EstadoEntrada
        from ventas.models import Entrada

        butacas_qs = self.sala.butacas.filter(es_pasillo=False, en_mantenimiento=False)
        requiere_4d = self.requiere_butacas_4d()
        if requiere_4d is True:
            butacas_qs = butacas_qs.filter(tipo='4D')
        elif requiere_4d is False:
            butacas_qs = butacas_qs.filter(tipo__in=['GENERAL', 'DISCAPACITADO'])

        total = butacas_qs.count()
        ocupadas = Entrada.objects.filter(
            id_funcion=self,
            estado__in=EstadoEntrada.ESTADOS_OCUPADOS,
            id_butaca__in=butacas_qs,
        ).count()

        disponibles = total - ocupadas
        return disponibles if disponibles > 0 else 0

    def actualizar_estado_por_disponibilidad(self):
        """Actualiza estado a AGOTADA/ACTIVA según disponibilidad real."""
        if self.estado == 'INACTIVA':
            return

        disponibles = self.get_asientos_disponibles_reales()
        if disponibles <= 0:
            if self.estado != 'AGOTADA':
                self.estado = 'AGOTADA'
                self.save(update_fields=['estado'])
            return

        if self.estado == 'AGOTADA':
            ahora = timezone.now()
            if self.fecha_activacion and ahora < self.fecha_activacion:
                self.estado = 'PREVENTA'
            else:
                self.estado = 'ACTIVA'
            self.save(update_fields=['estado'])
    
    def get_formatos_display(self):
        """Retorna los formatos de la función como string"""
        formatos = self.formatos_funcion.select_related('formato').all()
        return ', '.join([ff.formato.nombre for ff in formatos])
    
    def get_formatos_dimension(self):
        """Retorna solo los formatos de dimensión (2D/3D) sin audio ni pantalla"""
        formatos = self.formatos_funcion.select_related('formato').all()
        formatos_dimension = []
        
        for ff in formatos:
            nombre = ff.formato.nombre.upper()
            # Solo incluir formatos que sean 2D, 3D, o combinaciones de dimensión
            if '2D' in nombre or '3D' in nombre:
                formatos_dimension.append(ff.formato.nombre)
        
        return ' + '.join(formatos_dimension) if formatos_dimension else ''
    
    def get_formatos_destacados(self):
        """Retorna solo formatos VISUAL (2D/3D) y EXPERIENCIA (4DX, 4D, D-BOX), excluyendo Standard"""
        formatos = self.formatos_funcion.select_related('formato').all()
        formatos_destacados = []
        
        for ff in formatos:
            # Solo incluir categorías VISUAL y EXPERIENCIA
            if ff.formato.categoria in ['VISUAL', 'EXPERIENCIA']:
                # Excluir formatos que contengan "Standard" en su nombre
                if 'STANDARD' not in ff.formato.nombre.upper():
                    formatos_destacados.append(ff.formato.nombre)
        
        return ' + '.join(formatos_destacados) if formatos_destacados else 'Estándar'

    def obtener_promociones_activas(self):
        """
        Retorna todas las promociones automáticas activas para esta función,
        combinando con prioridad:
          1. Promos vinculadas específicamente a esta función  (origen='funcion')
          2. Promos vinculadas a la película de esta función   (origen='pelicula')
          3. Promos globales automáticas sin vínculo específico (origen='global')
        Sin duplicados por pk.
        Returns: list of dicts {'promo': Promocion, 'origen': str, 'etiqueta': str}
        """
        from django.utils import timezone as _tz
        from promociones.models.promocion import Promocion
        hoy = _tz.now().date()
        filtro_base = dict(
            activo=True,
            es_automatica=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
            fecha_baja__isnull=True,
        )
        resultado = []
        seen_pks = set()

        # 1. Vinculadas a esta función específica
        for promo in Promocion.objects.filter(**filtro_base, vinculos__funcion=self):
            if promo.pk not in seen_pks:
                seen_pks.add(promo.pk)
                resultado.append({
                    'promo': promo,
                    'origen': 'funcion',
                    'etiqueta': '¡Promoción exclusiva para esta función!',
                })

        # 2. Vinculadas a la película de esta función
        for promo in Promocion.objects.filter(**filtro_base, vinculos__pelicula=self.pelicula):
            if promo.pk not in seen_pks:
                seen_pks.add(promo.pk)
                resultado.append({
                    'promo': promo,
                    'origen': 'pelicula',
                    'etiqueta': f'Descuento especial para {self.pelicula.titulo}',
                })

        # 3. Globales: activas, automáticas, sin ningún vínculo
        for promo in Promocion.objects.filter(**filtro_base).exclude(vinculos__isnull=False):
            if promo.pk not in seen_pks:
                seen_pks.add(promo.pk)
                resultado.append({
                    'promo': promo,
                    'origen': 'global',
                    'etiqueta': '',
                })

        return resultado

    # historial de cambios
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Función"
        verbose_name_plural = "Funciones"
        ordering = ['fecha_hora', 'sala__numero']
        db_table = "funciones"  # 🎭 Nombre personalizado de la tabla
        
        # Índices para mejorar el rendimiento de las consultas
        indexes = [
            models.Index(fields=['fecha_hora', 'sala'], name='IDX_funcion_fecha_sala'),
            models.Index(fields=['pelicula', 'fecha_hora'], name='IDX_funcion_pelicula_fecha'),
        ]