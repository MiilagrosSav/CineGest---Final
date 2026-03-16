from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cine.models import Funcion, Pelicula
from cine.models.genero import Genero
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
import logging

# Cuando la cartelera se abre en modo 'intercambio' recibirá ?intercambio_for=<venta_id>
# y mostrará únicamente las funciones candidatas a intercambio para esa venta.
from ventas.services import obtener_funciones_candidatas
from ventas.models import Venta, PoliticaReembolso


logger = logging.getLogger(__name__)


def _promocion_aplica_en_fecha(promocion, fecha_objetivo):
    """Valida vigencia por rango de fechas y por día de semana configurado."""
    if not (promocion.fecha_inicio <= fecha_objetivo <= promocion.fecha_fin):
        return False

    dias_permitidos = promocion.get_dias_list()
    # Convención del modelo: lista vacía = todos los días.
    if not dias_permitidos:
        return True

    return fecha_objetivo.weekday() in dias_permitidos


def _obtener_firma_formato(funcion):
    """Devuelve firma y etiqueta de formato visibles para cartelera (sin ruidos "Standard")."""
    # get_formatos_destacados excluye formatos "Standard" de categorías técnicas
    # y devuelve un rótulo útil para usuario (ej: "2D", "2D + 4DX", "Estándar").
    etiqueta = (funcion.get_formatos_destacados() or 'Sin formato').strip()
    firma = etiqueta.upper().replace(' ', '_')
    return firma, etiqueta

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
    intercambio_debug = None
    if intercambio_for:
        try:
            intercambio_venta = Venta.objects.get(id_venta=int(intercambio_for), id_cliente__usuario=request.user)
            intercambio_debug = {}
            funciones = obtener_funciones_candidatas(intercambio_venta, debug_data=intercambio_debug).select_related('pelicula', 'sala')

            logger.info(
                "[CARTELERA][INTERCAMBIO] user=%s venta=%s candidatas_iniciales=%s",
                getattr(request.user, 'id', None),
                getattr(intercambio_venta, 'id_venta', None),
                funciones.count(),
            )

            # En modo intercambio, si la política no permite promos de vínculo específico,
            # ocultar funciones que tengan una promo específica vigente (por función o película).
            politica_intercambio = PoliticaReembolso.objects.filter(activo=True).first()
            if politica_intercambio and not politica_intercambio.ofrecer_promos_vinculo:
                from promociones.models.vinculo_promocional import VinculoPromocional

                funciones_lista = list(funciones)
                if funciones_lista:
                    funcion_ids = [f.id for f in funciones_lista]
                    pelicula_ids = {f.pelicula_id for f in funciones_lista}

                    vinculos = list(
                        VinculoPromocional.objects.filter(
                            Q(funcion_id__in=funcion_ids) | Q(pelicula_id__in=pelicula_ids),
                            promocion__activo=True,
                            promocion__es_automatica=True,
                            promocion__fecha_baja__isnull=True,
                        ).select_related('promocion')
                    )

                    excluir_ids = set()
                    for f in funciones_lista:
                        fecha_f = f.fecha_hora.date()
                        for v in vinculos:
                            if not _promocion_aplica_en_fecha(v.promocion, fecha_f):
                                continue
                            if v.funcion_id == f.id or v.pelicula_id == f.pelicula_id:
                                excluir_ids.add(f.id)
                                break

                    if excluir_ids:
                        detalles_exclusion = []
                        for f in funciones_lista:
                            if f.id in excluir_ids:
                                detalles_exclusion.append(
                                    f"funcion={f.id} pelicula={f.pelicula_id} fecha={f.fecha_hora}"
                                )

                        logger.info(
                            "[CARTELERA][INTERCAMBIO] venta=%s excluidas_por_vinculo=%s detalle=%s",
                            getattr(intercambio_venta, 'id_venta', None),
                            len(excluir_ids),
                            "; ".join(detalles_exclusion[:20]),
                        )

                        if intercambio_debug is not None:
                            intercambio_debug['descartadas_vinculo_count'] = len(excluir_ids)
                            intercambio_debug['descartadas_vinculo'] = detalles_exclusion[:200]

                        funciones = funciones.exclude(id__in=excluir_ids)

            logger.info(
                "[CARTELERA][INTERCAMBIO] user=%s venta=%s candidatas_finales=%s",
                getattr(request.user, 'id', None),
                getattr(intercambio_venta, 'id_venta', None),
                funciones.count(),
            )
            if intercambio_debug is not None:
                intercambio_debug['cartelera_final_count'] = funciones.count()
                intercambio_debug['cartelera_final_ids'] = list(funciones.values_list('id', flat=True)[:200])
        except Exception:
            logger.exception(
                "[CARTELERA][INTERCAMBIO] error_cargando_modo_intercambio user=%s venta_param=%s",
                getattr(request.user, 'id', None),
                intercambio_for,
            )
            intercambio_venta = None
            intercambio_debug = {
                'error': 'error_cargando_modo_intercambio'
            }
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

    funciones = funciones.prefetch_related('formatos_funcion__formato')
    
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
        funciones = funciones.filter(pelicula__clasificacion__nombre=clasificacion)
    
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

    for funcion in funciones:
        asientos_disponibles = funcion.get_asientos_disponibles_reales()
        funcion.asientos_disponibles = asientos_disponibles
        funcion.esta_agotada = asientos_disponibles <= 0
    
    # Mostrar cartelera separando por película + sala + formato.
    # Si cambia el formato, debe ir en tarjeta separada aunque comparta hora/sala.
    peliculas_con_funciones = {}

    if search:
        # MODO BUSQUEDA: agrupar por pelicula + sala + formato, mostrando todas las fechas.
        for funcion in funciones:
            firma_formato, etiqueta_formato = _obtener_firma_formato(funcion)
            clave = f"{funcion.pelicula.id}_{funcion.sala_id}_{firma_formato}"

            if clave not in peliculas_con_funciones:
                peliculas_con_funciones[clave] = {
                    'pelicula': funcion.pelicula,
                    'sala': funcion.sala,
                    'formato_grupo': etiqueta_formato,
                    'fechas': {},
                }

            fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
            if fecha_str not in peliculas_con_funciones[clave]['fechas']:
                peliculas_con_funciones[clave]['fechas'][fecha_str] = {
                    'fecha': funcion.fecha_hora.date(),
                    'funciones': [],
                }

            peliculas_con_funciones[clave]['fechas'][fecha_str]['funciones'].append(funcion)
    else:
        # MODO NORMAL: agrupar por pelicula + fecha + sala + formato.
        for funcion in funciones:
            fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
            firma_formato, etiqueta_formato = _obtener_firma_formato(funcion)
            clave = f"{funcion.pelicula.id}_{fecha_str}_{funcion.sala_id}_{firma_formato}"

            if clave not in peliculas_con_funciones:
                peliculas_con_funciones[clave] = {
                    'pelicula': funcion.pelicula,
                    'fecha': funcion.fecha_hora.date(),
                    'formato_grupo': etiqueta_formato,
                    'funciones': [],
                    'funciones_data': [],
                    'funciones_por_sala': {
                        funcion.sala_id: {
                            'sala': funcion.sala,
                            'funciones': [],
                        }
                    },
                }

            peliculas_con_funciones[clave]['funciones'].append(funcion)
            peliculas_con_funciones[clave]['funciones_data'].append({
                'funcion': funcion,
                'valoraciones': funcion.get_valoraciones_stats(),
            })
            peliculas_con_funciones[clave]['funciones_por_sala'][funcion.sala_id]['funciones'].append(funcion)
    
    # Calcular valoraciones agregadas por grupo (película + fecha)
    for clave, item in peliculas_con_funciones.items():
        if search:
            # MODO BÚSQUEDA: Calcular valoraciones globales de la película
            # y agregar comentarios de todas las fechas
            from valoraciones.models import Valoracion
            # CORRECCIÓN: Se usa el FK directo `pelicula` (más eficiente) y se eliminó
            # el filtro `funcion__fecha_hora__gte=ahora` que excluía TODAS las valoraciones
            # de funciones pasadas, que son precisamente donde los usuarios puntúan.
            valoraciones_pelicula = Valoracion.objects.filter(
                pelicula=item['pelicula']
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

            # CORRECCIÓN: Usar ratings a nivel PELÍCULA (todas las funciones pasadas y futuras).
            # El cálculo anterior solo sumaba ratings de las funciones en este grupo (futuras),
            # que inevitablemente devolvía 0 porque los usuarios puntúan funciones pasadas.
            item['valoraciones'] = item['pelicula'].get_valoraciones_stats()

            # Obtener comentarios de TODAS las funciones de la película (pasadas y futuras)
            from valoraciones.models import Valoracion
            comentarios_qs = Valoracion.objects.filter(
                pelicula=item['pelicula']
            ).select_related('cliente__usuario').order_by('-fecha_creacion')

            comentarios = []
            for val in comentarios_qs[:5]:
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
    
    # Clasificaciones disponibles (desde el modelo Clasificacion)
    from cine.models.clasificacion import Clasificacion
    clasificaciones_disponibles = list(
        Clasificacion.objects.filter(activo=True)
        .order_by('edad_minima', 'nombre')
        .values_list('nombre', 'nombre')
    )
    
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
    # SECCIÓN: Promociones específicas por película/función
    # ========================================================================
    from promociones.models.promocion import Promocion as _Promocion
    from promociones.models.vinculo_promocional import VinculoPromocional as _Vinculo
    from django.db.models import Q as _Q

    # Fecha de referencia para las consultas de promociones:
    # Si el usuario seleccionó un día en el carrusel, usamos ese día.
    # Así una promo que empieza mañana aparece al seleccionar mañana.
    try:
        from datetime import datetime as _dt
        fecha_consulta = _dt.strptime(dia_seleccionado, '%Y-%m-%d').date() if dia_seleccionado else hoy
    except (ValueError, TypeError):
        fecha_consulta = hoy
    # Nunca mostrar promos de fechas pasadas
    if fecha_consulta < hoy:
        fecha_consulta = hoy

    # Recolectar todos los IDs de películas y funciones actualmente en cartelera
    _all_pelicula_ids = set()
    _all_funcion_ids = set()
    for _item in peliculas_con_funciones.values():
        _all_pelicula_ids.add(_item['pelicula'].id)
        if 'funciones' in _item:
            for _f in _item['funciones']:
                _all_funcion_ids.add(_f.id)
        elif 'fechas' in _item:
            for _fd in _item['fechas'].values():
                for _f in _fd['funciones']:
                    _all_funcion_ids.add(_f.id)

    # Batch-fetch: 1 query para obtener todos los vínculos activos relevantes.
    # Usamos la fecha máxima de las funciones en cartelera para el corte de inicio,
    # y hoy para el corte de fin (promo no puede haber terminado antes de hoy).
    # Esto permite mostrar promos cuya vigencia empieza en fecha futura si la función
    # también es futura (ej: promo 11-12 para función del 12).
    _vinculos = list(
        _Vinculo.objects.filter(
            _Q(funcion_id__in=_all_funcion_ids) | _Q(pelicula_id__in=_all_pelicula_ids)
        ).select_related('promocion').filter(
            promocion__activo=True,
            promocion__es_automatica=True,
            promocion__fecha_fin__gte=fecha_consulta,  # promo vigente en la fecha seleccionada
            promocion__fecha_baja__isnull=True,
        )
    )
    _promos_por_funcion = {}
    _promos_por_pelicula = {}
    for _v in _vinculos:
        if _v.funcion_id:
            _promos_por_funcion.setdefault(_v.funcion_id, []).append(_v.promocion)
        if _v.pelicula_id:
            _promos_por_pelicula.setdefault(_v.pelicula_id, []).append(_v.promocion)

    # Adjuntar 'promociones_especificas' a cada grupo y escribir log de detección
    for _clave, _item in peliculas_con_funciones.items():
        _pelicula = _item['pelicula']
        _especificas = []
        _seen = set()

        # Funciones del grupo (search mode usa 'fechas', normal usa 'funciones')
        _funciones_grupo = list(_item.get('funciones', []))
        if not _funciones_grupo and 'fechas' in _item:
            for _fd in _item['fechas'].values():
                _funciones_grupo += _fd['funciones']

        # Promos vinculadas a funciones específicas del grupo
        # Solo incluir si la promo es válida en la fecha específica de esa función
        for _f in _funciones_grupo:
            _fecha_f = _f.fecha_hora.date()
            for _p in _promos_por_funcion.get(_f.id, []):
                if _p.pk not in _seen and _promocion_aplica_en_fecha(_p, _fecha_f):
                    _seen.add(_p.pk)
                    _hora = _f.fecha_hora.strftime('%H:%M')
                    _especificas.append({
                        'promo': _p,
                        'origen': 'funcion',
                        'etiqueta': f'¡Promoción exclusiva para esta función! ({_hora})',
                    })

        # Promos vinculadas a la película
        # Solo incluir si la promo es válida en alguna de las fechas de las funciones del grupo
        for _p in _promos_por_pelicula.get(_pelicula.id, []):
            if _p.pk not in _seen:
                _valida_en_alguna = any(
                    _promocion_aplica_en_fecha(_p, _f.fecha_hora.date())
                    for _f in _funciones_grupo
                )
                if _valida_en_alguna:
                    _seen.add(_p.pk)
                    _especificas.append({
                        'promo': _p,
                        'origen': 'pelicula',
                        'etiqueta': f'Descuento especial para {_pelicula.titulo}',
                    })

        _item['promociones_especificas'] = _especificas

        # Debug: imprimir en consola las promociones detectadas por película
        _detalle = ', '.join(
            f"{e['promo'].codigo}({e['origen']})" for e in _especificas
        ) if _especificas else 'ninguna'
        print(f"[PROMO][CARTELERA] '{_pelicula.titulo}': {len(_especificas)} específica(s) detec. → {_detalle}")

    # ========================================================================
    # SECCIÓN DESTACADOS: Promociones activas y películas más vistas
    # ========================================================================
    from promociones.models import Promocion
    
    # ✅ FILTRADO: Solo promociones ACTIVAS, VIGENTES EN LA FECHA SELECCIONADA y SIN vínculos
    # Condiciones:
    # 1. activo=True (campo SoftDeleteMixin)
    # 2. fecha_inicio <= fecha_consulta (ya comenzó en el día visualizado)
    # 3. fecha_fin >= fecha_consulta (aún no terminó en el día visualizado)
    # 4. fecha_baja IS NULL (no eliminada)
    # 5. es_automatica=True (no mostrar promociones tipo cupón)
    # 6. Sin vínculos específicos a películas/funciones
    promociones_activas_qs = Promocion.objects.filter(
        activo=True,
        es_automatica=True,  # ✅ Solo promociones automáticas (NO cupones)
        fecha_inicio__lte=fecha_consulta,
        fecha_fin__gte=fecha_consulta,
        fecha_baja__isnull=True  # Agregado: solo promociones NO eliminadas
    ).exclude(
        # Excluir promociones que tienen vínculos específicos
        vinculos__isnull=False
    ).order_by('-es_automatica', 'nombre')

    promociones_activas = [
        promo for promo in promociones_activas_qs
        if _promocion_aplica_en_fecha(promo, fecha_consulta)
    ][:3]
    
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
        'intercambio_debug': intercambio_debug,
        # 🌟 DESTACADOS
        'promociones_activas': promociones_procesadas,
        'peliculas_destacadas': peliculas_destacadas_con_funcion,
        'fecha_consulta': fecha_consulta,
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
    hoy = timezone.localtime(ahora).date()

    # Auto-transición: PREVENTA → ACTIVA cuando llega fecha_activacion o el día de la función
    from django.db.models import Q
    Funcion.objects.filter(
        estado='PREVENTA',
        fecha_hora__gte=ahora,
    ).filter(
        Q(fecha_activacion__lte=ahora) |
        Q(fecha_activacion__isnull=True, fecha_hora__date__lte=hoy)
    ).update(estado='ACTIVA')

    funciones = Funcion.objects.filter(
        fecha_hora__gte=ahora,
        fecha_hora__date__gt=hoy,  # Solo fechas FUTURAS, no hoy
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
        funciones = funciones.filter(pelicula__clasificacion__nombre=clasificacion)
    
    search = request.GET.get('search')
    if search:
        funciones = funciones.filter(pelicula__titulo__icontains=search)
    
    # Ordenamiento
    funciones = funciones.order_by('fecha_hora')
    
    # Agrupar funciones por película + fecha (un cartel por día por película)
    peliculas_con_funciones = {}
    
    for funcion in funciones:
        pelicula_id = funcion.pelicula.id
        fecha_str = funcion.fecha_hora.strftime('%Y-%m-%d')
        clave = f"{pelicula_id}_{fecha_str}"
        
        if clave not in peliculas_con_funciones:
            peliculas_con_funciones[clave] = {
                'pelicula': funcion.pelicula,
                'fecha': funcion.fecha_hora.date(),
                'funciones': [],
            }
        
        peliculas_con_funciones[clave]['funciones'].append(funcion)
    
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
    
    from cine.models.clasificacion import Clasificacion
    clasificaciones_disponibles = list(
        Clasificacion.objects.filter(activo=True)
        .order_by('edad_minima', 'nombre')
        .values_list('nombre', 'nombre')
    )
    
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