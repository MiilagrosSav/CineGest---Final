from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from ventas.models import Venta, Entrada
from cine.models import Funcion, Butaca
from ventas.forms import IntercambioEntradaForm
from ventas.services import obtener_funciones_candidatas


@login_required
def intercambiar_entrada_view(request, venta_id):
	"""Vista para intercambiar las entradas de una venta por otra función válida."""
	venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

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

	# Instanciar form
	if request.method == 'POST':
		form = IntercambioEntradaForm(request.POST, compra=venta)
		if form.is_valid():
			nueva_funcion = form.cleaned_data['nueva_funcion']
			cantidad = venta.entradas.count()

			# Ejecutar la operación de intercambio dentro de una transacción
			try:
				with transaction.atomic():
					# Marcar entradas antiguas como canceladas para liberar butacas
					venta.entradas.update(estado='CANCELADA')

					# Determinar butacas disponibles en la nueva función
					ocupadas_ids = set(
						Entrada.objects.filter(
							id_funcion=nueva_funcion,
							estado__in=['RESERVADA', 'VENDIDA', 'USADA']
						).values_list('id_butaca_id', flat=True)
					)

					disponibles_qs = Butaca.objects.filter(sala=nueva_funcion.sala, es_pasillo=False).exclude(id__in=ocupadas_ids).order_by('fila', 'numero')

					disponibles = list(disponibles_qs[:cantidad])
					if len(disponibles) < cantidad:
						raise Exception('No hay suficientes butacas disponibles en la nueva función.')

					# Crear nuevas entradas asignando las butacas
					for butaca in disponibles:
						Entrada.objects.create(
							id_venta=venta,
							id_funcion=nueva_funcion,
							id_sala=nueva_funcion.sala,
							id_butaca=butaca,
							id_pelicula=nueva_funcion.pelicula,
							estado='RESERVADA'
						)

				messages.success(request, '✅ Intercambio realizado con éxito.')
				return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
			except Exception as e:
				messages.error(request, f'❌ No se pudo completar el intercambio: {str(e)}')
	else:
		form = IntercambioEntradaForm(compra=venta)

	context = {
		'venta': venta,
		'form': form,
		'candidatas': candidatas,
	}
	return render(request, 'ventas/intercambiar_entrada.html', context)

# Create your views here.
