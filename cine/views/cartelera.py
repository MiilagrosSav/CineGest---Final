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
    
    # Filtro por día seleccionado (desde la lista de días de la semana)
    dia_seleccionado = request.GET.get('dia')
    if dia_seleccionado:
        try:
            from datetime import datetime
            fecha_obj = datetime.strptime(dia_seleccionado, '%Y-%m-%d').date()
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
    
    # Agrupar funciones por película Y fecha para mejor visualización
    peliculas_con_funciones = {}
    for funcion in funciones:
        # Crear clave única: pelicula_id + fecha
        fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
        clave = f"{funcion.pelicula.id}_{fecha_str}"
        
        if clave not in peliculas_con_funciones:
            peliculas_con_funciones[clave] = {
                'pelicula': funcion.pelicula,
                'fecha': funcion.fecha_hora.date(),
                'funciones': []
            }
        peliculas_con_funciones[clave]['funciones'].append(funcion)
    
    # Obtener opciones para los filtros
    generos_disponibles = Pelicula.GENERO_CHOICES
    formatos_disponibles = Funcion.FORMATO_CHOICES
    
    # Obtener lista de días de la semana (próximos 14 días)
    dias_semana = []
    hoy = date.today()
    
    # Nombres de los días en español
    dias_nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    for i in range(14):
        fecha_dia = hoy + timedelta(days=i)
        dia_semana_num = fecha_dia.weekday()  # 0=Lunes, 6=Domingo
        
        dias_semana.append({
            'fecha': fecha_dia.strftime('%Y-%m-%d'),
            'dia_nombre': dias_nombres[dia_semana_num],
            'dia_numero': fecha_dia.day,
            'mes_nombre': meses_nombres[fecha_dia.month - 1],
            'es_hoy': i == 0
        })
    
    context = {
        'peliculas_con_funciones': peliculas_con_funciones.values(),
        'total_funciones': funciones.count(),
        'generos_disponibles': generos_disponibles,
        'formatos_disponibles': formatos_disponibles,
        'dias_semana': dias_semana,
        # Filtros actuales para mantener estado
        'filtro_genero': genero,
        'filtro_formato': formato,
        'dia_seleccionado': dia_seleccionado,
        'filtro_search': search,
        'filtro_orden': orden,
    }
    
    return render(request, 'cine/cartelera.html', context)