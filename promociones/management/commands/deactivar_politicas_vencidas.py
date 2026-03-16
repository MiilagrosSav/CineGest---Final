"""
Management command: deactivar_politicas_vencidas

Desactiva automáticamente todas las PoliticaPromocion cuya promoción
asociada ha vencido (fecha_fin < hoy) o fue desactivada (activo=False).

Diseñado para ejecutarse diariamente (cron/scheduler).
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Desactiva las PoliticaPromocion cuya promoción asociada está '
        'vencida (fecha_fin < hoy) o inactiva. Ideal para ejecutar diariamente.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se desactivaría sin hacer cambios reales.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy = timezone.now().date()

        from django.db.models import Q
        from promociones.models.politicaPromocion import PoliticaPromocion

        # Políticas activas cuya promoción ha vencido o fue desactivada
        candidatas = PoliticaPromocion.objects.filter(activa=True).filter(
            Q(promocion_a_otorgar__activo=False)
            | Q(promocion_a_otorgar__fecha_fin__lt=hoy)
        ).select_related('promocion_a_otorgar')

        count = candidatas.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No hay políticas para desactivar.'))
            return

        for pol in candidatas:
            promo = pol.promocion_a_otorgar
            motivo = (
                'promoción inactiva (activo=False)'
                if not promo.activo
                else f'promoción vencida (fecha_fin={promo.fecha_fin})'
            )
            msg = f'  Política "{pol.nombre}" (pk={pol.pk}) — {motivo}'
            if dry_run:
                self.stdout.write(self.style.WARNING(f'[DRY-RUN] Desactivaría: {msg}'))
            else:
                self.stdout.write(msg)

        if not dry_run:
            desactivadas = candidatas.update(activa=False)
            logger.info(
                '[CRON] deactivar_politicas_vencidas: %d políticas desactivadas (fecha=%s)',
                desactivadas, hoy,
            )
            self.stdout.write(
                self.style.SUCCESS(f'\n✔ {desactivadas} política(s) desactivada(s).')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'\n[DRY-RUN] Se desactivarían {count} política(s). '
                                   'Ejecuta sin --dry-run para aplicar.')
            )
