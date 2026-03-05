from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from promociones.models.cuponGenerado import CuponGenerado
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.promocion import Promocion
from cine.models.funcion import Funcion
from accounts.models import Cliente

User = get_user_model()

class ActivacionPromocionTest(TestCase):
    def setUp(self):
        # usuario de prueba
        self.username = 'test_promo_user'
        self.password = 'TestPass123!'
        self.email = 'test_promo_user@example.test'
        self.user, created = User.objects.get_or_create(username=self.username, defaults={'email': self.email})
        if created:
            self.user.set_password(self.password)
            self.user.save()
        else:
            self.user.set_password(self.password)
            self.user.save()

        # cliente profile
        self.cliente, _ = Cliente.objects.get_or_create(usuario=self.user)

        # funcion de prueba (usar una futura si existe, sino crear una)
        self.funcion = Funcion.objects.filter(fecha_hora__gte=timezone.now()).order_by('fecha_hora').first()
        if not self.funcion:
            # crear objetos mínimos: pelicula y sala no trivial en test DB
            from cine.models.pelicula import Pelicula
            from cine.models.sala import Sala
            # Crear sala sin pasar capacidad (es property calculada)
            sala = Sala.objects.create(numero=1, nombre='Sala Test', activo=True)
            pelicula = Pelicula.objects.create(
                titulo='Test Movie',
                duracion=90,
                acepta_promociones=True,
                sinopsis='Test synopsis',
                director='Test Director',
                fecha_estreno=timezone.localdate(),
            )
            self.funcion = Funcion.objects.create(pelicula=pelicula, sala=sala, fecha_hora=timezone.now() + timedelta(days=1), precio_base=100)

        # promocion y politica
        self.promocion = Promocion.objects.create(
            codigo='TESTPROMO', nombre='Promo Test', descripcion='Promo Test', es_automatica=False,
            tipo_descuento='PORCENTAJE', valor_descuento=10, fecha_inicio=timezone.localdate(), fecha_fin=timezone.localdate()
        )
        from datetime import time as _time
        self.politica = PoliticaPromocion.objects.create(
            nombre='Pol Test',
            promocion_a_otorgar=self.promocion,
            activa=True,
            prioridad=1,
            hora_inicio_rango=_time(0, 0),
            hora_fin_rango=_time(23, 59),
        )

        # crear cupón asociado a la función
        self.expira = timezone.now() + timedelta(hours=24)
        self.cupon = CuponGenerado.objects.create(cliente=self.cliente, politica_origen=self.politica, expira_en=self.expira, funcion_origen=self.funcion)

        self.client = Client()

    def test_activacion_autenticado_redirige_a_seleccion_butacas_y_preserva_sesion(self):
        login_ok = self.client.login(username=self.username, password=self.password)
        self.assertTrue(login_ok)

        url = reverse('promociones:activar_promo', kwargs={'token': str(self.cupon.token)})
        resp = self.client.get(url, follow=True)

        # debe terminar en la vista de seleccionar butacas
        final_path = resp.request.get('PATH_INFO')
        expected_path = reverse('ventas:seleccionar_butacas', args=[self.funcion.id])
        self.assertEqual(final_path, expected_path)

        # status final 200
        self.assertEqual(resp.status_code, 200)

        # session debe contener las claves
        session = self.client.session
        self.assertIn('promo_activa_id', session)
        self.assertIn('promo_token', session)
        self.assertEqual(session['promo_token'], str(self.cupon.token))

        # cupón debe quedar marcado como usado
        cupon_db = CuponGenerado.objects.get(pk=self.cupon.pk)
        self.assertTrue(cupon_db.usado)
