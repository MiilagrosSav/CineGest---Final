def custom_social_user(backend, uid, user=None, *args, **kwargs):
    """
    Función personalizada que reemplaza social_core.pipeline.social_auth.social_user
    para evitar el error AuthAlreadyAssociated
    """
    from social_django.models import UserSocialAuth
    from django.contrib.auth import get_user_model
    
    print(f"🔍 Buscando usuario social: provider={backend.name}, uid={uid}")
    
    # Buscar asociación social existente
    social = UserSocialAuth.get_social_auth(backend.name, uid)
    if social:
        print(f"✅ Asociación social encontrada: {social.user.username}")
        return {'social': social, 'user': social.user, 'is_new': False}
    
    # Si no se encontró asociación social, buscar por email
    email = kwargs.get('details', {}).get('email')
    if email:
        User = get_user_model()
        try:
            existing_user = User.objects.get(email=email)
            print(f"👤 Usuario encontrado por email: {existing_user.username}")
            # Crear nueva asociación social para este usuario
            social = UserSocialAuth.create_social_auth(existing_user, uid, backend.name)
            print(f"🔗 Nueva asociación social creada")
            return {'social': social, 'user': existing_user, 'is_new': False}
        except User.DoesNotExist:
            print(f"📧 No se encontró usuario con email: {email}")
    
    # No hay usuario social ni usuario por email - continuar con pipeline normal
    # IMPORTANTE: No retornar social=None, simplemente no incluir la key
    return {}


def associate_by_email(backend, details, user=None, uid=None, *args, **kwargs):
    """
    Pipeline personalizado que busca usuarios existentes por email.
    Si encuentra uno, lo asocia automáticamente y crea la conexión social.
    """
    # Si ya hay un usuario, continuar
    if user:
        return {'user': user}
    
    email = details.get('email')
    if not email:
        print("⚠️ No se proporcionó email en OAuth")
        return None
    
    # Importar modelos necesarios
    from django.contrib.auth import get_user_model
    from social_django.models import UserSocialAuth
    User = get_user_model()
    
    try:
        # Buscar usuario existente con ese email
        existing_user = User.objects.get(email=email)
        print(f"👤 Usuario existente encontrado: {existing_user.username} ({email})")
        
        # Verificar si ya tiene asociación social con este proveedor
        social_user = UserSocialAuth.objects.filter(
            user=existing_user,
            provider=backend.name,
            uid=uid
        ).first()
        
        if not social_user:
            # Crear la asociación social si no existe
            UserSocialAuth.objects.create(
                user=existing_user,
                provider=backend.name,
                uid=uid,
                extra_data={}
            )
            print(f"🔗 Asociación social creada para {existing_user.username}")
        else:
            print(f"🔗 Asociación social ya existía para {existing_user.username}")
        
        return {'user': existing_user, 'is_new': False}
        
    except User.DoesNotExist:
        # No existe, continuar con el proceso normal
        print(f"📧 No se encontró usuario con email: {email}")
        return None


def setup_user_profile(backend, user, response, *args, **kwargs):
    """
    Pipeline personalizado que se ejecuta cuando un usuario se autentica con Google.
    
    ¿Qué hace esta función?
    - Se ejecuta automáticamente cuando alguien inicia sesión con Google
    - Asigna el tipo 'cliente' a usuarios nuevos
    - Actualiza el nombre, apellido y email con los datos de Google
    - Guarda todo en la base de datos
    
    Parámetros que Django nos pasa automáticamente:
    - backend: El sistema de Google OAuth2
    - user: El usuario de Django (recién creado o existente)
    - response: Los datos que Google nos envió sobre el usuario
    - *args, **kwargs: Parámetros adicionales
    """
    
    # Mostrar en la consola que esta función se está ejecutando
    print(f"🔧 Ejecutando pipeline para usuario: {user.username}")
    
    # Verificar si es un usuario completamente nuevo
    is_new_user = kwargs.get('is_new', False)
    
    # ✅ MARCAR USUARIO COMO OAUTH PARA EVITAR CONVERSIÓN AUTOMÁTICA A ADMIN
    user._oauth_user = True  # Flag temporal para el método save()
    
    if is_new_user:
        # Si es nuevo, asignarle automáticamente el tipo 'CLIENTE' (usar la constante del modelo)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user.user_type = User.CLIENTE
        # ✅ ASEGURAR QUE NO SEA SUPERUSUARIO
        user.is_superuser = False
        user.is_staff = False
        print(f"🆕 Usuario nuevo creado con Google: {user.username}")
        print(f"👤 Tipo de usuario asignado: {User.CLIENTE}")
    else:
        # Si es usuario existente, preservar su tipo actual
        print(f"👤 Usuario existente: {user.username}, tipo actual: {user.user_type}")
        # ✅ NO cambiar is_superuser para usuarios existentes
    
    # Actualizar información del perfil con datos que Google nos dio
    
    # Si Google nos dio el nombre
    if 'given_name' in response:
        user.first_name = response['given_name']
        print(f"📝 Nombre actualizado: {response['given_name']}")
        
        # ✅ OPCIONAL: También actualizar el username con el nombre de Google
        if is_new_user:
            # Solo para usuarios nuevos, cambiar el username al nombre de Google
            new_username = response['given_name'].lower().replace(' ', '')
            
            # Verificar que no exista ya ese username
            from django.contrib.auth import get_user_model
            User = get_user_model()
            counter = 1
            original_username = new_username
            
            while User.objects.filter(username=new_username).exclude(id=user.id).exists():
                new_username = f"{original_username}{counter}"
                counter += 1
            
            user.username = new_username
            print(f"👤 Username actualizado a: {new_username}")
    
    # Si Google nos dio el apellido  
    if 'family_name' in response:
        user.last_name = response['family_name']
        print(f"📝 Apellido actualizado: {response['family_name']}")
        
    # Si Google nos dio el email
    if 'email' in response:
        user.email = response['email']
        print(f"📧 Email actualizado: {response['email']}")
    
    # Guardar todos los cambios en la base de datos
    user.save()
    
    # ✅ LIMPIAR FLAG TEMPORAL
    if hasattr(user, '_oauth_user'):
        delattr(user, '_oauth_user')
    
    print(f"💾 Perfil guardado correctamente")
    
    # Devolver el usuario para que Django continúe con el proceso
    return {
        'user': user,
        'is_new': is_new_user
    }