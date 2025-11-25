import uuid
from django.db import models
from .politicaPromocion import PoliticaPromocion
from django.utils import timezone
from datetime import timedelta

class CuponGenerado(models.Model):
    """
    Token único generado para un cliente como parte de una PoliticaPromocion.
    """
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cliente = models.ForeignKey('accounts.Cliente', on_delete=models.PROTECT, related_name='cupones')
    funcion_origen = models.ForeignKey('cine.Funcion', on_delete=models.CASCADE, null=True, blank=True)
    politica_origen = models.ForeignKey(PoliticaPromocion, on_delete=models.PROTECT, related_name='cupones_generados')
    usado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    # Nuevo: fecha/hora de expiración calculada al crear el cupón
    expira_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'promociones_cupongenerado'

    def __str__(self):
        return f"Cupon {self.token} -> {self.cliente} ({'usado' if self.usado else 'disponible'})"