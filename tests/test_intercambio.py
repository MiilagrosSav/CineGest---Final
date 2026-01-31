"""
Tests de integración para el sistema de intercambio de entradas.

Valida el flujo completo end-to-end:
- Creación de venta inicial confirmada
- Validación de políticas de intercambio
- Ejecución de intercambio con transacción atómica
- Verificación de estados de entradas (canceladas y nuevas)
- Auditoría completa (registro de Intercambio)
- Integración con marketing (procesar_butaca_liberada)
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.models import Cliente
from ventas.models import Venta, Entrada, MetodoPago, Pago, Intercambio
from ventas.models.politica_reembolso import PoliticaReembolso
from ventas.intercambio_service import intercambio_service
from ventas.constants import EstadoEntrada
from cine.models import Pelicula, Sala, Funcion, Butaca, Genero


User = get_user_model()


class IntercambioIntegrationTest(TestCase):
    """Tests de integración completos para el sistema de intercambio."""
    
    def setUp(self):
        """Configuración inicial de datos de prueba."""
        # Crear género
        self.genero, _ = Genero.objects.get_or_create(nombre="Acción")
        
        # Crear película
        self.pelicula = Pelicula.objects.create(
            titulo="Película Test",
            duracion=120,
            sinopsis="Test",
            fecha_estreno=timezone.localdate()
        )
        self.pelicula.generos.add(self.genero)
        
        # Crear sala con butacas
        self.sala = Sala.objects.create(
            numero=1,
            nombre="Sala Test",
            capacidad_total=10
        )
        
        # Crear 10 butacas (2 filas de 5)
        for fila in ['A', 'B']:
            for num in range(1, 6):
                Butaca.objects.create(
                    sala=self.sala,
                    fila=fila,
                    numero=num,
                    tipo='NORMAL',
                    es_pasillo=False
                )
        
        # Crear funciones (origen y destino con mismo precio)
        fecha_base = timezone.now() + timedelta(days=5)
        self.funcion_origen = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=fecha_base,
            precio_base=Decimal('100.00')
        )
        
        self.funcion_destino = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=fecha_base + timedelta(days=1),
            precio_base=Decimal('100.00')
        )
        
        # Crear usuario y cliente
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Usuario'
        )
        self.cliente = Cliente.objects.create(
            usuario=self.user
        )
        
        # Crear método de pago
        self.metodo_pago = MetodoPago.objects.create(
            nombre='Efectivo',
            descripcion='Pago en efectivo'
        )
        
        # Crear política de intercambio activa
        self.politica = PoliticaReembolso.objects.create(
            nombre='Política Test',
            activo=True,
            dias_antes_minimo=2,  # 2 días (48 horas) de anticipación
            penalidad_percent=Decimal('0.00'),
            max_cambios_por_compra=2  # Permitir hasta 2 intercambios
        )
    
    def _crear_venta_confirmada(self, cantidad_entradas=2):
        """Helper para crear una venta confirmada con entradas."""
        # Crear venta
        venta = Venta.objects.create(
            id_cliente=self.cliente,
            estado='CONFIRMADA',
            cantidad_entradas=cantidad_entradas
        )
        
        # Crear pago
        Pago.objects.create(
            id_venta=venta,
            monto=self.funcion_origen.precio_base * cantidad_entradas,
            estado='COMPLETADO',
            id_metodo_pago=self.metodo_pago,
            nro_transaccion=f'TEST-{venta.id_venta}'
        )
        
        # Crear entradas VENDIDAS
        butacas = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[:cantidad_entradas])
        for butaca in butacas:
            Entrada.objects.create(
                id_venta=venta,
                id_funcion=self.funcion_origen,
                id_sala=self.sala,
                id_butaca=butaca,
                id_pelicula=self.pelicula,
                estado=EstadoEntrada.VENDIDA
            )
        
        return venta, butacas
    
    def test_intercambio_exitoso_basico(self):
        """Test: Intercambio exitoso básico con todas las validaciones."""
        # Arrange
        venta, butacas_originales = self._crear_venta_confirmada(cantidad_entradas=2)
        butacas_destino = list(
            Butaca.objects.filter(sala=self.sala)
            .exclude(id__in=[b.id for b in butacas_originales])
            .order_by('fila', 'numero')[:2]
        )
        
        # Act
        exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=self.funcion_destino,
            butacas=butacas_destino,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertTrue(exitoso, f"Intercambio falló: {mensaje}")
        self.assertIsNotNone(intercambio)
        
        # Verificar entradas canceladas
        entradas_canceladas = Entrada.objects.filter(
            id_venta=venta,
            id_funcion=self.funcion_origen,
            estado=EstadoEntrada.CANCELADA
        )
        self.assertEqual(entradas_canceladas.count(), 2)
        
        # Verificar nuevas entradas creadas
        entradas_nuevas = Entrada.objects.filter(
            id_venta=venta,
            id_funcion=self.funcion_destino,
            estado=EstadoEntrada.VENDIDA
        )
        self.assertEqual(entradas_nuevas.count(), 2)
        
        # Verificar butacas asignadas correctamente
        butacas_asignadas = set(entradas_nuevas.values_list('id_butaca_id', flat=True))
        butacas_esperadas = set([b.id for b in butacas_destino])
        self.assertEqual(butacas_asignadas, butacas_esperadas)
        
        # Verificar auditoría
        self.assertEqual(intercambio.venta, venta)
        self.assertEqual(intercambio.funcion_origen, self.funcion_origen)
        self.assertEqual(intercambio.funcion_destino, self.funcion_destino)
        self.assertEqual(intercambio.estado, 'COMPLETADO')
        self.assertEqual(intercambio.cantidad_entradas, 2)
        self.assertEqual(intercambio.penalidad_aplicada, Decimal('0.00'))
        
        # Verificar que venta sigue CONFIRMADA
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'CONFIRMADA')
    
    def test_validacion_politica_dias_anticipacion(self):
        """Test: Valida que se rechace intercambio fuera del plazo mínimo."""
        # Arrange: Función muy próxima (1 día, pero política requiere 2)
        fecha_proxima = timezone.now() + timedelta(hours=30)  # 1.25 días
        funcion_proxima = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=fecha_proxima,
            precio_base=Decimal('100.00')
        )
        
        venta, _ = self._crear_venta_confirmada(cantidad_entradas=2)
        
        # Actualizar entradas para usar función próxima
        Entrada.objects.filter(id_venta=venta).update(id_funcion=funcion_proxima)
        
        butacas_destino = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[:2])
        
        # Act
        exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=self.funcion_destino,
            butacas=butacas_destino,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertFalse(exitoso)
        self.assertIn('anticipación', mensaje.lower())
        self.assertIsNone(intercambio)
    
    def test_validacion_precio_diferente(self):
        """Test: Valida que se rechace intercambio a función con precio diferente."""
        # Arrange
        funcion_diferente_precio = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=timezone.now() + timedelta(days=5),
            precio_base=Decimal('150.00')  # Precio diferente
        )
        
        venta, _ = self._crear_venta_confirmada(cantidad_entradas=2)
        butacas_destino = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[:2])
        
        # Act
        exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=funcion_diferente_precio,
            butacas=butacas_destino,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertFalse(exitoso)
        self.assertIn('precio', mensaje.lower())
        self.assertIsNone(intercambio)
    
    def test_limite_max_cambios_por_compra(self):
        """Test: Valida límite de intercambios por compra (max_cambios_por_compra)."""
        # Arrange
        venta, _ = self._crear_venta_confirmada(cantidad_entradas=2)
        
        # Realizar primer intercambio (exitoso)
        butacas1 = list(Butaca.objects.filter(sala=self.sala, fila='B').order_by('numero')[:2])
        exitoso1, _, _ = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=self.funcion_destino,
            butacas=butacas1,
            motivo='OTRO',
            request=None
        )
        self.assertTrue(exitoso1)
        
        # Crear tercera función para segundo intercambio
        funcion3 = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=timezone.now() + timedelta(days=7),
            precio_base=Decimal('100.00')
        )
        
        # Realizar segundo intercambio (exitoso, aún dentro del límite)
        venta.refresh_from_db()
        butacas2 = list(Butaca.objects.filter(sala=self.sala, fila='A').order_by('numero')[2:4])
        exitoso2, _, _ = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=funcion3,
            butacas=butacas2,
            motivo='OTRO',
            request=None
        )
        self.assertTrue(exitoso2)
        
        # Verificar que hay 2 intercambios registrados
        self.assertEqual(Intercambio.objects.filter(venta=venta).count(), 2)
        
        # Crear cuarta función para tercer intercambio
        funcion4 = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=timezone.now() + timedelta(days=8),
            precio_base=Decimal('100.00')
        )
        
        # Intentar tercer intercambio (debe fallar por límite)
        venta.refresh_from_db()
        butacas3 = list(Butaca.objects.filter(sala=self.sala, fila='B')[2:4])
        exitoso3, mensaje3, _ = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=funcion4,
            butacas=butacas3,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertFalse(exitoso3)
        self.assertIn('límite', mensaje3.lower())
        self.assertEqual(Intercambio.objects.filter(venta=venta).count(), 2)  # No se creó el tercero
    
    def test_disponibilidad_butacas(self):
        """Test: Valida que se rechace intercambio si butacas están ocupadas."""
        # Arrange
        venta, _ = self._crear_venta_confirmada(cantidad_entradas=2)
        
        # Ocupar butacas en función destino
        butacas_ocupadas = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[:2])
        otro_cliente = Cliente.objects.create(
            usuario=User.objects.create_user(username='otro', password='pass')
        )
        otra_venta = Venta.objects.create(
            id_cliente=otro_cliente,
            estado='CONFIRMADA',
            cantidad_entradas=2
        )
        for butaca in butacas_ocupadas:
            Entrada.objects.create(
                id_venta=otra_venta,
                id_funcion=self.funcion_destino,
                id_sala=self.sala,
                id_butaca=butaca,
                id_pelicula=self.pelicula,
                estado=EstadoEntrada.VENDIDA
            )
        
        # Act: Intentar intercambio con butacas ocupadas
        exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=self.funcion_destino,
            butacas=butacas_ocupadas,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertFalse(exitoso)
        self.assertIsNone(intercambio)
        
        # Verificar que no se modificaron entradas originales
        entradas_originales = Entrada.objects.filter(
            id_venta=venta,
            id_funcion=self.funcion_origen
        )
        self.assertEqual(entradas_originales.count(), 2)
        self.assertTrue(all(e.estado == EstadoEntrada.VENDIDA for e in entradas_originales))
    
    def test_venta_no_confirmada(self):
        """Test: Valida que solo se puedan intercambiar ventas CONFIRMADAS."""
        # Arrange: Crear venta en estado PENDIENTE
        venta = Venta.objects.create(
            id_cliente=self.cliente,
            estado='PENDIENTE',  # No confirmada
            cantidad_entradas=2
        )
        
        butacas_originales = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[:2])
        for butaca in butacas_originales:
            Entrada.objects.create(
                id_venta=venta,
                id_funcion=self.funcion_origen,
                id_sala=self.sala,
                id_butaca=butaca,
                id_pelicula=self.pelicula,
                estado=EstadoEntrada.RESERVADA
            )
        
        butacas_destino = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[2:4])
        
        # Act
        exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=self.funcion_destino,
            butacas=butacas_destino,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertFalse(exitoso)
        self.assertIn('activas', mensaje.lower())
        self.assertIsNone(intercambio)
    
    def test_politica_inactiva(self):
        """Test: Valida que se rechace intercambio si no hay política activa."""
        # Arrange
        self.politica.activo = False
        self.politica.save()
        
        venta, _ = self._crear_venta_confirmada(cantidad_entradas=2)
        butacas_destino = list(Butaca.objects.filter(sala=self.sala).order_by('fila', 'numero')[:2])
        
        # Act
        exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
            venta=venta,
            funcion_destino=self.funcion_destino,
            butacas=butacas_destino,
            motivo='OTRO',
            request=None
        )
        
        # Assert
        self.assertFalse(exitoso)
        self.assertIn('activa', mensaje.lower())
        self.assertIsNone(intercambio)
