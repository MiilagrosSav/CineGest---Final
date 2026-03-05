"""
Custom Management Command: cancelar_ventas_vencidas

Este comando se encarga de limpiar ventas pendientes que han superado 
el tiempo de expiración (por defecto 10 minutos).

Uso:
    python manage.py cancelar_ventas_vencidas
    python manage.py cancelar_ventas_vencidas --minutos=15

Automatización recomendada:
    - Cron Job (cada minuto): * * * * * cd /ruta/proyecto && python manage.py cancelar_ventas_vencidas
    - Celery Beat: Configurar tarea periódica cada 60 segundos
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.models import Venta
from cine.models import ConfiguracionCine


class Command(BaseCommand):
    help = 'Cancela (expira) ventas pendientes que superaron el tiempo de expiración'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutos',
            type=int,
            default=None,
            help='Tiempo en minutos antes de que expire una venta pendiente (default: usar ConfiguracionCine.reserva_tiempo_espera)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada de cada venta expirada'
        )

    def handle(self, *args, **options):
        tiempo_expiracion = options['minutos']
        verbose = options['verbose']
        
        # Si no se especifica tiempo, usar configuración del cine
        if tiempo_expiracion is None:
            try:
                config = ConfiguracionCine.objects.first()
                tiempo_expiracion = config.reserva_tiempo_espera if config else 10
            except Exception:
                tiempo_expiracion = 10
        
        self.stdout.write(self.style.NOTICE(
            f'[*] Buscando ventas pendientes expiradas (>{tiempo_expiracion} minutos)...'
        ))
        
        # Ejecutar limpieza de ventas expiradas
        try:
            ventas_expiradas, butacas_liberadas = Venta.objects.limpiar_expiradas(
                tiempo_expiracion_minutos=tiempo_expiracion
            )
            
            if ventas_expiradas > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Exito: {ventas_expiradas} venta(s) expirada(s), '
                    f'{butacas_liberadas} butaca(s) liberada(s)'
                ))
                
                if verbose:
                    # Mostrar detalles de las ventas expiradas
                    from datetime import timedelta
                    tiempo_corte = timezone.now() - timedelta(minutes=tiempo_expiracion)
                    ventas_recien_expiradas = Venta.objects.filter(
                        estado='EXPIRADA',
                        fecha_compra__lt=tiempo_corte,
                        activo=False
                    ).select_related('id_cliente__usuario')[:ventas_expiradas]
                    
                    self.stdout.write('\n[DETALLE] Ventas expiradas:')
                    for venta in ventas_recien_expiradas:
                        cliente = venta.id_cliente.usuario.get_full_name() if venta.id_cliente else 'N/A'
                        self.stdout.write(
                            f'  - Venta #{venta.id_venta} | '
                            f'Cliente: {cliente} | '
                            f'Codigo: {venta.codigo_compra} | '
                            f'Fecha: {venta.fecha_compra.strftime("%Y-%m-%d %H:%M:%S")}'
                        )
            else:
                self.stdout.write(self.style.WARNING(
                    '[!] No se encontraron ventas pendientes para expirar'
                ))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Error al procesar ventas expiradas: {str(e)}'
            ))
            raise
        
        self.stdout.write(self.style.NOTICE(
            f'\n[INFO] Ejecutado a las {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ))
