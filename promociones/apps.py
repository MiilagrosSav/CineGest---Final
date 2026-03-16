from django.apps import AppConfig


class PromocionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'promociones'
    verbose_name = 'Promociones'

    def ready(self):
        import promociones.signals  # noqa: F401 — conecta las señales
