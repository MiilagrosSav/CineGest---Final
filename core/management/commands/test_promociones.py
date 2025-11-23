from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, time
from decimal import Decimal

from cine.models.pelicula import Pelicula
from cine.models.genero import Genero
from cine.models.funcion import Funcion

from promociones.models.promocion import Promocion
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.funcionPromocion import FuncionPromocion
from promociones.models.cuponGenerado import CuponGenerado

from promociones.services import calcular_precio_final, procesar_butaca_liberada
from ventas.obtener_mejor_promocion import obtener_mejor_promocion


class Command(BaseCommand):
    help = 'Ejecuta pruebas rápidas del flujo de promociones usando datos de prueba poblados.'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando pruebas de promociones...')
        hoy = timezone.localdate()
        fecha_inicio = hoy - timedelta(days=180)
        fecha_fin = hoy + timedelta(days=180)

        # Crear/recuperar genero y promocion
        try:
            terror = Genero.objects.get(nombre='TERROR')
        except Genero.DoesNotExist:
            self.stdout.write(self.style.ERROR('No existe el género TERROR. Ejecuta el poblador antes.'))
            return

        promo, created = Promocion.objects.get_or_create(
            codigo='REC_TERROR',
            defaults={
                'nombre': 'Recupero Terror',
                'descripcion': 'Oferta dirigida a fanáticos de terror',
                'es_automatica': True,
                'tipo_descuento': 'PORCENTAJE',
                'valor_descuento': Decimal('30.00'),
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'aplica_en_estrenos': False,
                'genero_requerido': terror,
                'dias_semana': ''
            }
        )
        self.stdout.write(f'Promoción: {promo} (creada={created})')

        # Vincular a la película
        try:
            pel = Pelicula.objects.get(titulo='La Monja 3')
        except Pelicula.DoesNotExist:
            self.stdout.write(self.style.ERROR('No existe la película "La Monja 3". Ejecuta el poblador antes.'))
            return

        fp, fpc = FuncionPromocion.objects.get_or_create(promocion=promo, pelicula=pel)
        self.stdout.write(f'FuncionPromocion: {fp} (creada={fpc})')

        # Crear política nocturna
        politica, pc = PoliticaPromocion.objects.get_or_create(
            nombre='Recupero Terror Noche',
            defaults={
                'activa': True,
                'promocion_a_otorgar': promo,
                'genero_pelicula': terror,
                'hora_inicio_rango': time(21, 0),
                'hora_fin_rango': time(23, 59),
                'dias_semana': '',
                'prioridad': 10,
                'minutos_validez': 120
            }
        )
        self.stdout.write(f'Política: {politica} (creada={pc})')

        # Elegir una función de terror preferentemente en el rango 21:00-23:59
        funcs = Funcion.objects.filter(pelicula__titulo='La Monja 3').order_by('fecha_hora')
        funcion_terror = None
        for f in funcs:
            h = f.fecha_hora.time()
            if h >= time(21, 0) and h <= time(23, 59):
                funcion_terror = f
                break
        if not funcion_terror:
            funcion_terror = funcs.first()

        # Si la función seleccionada no está en el horario nocturno esperado, crear una función futura a las 22:00 para pruebas
        h_sel = funcion_terror.fecha_hora.time() if funcion_terror else None
        if not (h_sel and h_sel >= time(21, 0) and h_sel <= time(23, 59)):
            # crear función temporal mañana a las 22:00 en la misma sala
            from cine.models.sala import Sala
            mañana_dt = timezone.now() + timedelta(days=1)
            mañana_date = mañana_dt.date()
            sala = funcion_terror.sala if funcion_terror else Sala.objects.first()
            from datetime import datetime as dt
            nueva_fecha = dt.combine(mañana_date, time(22, 0))
            if timezone.is_naive(nueva_fecha):
                nueva_fecha = timezone.make_aware(nueva_fecha)
            try:
                nueva_func = Funcion.objects.create(pelicula=pel, sala=sala, fecha_hora=nueva_fecha, precio_base=120.00)
                funcion_terror = nueva_func
                self.stdout.write(self.style.NOTICE(f'Creada función temporal para test: {funcion_terror}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'No se pudo crear función temporal: {e}'))
        if not funcion_terror:
            self.stdout.write(self.style.ERROR('No se encontró ninguna función de La Monja 3.'))
            return

        self.stdout.write(f'Función seleccionada: {funcion_terror} - {funcion_terror.fecha_hora}')

        # 1) obtener_mejor_promocion
        try:
            mejor = obtener_mejor_promocion(funcion_terror)
            self.stdout.write(f'Mejor promoción detectada por servicio: {mejor}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al ejecutar obtener_mejor_promocion: {e}'))

        # 2) calcular_precio_final para 3 entradas
        try:
            total, promo_aplicada, detalle = calcular_precio_final(funcion_terror, 3)
            self.stdout.write(f'calcular_precio_final -> total: {total}, promo: {promo_aplicada}, detalle: {detalle}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error en calcular_precio_final: {e}'))

        # 3) procesar_butaca_liberada (simula generación de cupones)
        try:
            respuestas = procesar_butaca_liberada(funcion_terror)
            self.stdout.write(f'procesar_butaca_liberada -> respuestas: {respuestas}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error en procesar_butaca_liberada: {e}'))

        # 4) listar cupones generados por la política
        cupones = CuponGenerado.objects.filter(politica_origen=politica)
        self.stdout.write(f'Cupones generados por {politica}: {cupones.count()}')
        for c in cupones[:20]:
            self.stdout.write(f' - Cliente: {c.cliente}, token: {c.token}, expira: {c.expira_en}, creado: {c.creado_en}')

        self.stdout.write(self.style.SUCCESS('Pruebas de promociones completadas.'))
