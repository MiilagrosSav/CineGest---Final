"""
Vista de debugging para promociones y vínculos.
Solo accesible para superusers.
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from promociones.models import Promocion
from promociones.models.vinculo_promocional import VinculoPromocional


@staff_member_required
def debug_promociones(request):
    """
    Vista de debug que muestra todas las promociones activas y sus vínculos.
    Solo accesible para staff.
    """
    
    # Obtener todas las promociones automáticas activas
    promociones = Promocion.objects.filter(
        es_automatica=True,
        activo=True,
        fecha_baja__isnull=True
    ).order_by('-fecha_creacion')
    
    promociones_data = []
    
    for promo in promociones:
        # Obtener vínculos
        vinculos = VinculoPromocional.objects.filter(
            promocion=promo
        ).select_related('funcion__pelicula', 'pelicula')
        
        vinculos_info = []
        for v in vinculos:
            if v.funcion:
                vinculos_info.append({
                    'tipo': 'funcion',
                    'id': v.funcion.pk,
                    'descripcion': f"Función #{v.funcion.pk}: {v.funcion.pelicula.titulo}",
                    'fecha': v.funcion.fecha_hora,
                    'sala': v.funcion.sala.nombre,
                    'estado': v.funcion.estado,
                    'activo': v.funcion.activo,
                    'pelicula_activa': v.funcion.pelicula.activo
                })
            if v.pelicula:
                # Contar funciones de esta película
                from cine.models import Funcion
                funciones_count = Funcion.objects.filter(
                    pelicula=v.pelicula,
                    activo=True
                ).count()
                
                vinculos_info.append({
                    'tipo': 'pelicula',
                    'id': v.pelicula.pk,
                    'descripcion': f"Película: {v.pelicula.titulo}",
                    'activo': v.pelicula.activo,
                    'funciones_count': funciones_count
                })
        
        promociones_data.append({
            'promo': promo,
            'tiene_vinculos': vinculos.exists(),
            'vinculos': vinculos_info,
            'count_vinculos': vinculos.count()
        })
    
    context = {
        'promociones_data': promociones_data,
        'total_promociones': len(promociones_data),
        'ahora': timezone.now()
    }
    
    return render(request, 'promociones/debug_promociones.html', context)
