# Ejecuta procesar_butaca_liberada para la primera función encontrada (diagnóstico)
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from cine.models.funcion import Funcion
from promociones.services import procesar_butaca_liberada

func = Funcion.objects.all().first()
if not func:
    print('No hay funciones en DB')
else:
    print('Ejecutando procesar_butaca_liberada para funcion id=', func.pk)
    res = procesar_butaca_liberada(func)
    print('Resultado:', res)
