# Normalizar prioridad: actualizar politicas con prioridad 0 a 100
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from promociones.models.politicaPromocion import PoliticaPromocion

qs = PoliticaPromocion.objects.filter(prioridad=0)
count = qs.count()
qs.update(prioridad=100)
print(f'Políticas actualizadas: {count}')
