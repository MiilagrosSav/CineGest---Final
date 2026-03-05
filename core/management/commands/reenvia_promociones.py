from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.services import notificacion_service
from promociones.models.cuponGenerado import CuponGenerado
from django.conf import settings
from cine.models import ConfiguracionCine

class Command(BaseCommand):
    help = 'Reenvía correos de oferta para cupones generados recientemente (por defecto últimos N horas).'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='Horas hacia atrás para seleccionar cupones (default 24)')
        parser.add_argument('--limit', type=int, default=100, help='Límite de cupones a reenviar')

    def handle(self, *args, **options):
        hours = options.get('hours', 24)
        limit = options.get('limit', 100)
        since = timezone.now() - timedelta(hours=hours)

        vals = list(CuponGenerado.objects.filter(creado_en__gte=since).order_by('-creado_en').values('pk','token','cliente_id','politica_origen_id','creado_en')[:limit])
        if not vals:
            self.stdout.write('No se encontraron cupones recientes para reenviar.')
            return

        base = getattr(settings, 'SITE_BASE_URL', 'https://uncategorized-noncommodiously-floy.ngrok-free.dev')
        enviados = 0
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives
        from types import SimpleNamespace
        from promociones.models.politicaPromocion import PoliticaPromocion
        from promociones.models.promocion import Promocion
        from accounts.models import Usuario

        for v in vals:
            pk = v['pk']
            token = v['token']
            cliente_id = v['cliente_id']
            politica_id = v['politica_origen_id']

            try:
                usuario = Usuario.objects.get(pk=cliente_id)
            except Exception:
                self.stdout.write(f'No se encontró usuario para cliente_id={cliente_id}, saltando')
                continue

            try:
                politica = PoliticaPromocion.objects.select_related('promocion_a_otorgar').get(pk=politica_id)
                promocion = politica.promocion_a_otorgar
            except Exception:
                promocion = None
                politica = None

            # Seguridad: sólo reenviar si existe una política activa asociada a este cupón
            if not politica or not promocion or not getattr(politica, 'activa', False):
                self.stdout.write(f'Saltando reenvío para token={token}: politica inválida o inactiva (politica_id={politica_id})')
                continue
            # Además, sólo reenviar promociones que no sean automáticas (es_automatica=False)
            try:
                if getattr(promocion, 'es_automatica', False):
                    self.stdout.write(f'Saltando reenvío para token={token}: promocion {getattr(promocion, "pk", None)} es automática.')
                    continue
            except Exception:
                self.stdout.write(f'Saltando reenvío para token={token}: error leyendo tipo de promocion')
                continue

            link = f"{base}/promociones/activar/{token}"

            # Obtener nombre del cine desde configuración
            try:
                config = ConfiguracionCine.load()
                nombre_cine = config.nombre if config else 'CineGest'
            except Exception:
                nombre_cine = 'CineGest'

            # Construir contexto similar al servicio de notificaciones
            cupon_obj = SimpleNamespace(token=token)
            context = {
                'cliente': None,
                'usuario': usuario,
                'promocion': promocion,
                'cupon': cupon_obj,
                'link': link,
                'funcion': None,
                'site_name': nombre_cine
            }

            asunto = f"Oferta limitada: {promocion.nombre if promocion else 'Promoción'} — ¡aprovechá ahora!"
            try:
                # Render templates and send mail directly to avoid instantiating Cliente
                html = render_to_string('core/emails/promocion_oferta.html', context)
                text = render_to_string('core/emails/promocion_oferta.txt', context)
                email = EmailMultiAlternatives(subject=asunto, body=text, from_email=None, to=[usuario.email])
                email.attach_alternative(html, 'text/html')
                email.send(fail_silently=False)
                enviados += 1
                self.stdout.write(f'Reenviado: {usuario.email} -> {link}')
            except Exception as e:
                self.stdout.write(f'Error enviando a {usuario.email}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Reenvío finalizado. Enviados: {enviados}/{len(vals)}'))
