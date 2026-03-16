from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from simple_history.models import HistoricalRecords
from cloudinary.models import CloudinaryField
from cine.image_utils import procesar_imagen_hibrida, verificar_conexion_cloudinary
import logging

logger = logging.getLogger(__name__)


class ConfiguracionCine(models.Model):
    """
    Modelo Singleton para la configuración general del cine.
    Solo puede existir una instancia de este modelo.
    """
    
    # Información básica
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Cine",
        help_text="Nombre comercial del establecimiento"
    )
    
    # ========================================================================
    # SISTEMA HÍBRIDO DE IMÁGENES (Cloudinary + Local)
    # ========================================================================
    # Campo principal: Cloudinary (almacenamiento en la nube)
    logo_red = CloudinaryField(
        folder='cine/logos',
        blank=True,
        null=True,
        verbose_name="Logo en Cloudinary",
        help_text="Logo almacenado en Cloudinary (requiere conexión a internet)"
    )
    
    # Campo de respaldo: Almacenamiento local
    logo_local = models.ImageField(
        upload_to='cine/logos/',
        blank=True,
        null=True,
        verbose_name="Logo Local",
        help_text="Copia local optimizada del logo (respaldo sin internet)"
    )
    
    # Campo legacy para retrocompatibilidad (DEPRECADO - usar get_logo_url)
    logo = models.ImageField(
        upload_to='cine/logos/',
        blank=True,
        default='',
        verbose_name="Logo del Cine",
        help_text="[DEPRECADO] Usar logo_red/logo_local + get_logo_url"
    )
    
    # Información fiscal
    cuil_cuit = models.CharField(
        max_length=13,
        verbose_name="CUIL/CUIT",
        validators=[
            RegexValidator(
                regex=r'^\d{2}-\d{8}-\d{1}$',
                message='Formato inválido. Use: XX-XXXXXXXX-X'
            )
        ],
        help_text="Formato: 20-12345678-9"
    )
    
    razon_social = models.CharField(
        max_length=200,
        verbose_name="Razón Social",
        help_text="Nombre legal de la empresa"
    )

    fecha_inicio_actividad = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Inicio de Actividad",
        help_text="Fecha en que el cine comenzó sus actividades (para comprobantes)"
    )
    
    # Datos de contacto
    direccion = models.CharField(
        max_length=300,
        verbose_name="Dirección",
        help_text="Dirección completa del cine"
    )
    
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono",
        help_text="Número de contacto principal"
    )
    
    email = models.EmailField(
        verbose_name="Email de Contacto",
        help_text="Correo electrónico para consultas"
    )
    
    # Configuración operativa
    minutos_limpieza = models.PositiveIntegerField(
        default=30,
        verbose_name="Minutos de Limpieza",
        help_text="Tiempo entre funciones para limpieza de sala (en minutos)"
    )

    reserva_tiempo_espera = models.PositiveIntegerField(
        default=10,
        verbose_name="Tiempo de Reserva (min)",
        help_text="Minutos que una butaca permanece reservada antes de liberarse automáticamente si no se completa el pago."
    )
    
    # Redes sociales (opcionales)
    facebook = models.URLField(
        blank=True,
        default='',
        verbose_name="Facebook",
        help_text="URL completa del perfil"
    )
    
    instagram = models.URLField(
        blank=True,
        default='',
        verbose_name="Instagram",
        help_text="URL completa del perfil"
    )
    
    twitter = models.URLField(
        blank=True,
        default='',
        verbose_name="Twitter/X",
        help_text="URL completa del perfil"
    )
    
    # Información adicional
    descripcion = models.TextField(
        blank=True,
        default='',
        verbose_name="Descripción",
        help_text="Descripción breve del cine (para mostrar en el sitio)"
    )
    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'configuracion_cine'
        verbose_name = 'Configuración del Cine'
        verbose_name_plural = 'Configuración del Cine'
    
    @property
    def get_logo_url(self):
        """
        Devuelve la URL del logo del cine.

        Lógica local-first (optimización de rendimiento):
        1. Usa logo_local
        2. Si no existe, usa logo (retrocompatibilidad)
        3. Si no hay logo, devuelve placeholder
        
        Returns:
            str: URL del logo (Cloudinary, local o placeholder)
        """
        # Fallback 1: Usar logo local optimizado
        if self.logo_local:
            try:
                return self.logo_local.url
            except Exception:
                pass
        
        # Fallback 2: Retrocompatibilidad con logo legacy
        if self.logo:
            try:
                return self.logo.url
            except Exception:
                pass
        
        # Fallback 3: Logo placeholder
        from django.templatetags.static import static
        return static('img/logo-placeholder.png')

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        
        # 1. Validación de Minutos de Limpieza (Evita -1 o valores nulos)
        if self.minutos_limpieza is not None and self.minutos_limpieza < 0:
            raise ValidationError({
                'minutos_limpieza': "El tiempo de limpieza no puede ser un valor negativo."
            })
        if self.minutos_limpieza > 240: # 4 horas máximo como límite lógico
            raise ValidationError({
                'minutos_limpieza': "El tiempo de limpieza parece excesivo. Máximo permitido: 240 min."
            })

        # 2. Validación de Tiempo de Reserva (Evita -1)
        if self.reserva_tiempo_espera is not None and self.reserva_tiempo_espera < 1:
            raise ValidationError({
                'reserva_tiempo_espera': "El tiempo de reserva debe ser de al menos 1 minuto."
            })
        if self.reserva_tiempo_espera > 60:
            raise ValidationError({
                'reserva_tiempo_espera': "El tiempo de reserva no puede superar los 60 minutos."
            })

        # 3. No permitir fecha de inicio de actividad en el futuro.
        if self.fecha_inicio_actividad and self.fecha_inicio_actividad > timezone.localdate():
            raise ValidationError({
                'fecha_inicio_actividad': "La fecha de inicio de actividad no puede ser futura."
            })

        # NOTA: La validación de horarios de apertura/cierre fue removida porque
        # ahora se usa el sistema flexible de HorarioAtencion por día de la semana.
        # Cada día tiene sus propios rangos horarios configurados en HorarioAtencion.


    def save(self, *args, **kwargs):
        """
        Override save para implementar patrón Singleton.
        Solo puede existir una configuración.
        """
        # Normalizar campos de texto
        if self.nombre:
            self.nombre = self.nombre.strip()
        
        if self.direccion:
            self.direccion = self.direccion.strip().title()
        
        # Normalizar email a minúsculas
        if self.email:
            self.email = self.email.strip().lower()
        
        # Normalizar URLs de redes sociales a minúsculas
        if self.facebook:
            self.facebook = self.facebook.strip().lower()
        
        if self.instagram:
            self.instagram = self.instagram.strip().lower()
        
        if self.twitter:
            self.twitter = self.twitter.strip().lower()
        
        # ========================================================================
        # PROCESAMIENTO HÍBRIDO DE IMÁGENES (Cloudinary + Local)
        # ========================================================================
        # Detectar si hay un nuevo logo subido
        logo_nuevo = None
        
        # Verificar si hay un logo en el campo logo (campo legacy/formulario)
        if self.logo and hasattr(self.logo, 'file'):
            logo_nuevo = self.logo
        # O si se subió directamente a logo_local
        elif self.logo_local and hasattr(self.logo_local, 'file'):
            logo_nuevo = self.logo_local
        
        # Procesar el logo si hay uno nuevo
        if logo_nuevo:
            try:
                # Procesar imagen con el sistema híbrido
                resultado = procesar_imagen_hibrida(
                    imagen=logo_nuevo,
                    folder='cine/logos',
                    instancia_modelo=self
                )
                
                # Guardar logo local optimizado
                if resultado.get('imagen_local'):
                    self.logo_local = resultado['imagen_local']
                
                # Si se subió a Cloudinary, guardar el public_id
                if resultado.get('cloudinary_public_id'):
                    self.logo_red = resultado['cloudinary_public_id']
                    logger.info(f"Logo del cine: Subido a Cloudinary y guardado localmente")
                else:
                    logger.warning(f"Logo del cine: Solo se guardó localmente (Cloudinary no disponible)")
                
            except Exception as e:
                logger.error(f"Error al procesar logo híbrido: {e}")
                # Continuar con el guardado aunque falle el procesamiento
        
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevenir eliminación de la configuración"""
        pass
    
    @classmethod
    def load(cls):
        """
        Método de clase para cargar la configuración.
        Si no existe, crea una instancia por defecto.
        """
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'nombre': 'Mi Cine',
                'cuil_cuit': '20-00000000-0',
                'razon_social': 'Cine S.A.',
                'direccion': 'Av. Principal 123',
                'telefono': '+54 11 0000-0000',
                'email': 'contacto@micine.com',
                'minutos_limpieza': 30,
                'reserva_tiempo_espera': 10,
            }
        )
        return obj
    
    def get_horarios_dia(self, dia_semana):
        """
        Retorna los rangos horarios activos para un día específico.
        
        Args:
            dia_semana (int): Número del día (0=Lunes, 6=Domingo)
            
        Returns:
            QuerySet: Horarios activos para ese día, ordenados por orden y hora de apertura
        """
        # Import local para evitar dependencias circulares
        from .horario_atencion import HorarioAtencion
        
        return HorarioAtencion.objects.filter(
            configuracion_cine=self,
            dia_semana=dia_semana,
            activo=True
        ).order_by('orden', 'hora_apertura')
    
    def esta_abierto_en(self, fecha_hora_obj):
        """
        Verifica si el cine está abierto en una fecha/hora específica.
        
        Args:
            fecha_hora_obj (datetime.datetime): Fecha y hora a verificar
            
        Returns:
            bool: True si el cine está abierto, False en caso contrario
            
        Example:
            >>> from django.utils import timezone
            >>> config = ConfiguracionCine.load()
            >>> ahora = timezone.now()
            >>> config.esta_abierto_en(ahora)
            True
        """
        from django.utils import timezone
        
        # Convertir a naive si es aware para obtener el weekday correcto
        if timezone.is_aware(fecha_hora_obj):
            fecha_hora_obj = timezone.localtime(fecha_hora_obj)
        
        dia_semana = fecha_hora_obj.weekday()  # 0=Monday en Python
        hora = fecha_hora_obj.time()
        
        horarios = self.get_horarios_dia(dia_semana)
        
        for rango in horarios:
            # Verificar si la hora está dentro del rango [apertura, cierre)
            if rango.hora_apertura <= hora < rango.hora_cierre:
                return True
        
        return False
    
    def validar_rango_horario(self, fecha_hora_inicio, fecha_hora_fin):
        """
        Valida que un rango completo [inicio, fin] esté dentro de los horarios de atención.
        
        Útil para validar funciones de cine que tienen duración (inicio + película + limpieza).
        
        Args:
            fecha_hora_inicio (datetime): Momento de inicio (ej: inicio de función)
            fecha_hora_fin (datetime): Momento de fin (ej: fin de función + limpieza)
            
        Returns:
            tuple: (bool, str or None)
                - (True, None) si el rango es válido
                - (False, mensaje_error) si hay conflicto
                
        Lógica de validación:
            1. PRIORIDAD EXCEPCIONES: Si hay excepción para esa fecha, usa esos criterios
               - Si cerrado=True → rechazar
               - Si cerrado=False → validar contra el rango de excepción
            2. HORARIOS REGULARES: Si no hay excepción, usar horarios del día de la semana
            3. VALIDACIÓN: El rango completo [inicio, fin] debe estar dentro de UN rango horario
               (no permite atravesar huecos entre rangos)
        
        Ejemplos:
            >>> # Lunes con horarios 10-14 y 17-23
            >>> # Función 13:00-15:30 (atraviesa hueco 14-17)
            >>> validar_rango_horario(lunes_13h, lunes_15h30)
            (False, "La función... no cabe completamente...")
            
            >>> # Función 18:00-20:30 (dentro de 17-23)
            >>> validar_rango_horario(lunes_18h, lunes_20h30)
            (True, None)
        """
        from django.utils import timezone
        
        # Convertir a localtime si es aware
        if timezone.is_aware(fecha_hora_inicio):
            fecha_hora_inicio = timezone.localtime(fecha_hora_inicio)
        if timezone.is_aware(fecha_hora_fin):
            fecha_hora_fin = timezone.localtime(fecha_hora_fin)
        
        fecha = fecha_hora_inicio.date()
        hora_inicio = fecha_hora_inicio.time()
        hora_fin = fecha_hora_fin.time()
        
        # PASO 1: Verificar si hay excepción para esta fecha
        from .excepcion_horario import ExcepcionHorario  # Import local para evitar ciclos
        
        # Buscar excepción que aplique a esta fecha (puede ser fecha exacta o dentro de un rango)
        # Lógica: Una excepción aplica si:
        # - Es de un solo día: fecha == fecha buscada
        # - Es de un rango: fecha <= fecha_buscada <= fecha_fin
        excepciones = ExcepcionHorario.objects.filter(
            configuracion_cine=self,
            fecha__lte=fecha  # fecha de inicio <= fecha buscada
        ).filter(
            models.Q(fecha_fin__isnull=True, fecha=fecha) |  # Excepción de un solo día
            models.Q(fecha_fin__gte=fecha)  # O fecha dentro del rango
        )
        
        if excepciones.exists():
            excepcion = excepciones.first()
            
            # Si el cine está cerrado ese día, rechazar
            if excepcion.cerrado:
                return (False, 
                       f'El cine está cerrado el {fecha.strftime("%d/%m/%Y")}. '
                       f'Motivo: {excepcion.descripcion or "Día no laborable"}.')
            
            # Usar el rango horario de la excepción
            if excepcion.hora_apertura and excepcion.hora_cierre:
                # Validar que TODO el rango esté dentro del horario excepcional
                if excepcion.hora_apertura <= hora_inicio and hora_fin <= excepcion.hora_cierre:
                    return (True, None)  # ✓ Válido
                else:
                    return (False,
                           f'La función (inicio: {hora_inicio.strftime("%H:%M")}, '
                           f'fin estimado: {hora_fin.strftime("%H:%M")}) excede el horario '
                           f'excepcional del {fecha.strftime("%d/%m/%Y")}: '
                           f'{excepcion.hora_apertura.strftime("%H:%M")} - '
                           f'{excepcion.hora_cierre.strftime("%H:%M")}. '
                           f'Motivo: {excepcion.descripcion or "Horario modificado"}.')
            else:
                # Excepción malformada (no debería pasar si los validadores funcionan)
                return (False, f'Excepción de horario malformada para el {fecha.strftime("%d/%m/%Y")}.')
        else:
            # PASO 2: No hay excepción, usar horarios regulares del día
            dia_semana = fecha_hora_inicio.weekday()
            rangos = self.get_horarios_dia(dia_semana)
            
            # PASO 3: Validar que el rango completo esté dentro de UN SOLO rango horario
            if not rangos.exists():
                dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                dia_nombre = dias_nombres[fecha_hora_inicio.weekday()]
                return (False, f'No hay horarios de atención configurados para el {dia_nombre}.')
            
            # Verificar si INICIO y FIN están dentro del mismo rango
            # Importante: No permitir atravesar huecos entre rangos
            for rango in rangos:
                # Verificar si TODO el rango [inicio, fin] está dentro de este rango horario
                # Usamos <= para inicio y <= para fin (intervalo cerrado completo)
                if rango.hora_apertura <= hora_inicio and hora_fin <= rango.hora_cierre:
                    return (True, None)  # ✓ Válido: Todo el rango está dentro de este horario
            
            # Si llegamos aquí, la función no cabe en ningún rango
            return (False, 
                   f'La función (inicio: {hora_inicio.strftime("%H:%M")}, '
                   f'fin estimado: {hora_fin.strftime("%H:%M")}) no cabe completamente '
                   f'dentro de ningún rango horario de atención. '
                   f'Verifica que no atraviese cierres intermedios.')
    
    def __str__(self):
        return self.nombre
    
    # historial de cambios
    history = HistoricalRecords()
