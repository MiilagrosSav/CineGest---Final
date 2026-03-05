import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from ventas.models.venta import Venta
from ventas.models.entrada import Entrada
from promociones.models.cuponGenerado import CuponGenerado
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.promocion import Promocion
from cine.models.pelicula import Pelicula
from cine.models.sala import Sala
from cine.models.funcion import Funcion
from cine.models.butaca import Butaca
from accounts.models import Cliente

from unittest.mock import patch
from django.db.models.signals import post_save


# Create your tests here.


class WebhookCouponConsumptionTest(TestCase):
	def setUp(self):
		self.client = Client()
		User = get_user_model()
		# Usuario / Cliente
		self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass', dni='0001')
		self.cliente = Cliente.objects.create(usuario=self.user)

		# Cine: Sala, Pelicula, Funcion, Butaca
		self.sala = Sala.objects.create(numero=1, nombre='Sala 1')
		tomorrow = timezone.now() + timedelta(days=1)
		self.pelicula = Pelicula.objects.create(
			titulo='Película Test',
			sinopsis='Test',
			director='Director',
			duracion=100,
			fecha_estreno=(date.today() + timedelta(days=1)),
			es_estreno=False,
			acepta_promociones=True
		)
		self.funcion = Funcion.objects.create(
			pelicula=self.pelicula,
			sala=self.sala,
			fecha_hora=tomorrow,
			precio_base=Decimal('500.00')
		)
		self.butaca = Butaca.objects.create(sala=self.sala, fila='A', numero=1)

		# Venta + Entrada (crear sin disparar simple_history para evitar errores en historical table en DB de test)
		_post_save_receivers = post_save.receivers[:]
		try:
			# eliminar temporalmente los receivers de simple_history
			post_save.receivers[:] = [r for r in post_save.receivers if 'simple_history' not in getattr(r[1], '__module__', '')]
			self.venta = Venta.objects.create(id_cliente=self.cliente)
		finally:
			post_save.receivers[:] = _post_save_receivers
		self.entrada = Entrada.objects.create(
			id_venta=self.venta,
			id_funcion=self.funcion,
			id_sala=self.sala,
			id_butaca=self.butaca,
			id_pelicula=self.pelicula,
			estado='RESERVADA'
		)

		# Promocion + Politica + Cupon
		self.promocion = Promocion.objects.create(
			codigo='PROMO1',
			nombre='Promo Test',
			tipo_descuento='PORCENTAJE',
			valor_descuento=Decimal('10.00'),
			fecha_inicio=date.today() - timedelta(days=1),
			fecha_fin=date.today() + timedelta(days=10),
			es_automatica=False,
			aplica_en_estrenos=False
		)

		self.politica = PoliticaPromocion.objects.create(
			nombre='Política Test',
			activo=True,
			promocion_a_otorgar=self.promocion,
			hora_inicio_rango=time(hour=0, minute=0),
			hora_fin_rango=time(hour=23, minute=59),
			minutos_validez=60,
		)

		self.cupon = CuponGenerado.objects.create(cliente=self.cliente, politica_origen=self.politica)

	def test_webhook_marks_coupon_used_and_confirms_sale(self):
		# Assign the coupon to the sale (as happens at checkout)
		self.venta.cupon_utilizado = self.cupon
		self.venta.save()

		# Prepare fake Mercado Pago service response
		fake_payment_id = 'TEST_PAYMENT_123'
		fake_response = {
			'status': 200,
			'response': {
				'external_reference': str(self.venta.id_venta),
				'status': 'approved',
				'id': fake_payment_id
			}
		}

		payload = {'type': 'payment', 'data': {'id': fake_payment_id}}

		webhook_url = reverse('ventas:webhook_mercadopago')

		# Patch the MercadoPagoService.procesar_notificacion_webhook to avoid real SDK calls
		with patch('ventas.views.pagos.MercadoPagoService.procesar_notificacion_webhook', return_value=fake_response):
			response = self.client.post(webhook_url, data=json.dumps(payload), content_type='application/json')

		# Reload objects from DB
		self.venta.refresh_from_db()
		self.cupon.refresh_from_db()
		self.entrada.refresh_from_db()

		# Asserts: webhook returns 200, venta confirmed and coupon marked used
		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.venta.estado, 'CONFIRMADA')
		self.assertTrue(self.cupon.usado)
		# Entrada debe haber sido marcada como VENDIDA
		self.assertEqual(self.entrada.estado, 'VENDIDA')

