"""
Signals para el módulo accounts
Gestiona la creación automática de perfiles según el rol del usuario
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Administrador, Empleado, Cliente

logger = logging.getLogger(__name__)

Usuario = get_user_model()


@receiver(post_save, sender=Usuario)
def crear_perfil_segun_rol(sender, instance, created, **kwargs):
    """
    Signal que crea automáticamente el perfil correspondiente según el rol del usuario.

    Usa get_or_create para evitar IntegrityError cuando el formulario
    ya creó el perfil antes de que se disparara el signal.
    """
    if hasattr(instance, '_creando_perfil'):
        return

    instance._creando_perfil = True

    try:
        if instance.rol == 'admin':
            try:
                Administrador.objects.get_or_create(usuario=instance)
            except Exception as e:
                logger.warning("Error al crear/verificar perfil Administrador para %s: %s", instance.username, e)

            if hasattr(instance, 'empleado'):
                try:
                    instance.empleado.delete()
                except Exception:
                    logger.warning("No se pudo eliminar perfil Empleado para %s (tiene datos relacionados)", instance.username)

            if hasattr(instance, 'cliente'):
                try:
                    instance.cliente.delete()
                except Exception:
                    logger.warning("No se pudo eliminar perfil Cliente para %s (tiene datos relacionados)", instance.username)

        elif instance.rol == 'empleado':
            try:
                from datetime import date
                Empleado.objects.get_or_create(
                    usuario=instance,
                    defaults={'fecha_ingreso': date.today()}
                )
            except Exception as e:
                logger.warning("Error al crear/verificar perfil Empleado para %s: %s", instance.username, e)

            if hasattr(instance, 'administrador'):
                try:
                    instance.administrador.delete()
                except Exception:
                    logger.warning("No se pudo eliminar perfil Administrador para %s", instance.username)

            if hasattr(instance, 'cliente'):
                try:
                    instance.cliente.delete()
                except Exception:
                    logger.warning("No se pudo eliminar perfil Cliente para %s (tiene datos relacionados)", instance.username)

        elif instance.rol == 'cliente':
            try:
                Cliente.objects.get_or_create(usuario=instance)
            except Exception as e:
                logger.warning("Error al crear/verificar perfil Cliente para %s: %s", instance.username, e)

            if hasattr(instance, 'administrador'):
                try:
                    instance.administrador.delete()
                except Exception:
                    logger.warning("No se pudo eliminar perfil Administrador para %s", instance.username)

            if hasattr(instance, 'empleado'):
                try:
                    instance.empleado.delete()
                except Exception:
                    logger.warning("No se pudo eliminar perfil Empleado para %s", instance.username)

    finally:
        if hasattr(instance, '_creando_perfil'):
            delattr(instance, '_creando_perfil')
