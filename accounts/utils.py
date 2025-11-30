from django.conf import settings
from django.utils import timezone

def get_or_create_consumidor_final():
    """Devuelve el objeto `Cliente` genérico "Consumidor Final".

    Crea un `Usuario` + `Cliente` si no existen. Usa DNI fijo '00000000'.
    Retorna la instancia de `Cliente`.
    """
    from accounts.models import Usuario, Cliente

    dni = '00000000'
    username = 'consumidor_final'
    email = 'consumidor.final@local'

    user, created = Usuario.objects.get_or_create(
        dni=dni,
        defaults={
            'username': username,
            'first_name': 'Consumidor',
            'last_name': 'Final',
            'email': email,
            'rol': 'cliente',
            'is_active': True,
        }
    )

    if created:
        # Asegurar que el usuario no tenga contraseña usable
        user.set_unusable_password()
        user.save()

    cliente, _ = Cliente.objects.get_or_create(usuario=user)
    return cliente
