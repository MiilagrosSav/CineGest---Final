from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from valoraciones.models import NotificacionValoracion, Valoracion
from valoraciones.services import puede_valorar
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Limpia notificaciones inválidas (funciones que no se pueden valorar)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Eliminar notificaciones de funciones de hace más de N días (default: 7)'
        )

    def handle(self, *args, **options):
        dias_limite = options['dias']
        self.stdout.write(f'🔍 Buscando notificaciones inválidas (límite: {dias_limite} días)...\n')
        
        # Obtener todas las notificaciones no leídas
        notificaciones = NotificacionValoracion.objects.filter(
            leido=False
        ).select_related('cliente', 'funcion', 'funcion__pelicula')
        
        total = notificaciones.count()
        self.stdout.write(f'📊 Total de notificaciones no leídas: {total}\n')
        
        eliminadas = 0
        marcadas_leidas = 0
        validas = 0
        
        for notif in notificaciones:
            cliente = notif.cliente
            funcion = notif.funcion
            
            # Información de debug
            try:
                fin_funcion = funcion.get_hora_fin()
            except:
                fin_funcion = funcion.fecha_hora + timedelta(minutes=funcion.pelicula.duracion)
            
            ahora = timezone.now()
            tiempo_desde_fin = (ahora - fin_funcion).total_seconds() / 60 if fin_funcion else None
            dias_desde_fin = tiempo_desde_fin / 1440 if tiempo_desde_fin else None
            
            # Verificar si la función se puede valorar
            puede = puede_valorar(cliente, funcion)
            
            # Verificar si la notificación es muy antigua
            es_antigua = dias_desde_fin and dias_desde_fin > dias_limite
            
            if not puede or es_antigua:
                # Verificar si es porque ya valoró
                if Valoracion.objects.filter(cliente=cliente, funcion=funcion).exists():
                    notif.leido = True
                    notif.save()
                    marcadas_leidas += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'✅ Marcada como leída: {cliente.usuario.username} - {funcion.pelicula.titulo} (ya valorada)'
                        )
                    )
                else:
                    # Mostrar razón por la cual no es válida
                    if es_antigua:
                        razon = f'notificación muy antigua (hace {dias_desde_fin:.0f} días)'
                    elif fin_funcion and fin_funcion > ahora:
                        razon = f'función aún no terminó (termina en {-tiempo_desde_fin:.0f} min)'
                    else:
                        razon = 'no tiene entrada válida'
                    
                    notif.delete()
                    eliminadas += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Eliminada: {cliente.usuario.username} - {funcion.pelicula.titulo} ({razon})'
                        )
                    )
            else:
                validas += 1
                # Mostrar info de la notificación válida
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Válida: {cliente.usuario.username} - {funcion.pelicula.titulo} '
                        f'(terminó hace {dias_desde_fin:.1f} días, fecha: {funcion.fecha_hora.strftime("%d/%m %H:%M")})'
                    )
                )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'\n✅ Proceso completado:\n'))
        self.stdout.write(f'   📌 Notificaciones válidas: {validas}')
        self.stdout.write(f'   ✓ Marcadas como leídas: {marcadas_leidas}')
        self.stdout.write(f'   🗑️  Eliminadas: {eliminadas}')
        self.stdout.write(f'   📊 Total procesadas: {total}\n')

