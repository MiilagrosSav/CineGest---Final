from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import logging

from ventas.models import Venta, Intercambio
from ventas.services import obtener_funciones_candidatas
from ventas.intercambio_service import intercambio_service

logger = logging.getLogger(__name__)


@login_required
def intercambiar_entrada_view(request, venta_id):
	"""Vista que muestra las funciones disponibles para intercambiar.
	
	El usuario selecciona una función y luego es redirigido a seleccionar_butacas_intercambio
	para elegir las butacas específicas manualmente.
	"""
	venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

	logger.info(f"Usuario {request.user.username} accediendo a intercambio para venta {venta_id}")

	# Obtener política activa
	politica = intercambio_service.obtener_politica_activa()
	
	# Validar que puede intercambiar (sin función destino aún)
	if politica:
		# Validar condiciones básicas de la venta
		if venta.estado != 'CONFIRMADA':
			messages.error(request, 'Solo se pueden intercambiar ventas confirmadas.')
			return redirect('ventas:detalle_venta', venta_id=venta.id_venta)

		# Validación de política (cupón/promos, reintercambio, anticipación, límites)
		permite_según_politica, motivo_politica = politica.permite_intercambio_para_venta(venta)
		if not permite_según_politica:
			messages.error(request, motivo_politica)
			return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
		
		# Verificar límite de intercambios usando la política
		puede, mensaje_error = Intercambio.puede_intercambiar(venta, politica)
		if not puede:
			messages.error(request, mensaje_error)
			return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
	
	# Obtener funciones candidatas (mismo precio)
	candidatas = obtener_funciones_candidatas(venta)

	# Si no hay candidatas, mostrar mensaje informativo
	if not candidatas.exists():
		precio = None
		entradas = venta.entradas.all()
		if entradas.exists():
			precio = entradas[0].id_funcion.precio_base

		context = {
			'venta': venta,
			'mensaje_no_candidatas': True,
			'precio': precio,
		}
		return render(request, 'ventas/intercambiar_entrada.html', context)

	# Mostrar funciones disponibles
	# El template tiene botones que redirigen a seleccionar_butacas_intercambio
	context = {
		'venta': venta,
		'candidatas': candidatas,
		'politica': politica,
	}
	return render(request, 'ventas/intercambiar_entrada.html', context)


@login_required
def intercambio_exitoso_view(request, intercambio_id):
	"""Vista GET para mostrar el resultado exitoso de un intercambio.
	
	Esta vista implementa el patrón Post/Redirect/Get (PRG) para prevenir
	que al recargar la página se re-ejecute el POST de procesar_intercambio.
	"""
	# Obtener el intercambio y validar que pertenece al usuario actual
	intercambio = get_object_or_404(
		Intercambio,
		id_intercambio=intercambio_id,
		venta__id_cliente__usuario=request.user
	)
	
	logger.info(f"Usuario {request.user.username} visualizando intercambio exitoso #{intercambio_id}")
	
	context = {
		'venta': intercambio.venta,
		'intercambio': intercambio,
		'funcion_nueva': intercambio.funcion_destino,
	}
	return render(request, 'ventas/intercambio_exitoso.html', context)
