"""
Configuración de Celery para CineGest

Este archivo configura Celery para manejar tareas asíncronas y programadas.
Para que funcione, necesitas:
    1. Instalar dependencias: pip install celery redis
    2. Ejecutar Redis: redis-server (o usar un servicio en la nube)
    3. Ejecutar worker: celery -A trabajofinal worker --loglevel=info
    4. Ejecutar beat: celery -A trabajofinal beat --loglevel=info

En producción, puedes combinar worker y beat:
    celery -A trabajofinal worker --beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab
import os

# Configurar Django settings por defecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')

# Crear instancia de Celery
app = Celery('cinegest')

# Configurar Celery usando settings de Django
# - Todas las configuraciones de Celery en settings.py deben tener prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en todas las apps instaladas
# Busca archivos tasks.py en cada app y registra las tareas
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarea de debug para verificar que Celery funciona correctamente"""
    print(f'Request: {self.request!r}')


# ========================================
# Configuración de Tareas Programadas
# ========================================

# Esta configuración se puede incluir aquí o en settings.py
# Si quieres manejarla desde settings.py, comenta este bloque

app.conf.beat_schedule = {
    # ✅ CRÍTICO: Limpiar ventas expiradas cada 1 minuto
    'limpiar-ventas-expiradas-cada-minuto': {
        'task': 'ventas.tasks.limpiar_ventas_expiradas',
        'schedule': 60.0,  # cada 60 segundos
        'options': {
            'expires': 50.0,  # la tarea expira si no se ejecuta en 50 segundos
        },
        'kwargs': {
            'tiempo_expiracion_minutos': 10  # política de 10 minutos
        }
    },
    
    # ✅ COMPLEMENTARIO: Liberar entradas huérfanas cada 5 minutos
    'liberar-entradas-huerfanas-cada-5-minutos': {
        'task': 'ventas.tasks.liberar_reservas_huerfanas',
        'schedule': 300.0,  # cada 5 minutos
        'options': {
            'expires': 240.0,
        }
    },
    
    # 📊 REPORTE: Generar reporte semanal de ventas expiradas (cada lunes a las 9 AM)
    'reporte-ventas-expiradas-semanal': {
        'task': 'ventas.tasks.generar_reporte_ventas_expiradas',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Lunes 9:00 AM
        'kwargs': {
            'dias': 7
        }
    },
    
    # 📊 REPORTE: Generar reporte diario (cada día a las 23:00)
    'reporte-ventas-expiradas-diario': {
        'task': 'ventas.tasks.generar_reporte_ventas_expiradas',
        'schedule': crontab(hour=23, minute=0),  # Todos los días a las 23:00
        'kwargs': {
            'dias': 1
        }
    },
}

# Configuración adicional de Celery
app.conf.update(
    # Zona horaria
    timezone='America/Argentina/Buenos_Aires',
    
    # Habilitar UTC
    enable_utc=True,
    
    # Formato de tareas
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Tiempo de expiración de resultados (en segundos)
    result_expires=3600,
    
    # Configuración de reintentos
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Prefetch: cantidad de tareas que el worker toma del broker
    worker_prefetch_multiplier=1,
    
    # Logs
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)


# ========================================
# Señales de Celery (para debugging)
# ========================================

from celery.signals import task_prerun, task_postrun, task_failure

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Se ejecuta antes de cada tarea"""
    print(f'🚀 Iniciando tarea: {task.name} (ID: {task_id})')


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Se ejecuta después de cada tarea exitosa"""
    print(f'✅ Tarea completada: {task.name} (ID: {task_id})')


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Se ejecuta cuando una tarea falla"""
    print(f'❌ Error en tarea {sender.name} (ID: {task_id}): {exception}')


if __name__ == '__main__':
    app.start()
