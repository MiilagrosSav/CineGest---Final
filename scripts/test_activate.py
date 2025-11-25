import os, sys, django
# Ensure project root is on PYTHONPATH so Django settings can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
django.setup()
from promociones.models.cuponGenerado import CuponGenerado
from django.test import Client
from django.conf import settings
import django.utils.timezone as tz

# Ensure test client host is allowed by Django
try:
    settings.ALLOWED_HOSTS = settings.ALLOWED_HOSTS + ['testserver', 'localhost', '127.0.0.1']
except Exception:
    try:
        settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    except Exception:
        pass

cup = CuponGenerado.objects.filter(usado=False).order_by('-creado_en').first()
if not cup:
    print('No hay cupones disponibles para testear')
    raise SystemExit(0)

token = cup.token
print('Usando token:', token)
print('creado_en:', cup.creado_en, ' expira_en:', cup.expira_en)
print('timezone.now():', tz.now())

c = Client()
resp = c.get(f'/promociones/activar/{token}/', follow=True)
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
print('\n--- response preview (first 800 chars) ---')
try:
    print(resp.content.decode('utf-8')[:800])
except Exception:
    print(resp.content[:800])

# comprobar estado del cupón en DB
cup_fresh = CuponGenerado.objects.get(pk=cup.pk)
print('cup.usado (db):', cup_fresh.usado)
