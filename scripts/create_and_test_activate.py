import os, sys, django
# Ensure project root is on PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
django.setup()

from django.utils import timezone
from django.test import Client
from django.conf import settings

# allow testserver
try:
    settings.ALLOWED_HOSTS = settings.ALLOWED_HOSTS + ['testserver', 'localhost', '127.0.0.1']
except Exception:
    try:
        settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    except Exception:
        pass

from promociones.models.cuponGenerado import CuponGenerado
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.promocion import Promocion
from datetime import timedelta

cliente_id = CuponGenerado.objects.values_list('cliente_id', flat=True).first()
if not cliente_id:
    print('No hay clientes referenciados por cupones existentes; no puedo inferir un cliente_id para crear un cupón.')
    raise SystemExit(1)

politica = PoliticaPromocion.objects.first()
if not politica:
    # crear promocion básica
    promo = Promocion.objects.create(
        codigo='TEST_PROMO', nombre='Promo Test', descripcion='Promo para testing', es_automatica=False,
        tipo_descuento='PORCENTAJE', valor_descuento=10, fecha_inicio=timezone.localdate(), fecha_fin=timezone.localdate(),
    )
    politica = PoliticaPromocion.objects.create(
        nombre='Pol Test', promocion_a_otorgar=promo, activa=True, prioridad=1
    )

expira = timezone.now() + timedelta(minutes=30)
cupon = CuponGenerado.objects.create(cliente_id=cliente_id, politica_origen=politica, expira_en=expira)
print('Cupón creado:', cupon.token, ' expira:', cupon.expira_en, 'cliente_id:', cliente_id)

c = Client()
resp = c.get(f'/promociones/activar/{cupon.token}/', follow=True)
print('status_code:', resp.status_code)
print('redirect_chain:', resp.redirect_chain)
try:
    final_path = resp.request.get('PATH_INFO')
except Exception:
    final_path = 'N/A'
print('final_url path:', final_path)
print('session promo_activa_id:', c.session.get('promo_activa_id'))
print('session promo_token:', c.session.get('promo_token'))
print('response length:', len(resp.content))

# comprobar estado del cupón en DB
cup_fresh = CuponGenerado.objects.get(pk=cupon.pk)
print('cup.usado (db):', cup_fresh.usado)
