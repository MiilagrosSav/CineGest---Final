from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def solo_empleados(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect('accounts:login')

        allowed = (
            getattr(user, 'rol', '') in ['empleado', 'admin']
            or getattr(user, 'is_superuser', False)
        )

        if allowed:
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Acceso restringido: sólo personal de boletería.')
        return redirect('accounts:dashboard')

    return _wrapped