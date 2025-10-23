from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import Usuario, Administrador, Empleado, Cliente

# Estos "inlines" permiten editar el perfil DENTRO del admin del Usuario
class AdministradorInline(admin.StackedInline):
    model = Administrador
    can_delete = False
    verbose_name_plural = 'Perfil de Administrador'
    fk_name = 'usuario'

class EmpleadoInline(admin.StackedInline):
    model = Empleado
    can_delete = False
    verbose_name_plural = 'Perfil de Empleado'
    fk_name = 'usuario'

class ClienteInline(admin.StackedInline):
    model = Cliente
    can_delete = False
    verbose_name_plural = 'Perfil de Cliente'
    fk_name = 'usuario'

@admin.register(Usuario)
class UsuarioAdmin(DjangoUserAdmin):
    # Campos que se muestran en la lista de usuarios
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_staff', 'is_active')
    
    # Campos que se muestran al editar un usuario
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'telefono', 'rol')}),
    )
    
    # Campos que se piden al CREAR un usuario
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'telefono', 'rol')}),
    )
    
    # Lista de inlines
    inlines = [] # Empezamos con una lista vacía

    # Sobreescribimos get_inlines para mostrar el perfil correcto
    def get_inlines(self, request, obj=None):
        if not obj:
            return []
        
        if obj.rol == 'admin':
            return [AdministradorInline]
        elif obj.rol == 'empleado':
            return [EmpleadoInline]
        elif obj.rol == 'cliente':
        
            return [ClienteInline]
        return []

# Nota: No registramos los perfiles por separado, ya que se manejan
# a través del admin de Usuario.
