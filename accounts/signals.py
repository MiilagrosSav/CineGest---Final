"""
Signals para el módulo accounts
Gestiona la creación automática de perfiles según el rol del usuario
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Administrador, Empleado, Cliente

Usuario = get_user_model()


@receiver(post_save, sender=Usuario)
def crear_perfil_segun_rol(sender, instance, created, **kwargs):
    """
    Signal que crea automáticamente el perfil correspondiente según el rol del usuario.
    
    - Si rol='admin' → Crea perfil Administrador
    - Si rol='empleado' → Crea perfil Empleado  
    - Si rol='cliente' → Crea perfil Cliente
    
    También sincroniza los perfiles si el rol cambia.
    """
    # Evitar recursión infinita si el usuario es nuevo
    # y estamos en el proceso de creación inicial
    if hasattr(instance, '_creando_perfil'):
        return
    
    # Marcar que estamos creando perfil para evitar recursión
    instance._creando_perfil = True
    
    try:
        # ADMINISTRADOR
        if instance.rol == 'admin':
            # Crear perfil de Administrador si no existe
            if not hasattr(instance, 'administrador'):
                try:
                    Administrador.objects.create(
                        usuario=instance,
                        nivel_acceso='TOTAL'  # Valor por defecto
                    )
                    print(f"✅ Perfil Administrador creado para {instance.username}")
                except Exception as e:
                    print(f"⚠️ Error al crear perfil Administrador para {instance.username}: {e}")
            
            # Intentar eliminar otros perfiles si existen (pero permitir que fallen si hay relaciones protegidas)
            if hasattr(instance, 'empleado'):
                try:
                    instance.empleado.delete()
                except Exception:
                    print(f"⚠️ No se pudo eliminar perfil Empleado para {instance.username} (tiene datos relacionados)")
            
            if hasattr(instance, 'cliente'):
                try:
                    instance.cliente.delete()
                except Exception:
                    print(f"⚠️ No se pudo eliminar perfil Cliente para {instance.username} (tiene datos relacionados - se mantiene)")
        
        # EMPLEADO
        elif instance.rol == 'empleado':
            # Crear perfil de Empleado si no existe
            if not hasattr(instance, 'empleado'):
                try:
                    from datetime import date
                    Empleado.objects.create(
                        usuario=instance,
                        fecha_ingreso=date.today()
                    )
                    print(f"✅ Perfil Empleado creado para {instance.username}")
                except Exception as e:
                    print(f"⚠️ Error al crear perfil Empleado para {instance.username}: {e}")
            
            # Intentar eliminar otros perfiles si existen
            if hasattr(instance, 'administrador'):
                try:
                    instance.administrador.delete()
                except Exception:
                    print(f"⚠️ No se pudo eliminar perfil Administrador para {instance.username}")
            
            if hasattr(instance, 'cliente'):
                try:
                    instance.cliente.delete()
                except Exception:
                    print(f"⚠️ No se pudo eliminar perfil Cliente para {instance.username} (tiene datos relacionados - se mantiene)")
        
        # CLIENTE
        elif instance.rol == 'cliente':
            # Crear perfil de Cliente si no existe
            if not hasattr(instance, 'cliente'):
                try:
                    Cliente.objects.create(
                        usuario=instance
                    )
                    print(f"✅ Perfil Cliente creado para {instance.username}")
                except Exception as e:
                    print(f"⚠️ Error al crear perfil Cliente para {instance.username}: {e}")
            
            # Intentar eliminar otros perfiles si existen
            if hasattr(instance, 'administrador'):
                try:
                    instance.administrador.delete()
                except Exception:
                    print(f"⚠️ No se pudo eliminar perfil Administrador para {instance.username}")
            
            if hasattr(instance, 'empleado'):
                try:
                    instance.empleado.delete()
                except Exception:
                    print(f"⚠️ No se pudo eliminar perfil Empleado para {instance.username}")
    
    finally:
        # Limpiar la marca
        if hasattr(instance, '_creando_perfil'):
            delattr(instance, '_creando_perfil')
