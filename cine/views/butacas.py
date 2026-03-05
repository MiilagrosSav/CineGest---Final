from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
import json
from cine.models import Butaca
from django.shortcuts import render
from cine.models import Sala
from django.contrib import messages


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
    Bloquea la edición si la sala tiene butacas vendidas.
    """
    sala = get_object_or_404(Sala, id=sala_id)
    
    # Verificar si la sala tiene butacas vendidas
    if sala.tiene_butacas_vendidas():
        messages.error(
            request, 
            f'No se puede modificar la distribución de asientos de la Sala {sala.numero} porque tiene butacas vendidas. '
            'Por seguridad, no es posible reconfigurar una sala con ventas activas.'
        )
        return redirect('cine:sala_list')
    
    butacas = list(sala.butacas.all().order_by('fila', 'numero').values('fila', 'numero', 'tipo', 'es_pasillo'))
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
    Recibe un JSON con la nueva distribución de asientos (incluyendo pasillos), 
    borra las butacas antiguas y crea las nuevas.
    Solo accesible para administradores.
    Bloquea el guardado si la sala tiene butacas vendidas.
    """
    try:
        sala = get_object_or_404(Sala, id=sala_id)
        
        # Verificar si la sala tiene butacas vendidas
        if sala.tiene_butacas_vendidas():
            return JsonResponse({
                'status': 'error', 
                'message': 'No se puede modificar la distribución de asientos porque la sala tiene butacas vendidas.'
            }, status=403)
        
        data = json.loads(request.body)

        # Borrar butacas antiguas
        sala.butacas.all().delete()

        # Preparar nuevas (incluyendo pasillos)
        nuevas = []
        seen = set()  # Para detectar duplicados
        duplicados = []
        
        for item in data:
            fila = item.get('fila')
            num = item.get('num')
            tipo = item.get('tipo', 'GENERAL')
            es_pasillo = item.get('es_pasillo', False)
            
            if not fila or num is None:
                continue
            
            # Verificar duplicados
            clave = (fila, num)
            if clave in seen:
                duplicados.append(f"{fila}{num}")
                continue  # Saltar duplicados
            seen.add(clave)
            
            # Si es pasillo (tipo 'vacio'), marcar es_pasillo=True
            if tipo == 'vacio':
                es_pasillo = True
                tipo = 'GENERAL'  # Los pasillos son tipo GENERAL pero con flag es_pasillo
            
            nuevas.append(Butaca(
                sala=sala, 
                fila=fila, 
                numero=num, 
                tipo=tipo,
                es_pasillo=es_pasillo
            ))

        if nuevas:
            try:
                Butaca.objects.bulk_create(nuevas)
            except Exception as e:
                error_msg = str(e)
                # Detectar el tipo de error
                if 'unique' in error_msg.lower() or 'duplicate' in error_msg.lower():
                    error_msg = f'Error de duplicados: Una o más butacas ya existen en esta combinación sala-fila-número. {error_msg}'
                else:
                    error_msg = f'Error al crear butacas: {error_msg}'
                    
                return JsonResponse({
                    'status': 'error', 
                    'message': error_msg,
                    'duplicados_detectados': duplicados if duplicados else [],
                    'total_enviado': len(data),
                    'total_procesado': len(nuevas)
                }, status=400)

        # Calcular capacidad real (solo butacas, sin pasillos)
        capacidad_real = sala.butacas.filter(es_pasillo=False).count()
        
        # Contar pasillos en la lista de nuevas antes de bulk_create
        total_pasillos = sum(1 for b in nuevas if b.es_pasillo)
        # --- PARCHE PARA ACTUALIZAR CAPACIDAD TOTAL ---
        # Como bulk_create no dispara señales, forzamos la actualización manual aquí.
        sala.capacidad_total = sala.butacas.filter(es_pasillo=False).count()
        sala.save(update_fields=['capacidad_total'])
        
        respuesta = {
            'status': 'ok', 
            'butacas_creadas': len(nuevas),
            'capacidad': capacidad_real,
            'pasillos': total_pasillos
        }
        
        if duplicados:
            respuesta['warning'] = f'{len(duplicados)} butacas duplicadas fueron ignoradas'
            respuesta['duplicados'] = duplicados
        
    
        return JsonResponse(respuesta)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
