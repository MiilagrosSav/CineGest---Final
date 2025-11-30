from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def solo_empleados(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        # --- DEBUG ---
        print(f"🔍 USUARIO ACTUAL: {user.username}")
        print(f"   -> Is Authenticated: {user.is_authenticated}")
        print(f"   -> Rol (atributo): '{getattr(user, 'rol', 'NO TIENE')}'")
        print(f"   -> Is Superuser: {user.is_superuser}")
        # -------------
        if not user.is_authenticated:
            return redirect('accounts:login')
            
        # Permitir si el rol es 'empleado' o 'admin', si es superuser, o si existe perfil Empleado
        allowed = False
        try:
            from accounts.models import Empleado
            rol = getattr(user, 'rol', '') or ''

            # 1) Rol explícito en el usuario
            if isinstance(rol, str) and rol.lower() in ['empleado', 'admin']:
                allowed = True

            # 2) Superusuario siempre permitido
            if not allowed and getattr(user, 'is_superuser', False):
                allowed = True

            # 3) Intentar obtener directamente el perfil Empleado por usuario_id
            if not allowed:
                try:
                    Empleado.objects.get(usuario_id=getattr(user, 'pk', None))
                    allowed = True
                except Empleado.DoesNotExist:
                    pass

            # 4) Fallbacks adicionales por username / email (por si hay mismatch)
            if not allowed:
                uname = getattr(user, 'username', None)
                if uname and Empleado.objects.filter(usuario__username=uname).exists():
                    allowed = True

            if not allowed:
                uemail = getattr(user, 'email', None)
                if uemail and Empleado.objects.filter(usuario__email=uemail).exists():
                    allowed = True

        except Exception:
            # Registrar la excepción para depuración pero no exponer detalles al usuario
            import logging
            logging.getLogger(__name__).exception('Error verificando permiso solo_empleados')

        if allowed:
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Acceso restringido: sólo personal de boletería.')
        # Redirigir al dashboard general
        return redirect('accounts:dashboard')

    return _wrapped