from django import forms
from django.utils.translation import gettext_lazy as _
from cine.models.funcion import Funcion
from ventas.models import PoliticaReembolso
from .services import obtener_funciones_candidatas


class PoliticaReembolsoAdminForm(forms.ModelForm):
	"""Formulario admin para la política de intercambio."""

	class Meta:
		model = PoliticaReembolso
		fields = '__all__'

	def clean_max_cambios_por_compra(self):
		valor = self.cleaned_data.get('max_cambios_por_compra')
		if valor is None:
			return 0
		if valor < 0:
			raise forms.ValidationError('El máximo de cambios por compra no puede ser negativo.')
		return valor

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
