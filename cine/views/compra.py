from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cine.models import Funcion


@login_required
def comprar_entrada_view(request, funcion_id):
    """
    Vista para la compra de entrada.
    Por ahora solo muestra la información de la función seleccionada.
    """
    funcion = get_object_or_404(
        Funcion.objects.select_related('pelicula', 'sala')
        .prefetch_related('formatos_funcion__formato'),
        id=funcion_id
    )
    
    # Verificar que la función no haya pasado
    from django.utils import timezone
    if funcion.fecha_hora < timezone.now():
        messages.error(request, '❌ Esta función ya ha pasado.')
        return redirect('cine:cartelera')
    
    context = {
        'funcion': funcion,
        'formatos': funcion.get_formatos_display(),
    }
    
    return render(request, 'cine/comprar_entrada.html', context)
