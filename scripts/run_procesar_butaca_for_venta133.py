import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
import django
django.setup()

from ventas.models.venta import Venta
from promociones.services import procesar_butaca_liberada

v = Venta.objects.filter(id_venta=133).select_related('id_cliente').first()
if not v:
    print('Venta 133 no encontrada')
    sys.exit(0)
entradas = v.entradas.filter(estado__in=['RESERVADA','VENDIDA'])
if not entradas.exists():
    print('Venta 133 no tiene entradas activas')
    sys.exit(0)
funcion_origen = entradas.first().id_funcion
print('Venta 133, funcion_origen=', funcion_origen.pk)
resultado = procesar_butaca_liberada(funcion_origen, cliente_excluido=v.id_cliente)
print('Resultado:', resultado)
