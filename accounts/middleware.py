"""
Middleware que detecta usuarios de Google con perfil incompleto (sin DNI)
y activa la bandera de sesión para mostrar el modal obligatorio.
"""

# URLs que no deben disparar el redirect del modal
_EXCLUDED_PATHS = (
    '/accounts/completar-perfil/',
    '/accounts/completar-perfil/dismiss/',
    '/accounts/check-username/',
    '/accounts/check-email/',
    '/accounts/logout/',
    '/admin/',
    '/social/',
    '/static/',
    '/media/',
)


class GoogleProfileCompletionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'rol', None) == 'cliente'
            and not any(request.path.startswith(p) for p in _EXCLUDED_PATHS)
        ):
            # Requisitos para cupones: DNI cargado + consentimiento de marketing/notificaciones.
            cliente = getattr(request.user, 'cliente', None)
            tiene_dni = bool(getattr(request.user, 'dni', None))
            acepta_marketing = bool(getattr(cliente, 'acepta_marketing', False))
            requisitos_cupones_ok = tiene_dni and acepta_marketing

            forzar_primera_sesion = bool(
                request.session.get('forzar_modal_completar_perfil_primera_sesion', False)
            )
            forzar_google = bool(getattr(request.user, 'is_google_user', False))
            modal_dismissed = bool(request.session.get('dismiss_modal_completar_perfil', False))

            # Si el usuario lo cerró manualmente, no volver a abrir en esta sesión.
            if modal_dismissed and not requisitos_cupones_ok:
                request.session.pop('mostrar_modal_completar_perfil', None)
                return self.get_response(request)

            if (forzar_google or forzar_primera_sesion) and not requisitos_cupones_ok:
                request.session['mostrar_modal_completar_perfil'] = True
            else:
                # Limpiar si ya no corresponde mostrarlo.
                request.session.pop('mostrar_modal_completar_perfil', None)
                request.session.pop('forzar_modal_completar_perfil_primera_sesion', None)
                request.session.pop('dismiss_modal_completar_perfil', None)

        return self.get_response(request)
