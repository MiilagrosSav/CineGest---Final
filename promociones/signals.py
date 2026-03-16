import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='promociones.Promocion')
def cascade_deactivate_politicas(sender, instance, **kwargs):
    """
    Señal post_save en Promocion:
    Si la promoción queda inactiva (activo=False) o vencida (fecha_fin < hoy),
    desactiva automáticamente todas las PoliticaPromocion que la referenciaban.
    """
    promo_inactiva = (
        not instance.activo
        or (
            instance.fecha_fin is not None
            and instance.fecha_fin < timezone.now().date()
        )
    )
    if not promo_inactiva:
        return

    from promociones.models.politicaPromocion import PoliticaPromocion

    desactivadas = PoliticaPromocion.objects.filter(
        promocion_a_otorgar=instance,
        activa=True,
    ).update(activa=False)

    if desactivadas:
        logger.info(
            '[PROMO SIGNAL] Promoción "%s" (pk=%s) inactiva/vencida → '
            '%d PoliticaPromocion auto-desactivadas.',
            instance.codigo, instance.pk, desactivadas,
        )
