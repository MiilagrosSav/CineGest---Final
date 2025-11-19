"""
Constantes compartidas para el módulo de ventas
"""

# Estados de Entrada
class EstadoEntrada:
    RESERVADA = 'RESERVADA'
    VENDIDA = 'VENDIDA'
    USADA = 'USADA'
    CANCELADA = 'CANCELADA'
    EXPIRADA = 'EXPIRADA'
    
    ESTADOS_ACTIVOS = [RESERVADA, VENDIDA, USADA]
    ESTADOS_OCUPADOS = [RESERVADA, VENDIDA, USADA]  # Estados que bloquean una butaca
    
    @classmethod
    def choices(cls):
        return [
            (cls.RESERVADA, 'Reservada'),
            (cls.VENDIDA, 'Vendida'),
            (cls.USADA, 'Usada'),
            (cls.CANCELADA, 'Cancelada'),
            (cls.EXPIRADA, 'Expirada'),
        ]


# Estados de Venta
class EstadoVenta:
    PENDIENTE = 'PENDIENTE'
    PENDIENTE_PAGO = 'PENDIENTE_PAGO'
    CONFIRMADA = 'CONFIRMADA'
    CANCELADA = 'CANCELADA'
    
    @classmethod
    def choices(cls):
        return [
            (cls.PENDIENTE, 'Pendiente'),
            (cls.PENDIENTE_PAGO, 'Pendiente de Pago'),
            (cls.CONFIRMADA, 'Confirmada'),
            (cls.CANCELADA, 'Cancelada'),
        ]


# Tipos de Venta
class TipoVenta:
    ONLINE = 'ONLINE'
    PRESENCIAL = 'PRESENCIAL'
    
    @classmethod
    def choices(cls):
        return [
            (cls.ONLINE, 'Online'),
            (cls.PRESENCIAL, 'Presencial'),
        ]


# Motivos de Intercambio
class MotivoIntercambio:
    HORARIO = 'HORARIO'
    FECHA = 'FECHA'
    PELICULA = 'PELICULA'
    DISPONIBILIDAD = 'DISPONIBILIDAD'
    OTRO = 'OTRO'
    
    @classmethod
    def choices(cls):
        return [
            (cls.HORARIO, 'Cambio de horario'),
            (cls.FECHA, 'Cambio de fecha'),
            (cls.PELICULA, 'Cambio de película'),
            (cls.DISPONIBILIDAD, 'Disponibilidad de asientos'),
            (cls.OTRO, 'Otro motivo'),
        ]


# Configuración de Intercambios
class ConfigIntercambio:
    # Número máximo de reintentos en caso de race condition
    MAX_REINTENTOS = 3
    
    # Tiempo mínimo en horas antes de la función para permitir intercambio
    HORAS_MINIMAS_DEFAULT = 24
    
    # Tiempo de espera entre reintentos (en segundos)
    TIEMPO_REINTENTO = 0.5
