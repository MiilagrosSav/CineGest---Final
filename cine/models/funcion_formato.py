from django.db import models
from django.core.exceptions import ValidationError
from cine.models.funcion import Funcion
from cine.models.formato import Formato


# Definir formatos incompatibles entre sí (a nivel de módulo para fácil importación)
FORMATOS_INCOMPATIBLES = {
    '2D': ['3D'],  # 2D no puede coexistir con 3D
    '3D': ['2D'],  # 3D no puede coexistir con 2D
}


class FuncionFormato(models.Model):
    """
    Modelo para la tabla intermedia entre Función y Formato.
    Representa la relación muchos a muchos entre funciones y formatos de proyección.
    Una función puede tener múltiples formatos compatibles (ej: 3D + 4DX).
    """
    
    funcion = models.ForeignKey(
        Funcion,
        on_delete=models.CASCADE,
        related_name='formatos_funcion',
        help_text="La función a la que pertenece este formato"
    )
    
    formato = models.ForeignKey(
        Formato,
        on_delete=models.PROTECT,  # No permitir eliminar formatos en uso
        related_name='funciones_formato',
        help_text="El formato de proyección disponible"
    )
    
    class Meta:
        db_table = 'funcion_formato'
        verbose_name = 'Formato de Función'
        verbose_name_plural = 'Formatos de Función'
        ordering = ['funcion', 'formato']
        constraints = [
            models.UniqueConstraint(fields=['funcion', 'formato'], name='UQ_funcionformato_funcion_formato')
        ]
    
    def clean(self):
        """
        Validar que no se asignen formatos incompatibles a la misma función
        """
        super().clean()
        
        if not self.funcion_id or not self.formato_id:
            return  # Skip si aún no están asignados
        
        # Obtener formatos ya asignados a esta función (excluyendo el actual)
        formatos_existentes = FuncionFormato.objects.filter(
            funcion=self.funcion
        ).exclude(pk=self.pk).select_related('formato')
        
        formato_actual = self.formato.nombre
        
        # Verificar incompatibilidades
        for ff in formatos_existentes:
            formato_existente = ff.formato.nombre
            
            # Verificar si el formato actual es incompatible con alguno existente
            incompatibles = FORMATOS_INCOMPATIBLES.get(formato_actual, [])
            if formato_existente in incompatibles:
                raise ValidationError(
                    f"El formato '{formato_actual}' no puede coexistir con '{formato_existente}' "
                    f"en la misma función. Son tecnologías mutuamente excluyentes."
                )
            
            # Verificar la incompatibilidad inversa
            incompatibles_inversos = FORMATOS_INCOMPATIBLES.get(formato_existente, [])
            if formato_actual in incompatibles_inversos:
                raise ValidationError(
                    f"El formato '{formato_actual}' no puede coexistir con '{formato_existente}' "
                    f"en la misma función. Son tecnologías mutuamente excluyentes."
                )
    
    def save(self, *args, **kwargs):
        """Ejecutar validaciones antes de guardar"""
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.funcion.pelicula.titulo} - {self.formato.nombre}"
