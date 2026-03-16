"""
Tests simplificados para el sistema de promociones
"""
from decimal import Decimal
from datetime import datetime, timedelta, date

from django.test import TestCase
from django.utils import timezone

from promociones.models.promocion import Promocion
from promociones.services import calcular_precio_final, es_promocion_valida_para_funcion

from cine.models import Pelicula, Sala, Funcion, Genero
from cine.models import Butaca


class PromocionSimpleTestCase(TestCase):
    """Tests simples para tipos de descuento de promociones"""
    
    def setUp(self):
        """Configuración mínima"""
        # Crear género
        self.genero, _ = Genero.objects.get_or_create(nombre='Test')
        
        # Obtener clasificación ATP
        from cine.models import Clasificacion
        self.clasificacion_atp, _ = Clasificacion.objects.get_or_create(
            nombre='ATP',
            defaults={'descripcion': 'Apta para todo público', 'edad_minima': 0}
        )
        
        # Crear película
        self.pelicula = Pelicula.objects.create(
            titulo='Test Movie',
            sinopsis='Test',
            duracion=120,
            clasificacion=self.clasificacion_atp,
            fecha_estreno=date.today(),
            acepta_promociones=True
        )
        self.pelicula.generos.add(self.genero)
        
        # Crear sala simple
        self.sala = Sala.objects.create(numero=999, nombre='Test Sala')
        # Crear solo 1 butaca para que funcione
        Butaca.objects.create(sala=self.sala, fila=1, numero=1, tipo='GENERAL')
        
        # Crear función
        self.funcion = Funcion.objects.create(
            pelicula=self.pelicula,
            sala=self.sala,
            fecha_hora=timezone.now() + timedelta(days=1),
            precio_base=Decimal('100.00'),
            estado='activa'
        )
    
    def test_porcentaje_20(self):
        """Test descuento porcentual 20%"""
        promo = Promocion.objects.create(
            codigo='TEST20',
            nombre='20% off',
            tipo_descuento='PORCENTAJE',
            valor_descuento=20,
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=30),
            es_automatica=True
        )
        
        total, promo_aplicada, _  = calcular_precio_final(
            self.funcion, 1, promo
        )
        
        self.assertEqual(total, Decimal('80.00'))
        self.assertEqual(promo_aplicada, promo)
    
    def test_2x1_dos_entradas(self):
        """Test 2x1 con 2 entradas"""
        promo = Promocion.objects.create(
            codigo='2X1',
            nombre='2x1',
            tipo_descuento='2X1',
            valor_descuento=50,
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=30),
            es_automatica=True
        )
        
        total, _, _ = calcular_precio_final(
            self.funcion, 2, promo
        )
        
        # 2x1: paga solo 1
        self.assertEqual(total, Decimal('100.00'))
    
    def test_promocion_expirada_no_aplica(self):
        """Promoción expirada debe rechazarse"""
        promo = Promocion.objects.create(
            codigo='EXP',
            nombre='Expirada',
            tipo_descuento='PORCENTAJE',
            valor_descuento=50,
            fecha_inicio=date.today() - timedelta(days=60),
            fecha_fin=date.today() - timedelta(days=1),  # Ayer
            es_automatica=False
        )
        
        # No debe aplicarse
        es_valida = es_promocion_valida_para_funcion(promo, self.funcion)
        self.assertFalse(es_valida)
    
    def test_promocion_especifica_expirada(self):
        """Promoción específica expirada no debe aplicar descuento"""
        promo = Promocion.objects.create(
            codigo='EXPSPEC',
            nombre='Expirada específica',
            tipo_descuento='PORCENTAJE',
            valor_descuento=50,
            fecha_inicio=date.today() - timedelta(days=60),
            fecha_fin=date.today() - timedelta(days=1),
            es_automatica=False
        )
        
        # Al pasar promoción expirada, debe aplicar precio normal
        total, promo_aplicada, detalle = calcular_precio_final(
            self.funcion, 2, promo
        )
        
        # Precio sin descuento
        self.assertEqual(total, Decimal('200.00'))
        self.assertIsNone(promo_aplicada)
        self.assertIn('no es válida', detalle.get('aviso', ''))


def run_tests():
    """Helper para ejecutar tests"""
    import sys
    from django.core.management import call_command
    result = call_command('test', 'tests.test_promociones', verbosity=2)
    sys.exit(0 if result == 0 else 1)


if __name__ == '__main__':
    run_tests()
