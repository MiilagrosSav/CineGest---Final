def custom_social_user(backend, uid, user=None, *args, **kwargs):
    """
    Pipeline que maneja usuarios sociales existentes y busca por email
    """
    from social_django.models import UserSocialAuth
    from django.contrib.auth import get_user_model
    
    print(f"🔍 Pipeline OAuth: provider={backend.name}, uid={uid}")
    
    # 1. Buscar asociación social existente
    try:
        social = UserSocialAuth.get_social_auth(backend.name, uid)
        if social:
            print(f"✅ Usuario social encontrado: {social.user.username}")
            return {'social': social, 'user': social.user, 'is_new': False}
    except UserSocialAuth.DoesNotExist:
        print("📝 No hay asociación social previa")
    
    # 2. Si no hay asociación social, buscar usuario por email
    details = kwargs.get('details', {})
    email = details.get('email')
    
    if email:
        User = get_user_model()
        try:
            existing_user = User.objects.get(email=email)
            print(f"👤 Usuario existente encontrado por email: {existing_user.username}")
            
            # Crear nueva asociación social
            try:
                social = UserSocialAuth.create_social_auth(existing_user, uid, backend.name)
                print(f"🔗 Asociación social creada exitosamente")
                return {'social': social, 'user': existing_user, 'is_new': False}
            except Exception as e:
                print(f"❌ Error creando asociación social: {e}")
                # Si no se puede crear la asociación, al menos retornar el usuario
                return {'user': existing_user, 'is_new': False}
                
        except User.DoesNotExist:
            print(f"📧 Usuario no encontrado con email: {email}")
    
    # 3. Si no hay usuario, el pipeline continuará para crear uno nuevo
    print("🆕 Continuando pipeline para crear nuevo usuario")
    return None


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
    
    if is_new_user:
        # Si es nuevo, asignarle automáticamente el tipo 'cliente'
        user.user_type = 'cliente'
        print(f"🆕 Usuario nuevo creado con Google: {user.username}")
        print(f"👤 Tipo de usuario asignado: cliente")
    
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
    print(f"💾 Perfil guardado correctamente")
    
    # Devolver el usuario para que Django continúe con el proceso
    return {
        'user': user,
        'is_new': is_new_user
    }