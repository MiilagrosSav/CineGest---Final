import logging

from django.utils import timezone
from datetime import timedelta

from cine.models.configuracion_cine import ConfiguracionCine
from ventas.models import Entrada


def liberar_reservas_expiradas():
    """Libera entradas en estado PENDIENTE o RESERVADA cuya fecha_creacion
    sea anterior al umbral definido por ConfiguracionCine.load().reserva_tiempo_espera.

    Retorna el número de entradas liberadas (marcadas como CANCELADA).
    """
    from django.db import transaction
    
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
            with transaction.atomic():
                entrada.estado = 'CANCELADA'
                entrada.reservado_por = None
                entrada.save()
            liberadas += 1
        except Exception:
            # continuar con las siguientes entradas si hay error individual
            continue

    return liberadas
from django.db.models import Count, Q, F
from django.db.models.functions import Coalesce
from cine.models.funcion import Funcion
from ventas.constants import EstadoEntrada


logger = logging.getLogger(__name__)


def obtener_funciones_candidatas(compra_original, debug_data=None):
    """
    Devuelve un QuerySet de `Funcion` que son candidatas válidas para realizar
    un intercambio de entradas de la `compra_original`.

    Reglas:
    - La función debe ser futura (fecha_hora > ahora).
    - No puede estar en PREVENTA (precio especial, no acepta promociones).
    - La función debe tener el mismo `precio_base` que la función original.
      Si la compra usó un cupón/promoción, se compara por precio unitario efectivo.
    - Debe tener asientos disponibles >= cantidad de entradas de la compra.

    Args:
        compra_original (Venta): objeto Venta/Compra original

    Returns:
        QuerySet[Funcion]
    """
    if debug_data is not None:
        debug_data.clear()
        debug_data['venta_id'] = getattr(compra_original, 'id_venta', None)

    # Obtener la función original y precio
    entradas = compra_original.entradas.filter(estado__in=EstadoEntrada.ESTADOS_ACTIVOS)
    if not entradas.exists():
        if debug_data is not None:
            debug_data['motivo'] = 'sin_entradas_activas'
            debug_data['pre_politica_count'] = 0
            debug_data['final_count'] = 0
        return Funcion.objects.none()

    primera_entrada = entradas[0]
    funcion_original = primera_entrada.id_funcion
    precio_original = funcion_original.precio_base
    cantidad_necesaria = compras_cantidad_entradas(compra_original)

    logger.info(
        "[INTERCAMBIO][CANDIDATAS] venta=%s funcion_origen=%s precio_origen=%s cantidad_necesaria=%s",
        getattr(compra_original, 'id_venta', None),
        getattr(funcion_original, 'id', None),
        precio_original,
        cantidad_necesaria,
    )
    if debug_data is not None:
        debug_data['funcion_origen'] = {
            'id': getattr(funcion_original, 'id', None),
            'pelicula': getattr(getattr(funcion_original, 'pelicula', None), 'titulo', ''),
            'fecha_hora': getattr(funcion_original, 'fecha_hora', None),
            'precio_base': str(precio_original),
        }
        debug_data['cantidad_necesaria'] = cantidad_necesaria

    ahora = timezone.now()

    # Contar butacas ocupadas por función (estados que cuentan como ocupadas)
    ocupados_filter = Q(entradas__estado__in=EstadoEntrada.ESTADOS_OCUPADOS)

    funciones = (
        Funcion.objects
        .filter(
            fecha_hora__gt=ahora,
            precio_base=precio_original,
        )
        .exclude(estado='PREVENTA')  # PREVENTA tiene precio especial y no admite promociones
        .exclude(estado='INACTIVA')
        .annotate(ocupadas=Coalesce(Count('entradas', filter=ocupados_filter, distinct=True), 0))
        # La capacidad se calcula como el conteo de butacas no-pasillo de la sala
        .annotate(asientos_total=Coalesce(Count('sala__butacas', filter=Q(sala__butacas__es_pasillo=False), distinct=True), 0))
        .annotate(asientos_disponibles=F('asientos_total') - F('ocupadas'))
        .filter(asientos_disponibles__gte=cantidad_necesaria)
        .order_by('fecha_hora')
    )

    logger.info(
        "[INTERCAMBIO][CANDIDATAS] venta=%s pre_politica_count=%s",
        getattr(compra_original, 'id_venta', None),
        funciones.count(),
    )

    funciones = funciones.distinct()
    if debug_data is not None:
        debug_data['pre_politica_count'] = funciones.count()
        debug_data['pre_politica_ids'] = list(funciones.values_list('id', flat=True)[:200])

    # Filtro final por política activa: solo devolver funciones que pasen
    # TODAS las reglas reales de intercambio (incluye precio exactamente igual).
    try:
        from ventas.models import PoliticaReembolso
        politica = PoliticaReembolso.objects.filter(activo=True).first()
        if politica:
            logger.info(
                "[INTERCAMBIO][CANDIDATAS] venta=%s politica=%s(%s) aplicada",
                getattr(compra_original, 'id_venta', None),
                getattr(politica, 'id', None),
                getattr(politica, 'nombre', None),
            )
            ids_validos = []
            descartadas_politica = []
            for funcion in funciones:
                es_valida, motivo = politica.validar_intercambio(compra_original, funcion)
                if es_valida:
                    ids_validos.append(funcion.id)
                else:
                    descartadas_politica.append((funcion.id, motivo))

            if debug_data is not None:
                debug_data['politica'] = {
                    'id': getattr(politica, 'id', None),
                    'nombre': getattr(politica, 'nombre', ''),
                    'dias_antes_minimo': getattr(politica, 'dias_antes_minimo', None),
                }
                debug_data['descartadas_politica_count'] = len(descartadas_politica)
                debug_data['descartadas_politica'] = [
                    {
                        'funcion_id': fid,
                        'motivo': motivo,
                    }
                    for fid, motivo in descartadas_politica[:200]
                ]

            if descartadas_politica:
                muestra = "; ".join(
                    [f"funcion={fid} motivo={motivo}" for fid, motivo in descartadas_politica[:20]]
                )
                logger.info(
                    "[INTERCAMBIO][CANDIDATAS] venta=%s descartadas_por_politica=%s detalle=%s",
                    getattr(compra_original, 'id_venta', None),
                    len(descartadas_politica),
                    muestra,
                )

            funciones = funciones.filter(id__in=ids_validos)
            logger.info(
                "[INTERCAMBIO][CANDIDATAS] venta=%s post_politica_count=%s",
                getattr(compra_original, 'id_venta', None),
                funciones.count(),
            )
            if debug_data is not None:
                debug_data['post_politica_count'] = funciones.count()
                debug_data['post_politica_ids'] = list(funciones.values_list('id', flat=True)[:200])
        else:
            logger.info(
                "[INTERCAMBIO][CANDIDATAS] venta=%s sin_politica_activa",
                getattr(compra_original, 'id_venta', None),
            )
    except Exception:
        # Ante cualquier error inesperado, mantener el comportamiento previo
        # y no bloquear la cartelera.
        logger.exception(
            "[INTERCAMBIO][CANDIDATAS] venta=%s error_aplicando_politica",
            getattr(compra_original, 'id_venta', None),
        )
        if debug_data is not None:
            debug_data['error_politica'] = True

    funciones_finales = funciones.distinct()
    logger.info(
        "[INTERCAMBIO][CANDIDATAS] venta=%s final_count=%s",
        getattr(compra_original, 'id_venta', None),
        funciones_finales.count(),
    )
    if debug_data is not None:
        debug_data['final_count'] = funciones_finales.count()
        debug_data['final_ids'] = list(funciones_finales.values_list('id', flat=True)[:200])

    return funciones_finales


def compras_cantidad_entradas(compra):
    """Helper: cantidad de entradas activas de una compra (Venta)."""
    try:
        return compra.entradas.filter(estado__in=EstadoEntrada.ESTADOS_ACTIVOS).count()
    except Exception:
        return 0


# calcular_porcentaje_reembolso eliminada - funcionalidad reemplazada por sistema de intercambio
