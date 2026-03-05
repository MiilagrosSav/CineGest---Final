# auditoria/templatetags/auditoria_extras.py
from django import template
from django.utils.dateparse import parse_datetime

register = template.Library()

@register.filter
def human_snapshot(value):
    """Convierte el snapshot en una cadena legible omitiendo IDs técnicos."""
    if not isinstance(value, dict):
        return value
    
    # Omitimos campos que el usuario no necesita ver en la lista
    exclude = ['id', 'uuid', 'password', 'last_login']
    items = [f"{k.replace('_', ' ').title()}: {v}" for k, v in value.items() if k not in exclude]
    
    res = " | ".join(items[:2]) # Solo mostramos los 2 primeros campos
    return res + "..." if len(items) > 2 else res

@register.filter(name='replace_underscore')
@register.filter
def limpiar_valor(value):
    """
    Limpia y formatea valores para mostrar en auditoría.
    
    - Convierte booleanos a Sí/No
    - Formatea fechas
    - Traduce campos al español
    - Normaliza email (sin modificar mayúsculas/minúsculas)
    """
    # Diccionario de traducciones de campos comunes
    TRADUCCIONES = {
        'username': 'Nombre de usuario',
        'email': 'Correo electrónico',
        'nombre': 'Nombre',
        'apellido': 'Apellido',
        'first_name': 'Nombre',
        'last_name': 'Apellido',
        'is_active': 'Activo',
        'activo': 'Activo',
        'rol': 'Rol',
        'telefono': 'Teléfono',
        'direccion': 'Dirección',
        'fecha_nacimiento': 'Fecha de nacimiento',
        'fecha_baja': 'Fecha de baja',
        'fecha_creacion': 'Fecha de creación',
        'fecha_modificacion': 'Fecha de modificación',
        'dni': 'DNI',
        'cuil': 'CUIL',
        'genero': 'Género',
        'edad': 'Edad',
        'points': 'Puntos',
        'created_at': 'Creado el',
        'updated_at': 'Actualizado el',
        'is_staff': 'Es staff',
        'is_superuser': 'Es superusuario',
        'last_login': 'Último acceso',
        'date_joined': 'Fecha de registro',
    }
    
    # 1. Si es un nombre de campo (clave), traducirlo
    if isinstance(value, str) and value.lower() in [k.lower() for k in TRADUCCIONES.keys()]:
        # Buscar la traducción case-insensitive
        for key, traduccion in TRADUCCIONES.items():
            if value.lower() == key.lower():
                return traduccion
    
    # 2. Si es booleano, mostrar Sí/No
    if isinstance(value, bool):
        return 'Sí' if value else 'No'
    
    # 3. Si es un diccionario (FK), sacamos el nombre legible
    if isinstance(value, dict):
        return value.get('repr', value.get('nombre', str(value)))
    
    # 4. Si es un string, chequeamos si es una fecha o texto técnico
    if isinstance(value, str):
        # Intentamos ver si es una fecha ISO
        fecha_parseada = parse_datetime(value)
        if fecha_parseada:
            return fecha_parseada.strftime("%d/%m/%Y %H:%M")
        
        # Si contiene '@', es un email - retornarlo sin modificar
        if '@' in value:
            return value
        
        # Si no es fecha ni email, limpiamos guiones bajos y capitalizamos
        return value.replace('_', ' ').title()
    
    return value


@register.filter
def format_boolean_badge(value):
    """
    Formatea valores booleanos con badges de color.
    Útil para campos como 'activo', 'is_active', etc.
    """
    if isinstance(value, bool):
        if value:
            return '<span class="badge-boolean badge-true">✓ TRUE</span>'
        else:
            return '<span class="badge-boolean badge-false">✗ FALSE</span>'
    return value