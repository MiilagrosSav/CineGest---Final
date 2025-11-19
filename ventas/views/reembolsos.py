from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
import logging

from ventas.models import Venta
from ventas.forms import IntercambioEntradaForm
from ventas.services import obtener_funciones_candidatas
from ventas.intercambio_service import intercambio_service, IntercambioValidacionError
from ventas.constants import MotivoIntercambio

logger = logging.getLogger(__name__)


@login_required
def intercambiar_entrada_view(request, venta_id):
	"""Vista para intercambiar las entradas de una venta por otra función válida."""
	venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

	logger.info(f"Usuario {request.user.username} accediendo a intercambio para venta {venta_id}")

	# Obtener política activa
	politica = intercambio_service.obtener_politica_activa()
	
	# Validar que puede intercambiar
	puede, mensaje_error = intercambio_service.validar_intercambio(venta, None, politica) if politica else (False, 'No hay política de intercambio configurada.')
	
	if not puede and request.method == 'GET':
		# Mostrar mensaje informativo en GET
		context = {
			'venta': venta,
			'mensaje_no_candidatas': True,
			'mensaje_error': mensaje_error,
		}
		return render(request, 'ventas/intercambiar_entrada.html', context)

	# Obtener funciones candidatas
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

	# Procesar formulario
	if request.method == 'POST':
		form = IntercambioEntradaForm(request.POST, compra=venta)
		if form.is_valid():
			nueva_funcion = form.cleaned_data['nueva_funcion']
			cantidad = venta.entradas.count()
			
			logger.info(
				f"Procesando intercambio: venta {venta_id}, "
				f"función destino {nueva_funcion.id}, cantidad {cantidad}"
			)

			# Verificar disponibilidad
			disponible, mensaje, butacas = intercambio_service.verificar_disponibilidad(
				nueva_funcion,
				cantidad
			)
			
			if not disponible:
				logger.warning(f"Disponibilidad insuficiente para venta {venta_id}: {mensaje}")
				messages.error(request, f'❌ {mensaje}')
				return redirect('ventas:intercambiar_entrada', venta_id=venta.id_venta)

			# Ejecutar intercambio usando el servicio
			exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
				venta=venta,
				funcion_destino=nueva_funcion,
				butacas=butacas,
				motivo=MotivoIntercambio.OTRO,
				request=request
			)
			
			if exitoso:
				logger.info(f"Intercambio exitoso para venta {venta_id}, intercambio #{intercambio.id_intercambio}")
				messages.success(request, f'✅ {mensaje}')
				return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
			else:
				logger.error(f"Intercambio fallido para venta {venta_id}: {mensaje}")
				messages.error(request, f'❌ {mensaje}')
		else:
			logger.warning(f"Formulario inválido para intercambio venta {venta_id}: {form.errors}")
			messages.error(request, '❌ Por favor corrige los errores en el formulario.')
	else:
		form = IntercambioEntradaForm(compra=venta)

	context = {
		'venta': venta,
		'form': form,
		'candidatas': candidatas,
		'politica': politica,
	}
	return render(request, 'ventas/intercambiar_entrada.html', context)
