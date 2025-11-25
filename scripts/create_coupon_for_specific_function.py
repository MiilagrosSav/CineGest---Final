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
from cine.models.funcion import Funcion
from django.conf import settings

# Buscar una función futura para test
funcion = Funcion.objects.filter(fecha_hora__gte=timezone.now()).order_by('fecha_hora').first()
if not funcion:
    print('No hay funciones futuras para asociar el cupón. Por favor crea una función de prueba.')
    raise SystemExit(1)

# Obtener cliente_id desde cupones existentes
cliente_id = CuponGenerado.objects.values_list('cliente_id', flat=True).first()
if not cliente_id:
    print('No hay clientes en la BD referenciados por cupones. No puedo crear cupón sin cliente_id.')
    raise SystemExit(1)

# Obtener o crear politica/promocion mínima
politica = PoliticaPromocion.objects.first()
if not politica:
    promo = Promocion.objects.create(
        codigo='FUNC_TEST',
        nombre='Promo Func Test',
        descripcion='Promoción para función específica',
        es_automatica=False,
        tipo_descuento='PORCENTAJE',
        valor_descuento=10,
        fecha_inicio=timezone.localdate(),
        fecha_fin=timezone.localdate()
    )
    politica = PoliticaPromocion.objects.create(nombre='Pol Func Test', promocion_a_otorgar=promo, activa=True, prioridad=1)

expira = timezone.now() + timedelta(hours=24)
cupon = CuponGenerado.objects.create(cliente_id=cliente_id, politica_origen=politica, expira_en=expira, funcion_origen=funcion)

base = getattr(settings, 'SITE_BASE_URL', 'https://uncategorized-noncommodiously-floy.ngrok-free.dev')
link = f"{base}/promociones/activar/{cupon.token}"

print('Cupón creado vinculado a función:')
print('token:', cupon.token)
print('funcion_id:', funcion.id, 'fecha_hora:', funcion.fecha_hora)
print('expira_en:', cupon.expira_en)
print('\nLink para probar (copiar/pegar en navegador):')
print(link)
