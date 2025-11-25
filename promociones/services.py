from decimal import Decimal
from django.utils import timezone
from django.db import models
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def calcular_precio_final(funcion, cantidad_entradas, promocion_especifica=None):
    """
    Calcula el precio final.
    Prioridad:
    1. Si llega 'promocion_especifica' (Cupón de sesión), usa esa.
    2. Si no, busca automáticas en FuncionPromocion.
    
    Retorna tupla: (total_decimal, promocion_aplicada, detalle_dict)
    """
    from promociones.models.funcionPromocion import FuncionPromocion
    from promociones.models.politicaPromocion import PoliticaPromocion # Si la usas para validar
    from decimal import Decimal, ROUND_HALF_UP
    from django.db import models
    from django.utils import timezone
    
    # 1. Preparar datos base
    precio_base = Decimal(funcion.precio_base)
    cantidad = int(cantidad_entradas)
    
    # El total sin descuento
    total_original = (precio_base * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Estructura de respuesta por defecto
    detalle = {
        'precio_unitario_base': precio_base,
        'total_original': total_original,
        'ahorro': Decimal('0.00'),
        'tipo_aplicado': None,
        'descripcion': 'Precio regular',
        'aviso': None
    }

    promo_a_usar = None

    # ---------------------------------------------------------
    # PASO 2: ELEGIR LA PROMOCIÓN
    # ---------------------------------------------------------
    
    # A) Si viene del Cupón (Sesión), esa GANA.
    if promocion_especifica:
        promo_a_usar = promocion_especifica
    
    # B) Si no hay cupón, buscamos Automáticas
    else:
        candidatos_qs = FuncionPromocion.objects.filter(
            models.Q(funcion=funcion) | models.Q(pelicula=funcion.pelicula),
            promocion__es_automatica=True
        ).select_related('promocion')
        
        # Aquí usamos tu validador existente para filtrar
        # (Asumo que es_promocion_valida_para_funcion está en este mismo archivo o importada)
        from .services import es_promocion_valida_para_funcion 
        
        for fp in candidatos_qs:
            if es_promocion_valida_para_funcion(fp.promocion, funcion):
                promo_a_usar = fp.promocion
                break # Nos quedamos con la primera válida (o aplicar lógica de mejor precio)

    # ---------------------------------------------------------
    # PASO 3: CALCULAR MATEMÁTICA
    # ---------------------------------------------------------
    total_final = total_original # Empezamos asumiendo precio full

    if promo_a_usar:
        # Normalizamos a mayúsculas y sin espacios para evitar errores '2x1' vs '2X1'
        tipo = str(promo_a_usar.tipo_descuento).upper().strip()
        
        if tipo == '2X1':
            # Fórmula: Pares pagan 1, Impares pagan (Pares + 1)
            # Ej: 3 entradas -> (3 // 2) + (3 % 2) = 1 + 1 = 2 a pagar.
            entradas_a_pagar = (cantidad // 2) + (cantidad % 2)
            total_final = precio_base * entradas_a_pagar
            
            # Aviso de UX si lleva impar
            if cantidad % 2 != 0:
                detalle['aviso'] = "¡Tenés 2x1! Llevás una cantidad impar, agregá una más GRATIS."

        elif tipo == 'PORCENTAJE':
            descuento = Decimal(promo_a_usar.valor_descuento or 0) / 100
            total_final = total_original * (1 - descuento)

        elif tipo == 'MONTO_FIJO':
            descuento_total = Decimal(promo_a_usar.valor_descuento or 0) * cantidad
            total_final = total_original - descuento_total

        # Redondeo y seguridad
        if total_final < 0: total_final = Decimal('0.00')
        total_final = total_final.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Llenar el detalle con la data del éxito
        detalle['ahorro'] = total_original - total_final
        detalle['tipo_aplicado'] = tipo
        detalle['descripcion'] = promo_a_usar.nombre
        detalle['porcentaje'] = promo_a_usar.valor_descuento # Opcional para mostrar

    # Retorno final
    return total_final, promo_a_usar, detalle

    def politica_valida_para_funcion(promocion):
        # Si existen políticas asociadas activas, requerir que al menos una coincida
        politicas = PoliticaPromocion.objects.filter(promocion_a_otorgar=promocion, activa=True)
        if not politicas.exists():
            return True

        for pol in politicas:
            # Día de la función
            dias = pol.get_dias_list()
            if dias and funcion.fecha_hora.weekday() not in dias:
                continue

            # Hora
            hora = funcion.fecha_hora.time()
            inicio = pol.hora_inicio_rango
            fin = pol.hora_fin_rango
            # manejar rango que cruza medianoche
            if inicio <= fin:
                if not (inicio <= hora <= fin):
                    continue
            else:
                # rango overnight: valido si hora >= inicio or hora <= fin
                if not (hora >= inicio or hora <= fin):
                    continue

            # si llegó hasta acá, la política aplica
            return True

        return False

    for fp in candidatos_qs:
        promo = fp.promocion

        # Verificar vigencia por fechas de la promoción
        if promo.fecha_inicio and promo.fecha_fin:
            if not (promo.fecha_inicio <= hoy <= promo.fecha_fin):
                continue

        # Si existen políticas activas asociadas, validar que alguna coincida con la función
        if not politica_valida_para_funcion(promo):
            continue

        # Calcular total según tipo
        tipo = promo.tipo_descuento
        detalle = {'tipo_aplicado': tipo, 'descripcion': promo.descripcion or promo.nombre}

        if tipo == 'PORCENTAJE':
            porcentaje = Decimal(promo.valor_descuento or 0) / Decimal(100)
            unitario = (precio_base * (Decimal(1) - porcentaje)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total = (unitario * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            detalle.update({'precio_unitario_final': unitario, 'porcentaje': promo.valor_descuento})

        elif tipo == 'MONTO_FIJO':
            monto = Decimal(promo.valor_descuento or 0)
            unitario = (precio_base - monto)
            if unitario < Decimal('0.00'):
                unitario = Decimal('0.00')
            unitario = unitario.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total = (unitario * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            detalle.update({'precio_unitario_final': unitario, 'monto': promo.valor_descuento})

        elif tipo == '2X1':
            # Corrección: paga (cantidad // 2) + (cantidad % 2) entradas
            # Ejemplos: 1→1, 2→1, 3→2, 4→2, 5→3
            entradas_a_pagar = (cantidad // 2) + (cantidad % 2)
            total = (precio_base * entradas_a_pagar).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            detalle.update({'precio_unitario_final': None})

        else:
            # comportamiento por defecto: no descuento
            total = (precio_base * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            detalle.update({'precio_unitario_final': precio_base})

        mejores.append((total, promo, detalle))

    # Si no hay promociones aplicables, retornar precio base
    if not mejores:
        total = (precio_base * cantidad).quantize(Decimal('0.01'))
        return total, None, {'precio_unitario_final': precio_base, 'tipo_aplicado': None}

    # escoger la promoción que deje el total mínimo (mayor beneficio al cliente)
    mejores.sort(key=lambda x: x[0])
    mejor_total, mejor_promo, mejor_detalle = mejores[0]
    return mejor_total, mejor_promo, mejor_detalle


def es_promocion_valida_para_funcion(promocion, funcion) -> bool:
    """
    Valida si una `promocion` aplica a una `funcion`.
    Maneja robustamente el campo dias_semana (List o String).
    """
    import logging
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)

    try:
        if not promocion:
            return False

        # 1. Vigencia por fechas
        hoy = timezone.localdate()
        if promocion.fecha_inicio and promocion.fecha_fin:
            if not (promocion.fecha_inicio <= hoy <= promocion.fecha_fin):
                return False

        # 2. VALIDACIÓN DE DÍAS (CORREGIDA)
        # Obtenemos el día de la función (0=Lunes, 6=Domingo)
        dia_funcion = funcion.fecha_hora.weekday()
        
        dias_configurados = promocion.dias_semana
        
        # Caso A: Es None o vacío -> Aplica todos los días (o ninguno, según tu lógica)
        # Asumimos que si está vacío es "Todos"
        if not dias_configurados:
            pass 
            
        # Caso B: Es una lista (comportamiento normal de MultiSelectField)
        elif isinstance(dias_configurados, list):
            # Convertimos todo a string para comparar seguro ('0' vs 0)
            dias_str = [str(d) for d in dias_configurados]
            if str(dia_funcion) not in dias_str:
                return False
                
        # Caso C: Es un string (comportamiento legacy o raw)
        elif isinstance(dias_configurados, str):
            # Limpiamos y convertimos '0, 1' a ['0', '1']
            dias_str = [d.strip() for d in dias_configurados.split(',') if d.strip()]
            if str(dia_funcion) not in dias_str:
                return False

        # 3. Género requerido (Si aplica)
        if promocion.genero_requerido:
            # funcion.pelicula.generos es ManyToMany? O ForeignKey?
            # Ajusta según tu modelo exacto. Asumiendo ManyToMany:
            if not funcion.pelicula.generos.filter(pk=promocion.genero_requerido.pk).exists():
                return False

        # 4. Estreno
        if getattr(funcion.pelicula, 'es_estreno', False):
            if not promocion.aplica_en_estrenos:
                return False

        # 5. La película debe aceptar promociones
        if not getattr(funcion.pelicula, 'acepta_promociones', True):
            return False

        return True

    except Exception as e:
        logger.exception(f'Error validando promo {promocion.pk}: {str(e)}')
        return False


from datetime import time
from datetime import timedelta
from typing import Optional
from django.db.models import Q
from django.conf import settings
from core.services import notificacion_service
import django.db.models as models

from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.funcionPromocion import FuncionPromocion
from promociones.models.cuponGenerado import CuponGenerado
from accounts.models import Cliente
from ventas.models.entrada import Entrada
import django.utils.timezone as timezone


def _hora_en_rango(hora_obj: time, inicio: time, fin: time) -> bool:
    """Devuelve True si `hora_obj` está dentro del rango [inicio, fin]. Soporta ranges que cruzan medianoche."""
    if inicio <= fin:
        return inicio <= hora_obj <= fin
    # cruzando medianoche
    return hora_obj >= inicio or hora_obj <= fin


def procesar_butaca_liberada(funcion_objeto, cliente_excluido: Optional[Cliente] = None):
    """
    Flujo exacto solicitado:

    1) Buscar PoliticaPromocion activa que coincida con el género de la película y cuyo rango horario incluya
       la hora de la función liberada.
    2) Obtener la promocion_a_otorgar y verificar en FuncionPromocion que la promoción aplica a la función
       o a la película; si no, abortar para esa política.
    3) Buscar clientes candidatos en el historial de `Entradas` que hayan visto el mismo género o hayan
       asistido en el mismo rango horario. Excluir `cliente_excluido`.
    4) Crear un `CuponGenerado` por cada cliente candidato y enviar un email (simulado hacia MailCrab).
    
    Args:
        funcion_objeto (cine.models.Funcion): la función en la que se liberó la butaca.
        cliente_excluido (accounts.models.Cliente | None): cliente que no debe recibir la oferta.
    """
    pelicula = funcion_objeto.pelicula
    # Obtener géneros de la película como queryset/list (puede ser vacía)
    pelicula_generos = list(pelicula.generos.all())
    hora_funcion = funcion_objeto.fecha_hora.time()

    politicas = PoliticaPromocion.objects.filter(activa=True)
    # Filtrar por género: si la película tiene géneros, permitir políticas cuyo genero_pelicula
    # esté en esa lista o políticas sin género especificado.
    if pelicula_generos:
        politicas = politicas.filter(models.Q(genero_pelicula__in=pelicula_generos) | models.Q(genero_pelicula__isnull=True))

    respuestas = []

    # Recolectar políticas que además cumplan rango horario y día
    weekday = funcion_objeto.fecha_hora.weekday()  # 0=Monday .. 6=Sunday
    politicas_match = []
    for politica in politicas:
        # validar rango horario
        if not _hora_en_rango(hora_funcion, politica.hora_inicio_rango, politica.hora_fin_rango):
            continue

        # Validar día de la semana (politica.dias_semana ahora CSV string)
        raw = (politica.dias_semana or '').strip()
        dias_int = []
        if raw and raw not in ['*', 'todos']:
            try:
                dias_int = [int(x) for x in [p for p in raw.split(',') if p.strip() != '']]
            except Exception:
                dias_int = []

        if dias_int and weekday not in dias_int:
            continue

        # Si llega aquí, la política coincide en género, horario y día
        politicas_match.append(politica)

    # Si no hay políticas coincidentes, devolvemos vacío
    if not politicas_match:
        return respuestas

    # Para el envío de emails sólo consideramos políticas cuya promoción asociada
    # NO sea automática (es_automatica == False). Si no hay políticas no-automáticas
    # entre las que coinciden, no hacemos envíos desde este flujo.
    politicas_para_envio = []
    for p in politicas_match:
        try:
            if not getattr(getattr(p, 'promocion_a_otorgar', None), 'es_automatica', True):
                politicas_para_envio.append(p)
        except Exception:
            # En caso de error leyendo la promoción, omitir esta política para envío
            logger.exception('Error leyendo promocion_a_otorgar para PoliticaPromocion %s', getattr(p, 'pk', None))

    if not politicas_para_envio:
        # No hay políticas con promociones tipo cupón aplicables -> no enviamos
        logger.info('No hay PoliticaPromocion con promociones no automáticas aplicables para la función %s', getattr(funcion_objeto, 'pk', None))
        return respuestas

    # Ordenar por prioridad ASCENDENTE y elegir la primera entre las candidatas para envío
    #politica = sorted(politicas_para_envio, key=lambda p: p.prioridad)[0]
    politicas_ordenadas = sorted(politicas_para_envio, key=lambda p: (p.prioridad, -p.id))
    
    # DEBUG: Imprimimos el ranking para ver quién ganó
    ranking_log = [f"{p.nombre} (Prioridad: {p.prioridad})" for p in politicas_ordenadas]
    # POR ESTO (Para verlo seguro en la pantalla negra):
    print("\n" + "="*50)
    print(f"🏆 RANKING DE PRIORIDADES:")
    for p in politicas_ordenadas:
        print(f"   -> {p.nombre} (Prioridad: {p.prioridad})")
    print("="*50 + "\n")

    # Tomamos la ganadora (la primera de la lista)
    politica = politicas_ordenadas[0]
    # YIELD MANAGEMENT: Filtro de tiempo
    # Si la política define horas_antes_de_funcion, verificar que estemos dentro de la ventana de urgencia
    if politica.horas_antes_de_funcion:
        ahora = timezone.now()
        horas_restantes = (funcion_objeto.fecha_hora - ahora).total_seconds() / 3600
        
        if horas_restantes > politica.horas_antes_de_funcion:
            # Aún falta mucho para la función, no enviar
            logger.info('Política %s requiere estar a %d horas de la función, pero faltan %.1f horas. No se envía.',
                       politica.pk, politica.horas_antes_de_funcion, horas_restantes)
            respuestas.append({'politica': politica, 'status': 'fuera_de_ventana', 'horas_restantes': horas_restantes})
            return respuestas

    promocion = politica.promocion_a_otorgar
    logger.debug('procesar_butaca_liberada: politica_elegida=%s, promocion=%s, promocion_es_automatica=%s', getattr(politica, 'pk', None), getattr(promocion, 'pk', None), getattr(promocion, 'es_automatica', None))

    # Verificar existencia en FuncionPromocion
    aplica = FuncionPromocion.objects.filter(promocion=promocion).filter(
        Q(funcion=funcion_objeto) | Q(pelicula=pelicula)
    ).exists()

    if not aplica:
        # Fallback: permitir la promoción si no está vinculada explícitamente pero
        # la promoción no especifica un género o su genero_requerido coincide con la película.
        try:
            genero_req = getattr(promocion, 'genero_requerido', None)
            if genero_req is None:
                aplica = True
                logger.debug('Fallback: promocion %s no vinculada pero sin genero_requerido -> aplicar', promocion.pk)
            else:
                if pelicula.generos.filter(pk=genero_req.pk).exists():
                    aplica = True
                    logger.debug('Fallback: promocion %s no vinculada pero genero_requerido coincide -> aplicar', promocion.pk)
        except Exception:
            logger.exception('Error evaluando fallback para promocion %s en funcion %s', getattr(promocion, 'pk', None), getattr(funcion_objeto, 'pk', None))

    if not aplica:
        respuestas.append({'politica': politica, 'status': 'promo_no_valida'})
        logger.info('promocion %s no aplicable a funcion %s; abortando envio', getattr(promocion, 'pk', None), getattr(funcion_objeto, 'pk', None))
        return respuestas

    # Targeting: buscar clientes que hayan visto el mismo género O hayan asistido en el mismo rango horario
    candidatos = Cliente.objects.filter(ventas__entradas__isnull=False)
    if pelicula_generos:
        candidatos = candidatos.filter(
            Q(ventas__entradas__id_pelicula__generos__in=pelicula_generos) |
            Q(ventas__entradas__id_funcion__fecha_hora__time__gte=politica.hora_inicio_rango,
              ventas__entradas__id_funcion__fecha_hora__time__lte=politica.hora_fin_rango)
        )
    else:
        candidatos = candidatos.filter(
            Q(ventas__entradas__id_funcion__fecha_hora__time__gte=politica.hora_inicio_rango,
              ventas__entradas__id_funcion__fecha_hora__time__lte=politica.hora_fin_rango)
        )

    if cliente_excluido is not None:
        candidatos = candidatos.exclude(pk=cliente_excluido.pk)

    candidatos = candidatos.distinct()

    enviados = 0
    total_candidatos = candidatos.count()
    logger.info('procesar_butaca_liberada: politica=%s promocion=%s candidatos=%d (excluido=%s) politicas_match=%s', getattr(politica, 'pk', None), getattr(promocion, 'pk', None), total_candidatos, getattr(cliente_excluido, 'pk', None) if cliente_excluido else None, [p.pk for p in politicas_match])

    for cliente in candidatos:
        # calcular expiración
        ahora = timezone.now()
        expira = ahora + timedelta(minutes=getattr(politica, 'minutos_validez', 60))

        cupon = CuponGenerado.objects.create(
            cliente=cliente,
            politica_origen=politica,
            expira_en=expira,
            funcion_origen=funcion_objeto
        )

        # Construir link absoluto: priorizamos `settings.SITE_BASE_URL` si está definido,
        # sino usamos el dominio pedido en requerimiento.
        base = getattr(settings, 'SITE_BASE_URL', 'https://uncategorized-noncommodiously-floy.ngrok-free.dev')
        link = f"{base}/promociones/activar/{cupon.token}"

        # Envío usando NotificacionService y plantillas HTML/texto
        try:
            # Sólo enviar si la promoción asociada no es automática (es_automatica == False).
            if getattr(promocion, 'es_automatica', False):
                logger.info('Promocion %s es automática; no se envía email de oferta (solo cupones se envían).', getattr(promocion, 'pk', None))
                continue

            logger.debug('Llamando notificacion_service.enviar_oferta_promocion: cliente=%s promocion=%s cupon=%s link=%s', getattr(cliente, 'pk', None), getattr(promocion, 'pk', None), getattr(cupon, 'token', None), link)
            sent = notificacion_service.enviar_oferta_promocion(
                cliente=cliente,
                promocion=promocion,
                cupon=cupon,
                link=link,
                funcion=funcion_objeto
            )
            if sent:
                enviados += 1
        except Exception:
            # No hacemos rollback; sólo registramos intento fallido
            logger.exception('Error enviando oferta promocion %s al cliente %s', getattr(promocion, 'pk', None), getattr(cliente, 'pk', None))

    logger.info('procesar_butaca_liberada resultado: politica=%s promocion=%s candidatos=%d enviados=%d', getattr(politica, 'pk', None), getattr(promocion, 'pk', None), total_candidatos, enviados)
    respuestas.append({'politica': politica, 'status': 'procesada', 'candidatos': total_candidatos, 'enviados': enviados})
    return respuestas
