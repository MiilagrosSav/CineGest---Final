from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
# --- Mixin de Seguridad para Administradores (CORREGIDO) ---
# Este mixin se asegura de que solo los usuarios con el rol 'administrador'
# o los superusuarios puedan acceder a las vistas de gestión.

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Asegura que el usuario esté logueado y sea un administrador o superusuario.
    """
    def test_func(self):
        # ✅ ESTA ES LA LÓGICA CORREGIDA
        # Comprueba si el usuario está autenticado Y si es superusuario O su rol es 'admin'
        if not self.request.user.is_authenticated:
            return False
        return self.request.user.is_superuser or self.request.user.rol == 'admin'

    def handle_no_permission(self):
        # Redirige al dashboard (el dashboard_view se encargará de mandarlo
        # al dashboard de cliente si es que no tiene permisos)
        return redirect('accounts:dashboard') # Usa el nombre correcto de la URL
# --- FIN DEL MIXIN DE SEGURIDAD PARA ADMINISTRADORES ---