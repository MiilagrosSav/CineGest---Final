from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cine.models import Funcion, Pelicula
from cine.models.genero import Genero
from django.utils import timezone
from datetime import timedelta

# Cuando la cartelera se abre en modo 'intercambio' recibirá ?intercambio_for=<venta_id>
# y mostrará únicamente las funciones candidatas a intercambio para esa venta.
from ventas.services import obtener_funciones_candidatas
from ventas.models import Venta

# --- Vista de Cartelera Pública para Clientes ---
@login_required
def cartelera_view(request):
    """
    Vista de cartelera pública para clientes.
    Muestra todas las funciones disponibles ordenadas por fecha.
    Incluye filtros por género, formato, fecha y búsqueda.
    """
    # Bloquear acceso a empleados
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados no tienen acceso a la cartelera. Usa el módulo de ventas presenciales.')
        return redirect('accounts:dashboard')
    
    # Limpiar promociones de sesión si el usuario llega a cartelera de forma normal
    # (no desde activación de link). Esto evita que promociones antiguas se queden pegadas.
    if 'promo_activa_id' in request.session or 'promo_token' in request.session:
        # Verificar si viene de activación reciente (último minuto)
        promo_activada_recientemente = request.session.get('promo_activada_timestamp')
        if promo_activada_recientemente:
            import datetime
            try:
                timestamp = datetime.datetime.fromisoformat(promo_activada_recientemente)
                ahora = timezone.now()
                if (ahora - timestamp).total_seconds() > 60:  # Más de 1 minuto
                    # Limpiar promoción antigua
                    request.session.pop('promo_activa_id', None)
                    request.session.pop('promo_token', None)
                    request.session.pop('promo_activada_timestamp', None)
                    request.session.modified = True
            except:
                # Error parseando timestamp, limpiar por seguridad
                request.session.pop('promo_activa_id', None)
                request.session.pop('promo_token', None)
                request.session.pop('promo_activada_timestamp', None)
                request.session.modified = True
    
    # Obtener funciones futuras (desde hoy en adelante)
    ahora = timezone.now()

    # Soporte para modo intercambio: si se pasa intercambio_for, calculamos candidatas solamente
    intercambio_for = request.GET.get('intercambio_for')
    intercambio_venta = None
    if intercambio_for:
        try:
            intercambio_venta = Venta.objects.get(id_venta=int(intercambio_for), id_cliente__usuario=request.user)
            funciones = obtener_funciones_candidatas(intercambio_venta).select_related('pelicula', 'sala')
        except Exception:
            intercambio_venta = None
            funciones = Funcion.objects.filter(
                fecha_hora__gte=ahora,
                sala__activo=True
            ).exclude(estado='INACTIVA').select_related('pelicula', 'sala')
    else:
        # Filtrar funciones futuras y no inactivas
        funciones = Funcion.objects.filter(
            fecha_hora__gte=ahora,
            sala__activo=True  # ✅ CORREGIDO: campo es 'activo', no 'activa'
        ).exclude(estado='INACTIVA').select_related(
            'pelicula', 'sala'
        )
    
    # Filtro por género
    genero = request.GET.get('genero')
    if genero:
        # `Pelicula` ahora tiene ManyToMany `generos`. Filtrar por el id del género.
        try:
            genero_id = int(genero)
            funciones = funciones.filter(pelicula__generos__id=genero_id)
        except (ValueError, TypeError):
            # Si no es un id, intentar filtrar por nombre (case-insensitive)
            funciones = funciones.filter(pelicula__generos__nombre__iexact=genero)
    
    # Filtro por formato (corregido: ahora filtra por la relación many-to-many)
    formato = request.GET.get('formato')
    if formato:
        funciones = funciones.filter(formatos_funcion__formato__nombre=formato).distinct()
    
    # Filtro por idioma (nuevo: permite filtrar funciones por idioma)
    idioma = request.GET.get('idioma')
    if idioma:
        funciones = funciones.filter(idioma=idioma)
    
    # Filtro por clasificación de edad (nuevo: permite filtrar por clasificación)
    clasificacion = request.GET.get('clasificacion')
    if clasificacion:
        funciones = funciones.filter(pelicula__clasificacion=clasificacion)
    
    # Búsqueda por título (DEBE IR ANTES del filtro de día)
    search = request.GET.get('search')
    if search:
        funciones = funciones.filter(pelicula__titulo__icontains=search)
        # NOTA: Cuando hay búsqueda, se mostrarán TODAS las fechas futuras (sin filtro de día)
    
    # Filtro por día seleccionado (desde la lista de días de la semana o calendario)
    dia_seleccionado = request.GET.get('dia')
    
    # MEJORA: Si hay búsqueda, NO filtrar por día para mostrar todas las fechas
    if search:
        # Cuando se busca una película, mostrar TODAS las fechas futuras donde aparece
        # No aplicar filtro de día
        pass
    elif dia_seleccionado:
        # Solo filtrar por día si NO hay búsqueda activa
        try:
            from datetime import datetime
            fecha_obj = datetime.strptime(dia_seleccionado, '%Y-%m-%d').date()
            # Asegurar que no se pueda seleccionar fechas pasadas
            if fecha_obj >= date.today():
                funciones = funciones.filter(fecha_hora__date=fecha_obj)
            else:
                # Si intenta seleccionar fecha pasada, redirigir a hoy
                dia_seleccionado = date.today().strftime('%Y-%m-%d')
                funciones = funciones.filter(fecha_hora__date=date.today())
        except ValueError:
            # Si hay error en la fecha, usar hoy
            dia_seleccionado = date.today().strftime('%Y-%m-%d')
            funciones = funciones.filter(fecha_hora__date=date.today())
    else:
        # Si no hay filtro de día seleccionado ni búsqueda, usar HOY por defecto
        dia_seleccionado = date.today().strftime('%Y-%m-%d')
        funciones = funciones.filter(fecha_hora__date=date.today())
    
    # Ordenamiento por fecha (único criterio relevante para cartelera de cines)
    funciones = funciones.order_by('fecha_hora')
    
    # Agrupar funciones por película Y fecha para mejor visualización
    # MEJORA: Si hay búsqueda, agrupar SOLO por película (mostrar todas las fechas)
    peliculas_con_funciones = {}
    
    if search:
        # MODO BÚSQUEDA: Agrupar por película, mostrar todas las fechas
        for funcion in funciones:
            pelicula_id = funcion.pelicula.id
            
            if pelicula_id not in peliculas_con_funciones:
                peliculas_con_funciones[pelicula_id] = {
                    'pelicula': funcion.pelicula,
                    'fechas': {},  # Diccionario de fechas con sus funciones
                }
            
            # Agrupar funciones por fecha dentro de cada película
            fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
            if fecha_str not in peliculas_con_funciones[pelicula_id]['fechas']:
                peliculas_con_funciones[pelicula_id]['fechas'][fecha_str] = {
                    'fecha': funcion.fecha_hora.date(),
                    'funciones': [],
                }
            
            peliculas_con_funciones[pelicula_id]['fechas'][fecha_str]['funciones'].append(funcion)
    else:
        # MODO NORMAL: Agrupar por película + fecha (como antes)
        for funcion in funciones:
            # Crear clave única: pelicula_id + fecha
            fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
            clave = f"{funcion.pelicula.id}_{fecha_str}"
            
            if clave not in peliculas_con_funciones:
                peliculas_con_funciones[clave] = {
                    'pelicula': funcion.pelicula,
                    'fecha': funcion.fecha_hora.date(),
                    'funciones': [],
                    'funciones_data': [],  # Lista con datos de valoraciones por función
                }
            
            # Agregar función y sus estadísticas
            peliculas_con_funciones[clave]['funciones'].append(funcion)
            peliculas_con_funciones[clave]['funciones_data'].append({
                'funcion': funcion,
                'valoraciones': funcion.get_valoraciones_stats(),
            })
    
    # Calcular valoraciones agregadas por grupo (película + fecha)
    for clave, item in peliculas_con_funciones.items():
        if search:
            # MODO BÚSQUEDA: Calcular valoraciones globales de la película
            # y agregar comentarios de todas las fechas
            from valoraciones.models import Valoracion
            valoraciones_pelicula = Valoracion.objects.filter(
                funcion__pelicula=item['pelicula'],
                funcion__fecha_hora__gte=ahora
            ).select_related('cliente__usuario')
            
            total_valoraciones = valoraciones_pelicula.count()
            if total_valoraciones > 0:
                from django.db.models import Avg
                promedio_general = valoraciones_pelicula.aggregate(Avg('puntuacion'))['puntuacion__avg'] or 0
                estrellas_llenas = int(promedio_general) if promedio_general > 0 else 0
                estrellas_vacias = 5 - estrellas_llenas
                
                item['valoraciones'] = {
                    'promedio': round(promedio_general, 1),
                    'total': total_valoraciones,
                    'estrellas_llenas': estrellas_llenas,
                    'estrellas_vacias': estrellas_vacias,
                }
            else:
                item['valoraciones'] = {
                    'promedio': 0,
                    'total': 0,
                    'estrellas_llenas': 0,
                    'estrellas_vacias': 5,
                }
            
            # Comentarios de todas las fechas
            comentarios = []
            for val in valoraciones_pelicula.order_by('-fecha_creacion')[:3]:
                if val.comentario and val.comentario.strip():
                    comentarios.append({
                        'cliente': val.cliente.usuario.get_full_name() or val.cliente.usuario.username,
                        'puntuacion': val.puntuacion,
                        'comentario': val.comentario,
                        'fecha': val.fecha_creacion.strftime('%d/%m/%Y'),
                    })
            item['comentarios'] = comentarios
        else:
            # MODO NORMAL: Calcular como antes (por película + fecha)
            funciones_data = []
            for funcion in item['funciones']:
                funciones_data.append({
                    'funcion': funcion,
                    'valoraciones': funcion.get_valoraciones_stats(),
                })
            
            item['funciones_data'] = funciones_data
            
            # Sumar todas las valoraciones de todas las funciones de este grupo
            total_valoraciones = sum(f['valoraciones']['total'] for f in funciones_data)
            
            if total_valoraciones > 0:
                # Calcular promedio ponderado basado en cantidad de valoraciones por función
                suma_ponderada = sum(
                    f['valoraciones']['promedio'] * f['valoraciones']['total'] 
                    for f in funciones_data
                )
                promedio_general = suma_ponderada / total_valoraciones if total_valoraciones > 0 else 0
                
                # Usar int() para truncar, no round() (evita 6 estrellas)
                estrellas_llenas = int(promedio_general) if promedio_general > 0 else 0
                estrellas_vacias = 5 - estrellas_llenas
                
                item['valoraciones'] = {
                    'promedio': round(promedio_general, 1),
                    'total': total_valoraciones,
                    'estrellas_llenas': estrellas_llenas,
                    'estrellas_vacias': estrellas_vacias,
                }
            else:
                item['valoraciones'] = {
                    'promedio': 0,
                    'total': 0,
                    'estrellas_llenas': 0,
                    'estrellas_vacias': 5,
                }
            
            # Obtener comentarios de valoraciones de todas las funciones de este grupo
            from valoraciones.models import Valoracion
            comentarios = []
            for func_data in funciones_data:
                valoraciones_funcion = Valoracion.objects.filter(
                    funcion=func_data['funcion']
                ).select_related('cliente__usuario').order_by('-fecha_creacion')
                
                for val in valoraciones_funcion:
                    if val.comentario and val.comentario.strip():
                        comentarios.append({
                            'cliente': val.cliente.usuario.get_full_name() or val.cliente.usuario.username,
                            'puntuacion': val.puntuacion,
                            'comentario': val.comentario,
                            'fecha': val.fecha_creacion.strftime('%d/%m/%Y'),
                        })
            
            item['comentarios'] = comentarios
    
    # Obtener opciones para los filtros desde la base de datos
    # Géneros disponibles (desde tabla Genero)
    generos_disponibles = list(Genero.objects.values_list('id', 'nombre'))
    
    # Formatos disponibles (desde tabla Formato, solo los que tienen funciones activas)
    from cine.models.formato import Formato
    formatos_disponibles = list(
        Formato.objects.filter(
            funciones_formato__funcion__fecha_hora__gte=ahora
        ).distinct().values_list('nombre', 'nombre')
    )
    
    # Idiomas disponibles (desde las funciones activas)
    idiomas_disponibles = Funcion.IDIOMA_CHOICES
    
    # Clasificaciones disponibles (desde Pelicula model)
    from cine.models.pelicula import Pelicula
    clasificaciones_disponibles = Pelicula.CLASIFICACION_CHOICES
    
    # Obtener lista de días de la semana (próximos 14 días desde el día seleccionado o hoy)
    dias_semana = []
    
    # Determinar el día base para el carrusel (usar timezone para consistencia)
    hoy = timezone.now().date()
    
    if dia_seleccionado:
        try:
            from datetime import datetime
            fecha_seleccionada = datetime.strptime(dia_seleccionado, '%Y-%m-%d').date()
            # PROTECCIÓN: No permitir navegar a fechas anteriores a hoy
            if fecha_seleccionada < hoy:
                fecha_base = hoy
            else:
                # Si la fecha seleccionada está dentro de los primeros 14 días desde hoy,
                # comenzar el carrusel desde hoy para que siempre sea visible
                if fecha_seleccionada < hoy + timedelta(days=14):
                    fecha_base = hoy
                else:
                    # Si está más adelante, centrar el carrusel alrededor de la fecha seleccionada
                    fecha_base = fecha_seleccionada - timedelta(days=6)
        except ValueError:
            fecha_base = hoy
    else:
        fecha_base = hoy
    
    # Nombres de los días en español
    dias_nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    for i in range(14):
        fecha_dia = fecha_base + timedelta(days=i)
        dia_semana_num = fecha_dia.weekday()  # 0=Lunes, 6=Domingo
        
        dias_semana.append({
            'fecha': fecha_dia.strftime('%Y-%m-%d'),
            'dia_nombre': dias_nombres[dia_semana_num],
            'dia_numero': fecha_dia.day,
            'mes_nombre': meses_nombres[fecha_dia.month - 1],
            'es_hoy': fecha_dia == hoy
        })
    
    # Verificar si podemos navegar hacia atrás sin ir antes de hoy
    # Solo deshabilitar el botón si retroceder 7 días nos llevaría a fecha anterior a hoy
    fecha_retroceso = fecha_base - timedelta(days=7)
    puede_retroceder = fecha_retroceso >= hoy
    
    # Sólo exponer intercambio_for si validamos la venta para este usuario
    contexto_intercambio_for = intercambio_venta.id_venta if intercambio_venta else None
    
    # ========================================================================
    # SECCIÓN DESTACADOS: Promociones activas y películas más vistas
    # ========================================================================
    from promociones.models import Promocion, VinculoPromocional
    from django.db.models import Count, Q
    
    # ✅ FILTRADO ESTRICTO: Solo promociones ACTIVAS, VIGENTES HOY y SIN vínculos
    # Condiciones:
    # 1. activo=True (campo SoftDeleteMixin)
    # 2. fecha_inicio <= HOY (ya comenzó)
    # 3. fecha_fin >= HOY (aún no terminó)
    # 4. fecha_baja IS NULL (no eliminada)
    # 5. es_automatica=True (no mostrar promociones tipo cupón)
    # 6. Sin vínculos específicos a películas/funciones
    promociones_activas = Promocion.objects.filter(
        activo=True,
        es_automatica=True,  # ✅ Solo promociones automáticas (NO cupones)
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy,
        fecha_baja__isnull=True  # Agregado: solo promociones NO eliminadas
    ).exclude(
        # Excluir promociones que tienen vínculos específicos
        vinculos__isnull=False
    ).order_by('-es_automatica', 'nombre')[:3]  # Máximo 3 promociones
    
    # Procesar información adicional para cada promoción
    promociones_procesadas = []
    dias_nombres_completos = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    for promo in promociones_activas:
        # Parsear días de la semana
        dias_aplicables = []
        todos_los_dias = False
        
        if promo.dias_semana:
            try:
                indices = [int(d.strip()) for d in promo.dias_semana.split(',') if d.strip()]
                # Si hay 7 días o todos los índices 0-6, es "todos los días"
                if len(indices) >= 7 or set(indices) == {0, 1, 2, 3, 4, 5, 6}:
                    todos_los_dias = True
                else:
                    dias_aplicables = [dias_nombres_completos[i] for i in indices if 0 <= i <= 6]
            except (ValueError, IndexError):
                todos_los_dias = True  # Si hay error, asumir todos los días
        else:
            # Sin días especificados = todos los días
            todos_los_dias = True
        
        promociones_procesadas.append({
            'promo': promo,
            'dias_texto': ', '.join(dias_aplicables) if dias_aplicables else 'Todos los días',
            'tiene_dias_especificos': bool(dias_aplicables) and not todos_los_dias,
            'todos_los_dias': todos_los_dias,
        })
    
    # Obtener las 3 películas más vistas (basado en entradas vendidas)
    peliculas_destacadas = Pelicula.objects.filter(
        funciones__fecha_hora__gte=ahora,
        funciones__entradas__estado__in=['VENDIDA', 'ENTREGADA', 'USADA']
    ).annotate(
        total_entradas=Count('funciones__entradas')
    ).order_by('-total_entradas').distinct()[:3]
    
    # Para cada película destacada, obtener su próxima función disponible
    peliculas_destacadas_con_funcion = []
    for pelicula in peliculas_destacadas:
        proxima_funcion = Funcion.objects.filter(
            pelicula=pelicula,
            fecha_hora__gte=ahora,
            sala__activo=True
        ).exclude(estado='INACTIVA').order_by('fecha_hora').first()
        
        if proxima_funcion:
            peliculas_destacadas_con_funcion.append({
                'pelicula': pelicula,
                'funcion': proxima_funcion,
                'total_entradas': pelicula.total_entradas,
            })

    context = {
        'peliculas_con_funciones': peliculas_con_funciones.values(),
        'total_funciones': funciones.count(),
        'generos_disponibles': generos_disponibles,
        'formatos_disponibles': formatos_disponibles,
        'idiomas_disponibles': idiomas_disponibles,
        'clasificaciones_disponibles': clasificaciones_disponibles,
        'dias_semana': dias_semana,
        # Filtros actuales para mantener estado
        'filtro_genero': genero,
        'filtro_formato': formato,
        'filtro_idioma': idioma,
        'filtro_clasificacion': clasificacion,
        'dia_seleccionado': dia_seleccionado,
        'filtro_search': search,
        # Control de navegación temporal
        'puede_retroceder': puede_retroceder,
        'fecha_base': fecha_base.strftime('%Y-%m-%d'),
        # Soporte para modo intercambio: ?intercambio_for=<venta_id>
        'intercambio_for': contexto_intercambio_for,
        'intercambio_venta': intercambio_venta,
        # 🌟 DESTACADOS
        'promociones_activas': promociones_procesadas,
        'peliculas_destacadas': peliculas_destacadas_con_funcion,
    }
    
    return render(request, 'cine/cartelera.html', context)


# --- Vista de Cartelera de PREVENTA ---
@login_required
def preventa_view(request):
    """
    Vista de cartelera especializada para funciones en PREVENTA.
    Muestra solo funciones con estado=PREVENTA para incentivar compra anticipada.
    """
    # Bloquear acceso a empleados
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados no tienen acceso a la cartelera. Usa el módulo de ventas presenciales.')
        return redirect('accounts:dashboard')
    
    # Obtener funciones futuras EN PREVENTA
    ahora = timezone.now()
    funciones = Funcion.objects.filter(
        fecha_hora__gte=ahora,
        sala__activo=True,
        estado='PREVENTA'  # FILTRO CLAVE: Solo PREVENTA
    ).select_related('pelicula', 'sala')
    
    # Aplicar los mismos filtros que cartelera normal
    genero = request.GET.get('genero')
    if genero:
        try:
            genero_id = int(genero)
            funciones = funciones.filter(pelicula__generos__id=genero_id)
        except (ValueError, TypeError):
            funciones = funciones.filter(pelicula__generos__nombre__iexact=genero)
    
    formato = request.GET.get('formato')
    if formato:
        funciones = funciones.filter(formatos_funcion__formato__nombre=formato).distinct()
    
    idioma = request.GET.get('idioma')
    if idioma:
        funciones = funciones.filter(idioma=idioma)
    
    clasificacion = request.GET.get('clasificacion')
    if clasificacion:
        funciones = funciones.filter(pelicula__clasificacion=clasificacion)
    
    search = request.GET.get('search')
    if search:
        funciones = funciones.filter(pelicula__titulo__icontains=search)
    
    # Ordenamiento
    funciones = funciones.order_by('fecha_hora')
    
    # Agrupar funciones por película (mostrar TODAS las fechas de preventa)
    peliculas_con_funciones = {}
    
    for funcion in funciones:
        pelicula_id = funcion.pelicula.id
        
        if pelicula_id not in peliculas_con_funciones:
            peliculas_con_funciones[pelicula_id] = {
                'pelicula': funcion.pelicula,
                'fechas': {},
            }
        
        fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
        if fecha_str not in peliculas_con_funciones[pelicula_id]['fechas']:
            peliculas_con_funciones[pelicula_id]['fechas'][fecha_str] = {
                'fecha': funcion.fecha_hora.date(),
                'funciones': [],
            }
        
        peliculas_con_funciones[pelicula_id]['fechas'][fecha_str]['funciones'].append(funcion)
    
    # Calcular valoraciones por película
    for item in peliculas_con_funciones.values():
        from valoraciones.models import Valoracion
        valoraciones_pelicula = Valoracion.objects.filter(
            funcion__pelicula=item['pelicula'],
            funcion__fecha_hora__gte=ahora
        ).select_related('cliente__usuario')
        
        total_valoraciones = valoraciones_pelicula.count()
        if total_valoraciones > 0:
            from django.db.models import Avg
            promedio_general = valoraciones_pelicula.aggregate(Avg('puntuacion'))['puntuacion__avg'] or 0
            estrellas_llenas = int(promedio_general) if promedio_general > 0 else 0
            
            item['valoraciones'] = {
                'promedio': round(promedio_general, 1),
                'total': total_valoraciones,
                'estrellas_llenas': estrellas_llenas,
                'estrellas_vacias': 5 - estrellas_llenas,
            }
        else:
            item['valoraciones'] = {
                'promedio': 0,
                'total': 0,
                'estrellas_llenas': 0,
                'estrellas_vacias': 5,
            }
        
        # Comentarios
        comentarios = []
        for val in valoraciones_pelicula.order_by('-fecha_creacion')[:3]:
            if val.comentario and val.comentario.strip():
                comentarios.append({
                    'cliente': val.cliente.usuario.get_full_name() or val.cliente.usuario.username,
                    'puntuacion': val.puntuacion,
                    'comentario': val.comentario,
                    'fecha': val.fecha_creacion.strftime('%d/%m/%Y'),
                })
        item['comentarios'] = comentarios
    
    # Obtener filtros dinámicos
    generos_disponibles = list(Genero.objects.values_list('id', 'nombre'))
    
    from cine.models.formato import Formato
    formatos_disponibles = list(
        Formato.objects.filter(
            funciones_formato__funcion__estado='PREVENTA',
            funciones_formato__funcion__fecha_hora__gte=ahora
        ).distinct().values_list('nombre', 'nombre')
    )
    
    idiomas_disponibles = Funcion.IDIOMA_CHOICES
    
    from cine.models.pelicula import Pelicula
    clasificaciones_disponibles = Pelicula.CLASIFICACION_CHOICES
    
    context = {
        'peliculas_con_funciones': peliculas_con_funciones.values(),
        'total_funciones': funciones.count(),
        'generos_disponibles': generos_disponibles,
        'formatos_disponibles': formatos_disponibles,
        'idiomas_disponibles': idiomas_disponibles,
        'clasificaciones_disponibles': clasificaciones_disponibles,
        'filtro_genero': genero,
        'filtro_formato': formato,
        'filtro_idioma': idioma,
        'filtro_clasificacion': clasificacion,
        'filtro_search': search,
        'es_preventa': True,  # Flag para template
    }
    
    return render(request, 'cine/cartelera_preventa.html', context)