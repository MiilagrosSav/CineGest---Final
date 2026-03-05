from django.apps import AppConfig


class ValoracionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'valoraciones'
    verbose_name = 'Valoraciones'
    
    def ready(self):
        """Registrar signals cuando la app esté lista"""
        import valoraciones.signals

