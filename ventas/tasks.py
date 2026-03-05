"""
Tareas programadas de Celery para CineGest

Este módulo contiene todas las tareas asíncronas y programadas del sistema.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name='ventas.tasks.limpiar_ventas_expiradas')
def limpiar_ventas_expiradas(tiempo_expiracion_minutos=10):
    """
    Tarea Celery para limpiar ventas pendientes expiradas.
    
    Esta tarea se ejecuta periódicamente (cada minuto) para:
    - Identificar ventas con estado='PENDIENTE' que superaron el tiempo de expiración
    - Cambiar su estado a 'EXPIRADA'
    - Marcarlas como inactivas (activo=False)
    - Liberar las butacas asociadas (cambiar entradas a 'EXPIRADA')
    
    Args:
        tiempo_expiracion_minutos (int): Tiempo en minutos para considerar una venta expirada.
                                         Por defecto son 10 minutos.
    
    Returns:
        dict: Diccionario con estadísticas de la operación
              {
                  'ventas_expiradas': int,
                  'butacas_liberadas': int,
                  'timestamp': str
              }
    """
    try:
        from ventas.models import Venta
        
        logger.info(f"🔍 Iniciando limpieza de ventas expiradas (>{tiempo_expiracion_minutos} minutos)")
        
        # Ejecutar limpieza
        ventas_expiradas, butacas_liberadas = Venta.objects.limpiar_expiradas(
            tiempo_expiracion_minutos=tiempo_expiracion_minutos
        )
        
        resultado = {
            'ventas_expiradas': ventas_expiradas,
            'butacas_liberadas': butacas_liberadas,
            'timestamp': timezone.now().isoformat()
        }
        
        if ventas_expiradas > 0:
            logger.info(
                f"✅ Celery: {ventas_expiradas} venta(s) expirada(s), "
                f"{butacas_liberadas} butaca(s) liberada(s)"
            )
        else:
            logger.debug("⚪ No se encontraron ventas pendientes para expirar")
        
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Error en tarea limpiar_ventas_expiradas: {str(e)}", exc_info=True)
        raise


@shared_task(name='ventas.tasks.liberar_reservas_huerfanas')
def liberar_reservas_huerfanas():
    """
    Tarea complementaria para liberar entradas que quedaron huérfanas.
    
    Busca entradas con estado PENDIENTE/RESERVADA cuya venta asociada
    ya fue cancelada o expirada, y las marca como EXPIRADA.
    
    Esta es una tarea de limpieza adicional para casos borde.
    
    Returns:
        dict: Estadísticas de la operación
    """
    try:
        from ventas.models import Entrada, Venta
        
        logger.info("🔍 Buscando entradas huérfanas...")
        
        # Buscar entradas PENDIENTE/RESERVADA cuya venta está CANCELADA o EXPIRADA
        entradas_huerfanas = Entrada.objects.filter(
            estado__in=['PENDIENTE', 'RESERVADA'],
            id_venta__estado__in=['CANCELADA', 'EXPIRADA']
        )
        
        cantidad = entradas_huerfanas.count()
        
        if cantidad > 0:
            # Actualizar a EXPIRADA
            entradas_huerfanas.update(estado='EXPIRADA')
            logger.info(f"✅ Liberadas {cantidad} entrada(s) huérfana(s)")
        else:
            logger.debug("⚪ No se encontraron entradas huérfanas")
        
        return {
            'entradas_liberadas': cantidad,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error en tarea liberar_reservas_huerfanas: {str(e)}", exc_info=True)
        raise


@shared_task(name='ventas.tasks.generar_reporte_ventas_expiradas')
def generar_reporte_ventas_expiradas(dias=7):
    """
    Genera un reporte de ventas expiradas para análisis.
    
    Args:
        dias (int): Cantidad de días hacia atrás para el reporte (default: 7)
    
    Returns:
        dict: Reporte con estadísticas de ventas expiradas
    """
    try:
        from ventas.models import Venta
        
        logger.info(f"📊 Generando reporte de ventas expiradas (últimos {dias} días)")
        
        fecha_inicio = timezone.now() - timedelta(days=dias)
        
        ventas_expiradas = Venta.objects.filter(
            estado='EXPIRADA',
            fecha_compra__gte=fecha_inicio
        ).select_related('id_cliente__usuario')
        
        total_ventas = ventas_expiradas.count()
        
        # Agrupar por día
        stats_por_dia = {}
        for venta in ventas_expiradas:
            fecha_str = venta.fecha_compra.strftime('%Y-%m-%d')
            stats_por_dia[fecha_str] = stats_por_dia.get(fecha_str, 0) + 1
        
        # Calcular total de entradas perdidas
        total_entradas = sum(venta.entradas.count() for venta in ventas_expiradas)
        
        reporte = {
            'periodo': f'{fecha_inicio.strftime("%Y-%m-%d")} - {timezone.now().strftime("%Y-%m-%d")}',
            'total_ventas_expiradas': total_ventas,
            'total_entradas_perdidas': total_entradas,
            'estadisticas_por_dia': stats_por_dia,
            'promedio_diario': total_ventas / dias if dias > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"📊 Reporte generado: {total_ventas} ventas expiradas, "
            f"{total_entradas} entradas perdidas"
        )
        
        return reporte
        
    except Exception as e:
        logger.error(f"❌ Error en tarea generar_reporte_ventas_expiradas: {str(e)}", exc_info=True)
        raise


# ========================================
# Configuración recomendada para Celery Beat
# ========================================
"""
Agregar en trabajofinal/settings.py:

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Limpiar ventas expiradas cada 1 minuto
    'limpiar-ventas-expiradas': {
        'task': 'ventas.tasks.limpiar_ventas_expiradas',
        'schedule': 60.0,  # cada 60 segundos
        'kwargs': {'tiempo_expiracion_minutos': 10}
    },
    
    # Liberar entradas huérfanas cada 5 minutos (limpieza adicional)
    'liberar-reservas-huerfanas': {
        'task': 'ventas.tasks.liberar_reservas_huerfanas',
        'schedule': 300.0,  # cada 5 minutos
    },
    
    # Generar reporte semanal de ventas expiradas (cada lunes a las 9 AM)
    'reporte-ventas-expiradas-semanal': {
        'task': 'ventas.tasks.generar_reporte_ventas_expiradas',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),
        'kwargs': {'dias': 7}
    },
}
"""
