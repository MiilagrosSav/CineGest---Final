from django.apps import AppConfig


class VentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ventas'
    
    def ready(self):
        """Importar signals cuando la app esté lista"""
        import ventas.signals  # noqa
