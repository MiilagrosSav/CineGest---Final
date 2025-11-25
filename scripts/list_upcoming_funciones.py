import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
import django
django.setup()

from cine.models import Funcion
from django.utils import timezone

ahora = timezone.now()
qs = Funcion.objects.filter(fecha_hora__gte=ahora).select_related('pelicula','sala').order_by('fecha_hora')[:30]
for f in qs:
    generos = ','.join([g.nombre for g in f.pelicula.generos.all()])
    print(f"id={f.pk} fecha={f.fecha_hora} pelicula={f.pelicula.titulo} generos={generos} precio={f.precio_base}")
