from django import forms
from django.utils.translation import gettext_lazy as _
from cine.models.funcion import Funcion
from .services import obtener_funciones_candidatas

class IntercambioEntradaForm(forms.Form):
	nueva_funcion = forms.ModelChoiceField(
		queryset=Funcion.objects.none(),
		label=_('Nueva función'),
		required=True,
		empty_label=_('Selecciona una función disponible')
	)

	def __init__(self, *args, **kwargs):
		# Extra arg: compra (Venta)
		compra = kwargs.pop('compra', None)
		super().__init__(*args, **kwargs)

		if compra is not None:
			qs = obtener_funciones_candidatas(compra)
			self.fields['nueva_funcion'].queryset = qs
		else:
			self.fields['nueva_funcion'].queryset = Funcion.objects.none()

	def clean(self):
		cleaned = super().clean()
		# Si el queryset quedó vacío, se puede validar aquí o dejar que la vista maneje el caso
		return cleaned
