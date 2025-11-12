"""
Vista para procesar la compra de entradas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from cine.models import Funcion, Butaca
from ventas.models import Venta, Entrada
from accounts.models import Cliente


@login_required
def procesar_compra(request, funcion_id):
    """Vista para procesar la compra de entradas"""
    
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    
    # Obtener las butacas seleccionadas del formulario
    butacas_ids = request.POST.getlist('butacas[]')
    
    if not butacas_ids:
        messages.error(request, '❌ Debes seleccionar al menos una butaca.')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    try:
        with transaction.atomic():
            # Obtener o crear el cliente asociado al usuario
            cliente, created = Cliente.objects.get_or_create(
                usuario=request.user,
                defaults={
                    'direccion': '',  # Valores opcionales para Cliente
                    'fecha_nacimiento': None,
                }
            )
            
            # Crear la venta
            venta = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='ONLINE',
                estado='PENDIENTE'
            )
            
            # Verificar que las butacas estén disponibles y crear las entradas
            for butaca_id in butacas_ids:
                butaca = get_object_or_404(Butaca, id=butaca_id)
                
                # Verificar que la butaca no esté ocupada
                entrada_existente = Entrada.objects.filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado__in=['RESERVADA', 'VENDIDA']
                ).exists()
                
                if entrada_existente:
                    raise Exception(f'La butaca {butaca.fila}{butaca.numero} ya está ocupada.')
                
                # Crear la entrada
                Entrada.objects.create(
                    id_venta=venta,
                    id_funcion=funcion,
                    id_sala=funcion.sala,
                    id_butaca=butaca,
                    id_pelicula=funcion.pelicula,
                    estado='RESERVADA'
                )
            
            messages.success(request, f'✅ Se creó tu reserva con {len(butacas_ids)} entrada(s). ¡Ahora procede al pago!')
            
            # Redirigir al proceso de pago
            return redirect('ventas:iniciar_pago', venta_id=venta.id_venta)
            
    except Exception as e:
        messages.error(request, f'❌ Error al procesar la compra: {str(e)}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
            
    except Exception as e:
        messages.error(request, f'❌ Error al procesar la compra: {str(e)}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)


@login_required
def confirmar_compra(request, funcion_id):
    """Vista para mostrar resumen y confirmar la compra antes del pago"""
    
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    butacas_ids = request.POST.getlist('butacas[]')
    
    if not butacas_ids:
        messages.error(request, '❌ Debes seleccionar al menos una butaca.')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    # Obtener las butacas seleccionadas
    butacas = Butaca.objects.filter(id__in=butacas_ids)
    
    # Calcular el total
    total = len(butacas_ids) * funcion.precio_base
    
    context = {
        'funcion': funcion,
        'butacas': butacas,
        'cantidad': len(butacas_ids),
        'precio_unitario': funcion.precio_base,
        'total': total,
        'butacas_ids': butacas_ids,
    }
    
    return render(request, 'ventas/confirmar_compra.html', context)
