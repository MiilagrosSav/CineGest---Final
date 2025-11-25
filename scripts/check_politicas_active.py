import os
import sys
import json

# Asegurar que el directorio del proyecto esté en sys.path para poder importar settings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from promociones.models.politicaPromocion import PoliticaPromocion

qs = PoliticaPromocion.objects.select_related('promocion_a_otorgar').filter(activa=True)

def s(x):
    return str(x) if x is not None else None

out = []
for p in qs:
    promo = getattr(p, 'promocion_a_otorgar', None)
    out.append({
        'id': p.pk,
        'nombre': p.nombre,
        'promocion_id': getattr(promo, 'pk', None),
        'promocion_nombre': getattr(promo, 'nombre', None),
        'promocion_es_automatica': getattr(promo, 'es_automatica', None),
        'hora_inicio': s(p.hora_inicio_rango),
        'hora_fin': s(p.hora_fin_rango),
        'dias_semana': p.dias_semana,
        'prioridad': p.prioridad,
        'horas_antes_de_funcion': p.horas_antes_de_funcion,
        'minutos_validez': p.minutos_validez,
    })

print(json.dumps(out, indent=2, ensure_ascii=False))
