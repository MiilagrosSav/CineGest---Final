import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
import django
django.setup()

from cine.models import Funcion
from promociones.services import procesar_butaca_liberada

funcion_id = 31
f = Funcion.objects.get(pk=funcion_id)
print('Ejecutando procesar_butaca_liberada para funcion', funcion_id, f.fecha_hora)
res = procesar_butaca_liberada(f, cliente_excluido=None)
print('Resultado:', res)
