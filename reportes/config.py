"""
Configuración centralizada del módulo de reportes.
"""
from django.conf import settings


class ReportesConfig:
    """
    Configuración del módulo de reportes.
    
    Valores configurables vía settings.py:
    - REPORTE_DEFAULT_DAYS: Días por defecto para rangos (default: 30)
    - REPORTE_LIMIT_DEFAULT: Límite de películas en listados (default: 50)
    - REPORTE_FILTRO_DIAS_THRESHOLD: Días para activar filtrado (default: 7)
    """
    
    # ============================================================
    # CONFIGURACIÓN OPERACIONAL (Configurable vía settings.py)
    # ============================================================
    
    # Días por defecto para reportes cuando no se especifica rango
    DEFAULT_DAYS = getattr(settings, 'REPORTE_DEFAULT_DAYS', 30)
    
    # Límite de películas en rankings/listados
    LIMIT_DEFAULT = getattr(settings, 'REPORTE_LIMIT_DEFAULT', 50)
    
    # Threshold de días para activar filtrado por días específicos
    FILTRO_DIAS_THRESHOLD = getattr(settings, 'REPORTE_FILTRO_DIAS_THRESHOLD', 7)
    
    # ============================================================
    # CONSTANTES DE DOMINIO (Lógica de negocio)
    # ============================================================
    
    # Días de la semana en español (orden Lunes-Domingo)
    DIAS_SEMANA_ES = [
        'Lunes', 'Martes', 'Miércoles', 'Jueves', 
        'Viernes', 'Sábado', 'Domingo'
    ]
    
    # Franjas horarias para análisis de ocupación
    FRANJAS_HORARIAS = ['Matiné', 'Tarde', 'Noche']
    
    # Mapeo de días Django (1=Domingo, 2=Lunes... 7=Sábado) a orden Lunes-first
    WEEKDAY_NUMBERS_MONDAY_START = [2, 3, 4, 5, 6, 7, 1]
    
    # Thresholds para ratings de RevPAS (Revenue Per Available Seat)
    # Basados en ingresos por butaca disponible
    REVPAS_RATING_THRESHOLDS = {
        'EXCELENTE': 0.40,  # >= $0.40 por butaca
        'BUENO': 0.25,      # >= $0.25 por butaca
        'REGULAR': 0.15,    # >= $0.15 por butaca
        'MALO': 0.00        # < $0.15 por butaca
    }
    
    # Thresholds para ratings de performance de películas
    # Basados en índice de performance (0-100)
    PERFORMANCE_RATING_THRESHOLDS = {
        'EXCELENTE': 80,  # >= 80 puntos
        'BUENO': 60,      # >= 60 puntos
        'REGULAR': 40,    # >= 40 puntos
        'MALO': 0         # < 40 puntos
    }
    
    # Límite de registros para diferentes rankings (para optimización)
    RANKING_LIMITS = {
        'peliculas': 10,
        'salas': 5,
        'horarios': 7,  # Máximo 7 días de la semana
    }
    
    # ============================================================
    # CONFIGURACIÓN DE EXPORTACIONES
    # ============================================================
    
    # Prefijos de nombres de archivos exportados
    EXPORT_FILENAME_PREFIX = {
        'financiero_pdf': 'reporte_financiero',
        'financiero_excel': 'reporte_financiero',
        'operativo_pdf': 'reporte_operativo',
        'operativo_excel': 'reporte_operativo'
    }


# Alias para importación más limpia
config = ReportesConfig
