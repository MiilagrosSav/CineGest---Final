import os, sys, django
from datetime import timedelta

# Ensure project root is on PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
django.setup()

from django.utils import timezone
from promociones.models.cuponGenerado import CuponGenerado
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.promocion import Promocion
from django.conf import settings

# Obtener un cliente_id existente para asignar (evitamos instanciar Cliente)
cliente_id = CuponGenerado.objects.values_list('cliente_id', flat=True).first()
if not cliente_id:
    print('No hay clientes en la BD referenciados por cupones. No puedo crear cupón sin cliente_id.')
    raise SystemExit(1)

# Obtener o crear una política/promoción mínima
politica = PoliticaPromocion.objects.first()
if not politica:
    promo = Promocion.objects.create(
        codigo='AUTO_TEST_24H',
        nombre='Promo Test 24h',
        descripcion='Promoción de prueba 24 horas',
        es_automatica=False,
        tipo_descuento='PORCENTAJE',
        valor_descuento=5,
        fecha_inicio=timezone.localdate(),
        fecha_fin=timezone.localdate()
    )
    politica = PoliticaPromocion.objects.create(nombre='Pol Test 24h', promocion_a_otorgar=promo, activa=True, prioridad=1)

expira = timezone.now() + timedelta(hours=24)
cupon = CuponGenerado.objects.create(cliente_id=cliente_id, politica_origen=politica, expira_en=expira)

base = getattr(settings, 'SITE_BASE_URL', 'https://uncategorized-noncommodiously-floy.ngrok-free.dev')
link = f"{base}/promociones/activar/{cupon.token}"

print('Cupón creado con 24h de validez:')
print('token:', cupon.token)
print('expira_en:', cupon.expira_en)
print('cliente_id:', cliente_id)
print('\nLink para probar (copiar/pegar en navegador):')
print(link)

# Option: also print short html anchor
print('\nHTML:')
print(f"<a href=\"{link}\">Activar promoción</a>")
