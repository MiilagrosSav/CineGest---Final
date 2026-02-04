import django.db.models as models
from django.db.models import Q
from .promocion import Promocion
from django.utils import timezone

class VinculoPromocional(models.Model):
    """
    Tabla intermedia explícita que vincula una promoción con:
    - Una película específica (todas sus funciones), O
    - Una función específica (solo esa proyección)
    
    Casos de uso:
    - película != None, funcion = None → Aplica a TODAS las funciones de esa película
    - película = None, funcion != None → Aplica SOLO a esa función específica
    
    Ejemplo: Promoción "Lunes de Terror" activa para:
    - "La Monja 3" (todas las funciones) → pelicula_id=5, funcion=None
    - "Avengers" función del lunes 18:00 → pelicula=None, funcion_id=123
    - "Avengers" función del lunes 21:00 → SIN vínculo (NO aplica)
    """
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name='vinculos')
    funcion = models.ForeignKey('cine.Funcion', null=True, blank=True, on_delete=models.CASCADE, related_name='promociones_vinculadas')
    pelicula = models.ForeignKey('cine.Pelicula', null=True, blank=True, on_delete=models.CASCADE, related_name='promociones_vinculadas')

    class Meta:
        db_table = 'promociones_funcionpromocion'
        verbose_name = 'Vínculo Promocional'
        verbose_name_plural = 'Vínculos Promocionales'
        constraints = [
            # ✅ UNICIDAD: Una promoción NO puede tener el mismo vínculo duplicado
            models.UniqueConstraint(
                fields=['promocion', 'funcion'],
                condition=Q(funcion__isnull=False),
                name='UQ_vinculo_promocion_funcion'
            ),
            models.UniqueConstraint(
                fields=['promocion', 'pelicula'],
                condition=Q(pelicula__isnull=False),
                name='UQ_vinculo_promocion_pelicula'
            ),
            # ✅ CONSISTENCIA: Garantiza exactamente UNO de película o función (no ambos, no ninguno)
            models.CheckConstraint(
                check=Q(pelicula__isnull=False, funcion__isnull=True) | Q(pelicula__isnull=True, funcion__isnull=False),
                name='check_vinculo_exactamente_uno'
            )
        ]

    def clean(self):
        """
        Validación a nivel de modelo (se ejecuta en admin y forms).
        CheckConstraint en Meta garantiza integridad en base de datos.
        """
        from django.core.exceptions import ValidationError
        
        # Validación 1: Exactamente uno de película o función
        if not self.funcion and not self.pelicula:
            raise ValidationError('Debe especificarse una función O una película (no ambas, no ninguna).')
        
        if self.funcion and self.pelicula:
            raise ValidationError('Solo puede vincular UNA función O UNA película, no ambas simultáneamente.')
        
        # Validación 2: No duplicar vínculos en la misma promoción
        # ⚠️ IMPORTANTE: Solo validar si la promoción ya existe en DB (tiene PK)
        if self.promocion and self.promocion.pk:
            duplicados = VinculoPromocional.objects.filter(promocion=self.promocion)
            
            # Excluir el propio registro si ya existe (update)
            if self.pk:
                duplicados = duplicados.exclude(pk=self.pk)
            
            # Verificar duplicado de función
            if self.funcion:
                if duplicados.filter(funcion=self.funcion).exists():
                    raise ValidationError({
                        'funcion': f'La función "{self.funcion}" ya está vinculada a esta promoción. No se permiten duplicados.'
                    })
            
            # Verificar duplicado de película
            if self.pelicula:
                if duplicados.filter(pelicula=self.pelicula).exists():
                    raise ValidationError({
                        'pelicula': f'La película "{self.pelicula}" ya está vinculada a esta promoción. No se permiten duplicados.'
                    })
