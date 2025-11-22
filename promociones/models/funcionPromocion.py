import django.db.models as models
from .promocion import Promocion
from django.utils import timezone

class FuncionPromocion(models.Model):
    """
    Tabla intermedia que vincula una promocion con una funcion o con una pelicula.
    Al menos uno de `funcion` o `pelicula` debe estar presente.
    """
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name='funciones_asociadas')
    funcion = models.ForeignKey('cine.Funcion', null=True, blank=True, on_delete=models.CASCADE, related_name='promociones')
    pelicula = models.ForeignKey('cine.Pelicula', null=True, blank=True, on_delete=models.CASCADE, related_name='promociones')

    class Meta:
        db_table = 'promociones_funcionpromocion'
        unique_together = [['promocion', 'funcion', 'pelicula']]

    def clean(self):
        # Validaciones: al menos funcion o pelicula
        from django.core.exceptions import ValidationError
        if not self.funcion and not self.pelicula:
            raise ValidationError('Debe especificarse una función o una película para la promoción.')
        if self.funcion and self.pelicula:
            # si ambos están presentes, validar que coincidan
            if self.funcion.pelicula_id != self.pelicula_id:
                raise ValidationError('Si se especifican función y película, la película debe coincidir con la función.')
