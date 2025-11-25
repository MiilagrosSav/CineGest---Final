import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','trabajofinal.settings')
import django
django.setup()

from promociones.models.politicaPromocion import PoliticaPromocion
from cine.models import Funcion
from datetime import time

FUNC_ID = 31
f = Funcion.objects.get(pk=FUNC_ID)
print('Funcion', FUNC_ID, 'fecha_hora', f.fecha_hora, 'pelicula', f.pelicula.titulo)

# helper
def hora_en_rango(hora_obj, inicio, fin):
    if inicio <= fin:
        return inicio <= hora_obj <= fin
    return hora_obj >= inicio or hora_obj <= fin

politicas = PoliticaPromocion.objects.filter(activa=True).select_related('promocion_a_otorgar')
for p in politicas:
    genero_ok = True
    pelicula_generos = list(f.pelicula.generos.all())
    if pelicula_generos:
        if p.genero_pelicula is not None and p.genero_pelicula.pk not in [g.pk for g in pelicula_generos]:
            genero_ok = False
    hora = f.fecha_hora.time()
    hora_ok = hora_en_rango(hora, p.hora_inicio_rango, p.hora_fin_rango)
    dias_raw = (p.dias_semana or '').strip()
    dias_ok = True
    if dias_raw and dias_raw not in ['*','todos']:
        try:
            dias = [int(x) for x in [q for q in dias_raw.split(',') if q.strip()!='']]
            dias_ok = (f.fecha_hora.weekday() in dias)
        except Exception:
            dias_ok = False
    print('Politica', p.pk, p.nombre, 'promocion', getattr(p.promocion_a_otorgar,'pk',None), 'es_auto', getattr(getattr(p,'promocion_a_otorgar',None),'es_automatica',None))
    print('  genero_ok', genero_ok, 'hora_ok', hora_ok, 'dias_ok', dias_ok)


