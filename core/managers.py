"""
Managers personalizados para implementar baja lógica (soft delete) en todo el proyecto.

Este módulo proporciona managers que filtran automáticamente registros inactivos,
manteniendo compatibilidad con simple_history y permitiendo acceso administrativo
a todos los registros cuando sea necesario.
"""

from django.db import models


class ActiveManager(models.Manager):
    """
    Manager que filtra automáticamente solo registros activos (activo=True).
    
    Este manager se usa como default (objects) en modelos con baja lógica,
    asegurando que las consultas normales solo devuelvan registros activos.
    
    Ejemplo:
        Pelicula.objects.all()  # Solo películas con activo=True
        Pelicula.objects.filter(titulo__icontains='Matrix')  # Solo activas
    """
    
    def get_queryset(self):
        """Sobrescribe queryset para filtrar solo registros activos"""
        return super().get_queryset().filter(activo=True)


class AllObjectsManager(models.Manager):
    """
    Manager que devuelve TODOS los registros, incluyendo inactivos.
    
    Este manager se usa para permitir acceso administrativo a registros
    dados de baja, útil para reportes, auditoría y recuperación.
    
    Ejemplo:
        Pelicula.all_objects.all()  # Todas las películas (activas e inactivas)
        Pelicula.all_objects.filter(activo=False)  # Solo inactivas
    """
    
    def get_queryset(self):
        """Devuelve queryset sin filtrar por estado activo"""
        return super().get_queryset()
