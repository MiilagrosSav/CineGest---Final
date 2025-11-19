from django.utils import timezone
from django.db.models import Count, Q, F
from django.db.models.functions import Coalesce
from cine.models.funcion import Funcion


def obtener_funciones_candidatas(compra_original):
    """
    Devuelve un QuerySet de `Funcion` que son candidatas válidas para realizar
    un intercambio de entradas de la `compra_original`.

    Reglas:
    - La función debe ser futura (fecha_hora > ahora).
    - La función debe tener el mismo `precio_base` que la función original.
    - Debe tener asientos disponibles >= cantidad de entradas de la compra.

    Args:
        compra_original (Venta): objeto Venta/Compra original

    Returns:
        QuerySet[Funcion]
    """
    # Obtener la función original y precio
    entradas = compra_original.entradas.all()
    if not entradas.exists():
        return Funcion.objects.none()

    funcion_original = entradas[0].id_funcion
    precio_original = funcion_original.precio_base
    cantidad_necesaria = compras_cantidad_entradas(compra_original)

    ahora = timezone.now()

    # Contar butacas ocupadas por función (estados que cuentan como ocupadas)
    ocupados_filter = Q(entradas__estado__in=['RESERVADA', 'VENDIDA', 'USADA'])

    funciones = (
        Funcion.objects
        .filter(fecha_hora__gt=ahora, precio_base=precio_original)
        .annotate(ocupadas=Coalesce(Count('entradas', filter=ocupados_filter), 0))
        # La capacidad se calcula como el conteo de butacas no-pasillo de la sala
        .annotate(asientos_total=Coalesce(Count('sala__butacas', filter=Q(sala__butacas__es_pasillo=False)), 0))
        .annotate(asientos_disponibles=F('asientos_total') - F('ocupadas'))
        .filter(asientos_disponibles__gte=cantidad_necesaria)
        .order_by('fecha_hora')
    )

    return funciones.distinct()


def compras_cantidad_entradas(compra):
    """Helper: cantidad de entradas de una compra (Venta)"""
    try:
        return compra.entradas.count()
    except Exception:
        return 0


def calcular_porcentaje_reembolso(fecha_evento):
    """Devuelve el porcentaje de reembolso según las políticas configuradas.

    Args:
        fecha_evento (datetime): fecha y hora del evento (función)

    Returns:
        int: porcentaje a reembolsar (0-100)
    """
    if not fecha_evento:
        return 0

    ahora = timezone.now()
    # Si el evento ya pasó, no hay reembolso
    diferencia = fecha_evento - ahora
    horas_restantes = diferencia.total_seconds() / 3600.0
    if horas_restantes <= 0:
        return 0

    # Refund policies were removed; default to 0
    return 0
