from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameBackend(ModelBackend):
    """
    Backend de autenticación híbrido.
    - Si el campo contiene '@' → busca por email.
    - De lo contrario → busca por username (normalizado a minúsculas).
    Compatible con cuentas inactivas (is_active=False se rechaza en user_can_authenticate).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()

        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if not username or not password:
            return None

        try:
            if '@' in username:
                user = User.all_objects.get(email=username.strip().lower())
            else:
                user = User.all_objects.get(username=username.strip().lower())
        except User.DoesNotExist:
            # Ejecutar hash de contraseña para mitigar timing attacks
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
