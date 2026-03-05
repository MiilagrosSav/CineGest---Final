from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from simple_history.admin import SimpleHistoryAdmin
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
class UsuarioAdmin(SimpleHistoryAdmin, DjangoUserAdmin):
    # Campos que se muestran en la lista de usuarios
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_staff', 'is_active')
    
    # Campos que se muestran al editar un usuario
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'telefono', 'rol')}),
    )
    
    # Campos que se piden al CREAR un usuario con email
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'email', 'telefono', 'rol')}),
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

# Registrar los perfiles también como modelos independientes para visibilidad
@admin.register(Administrador)
class AdministradorAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'get_email', 'nivel_acceso', 'get_fecha_creacion')
    search_fields = ('usuario__username', 'usuario__email')
    list_filter = ('nivel_acceso',)
    
    def get_username(self, obj):
        return obj.usuario.username
    get_username.short_description = 'Usuario'
    get_username.admin_order_field = 'usuario__username'
    
    def get_email(self, obj):
        return obj.usuario.email
    get_email.short_description = 'Email'
    
    def get_fecha_creacion(self, obj):
        return obj.usuario.date_joined
    get_fecha_creacion.short_description = 'Fecha de creación'
    get_fecha_creacion.admin_order_field = 'usuario__date_joined'

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'get_email', 'fecha_ingreso', 'get_fecha_creacion')
    search_fields = ('usuario__username', 'usuario__email')
    list_filter = ('fecha_ingreso',)
    
    def get_username(self, obj):
        return obj.usuario.username
    get_username.short_description = 'Usuario'
    get_username.admin_order_field = 'usuario__username'
    
    def get_email(self, obj):
        return obj.usuario.email
    get_email.short_description = 'Email'
    
    def get_fecha_creacion(self, obj):
        return obj.usuario.date_joined
    get_fecha_creacion.short_description = 'Fecha de registro'
    get_fecha_creacion.admin_order_field = 'usuario__date_joined'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'get_email', 'fecha_registro')
    search_fields = ('usuario__username', 'usuario__email')
    list_filter = ('fecha_registro',)
    
    def get_username(self, obj):
        return obj.usuario.username
    get_username.short_description = 'Usuario'
    get_username.admin_order_field = 'usuario__username'
    
    def get_email(self, obj):
        return obj.usuario.email
    get_email.short_description = 'Email'
