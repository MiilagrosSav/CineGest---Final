from datetime import date, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from cine.models import Funcion, Pelicula
from django.utils import timezone
from datetime import timedelta

# --- Vista de Cartelera Pública para Clientes ---
@login_required
def cartelera_view(request):
    """
    Vista de cartelera pública para clientes.
    Muestra todas las funciones disponibles ordenadas por fecha.
    Incluye filtros por género, formato, fecha y búsqueda.
    """
    # Obtener funciones futuras (desde hoy en adelante)
    ahora = timezone.now()
    
    # Filtrar funciones futuras
    funciones = Funcion.objects.filter(
        fecha_hora__gte=ahora,
        sala__activa=True
    ).select_related(
        'pelicula', 'sala'
    )
    
    # Filtro por género
    genero = request.GET.get('genero')
    if genero:
        funciones = funciones.filter(pelicula__genero=genero)
    
    # Filtro por formato
    formato = request.GET.get('formato')
    if formato:
        funciones = funciones.filter(formato_proyeccion=formato)
    
    # Filtro por fecha
    fecha = request.GET.get('fecha')
    if fecha:
        try:
            from datetime import datetime
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
            funciones = funciones.filter(fecha_hora__date=fecha_obj)
        except ValueError:
            pass
    
    # Búsqueda por título
    search = request.GET.get('search')
    if search:
        funciones = funciones.filter(pelicula__titulo__icontains=search)
    
    # Ordenamiento
    orden = request.GET.get('orden', 'fecha')
    if orden == 'precio_asc':
        funciones = funciones.order_by('precio_base', 'fecha_hora')
    elif orden == 'precio_desc':
        funciones = funciones.order_by('-precio_base', 'fecha_hora')
    elif orden == 'titulo':
        funciones = funciones.order_by('pelicula__titulo', 'fecha_hora')
    else:  # 'fecha' por defecto
        funciones = funciones.order_by('fecha_hora')
    
    # Agrupar funciones por película para mejor visualización
    peliculas_con_funciones = {}
    for funcion in funciones:
        pelicula_id = funcion.pelicula.id
        if pelicula_id not in peliculas_con_funciones:
            peliculas_con_funciones[pelicula_id] = {
                'pelicula': funcion.pelicula,
                'funciones': []
            }
        peliculas_con_funciones[pelicula_id]['funciones'].append(funcion)
    
    # Obtener opciones para los filtros
    generos_disponibles = Pelicula.GENERO_CHOICES
    formatos_disponibles = Funcion.FORMATO_CHOICES
    
    # Obtener rango de fechas (próximos 7 días)

    fechas_disponibles = []
    for i in range(7):
        fecha_dia = date.today() + timedelta(days=i)
        fechas_disponibles.append({
            'valor': fecha_dia.strftime('%Y-%m-%d'),
            'display': fecha_dia.strftime('%d/%m/%Y')
        })
    
    context = {
        'peliculas_con_funciones': peliculas_con_funciones.values(),
        'total_funciones': funciones.count(),
        'generos_disponibles': generos_disponibles,
        'formatos_disponibles': formatos_disponibles,
        'fechas_disponibles': fechas_disponibles,
        # Filtros actuales para mantener estado
        'filtro_genero': genero,
        'filtro_formato': formato,
        'filtro_fecha': fecha,
        'filtro_search': search,
        'filtro_orden': orden,
    }
    
    return render(request, 'cine/cartelera.html', context)