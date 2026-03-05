from django.utils import timezone
from datetime import timedelta
from ventas.models.entrada import Entrada


def puede_valorar(cliente, funcion) -> bool:
    """Determina si `cliente` puede dejar una valoración para `funcion`.

    Reglas:
    1) La función debe haber finalizado (fecha_hora + duracion < now).
    2) El cliente debe poseer al menos una entrada en estado VENDIDA o USADA para esa función.
    3) No debe existir ya una valoración del cliente para esa función.
    """
    # 1) la función terminó
    try:
        fin_funcion = funcion.get_hora_fin()
    except Exception:
        # fallback: usar fecha_hora + duracion (si existe pelicula.duracion)
        try:
            dur = funcion.pelicula.duracion
            fin_funcion = funcion.fecha_hora + timedelta(minutes=dur)
        except Exception:
            return False

    if not fin_funcion or fin_funcion > timezone.now():
        return False

    # 2) posesión: buscar entradas del cliente para esa función con estado VENDIDA o USADA
    entradas = Entrada.objects.filter(
        id_funcion=funcion,
        id_venta__id_cliente=cliente,
        estado__in=['VENDIDA', 'USADA']
    )
    if not entradas.exists():
        return False

    # 3) unicidad: verificar que no haya valoración previa
    from valoraciones.models import Valoracion
    if Valoracion.objects.filter(cliente=cliente, funcion=funcion).exists():
        return False

    return True
