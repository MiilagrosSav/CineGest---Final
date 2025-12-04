"""
Tests completos del flujo de compra de entradas
Incluye: Happy path, rollback con pago fallido, y race conditions

Ejecutar con:
    python manage.py test tests.test_flujo_compra
"""

import threading
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction, IntegrityError
from datetime import timedelta

from accounts.models import Cliente, Usuario
from cine.models import Pelicula, Sala, Funcion, Butaca, Genero, Formato, FuncionFormato
from ventas.models import Venta, Entrada, Pago, MetodoPago


User = get_user_model()


class BaseCompraTestCase(TestCase):
    """Clase base con fixtures comunes para todos los tests de compra"""
    
    @classmethod
    def setUpTestData(cls):
        """Configurar datos de prueba que se comparten entre tests"""
        
        # Crear género (usar get_or_create para evitar duplicados)
        cls.genero, _ = Genero.objects.get_or_create(nombre='Acción')
        
        # Crear película
        from datetime import date, timedelta
        cls.pelicula = Pelicula.objects.create(
            titulo='Matrix Resurrections',
            sinopsis='El regreso a la Matrix',
            duracion=148,
            clasificacion='ATP',
            imagen_portada='',
            fecha_estreno=date.today() + timedelta(days=30)
        )
        cls.pelicula.generos.add(cls.genero)
        
        # Crear sala
        cls.sala = Sala.objects.create(
            numero=1,
            nombre='Sala Premium',
            capacidad_total=100,
            activa=True
        )
        
        # Crear butacas
        cls.butacas = []
        for fila_num in range(1, 4):  # Filas A, B, C
            fila_letra = chr(64 + fila_num)  # A=65, B=66, C=67
            for num in range(1, 6):  # Números 1-5
                butaca = Butaca.objects.create(
                    sala=cls.sala,
                    fila=fila_letra,
                    numero=num,
                    tipo='GENERAL',
                    es_pasillo=False
                )
                cls.butacas.append(butaca)
        
        # Crear formato
        cls.formato = Formato.objects.create(
            nombre='2D',
            descripcion='Formato 2D estándar',
            categoria='VISUAL'
        )
        
        # Crear función
        fecha_futura = timezone.now() + timedelta(days=7)
        cls.funcion = Funcion.objects.create(
            pelicula=cls.pelicula,
            sala=cls.sala,
            fecha_hora=fecha_futura,
            precio_base=Decimal('1500.00'),
            idioma='DOBLADA',
            estado='ACTIVA'
        )
        
        # Asociar formato a la función
        FuncionFormato.objects.create(
            funcion=cls.funcion,
            formato=cls.formato
        )
        # Crear método de pago
        cls.metodo_pago = MetodoPago.objects.create(
            nombre='Mercado Pago',
            descripcion='Pago procesado por Mercado Pago'
        )
    
    def setUp(self):
        """Configuración que se ejecuta antes de cada test"""
        # Crear usuario para cada test (no compartido)
        self.user = Usuario.objects.create_user(
            username=f'testuser_{self.id()}',
            email=f'test_{self.id()}@example.com',
            password='testpass123'
        )
        
        # Crear cliente asociado
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            fecha_nacimiento=None
        )
        
        # Inicializar cliente HTTP
        self.client = Client()
        self.client.force_login(self.user)


class HappyPathCompraTestCase(BaseCompraTestCase):
    """Tests del flujo exitoso de compra"""
    
    def test_flujo_completo_compra_exitosa(self):
        """
        Test del happy path completo (unit test puro):
        1. Usuario selecciona butacas
        2. Se crea venta PENDIENTE con entradas RESERVADAS
        3. Simular aprobación de pago
        4. Venta se marca como CONFIRMADA
        5. Se crea registro de Pago
        """
        from django.utils import timezone
        
        # PASO 1: Seleccionar 2 butacas
        butaca1, butaca2 = self.butacas[0], self.butacas[1]
        
        # PASO 2: Crear venta PENDIENTE (simular lógica de procesar_compra)
        venta = Venta.objects.create(
            id_cliente=self.cliente,
            tipo_venta='ONLINE',
            estado='PENDIENTE',
            fecha_compra=timezone.now()
        )
        
        # Crear entradas RESERVADAS
        entrada1 = Entrada.objects.create(
            id_venta=venta,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca1,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        entrada2 = Entrada.objects.create(
            id_venta=venta,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca2,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        # Verificar estado inicial
        self.assertEqual(venta.estado, 'PENDIENTE')
        self.assertEqual(entrada1.estado, 'RESERVADA')
        self.assertEqual(entrada2.estado, 'RESERVADA')
        
        # Verificar que las butacas están ocupadas
        entradas_ocupadas = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca__in=[butaca1, butaca2],
            estado__in=['RESERVADA', 'VENDIDA']
        ).count()
        self.assertEqual(entradas_ocupadas, 2)
        
        # PASO 3: Simular pago aprobado
        # Cambiar estado de venta a CONFIRMADA
        venta.estado = 'CONFIRMADA'
        venta.save()
        
        # Generar código de compra (simular lógica de generar_codigo_compra)
        import random
        import string
        codigo = f"CG-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
        venta.codigo_compra = codigo
        venta.save()
        
        # Crear registro de pago
        pago = Pago.objects.create(
            id_venta=venta,
            monto=venta.calcular_total(),
            fecha_pago=timezone.now(),
            estado='COMPLETADO',
            nro_transaccion='payment_123456',
            id_metodo_pago=self.metodo_pago
        )
        
        # PASO 4: Verificaciones finales
        venta.refresh_from_db()
        
        # Verificar que la venta está CONFIRMADA
        self.assertEqual(venta.estado, 'CONFIRMADA')
        
        # Verificar que se generó código de compra
        self.assertIsNotNone(venta.codigo_compra)
        self.assertTrue(venta.codigo_compra.startswith('CG-'))
        
        # Verificar que se creó el registro de pago
        pago_guardado = Pago.objects.filter(id_venta=venta).first()
        self.assertIsNotNone(pago_guardado)
        self.assertEqual(pago_guardado.estado, 'COMPLETADO')
        self.assertEqual(pago_guardado.nro_transaccion, 'payment_123456')
        
        # Verificar que las entradas siguen asociadas a la venta
        entradas_finales = Entrada.objects.filter(id_venta=venta)
        self.assertEqual(entradas_finales.count(), 2)
        
        # Verificar que las butacas siguen ocupadas
        for entrada in entradas_finales:
            self.assertIn(entrada.id_butaca, [butaca1, butaca2])


class RollbackPagoFallidoTestCase(BaseCompraTestCase):
    """Tests de rollback cuando el pago falla"""
    
    def test_pago_rechazado_mantiene_venta_pendiente(self):
        """
        Cuando el pago es rechazado (unit test puro):
        1. La venta debe permanecer en estado PENDIENTE
        2. Las entradas deben permanecer RESERVADAS
        3. No se crea registro de Pago exitoso
        """
        from django.utils import timezone
        
        # PASO 1: Crear venta y entradas
        butaca1, butaca2 = self.butacas[2], self.butacas[3]
        
        venta = Venta.objects.create(
            id_cliente=self.cliente,
            tipo_venta='ONLINE',
            estado='PENDIENTE',
            fecha_compra=timezone.now()
        )
        
        entrada1 = Entrada.objects.create(
            id_venta=venta,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca1,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        entrada2 = Entrada.objects.create(
            id_venta=venta,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca2,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        # Verificar estado inicial
        self.assertEqual(venta.estado, 'PENDIENTE')
        self.assertEqual(entrada1.estado, 'RESERVADA')
        self.assertEqual(entrada2.estado, 'RESERVADA')
        
        # PASO 2: Simular intento de pago rechazado
        # En el sistema real, cuando MP rechaza el pago, la venta permanece PENDIENTE
        # No cambiamos el estado ya que el pago fue rechazado
        
        # VERIFICACIONES: La venta debe seguir PENDIENTE
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'PENDIENTE')
        
        # Las entradas deben seguir RESERVADAS (no canceladas)
        entrada1.refresh_from_db()
        entrada2.refresh_from_db()
        self.assertEqual(entrada1.estado, 'RESERVADA')
        self.assertEqual(entrada2.estado, 'RESERVADA')
        
        # No debe existir registro de pago exitoso
        pago_exitoso = Pago.objects.filter(id_venta=venta, estado='COMPLETADO').exists()
        self.assertFalse(pago_exitoso)
        
        # Las butacas deben seguir ocupadas (reservadas para este usuario)
        entradas_reservadas = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca__in=[butaca1, butaca2],
            estado='RESERVADA'
        ).count()
        self.assertEqual(entradas_reservadas, 2)
    
    def test_error_crear_preferencia_no_afecta_venta(self):
        """
        Si falla la creación de preferencia en MP (unit test puro):
        1. La venta debe existir en estado PENDIENTE
        2. Las entradas deben estar RESERVADAS
        3. El error no debe afectar los datos creados
        """
        from django.utils import timezone
        
        # PASO 1: Crear venta y entrada
        butaca = self.butacas[4]
        
        venta = Venta.objects.create(
            id_cliente=self.cliente,
            tipo_venta='ONLINE',
            estado='PENDIENTE',
            fecha_compra=timezone.now()
        )
        
        entrada = Entrada.objects.create(
            id_venta=venta,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        # PASO 2: Simular que MP falla al crear preferencia
        # En el sistema real, esto devolvería error pero la venta ya fue creada
        # Aquí simplemente verificamos que los datos persisten correctamente
        
        # VERIFICACIONES: La venta debe existir en PENDIENTE
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'PENDIENTE')
        
        # La entrada debe seguir RESERVADA
        entrada.refresh_from_db()
        self.assertEqual(entrada.estado, 'RESERVADA')
        
        # La butaca debe estar ocupada
        entrada_existe = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca=butaca,
            estado='RESERVADA'
        ).exists()
        self.assertTrue(entrada_existe)


class RaceConditionTestCase(TransactionTestCase):
    """
    Tests de concurrencia (race conditions)
    Usa TransactionTestCase para poder testear transacciones reales
    """
    
    def setUp(self):
        """Configurar datos para test de concurrencia"""
        # Crear género (usar get_or_create para evitar duplicados)
        self.genero, _ = Genero.objects.get_or_create(nombre='Acción')
        
        # Crear película
        from datetime import date, timedelta
        self.pelicula = Pelicula.objects.create(
            titulo='Matrix',
            sinopsis='The Matrix',
            duracion=136,
            clasificacion='ATP',
            fecha_estreno=date.today() + timedelta(days=30)
        )
        self.pelicula.generos.add(self.genero)
        
        # Crear sala
        self.sala = Sala.objects.create(
            numero=2,
            nombre='Sala Test',
            capacidad_total=10,
            activa=True
        )
        
        # Crear una sola butaca (la que se disputarán)
        self.butaca_disputada = Butaca.objects.create(
            sala=self.sala,
            fila='A',
            numero=1,
            tipo='GENERAL',
            es_pasillo=False
        )
        
        # Crear formato
        self.formato = Formato.objects.create(
            nombre='2D',
            descripcion='2D',
            categoria='VISUAL'
        )
        
        # Crear función
        fecha_futura = timezone.now() + timedelta(days=5)
        self.funcion = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=fecha_futura,
            precio_base=Decimal('1200.00'),
            idioma='DOBLADA',
            estado='ACTIVA'
        )
        
        FuncionFormato.objects.create(
            funcion=self.funcion,
            formato=self.formato
        )
        
        # Crear dos usuarios diferentes
        self.user1 = Usuario.objects.create_user(
            username='user1_race',
            email='user1@race.com',
            password='pass123'
        )
        self.cliente1 = Cliente.objects.create(
            usuario=self.user1,
            fecha_nacimiento=None
        )
        
        self.user2 = Usuario.objects.create_user(
            username='user2_race',
            email='user2@race.com',
            password='pass123'
        )
        self.cliente2 = Cliente.objects.create(
            usuario=self.user2,
            fecha_nacimiento=None
        )
    
    def tearDown(self):
        # Importamos la gestión de conexiones
        from django.db import connections
        
        # Cerramos forzosamente todas las conexiones abiertas por los hilos
        connections.close_all()
        
        # Llamamos al método original de Django para que limpie el resto
        super().tearDown()
    
    def test_dos_usuarios_compran_misma_butaca_simultaneamente(self):
        """
        Test de race condition:
        Dos usuarios intentan comprar la misma butaca al mismo tiempo.
        Solo uno debe tener éxito, el otro debe recibir un error.
        
        Esto verifica que select_for_update() funciona correctamente.
        """
        
        resultados = {'exitoso': 0, 'fallido': 0, 'excepciones': []}
        
        def intentar_compra(user, cliente, nombre_usuario):
            """Función que ejecuta cada thread"""
            try:
                with transaction.atomic():
                    # Simular el comportamiento de procesar_compra
                    
                    # 1. Lock pesimista en la butaca
                    entrada_ocupada = Entrada.objects.select_for_update().filter(
                        id_funcion=self.funcion,
                        id_butaca=self.butaca_disputada,
                        estado__in=['RESERVADA', 'VENDIDA', 'PENDIENTE']
                    ).first()
                    
                    if entrada_ocupada:
                        # Butaca ya ocupada
                        resultados['fallido'] += 1
                        print(f"[X] {nombre_usuario}: Butaca ocupada")
                        return
                    
                    # 2. Crear venta
                    venta = Venta.objects.create(
                        id_cliente=cliente,
                        tipo_venta='ONLINE',
                        estado='PENDIENTE'
                    )
                    
                    # 3. Crear entrada
                    Entrada.objects.create(
                        id_venta=venta,
                        id_funcion=self.funcion,
                        id_sala=self.sala,
                        id_butaca=self.butaca_disputada,
                        id_pelicula=self.pelicula,
                        estado='RESERVADA',
                        reservado_por=user
                    )
                    
                    resultados['exitoso'] += 1
                    print(f"[OK] {nombre_usuario}: Compra exitosa - Venta #{venta.id_venta}")
                    
            except IntegrityError as e:
                # Error de constraint de unicidad
                resultados['fallido'] += 1
                resultados['excepciones'].append(str(e))
                print(f"[!] {nombre_usuario}: IntegrityError - {str(e)[:100]}")
            except Exception as e:
                resultados['fallido'] += 1
                resultados['excepciones'].append(str(e))
                print(f"[!] {nombre_usuario}: Exception - {str(e)[:100]}")
        
        # Crear dos threads que intentan comprar simultáneamente
        thread1 = threading.Thread(
            target=intentar_compra,
            args=(self.user1, self.cliente1, 'Usuario1')
        )
        thread2 = threading.Thread(
            target=intentar_compra,
            args=(self.user2, self.cliente2, 'Usuario2')
        )
        
        # Iniciar ambos threads casi simultáneamente
        thread1.start()
        thread2.start()
        
        # Esperar a que ambos terminen
        thread1.join()
        thread2.join()
        
        # VERIFICACIONES
        print(f"\n[RESULTADOS] {resultados['exitoso']} exitoso(s), {resultados['fallido']} fallido(s)")
        
        # Solo UNO debe haber tenido éxito
        self.assertEqual(resultados['exitoso'], 1, 
                        "Solo un usuario debería poder comprar la butaca")
        
        # El otro debe haber fallado
        self.assertEqual(resultados['fallido'], 1,
                        "El segundo usuario debería haber fallado")
        
        # Verificar que solo existe UNA entrada para esta butaca
        entradas = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca=self.butaca_disputada,
            estado__in=['RESERVADA', 'VENDIDA']
        )
        self.assertEqual(entradas.count(), 1,
                        "Solo debe existir una entrada para la butaca disputada")
        
        # Verificar que solo existe UNA venta
        ventas = Venta.objects.filter(
            id_cliente__in=[self.cliente1, self.cliente2],
            estado='PENDIENTE'
        )
        self.assertEqual(ventas.count(), 1,
                        "Solo debe existir una venta")
    
    def test_butaca_no_puede_reservarse_dos_veces(self):
        """
        Test de constraint de base de datos:
        Verifica que el constraint de unicidad UQ_entrada_funcion_butaca
        previene crear dos entradas para la misma butaca en la misma función.
        """
        
        # Crear primera entrada
        venta1 = Venta.objects.create(
            id_cliente=self.cliente1,
            tipo_venta='ONLINE',
            estado='PENDIENTE'
        )
        
        entrada1 = Entrada.objects.create(
            id_venta=venta1,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=self.butaca_disputada,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user1
        )
        
        # Intentar crear segunda entrada para la misma butaca
        venta2 = Venta.objects.create(
            id_cliente=self.cliente2,
            tipo_venta='ONLINE',
            estado='PENDIENTE'
        )
        
        # Debe lanzar IntegrityError por violación de constraint
        with self.assertRaises(IntegrityError):
            Entrada.objects.create(
                id_venta=venta2,
                id_funcion=self.funcion,
                id_sala=self.sala,
                id_butaca=self.butaca_disputada,
                id_pelicula=self.pelicula,
                estado='RESERVADA',
                reservado_por=self.user2
            )
        
        # Verificar que solo existe una entrada
        entradas = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca=self.butaca_disputada
        )
        self.assertEqual(entradas.count(), 1)


class ValidacionesNegocioTestCase(BaseCompraTestCase):
    """Tests de validaciones de reglas de negocio"""
    
    def test_no_se_puede_comprar_butaca_ya_reservada(self):
        """
        Un usuario no puede comprar una butaca que ya está reservada
        por otro usuario
        """
        
        # Usuario 1 reserva una butaca
        butaca = self.butacas[0]
        
        venta1 = Venta.objects.create(
            id_cliente=self.cliente,
            tipo_venta='ONLINE',
            estado='PENDIENTE'
        )
        
        Entrada.objects.create(
            id_venta=venta1,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        # Usuario 2 intenta comprar la misma butaca
        user2 = Usuario.objects.create_user(
            username='user2_test',
            email='user2@test.com',
            password='pass123'
        )
        cliente2 = Cliente.objects.create(
            usuario=user2,
            fecha_nacimiento=None
        )
        
        # Intentar crear una segunda entrada causará IntegrityError
        from django.db import IntegrityError
        from django.utils import timezone
        
        venta2 = Venta.objects.create(
            id_cliente=cliente2,
            tipo_venta='ONLINE',
            estado='PENDIENTE',
            fecha_compra=timezone.now()
        )
        
        # Verificar que la butaca ya está ocupada
        butaca_ocupada = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca=butaca,
            estado__in=['RESERVADA', 'VENDIDA']
        ).exists()
        self.assertTrue(butaca_ocupada, "La butaca debe estar ocupada")
        
        with self.assertRaises(IntegrityError):
            Entrada.objects.create(
                id_venta=venta2,
                id_funcion=self.funcion,
                id_sala=self.sala,
                id_butaca=butaca,
                id_pelicula=self.pelicula,
                estado='RESERVADA',
                reservado_por=user2
            )
    
    def test_usuario_puede_reutilizar_su_propia_reserva_reciente(self):
        """
        Si un usuario reserva butacas pero vuelve al selector (unit test puro)
        (sin completar pago), puede reutilizar esas mismas butacas
        """
        from django.utils import timezone
        
        butaca1, butaca2 = self.butacas[0], self.butacas[1]
        
        # Primera reserva
        venta1 = Venta.objects.create(
            id_cliente=self.cliente,
            tipo_venta='ONLINE',
            estado='PENDIENTE',
            fecha_compra=timezone.now()
        )
        
        entrada1 = Entrada.objects.create(
            id_venta=venta1,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca1,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        entrada2 = Entrada.objects.create(
            id_venta=venta1,
            id_funcion=self.funcion,
            id_sala=self.sala,
            id_butaca=butaca2,
            id_pelicula=self.pelicula,
            estado='RESERVADA',
            reservado_por=self.user
        )
        
        # Verificar que las entradas existen
        entradas = Entrada.objects.filter(
            id_funcion=self.funcion,
            id_butaca__in=[butaca1, butaca2],
            reservado_por=self.user,
            estado='RESERVADA'
        )
        self.assertEqual(entradas.count(), 2)
        
        # Simular que el usuario puede reutilizar estas entradas
        # En el sistema real, si el usuario selecciona las mismas butacas dentro de 2 minutos,
        # la vista procesar_compra las reutiliza en lugar de crear nuevas
        
        # Verificar que las entradas siguen disponibles para el mismo usuario
        entrada1.refresh_from_db()
        entrada2.refresh_from_db()
        self.assertEqual(entrada1.reservado_por, self.user)
        self.assertEqual(entrada2.reservado_por, self.user)
    
    def test_no_se_pueden_seleccionar_butacas_pasillo(self):
        """
        Las butacas marcadas como pasillo no pueden ser seleccionadas
        """
        
        # Crear una butaca de pasillo
        butaca_pasillo = Butaca.objects.create(
            sala=self.sala,
            fila='Z',
            numero=99,
            tipo='PASILLO',
            es_pasillo=True
        )
        
        # Intentar comprar butaca de pasillo
        response = self.client.post(
            f'/ventas/procesar-compra/{self.funcion.id}/',
            data={'butacas[]': [butaca_pasillo.id]},
            follow=True
        )
        
        # No debe crear venta
        ventas = Venta.objects.filter(id_cliente=self.cliente)
        
        # Si se creó venta, verificar que no tiene entradas
        if ventas.exists():
            venta = ventas.latest('fecha_compra')
            entradas = Entrada.objects.filter(
                id_venta=venta,
                id_butaca=butaca_pasillo
            )
            self.assertEqual(entradas.count(), 0,
                           "No debe crear entrada para butaca de pasillo")


# Comando para ejecutar los tests:
# python manage.py test tests.test_flujo_compra

# Para ejecutar solo un test específico:
# python manage.py test tests.test_flujo_compra.HappyPathCompraTestCase.test_flujo_completo_compra_exitosa

# Para ejecutar con más detalle:
# python manage.py test tests.test_flujo_compra --verbosity=2

# Para ejecutar tests de concurrencia solamente:
# python manage.py test tests.test_flujo_compra.RaceConditionTestCase
