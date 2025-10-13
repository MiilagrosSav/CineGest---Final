from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    """Formulario personalizado para crear usuarios en el admin"""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('user_type',)

class CustomUserChangeForm(UserChangeForm):
    """Formulario personalizado para editar usuarios en el admin"""
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # Usar formularios personalizados
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    # Configurar la visualización en la lista
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_staff', 'is_active')
    list_filter = ('user_type', 'is_staff', 'is_active', 'date_joined')
    
    # ✅ CONFIGURAR FIELDSETS PERSONALIZADOS (sin campos problemáticos)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Información Adicional', {'fields': ('user_type',)}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    # ✅ CONFIGURAR ADD_FIELDSETS PERSONALIZADOS 
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'user_type'),
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email'),
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )
    
    # Configurar búsqueda y ordenamiento
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
