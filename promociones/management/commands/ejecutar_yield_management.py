"""
Comando de gestión para ejecutar Yield Management Automático.

Este comando escanea funciones futuras y dispara promociones automáticas
cuando la ocupación es baja, según las políticas configuradas.

Uso:
    python manage.py ejecutar_yield_management [--dry-run] [--verbosity=2]

Configuración recomendada de Cron (cada hora):
    0 * * * * cd /path/to/proyecto && python manage.py ejecutar_yield_management >> /var/log/yield_management.log 2>&1
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q
from django.db import transaction

from cine.models import Funcion
from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.cuponGenerado import CuponGenerado
from accounts.models import Cliente
from ventas.models import Venta
from core.services.notificaciones import NotificacionService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ejecuta el sistema de Yield Management automático: escanea funciones con baja ocupación y dispara promociones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la ejecución sin enviar emails ni modificar la base de datos',
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='[PRUEBAS] Revisa todas las funciones futuras y permite envíos múltiples',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        test_mode = options.get('test_mode', False)
        verbosity = options['verbosity']

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS('=== Iniciando Yield Management Automático ==='))
            if dry_run:
                self.stdout.write(self.style.WARNING('[MODO DRY-RUN] No se realizarán cambios ni envíos'))
            if test_mode:
                self.stdout.write(self.style.WARNING('[MODO TEST] Revisa todas las funciones futuras, permite envíos múltiples'))

        # 1. Obtener políticas activas con yield management habilitado
        politicas_activas = PoliticaPromocion.objects.filter(
            activa=True,
            activar_por_ocupacion=True
        ).select_related('promocion_a_otorgar', 'genero_pelicula').order_by('prioridad')

        if not politicas_activas.exists():
            if verbosity >= 1:
                self.stdout.write(self.style.WARNING('No hay políticas activas con yield management habilitado.'))
            return

        if verbosity >= 2:
            self.stdout.write(f'Políticas activas encontradas: {politicas_activas.count()}')
            for pol in politicas_activas:
                self.stdout.write(f'  - {pol.nombre} (umbral: {pol.umbral_ocupacion}%, anticipación: {pol.horas_anticipacion}h)')

        # Contadores para el reporte final
        funciones_evaluadas = 0
        funciones_activadas = 0
        cupones_generados = 0
        emails_enviados = 0

        now = timezone.now()

        # 2. Iterar sobre cada política y buscar funciones candidatas
        for politica in politicas_activas:
            # Calcular ventana de tiempo
            inicio_ventana = now
            if test_mode:
                # En modo test, revisar TODAS las funciones futuras sin límite de tiempo
                fin_ventana = now + timedelta(days=365)  # 1 año hacia adelante
            else:
                fin_ventana = now + timedelta(hours=politica.horas_anticipacion)

            if verbosity >= 2:
                self.stdout.write(f'\n--- Procesando política: {politica.nombre} ---')
                self.stdout.write(f'Ventana: {inicio_ventana.strftime("%Y-%m-%d %H:%M")} a {fin_ventana.strftime("%Y-%m-%d %H:%M")}')

            # Buscar funciones candidatas:
            # - Futuras dentro de la ventana de anticipación
            # - Estado NORMAL (no tienen oferta activa) [excepto en test_mode]
            # - Opcionalmente filtrar por género si la política lo especifica
            # - Opcionalmente filtrar por día de la semana
            # - Opcionalmente filtrar por horario

            funciones_query = Funcion.objects.filter(
                fecha_hora__gte=inicio_ventana,
                fecha_hora__lte=fin_ventana
            )
            
            # En modo test, permitir procesar funciones múltiples veces
            if not test_mode:
                funciones_query = funciones_query.filter(estado_promocion='NORMAL')
            
            funciones_query = funciones_query.select_related('pelicula', 'sala').prefetch_related('pelicula__generos')

            # Filtrar por género si la política lo requiere
            if politica.genero_pelicula:
                funciones_query = funciones_query.filter(pelicula__generos=politica.genero_pelicula)

            # Filtrar por día de la semana si la política lo especifica
            dias_permitidos = politica.get_dias_list()
            if dias_permitidos:
                # Filtrar funciones cuyo weekday esté en la lista
                funciones_candidatas = []
                for funcion in funciones_query:
                    if funcion.fecha_hora.weekday() in dias_permitidos:
                        funciones_candidatas.append(funcion)
                funciones_query = funciones_candidatas
            else:
                funciones_query = list(funciones_query)

            # Filtrar por rango horario
            funciones_filtradas = []
            for funcion in funciones_query:
                hora_funcion = funcion.fecha_hora.time()
                if politica.hora_inicio_rango <= hora_funcion <= politica.hora_fin_rango:
                    funciones_filtradas.append(funcion)

            if verbosity >= 2:
                self.stdout.write(f'Funciones candidatas después de filtros: {len(funciones_filtradas)}')

            # 3. Para cada función candidata, calcular ocupación y evaluar
            for funcion in funciones_filtradas:
                funciones_evaluadas += 1

                # Calcular ocupación actual
                total_butacas = funcion.sala.capacidad
                entradas_vendidas = funcion.entradas.filter(
                    estado__in=['RESERVADA', 'VENDIDA', 'USADA']
                ).count()
                
                if total_butacas == 0:
                    ocupacion_porcentaje = 0
                else:
                    ocupacion_porcentaje = (entradas_vendidas / total_butacas) * 100

                if verbosity >= 2:
                    self.stdout.write(
                        f'  Función: {funcion.pelicula.titulo} - '
                        f'{funcion.fecha_hora.strftime("%d/%m %H:%M")} - '
                        f'Sala {funcion.sala.numero} - '
                        f'Ocupación: {ocupacion_porcentaje:.1f}% '
                        f'({entradas_vendidas}/{total_butacas})'
                    )

                # Evaluar si la ocupación es menor al umbral
                if ocupacion_porcentaje < politica.umbral_ocupacion:
                    if verbosity >= 1:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[OK] Activando promocion para funcion {funcion.id} '
                                f'({funcion.pelicula.titulo} - {funcion.fecha_hora.strftime("%d/%m %H:%M")})'
                            )
                        )

                    if not dry_run:
                        # Marcar función con oferta activa
                        with transaction.atomic():
                            funcion.estado_promocion = 'OFERTA_ACTIVA'
                            funcion.promocion_aplicada = politica.promocion_a_otorgar
                            funcion.save(update_fields=['estado_promocion', 'promocion_aplicada'])

                        funciones_activadas += 1

                        # 4. Disparar marketing: buscar clientes objetivo
                        clientes_objetivo = self._buscar_clientes_objetivo(
                            funcion=funcion,
                            genero=politica.genero_pelicula,
                            verbosity=verbosity
                        )

                        if verbosity >= 2:
                            self.stdout.write(f'  Clientes objetivo identificados: {len(clientes_objetivo)}')

                        # 5. Generar cupones y enviar emails
                        notificacion_service = NotificacionService()

                        for cliente in clientes_objetivo:
                            # Generar cupón
                            cupon = CuponGenerado.objects.create(
                                cliente=cliente,
                                funcion_origen=funcion,
                                politica_origen=politica,
                                usado=False,
                                expira_en=timezone.now() + timedelta(minutes=politica.minutos_validez)
                            )
                            cupones_generados += 1

                            # Enviar email promocional
                            enviado = self._enviar_email_promocional(
                                cliente=cliente,
                                funcion=funcion,
                                promocion=politica.promocion_a_otorgar,
                                cupon=cupon,
                                notificacion_service=notificacion_service,
                                verbosity=verbosity
                            )

                            if enviado:
                                emails_enviados += 1

                    else:
                        # Modo dry-run: solo simular
                        funciones_activadas += 1
                        self.stdout.write(f'  [DRY-RUN] Se activaría promoción: {politica.promocion_a_otorgar.codigo}')

        # 6. Reporte final
        if verbosity >= 1:
            self.stdout.write('\n' + self.style.SUCCESS('=== Resumen de Ejecución ==='))
            self.stdout.write(f'Funciones evaluadas: {funciones_evaluadas}')
            self.stdout.write(f'Funciones con oferta activada: {funciones_activadas}')
            if not dry_run:
                self.stdout.write(f'Cupones generados: {cupones_generados}')
                self.stdout.write(f'Emails enviados: {emails_enviados}')
            self.stdout.write(self.style.SUCCESS('=== Finalizado ==='))

    def _buscar_clientes_objetivo(self, funcion, genero, verbosity):
        """
        Busca clientes frecuentes que sean candidatos para la promoción.
        
        Estrategia:
        1. Clientes que han comprado funciones del mismo género anteriormente
        2. Clientes activos (con compras en los últimos 6 meses)
        3. Excluir clientes que ya tienen entradas para esta función
        """
        # Clientes que ya compraron para esta función (excluir)
        clientes_con_entrada = Venta.objects.filter(
            entradas__id_funcion=funcion,
            entradas__estado__in=['RESERVADA', 'VENDIDA', 'USADA']
        ).values_list('id_cliente', flat=True).distinct()

        # Clientes activos en los últimos 6 meses
        fecha_limite = timezone.now() - timedelta(days=180)
        
        clientes_query = Cliente.objects.filter(
            usuario__is_active=True
        ).exclude(
            usuario_id__in=clientes_con_entrada
        )

        # Si hay género específico, priorizar clientes que han visto ese género
        if genero:
            clientes_con_genero = Venta.objects.filter(
                fecha_compra__gte=fecha_limite,
                entradas__id_funcion__pelicula__generos=genero
            ).values_list('id_cliente', flat=True).distinct()
            
            # Primero los que han visto el género, luego todos los demás
            clientes_prioritarios = clientes_query.filter(usuario_id__in=clientes_con_genero)
            
            # Para el resto, obtener clientes activos (con compras recientes)
            clientes_activos_ids = Venta.objects.filter(
                fecha_compra__gte=fecha_limite
            ).values_list('id_cliente', flat=True).distinct()
            
            clientes_resto = clientes_query.exclude(usuario_id__in=clientes_con_genero).filter(
                usuario_id__in=clientes_activos_ids
            )
            
            # Combinar priorizando los del género (limitado a 5 para pruebas)
            clientes_objetivo = list(clientes_prioritarios[:5])
        else:
            # Sin género específico, tomar clientes activos
            # Obtener clientes con compras recientes y ordenar por frecuencia
            clientes_con_compras = Venta.objects.filter(
                fecha_compra__gte=fecha_limite
            ).values('id_cliente').annotate(
                num_compras=Count('id_venta')
            ).order_by('-num_compras').values_list('id_cliente', flat=True)[:5]
            
            clientes_objetivo = list(
                clientes_query.filter(usuario_id__in=clientes_con_compras)
            )

        return clientes_objetivo

    def _enviar_email_promocional(self, cliente, funcion, promocion, cupon, notificacion_service, verbosity):
        """
        Envía email promocional al cliente con el cupón generado.
        
        Reutiliza la infraestructura existente de notificaciones.
        """
        try:
            usuario = cliente.usuario
            
            # Construir URL del cupón - usa endpoint de activación que redirige automáticamente
            cupon_url = f'https://uncategorized-noncommodiously-floy.ngrok-free.dev/promociones/activar/{cupon.token}/'
            
            context = {
                'usuario': usuario,
                'cliente': cliente,
                'funcion': funcion,
                'promocion': promocion,
                'cupon': cupon,
                'cupon_url': cupon_url,
                'pelicula': funcion.pelicula,
                'sala': funcion.sala,
                'descuento_texto': self._get_descuento_texto(promocion),
                'fecha_funcion': funcion.fecha_hora,
                'hora_funcion': funcion.fecha_hora,
            }
            
            # Enviar usando el servicio de notificaciones
            resultado = notificacion_service._enviar_email(
                asunto=f'🎬 ¡Oferta especial! {funcion.pelicula.titulo}',
                template_html='core/emails/promocion_yield.html',
                template_txt='core/emails/promocion_yield.txt',
                destinatario=usuario.email,
                context=context
            )
            
            if resultado and verbosity >= 2:
                self.stdout.write(f'    Email enviado a: {usuario.email}')
            
            return resultado
            
        except Exception as e:
            logger.error(f'Error enviando email promocional a {cliente.id_cliente}: {e}', exc_info=True)
            if verbosity >= 1:
                self.stdout.write(self.style.ERROR(f'    Error enviando email a {cliente.usuario.email}: {e}'))
            return False

    def _get_descuento_texto(self, promocion):
        """Retorna texto legible del descuento según el tipo"""
        if promocion.tipo_descuento == 'PORCENTAJE':
            return f'{int(promocion.valor_descuento)}% de descuento'
        elif promocion.tipo_descuento == '2X1':
            return '2x1 en entradas'
        elif promocion.tipo_descuento == 'MONTO_FIJO':
            return f'${int(promocion.valor_descuento)} de descuento'
        return 'Descuento especial'
