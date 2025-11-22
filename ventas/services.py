from django.utils import timezone
from datetime import timedelta

from cine.models.configuracion_cine import ConfiguracionCine
from ventas.models import Entrada


def liberar_reservas_expiradas():
    """Libera entradas en estado PENDIENTE o RESERVADA cuya fecha_creacion
    sea anterior al umbral definido por ConfiguracionCine.load().reserva_tiempo_espera.

    Retorna el número de entradas liberadas (marcadas como CANCELADA).
    """
    try:
        minutos = ConfiguracionCine.load().reserva_tiempo_espera
    except Exception:
        minutos = 10

    threshold = timezone.now() - timedelta(minutes=int(minutos))

    estados_objetivo = ['PENDIENTE', 'RESERVADA']
    qs = Entrada.objects.filter(estado__in=estados_objetivo, fecha_creacion__lt=threshold)

    total = qs.count()
    if total == 0:
        return 0

    liberadas = 0
    for entrada in qs.select_related('id_butaca', 'id_funcion'):
        try:
            entrada.estado = 'CANCELADA'
            entrada.reservado_por = None
            entrada.save()
            liberadas += 1
        except Exception:
            # continuar con las siguientes entradas si hay error individual
            continue

    return liberadas
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


# calcular_porcentaje_reembolso eliminada - funcionalidad reemplazada por sistema de intercambio
