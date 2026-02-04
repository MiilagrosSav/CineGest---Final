from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models.deletion import ProtectedError


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


# --- Mixin para Manejo Centralizado de ProtectedError (DRY) ---
class ProtectedDeleteMixin:
    """
    Mixin que centraliza el manejo de ProtectedError en vistas de eliminación.
    Extrae la lógica repetida de generación de mensajes de error detallados.
    
    Las vistas que usen este mixin deben definir:
    - protected_model: Modelo relacionado que causa la protección
    - protected_filter_field: Campo para filtrar objetos relacionados
    - object_name_field: Campo del modelo a mostrar en mensajes
    - related_name: Nombre descriptivo del tipo de relación (ej: "política(s)")
    """
    
    protected_model = None
    protected_filter_field = None
    object_name_field = 'nombre'
    related_name = 'objeto(s)'
    
    def get_protected_queryset(self, obj):
        """
        Retorna el queryset de objetos relacionados que causan la protección.
        Debe ser sobrescrito si se necesita lógica personalizada.
        """
        filter_kwargs = {self.protected_filter_field: obj}
        return self.protected_model.objects.filter(**filter_kwargs)
    
    def get_protected_message_parts(self, obj, protected_objects):
        """
        Construye las partes del mensaje de error.
        Puede ser sobrescrito para personalizar el mensaje.
        """
        return [
            f'No se puede eliminar "{getattr(obj, self.object_name_field)}" porque está asociado a:',
            f'<br><strong>• {protected_objects.count()} {self.related_name}</strong>'
        ]
    
    def get_alternative_messages(self):
        """
        Retorna lista de mensajes alternativos.
        Puede ser sobrescrito para personalizar alternativas.
        """
        return [
            '<br><br><strong>Alternativas:</strong>',
            '1. Eliminar o modificar los objetos relacionados',
            '2. Marcar como inactivo en lugar de eliminar'
        ]
    
    def delete(self, request, *args, **kwargs):
        """
        Sobrescribe el método delete para capturar ProtectedError
        y generar mensajes de error detallados automáticamente.
        """
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        try:
            self.object.delete()
            messages.success(
                request, 
                f'"{getattr(self.object, self.object_name_field)}" ha sido eliminado exitosamente.'
            )
            return redirect(success_url)
        except ProtectedError:
            # Obtener objetos relacionados
            protected_objects = self.get_protected_queryset(self.object)
            
            # Construir mensaje
            mensaje_partes = self.get_protected_message_parts(self.object, protected_objects)
            mensaje_partes.extend(self.get_alternative_messages())
            
            mensaje_final = '<br>'.join(mensaje_partes)
            messages.error(request, mensaje_final, extra_tags='safe')
            return redirect(success_url)
# --- FIN DEL MIXIN DE MANEJO DE PROTECTEDERROR ---