import django.db.models as models
from django.core.exceptions import ValidationError
from django.apps import apps
from simple_history.models import HistoricalRecords

class Promocion(models.Model):
    """
    Modelo Promocion: representa un beneficio genérico que puede aplicarse
    a funciones o películas.
    """
    TIPO_DESCUENTO_CHOICES = [
        ('PORCENTAJE', 'Porcentaje'),
        ('2X1', '2x1'),
        ('MONTO_FIJO', 'Monto fijo'),
    ]

    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default='')
    # Si es True, la promoción se aplica automáticamente cuando la función/película
    # esté vinculada en `FuncionPromocion`. Si es False, requiere código o cupón.
    es_automatica = models.BooleanField(default=False, help_text='Si está marcada, la promoción se aplicará automáticamente a funciones vinculadas.')
    tipo_descuento = models.CharField(max_length=20, choices=TIPO_DESCUENTO_CHOICES)
    valor_descuento = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, # Valor por defecto
        null=False 
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    
    # Reglas de negocio (Inversión de Control)
    aplica_en_estrenos = models.BooleanField(
        default=False,
        help_text='Si es True, ignora el flag es_estreno de la película.'
    )
    genero_requerido = models.ForeignKey(
        'cine.Genero',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Si es None, aplica a todos los géneros. Si tiene valor, solo aplica a ese género.'
    )
    
    # Días de la semana (solo para promociones automáticas)
    # Almacenado como CSV: "0,2,4" para Lun/Mié/Vie. Vacío = todos los días.
    dias_semana = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Días permitidos como CSV de índices (0=Lunes,..6=Domingo). Ej: "0,2,4". Vacío = todos los días.'
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'promociones_promocion'
        verbose_name = 'Promoción'
        verbose_name_plural = 'Promociones'
        constraints = [
            models.UniqueConstraint(fields=['codigo'], name='UQ_promocion_codigo')
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        """
        Override save para garantizar que 2x1 siempre tenga valor_descuento=50.
        Esto evita errores en cálculos y reportes que esperan un número.
        """
        if self.tipo_descuento == '2X1':
            self.valor_descuento = 50
        super().save(*args, **kwargs)
    
    def clean(self):
        """
        Validaciones de integridad:
        1. Evita modificar el campo `codigo` si existen políticas activas relacionadas.
        2. ✅ NUEVA VALIDACIÓN: Advierte sobre superposición de fechas en promociones automáticas.
        """
        super().clean()
        # ========== VALIDACIÓN 1: Proteger código e integridad de fechas ==========
        if self.pk:
            try:
                original = self.__class__.objects.get(pk=self.pk)
            except self.__class__.DoesNotExist:
                original = None
            
            if original:
                # --- A: Proteger Código ---
                if original.codigo != self.codigo:
                    PoliticaPromocion = apps.get_model('promociones', 'PoliticaPromocion')
                    existe_activa = PoliticaPromocion.objects.filter(
                        promocion_a_otorgar=original, 
                        activa=True
                    ).exists()
                    if existe_activa:
                        raise ValidationError({
                            'codigo': 'No se puede modificar el código: existen políticas de recuperación activas que dependen de esta promoción.'
                        })

                from django.utils import timezone
                hoy = timezone.now().date()

                # Si la promo ya empezó o ya terminó (ya está en el historial/uso)
                if original.fecha_inicio <= hoy:
                    # Bloqueamos que muevan la fecha de inicio hacia el futuro (altera el pasado)
                    if original.fecha_inicio != self.fecha_inicio:
                        raise ValidationError({
                            'fecha_inicio': f'La promoción ya inició el {original.fecha_inicio}. No se puede modificar la fecha de inicio para proteger la integridad del historial.'
                        })
                    
                    # Bloqueamos que la fecha de fin sea anterior a hoy (terminarla "por la fuerza" antes de tiempo)
                    if self.fecha_fin < hoy and original.fecha_fin >= hoy:
                         raise ValidationError({
                            'fecha_fin': 'No podés poner una fecha de fin pasada si la promoción está vigente. Usá el campo "Activo" para suspenderla manualmente.'
                        })
                if self.fecha_inicio and self.fecha_fin:
                    if self.fecha_fin < self.fecha_inicio:
                        raise ValidationError({
                            'fecha_fin': 'La fecha de fin no puede ser anterior a la fecha de inicio.'
                        })
                    
        # ========== VALIDACIÓN 2: Advertir superposición de fechas en automáticas ==========
        if self.es_automatica and self.fecha_inicio and self.fecha_fin:
            # ✅ Verificar si esta promoción tiene vínculos específicos (existentes o pendientes)
            VinculoPromocional = apps.get_model('promociones', 'VinculoPromocional')
            tiene_vinculos_especificos = False
            
            # Verificar vínculos ya guardados en BD
            if self.pk:
                tiene_vinculos_especificos = VinculoPromocional.objects.filter(promocion=self).exists()
            
            # ✅ CORRECCIÓN: Verificar si hay vínculos pendientes de guardar (flag temporal de la vista)
            if hasattr(self, '_tiene_vinculos_pendientes') and self._tiene_vinculos_pendientes:
                tiene_vinculos_especificos = True
            
            # Solo validar superposición si NO tiene vínculos específicos (es global)
            if not tiene_vinculos_especificos:
                # Buscar otras promociones automáticas sin vínculos específicos con fechas solapadas
                conflictos_base = self.__class__.objects.filter(
                    es_automatica=True,
                    fecha_inicio__lte=self.fecha_fin,
                    fecha_fin__gte=self.fecha_inicio
                )
                
                # Excluir la propia promoción si ya existe
                if self.pk:
                    conflictos_base = conflictos_base.exclude(pk=self.pk)
                
                # Filtrar solo las que NO tienen vínculos específicos (globales)
                conflictos = []
                for promo in conflictos_base:
                    if not VinculoPromocional.objects.filter(promocion=promo).exists():
                        conflictos.append(promo)
                
                if conflictos:
                    codigos_conflicto = ', '.join([p.codigo for p in conflictos[:3]])
                    raise ValidationError({
                        'es_automatica': f'⚠️ ADVERTENCIA: Existe superposición de fechas con otras promociones automáticas globales ({codigos_conflicto}). El sistema aplicará automáticamente la que ofrezca el mayor descuento al cliente.'
                    })
    
    def get_dias_list(self):
        """Devuelve la lista de días como enteros. Si vacío -> todos los días ([])"""
        raw = (self.dias_semana or '').strip()
        if raw == '' or raw == '*' or raw.lower() == 'todos':
            return []
        try:
            parts = [p for p in [x.strip() for x in raw.split(',')] if p != '']
            return [int(p) for p in parts]
        except Exception:
            return []
    
    def obtener_dias_resumen(self):
        """
        Devuelve resumen legible de días:
        - Si vacío: "Todos los días"
        - Si tiene días específicos: lista de nombres cortos ['Lun', 'Mar', ...]
        """
        dias_list = self.get_dias_list()
        if not dias_list:
            return "Todos los días"
        
        nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        return [nombres[d] for d in dias_list if 0 <= d <= 6]
    
    # historial de cambios
    history = HistoricalRecords()