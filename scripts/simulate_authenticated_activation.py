import os, sys, django

# Setup django env
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from promociones.models.cuponGenerado import CuponGenerado
from accounts.models import Cliente

User = get_user_model()

# token to test (from previous script)
TOKEN = '5e8c33ff-bde1-431c-9bd5-7dd3f8e4fc5f'

# Ensure ALLOWED_HOSTS includes testserver
from django.conf import settings
try:
    settings.ALLOWED_HOSTS = settings.ALLOWED_HOSTS + ['testserver', 'localhost', '127.0.0.1']
except Exception:
    settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Create or get test user
username = 'promo_tester'
password = 'TestPass123!'
email = 'promo_tester@example.test'
user, created = User.objects.get_or_create(username=username, defaults={'email': email})
if created:
    user.set_password(password)
    user.rol = 'cliente'
    user.save()
    print('Usuario creado:', username)
else:
    # ensure password is set to known value
    user.set_password(password)
    user.save()
    print('Usuario reutilizado:', username)

# Create Cliente profile if missing
try:
    cliente = Cliente.objects.get(usuario=user)
    print('Cliente profile exists')
except Cliente.DoesNotExist:
    cliente = Cliente.objects.create(usuario=user)
    print('Cliente profile creado')

c = Client()
login_ok = c.login(username=username, password=password)
print('Login OK?', login_ok)

# Perform GET to activation link
resp = c.get(f'/promociones/activar/{TOKEN}/', follow=True)

print('Final status_code:', resp.status_code)
print('Redirect chain:', resp.redirect_chain)
# attempt to find final path
try:
    final_path = resp.request.get('PATH_INFO')
except Exception:
    final_path = 'N/A'
print('Final path:', final_path)

# session keys
print('Session promo_activa_id:', c.session.get('promo_activa_id'))
print('Session promo_token:', c.session.get('promo_token'))

# DB check
cup = CuponGenerado.objects.filter(token=TOKEN).first()
print('Cupón in DB - usado:', cup.usado if cup else 'not found', 'funcion_origen id:', getattr(cup, 'funcion_origen_id', None))

# print a small portion of content
print('Response length:', len(resp.content))
try:
    print('Response snippet:', resp.content.decode('utf-8')[:400])
except Exception:
    pass
