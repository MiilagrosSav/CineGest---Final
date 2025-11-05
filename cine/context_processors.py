from cine.models import ConfiguracionCine


def configuracion_cine(request):
    """
    Context processor para hacer disponible la configuración del cine
    en todas las plantillas.
    """
    try:
        config = ConfiguracionCine.load()
        return {'configuracion_cine': config}
    except Exception:
        return {'configuracion_cine': None}
