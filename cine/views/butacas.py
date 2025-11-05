from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
import json
from cine.models import Butaca
from django.shortcuts import render
from cine.models import Sala


# --- Vistas para el Diseñador de Butacas ---
# Función auxiliar para verificar si es admin
def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.rol == 'admin')


@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def disenar_layout_sala(request, sala_id):
    """
    Muestra la página del diseñador visual para una sala específica.
    Solo accesible para administradores.
    """
    sala = get_object_or_404(Sala, id=sala_id)
    butacas = list(sala.butacas.all().order_by('fila', 'numero').values('fila', 'numero', 'tipo'))
    context = {
        'sala': sala,
        'butacas_existentes': butacas
    }
    return render(request, 'cine/disenar_layout.html', context)


@require_http_methods(["POST"])
@login_required
@user_passes_test(es_admin, login_url='/accounts/dashboard/')
def api_guardar_layout_sala(request, sala_id):
    """
    Recibe un JSON con el nuevo layout, borra las butacas antiguas
    y crea las nuevas. Solo accesible para administradores.
    """
    try:
        sala = get_object_or_404(Sala, id=sala_id)
        data = json.loads(request.body)

        # Borrar butacas antiguas
        sala.butacas.all().delete()

        # Preparar nuevas
        nuevas = []
        for item in data:
            fila = item.get('fila')
            num = item.get('num')
            tipo = item.get('tipo', 'GENERAL')
            if not fila or not num:
                continue
            nuevas.append(Butaca(sala=sala, fila=fila, numero=num, tipo=tipo))

        if nuevas:
            Butaca.objects.bulk_create(nuevas)

        sala.capacidad = sala.butacas.count()
        sala.save()

        return JsonResponse({'status': 'ok', 'butacas_creadas': len(nuevas), 'capacidad': sala.capacidad})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
