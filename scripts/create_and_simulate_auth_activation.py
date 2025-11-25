import os, sys, django
from datetime import timedelta

# Setup
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from promociones.models.cuponGenerado import CuponGenerado
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.promocion import Promocion
from cine.models.funcion import Funcion
from accounts.models import Cliente

User = get_user_model()

# Parameters
FUNCION_ID = 31

# Ensure ALLOWED_HOSTS
from django.conf import settings
try:
    settings.ALLOWED_HOSTS = settings.ALLOWED_HOSTS + ['testserver', 'localhost', '127.0.0.1']
except Exception:
    settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Get or create user
username = 'promo_tester'
password = 'TestPass123!'
email = 'promo_tester@example.test'
user, created = User.objects.get_or_create(username=username, defaults={'email': email})
if created:
    user.set_password(password)
    user.rol = 'cliente'
    user.save()
else:
    user.set_password(password)
    user.save()

cliente, ccreated = Cliente.objects.get_or_create(usuario=user)

# Get function
funcion = Funcion.objects.filter(pk=FUNCION_ID).first()
if not funcion:
    print('Función no encontrada:', FUNCION_ID)
    raise SystemExit(1)

# Get or create politica
politica = PoliticaPromocion.objects.first()
if not politica:
    promo = Promocion.objects.create(
        codigo='AUTO_TEST_FUNC', nombre='Promo Test Func', descripcion='Promo Func', es_automatica=False,
        tipo_descuento='PORCENTAJE', valor_descuento=5, fecha_inicio=timezone.localdate(), fecha_fin=timezone.localdate()
    )
    politica = PoliticaPromocion.objects.create(nombre='Pol Func Test', promocion_a_otorgar=promo, activa=True, prioridad=1)

# Create fresh coupon for this user and function
expira = timezone.now() + timedelta(hours=24)
cupon = CuponGenerado.objects.create(cliente=cliente, politica_origen=politica, expira_en=expira, funcion_origen=funcion)
print('Created coupon token:', cupon.token, 'funcion_id:', funcion.id)

# Simulate authenticated request
c = Client()
login_ok = c.login(username=username, password=password)
print('Login OK?', login_ok)
resp = c.get(f'/promociones/activar/{cupon.token}/', follow=True)
print('Final status_code:', resp.status_code)
print('Redirect chain:', resp.redirect_chain)
try:
    final_path = resp.request.get('PATH_INFO')
except Exception:
    final_path = 'N/A'
print('Final path:', final_path)
print('Session promo_activa_id:', c.session.get('promo_activa_id'))
print('Session promo_token:', c.session.get('promo_token'))

# DB state
cup_db = CuponGenerado.objects.get(pk=cupon.pk)
print('Cupón usado (db):', cup_db.usado)
