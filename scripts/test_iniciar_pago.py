# Test calling the iniciar_pago view for a venta (no rendering of template, only ensure it returns an HttpResponse)
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from django.test import RequestFactory
from ventas.views.pagos import iniciar_pago
from ventas.models import Venta

venta = Venta.objects.filter(estado='PENDIENTE').first()
if not venta:
    print('No hay ventas pendientes para probar')
else:
    rf = RequestFactory()
    request = rf.get(f'/ventas/pago/iniciar/{venta.id_venta}/')
    # asignar usuario y session
    request.user = venta.id_cliente.usuario
    request.session = {}
    # Evitar DisallowedHost en get_host() durante pruebas
    request.META['HTTP_HOST'] = 'localhost'
    # Inicializar sistema de mensajes para evitar MessageFailure
    from django.contrib.messages.storage.fallback import FallbackStorage
    request._messages = FallbackStorage(request)
    try:
        resp = iniciar_pago(request, venta.id_venta)
        print('iniciar_pago devolvió:', type(resp), getattr(resp, 'status_code', 'N/A'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('iniciar_pago lanzó excepción:', e)
