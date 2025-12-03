from decimal import Decimal
from django.utils import timezone
from django.db import models
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def calcular_precio_final(funcion, cantidad_entradas, promocion_especifica=None):
    """
    Calcula el precio final de una compra.

    Reglas:
    - Si llega `promocion_especifica`, se aplica directamente.
    - Si no, buscamos entre las `Promocion` con `es_automatica=True` y que sean
      válidas para la función usando `es_promocion_valida_para_funcion`.

    Retorna: (total_decimal, promocion_aplicada | None, detalle_dict)
    """
    from promociones.models.promocion import Promocion
    from decimal import Decimal, ROUND_HALF_UP

    logger.info(f'[PROMO] Calculando precio para Función {funcion.id} ({funcion.pelicula.titulo}), '
                f'{cantidad_entradas} entradas, promo_especifica={promocion_especifica}')

    precio_base = Decimal(funcion.precio_base)
    cantidad = int(cantidad_entradas)
    total_original = (precio_base * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    detalle = {
        'precio_unitario_base': precio_base,
        'total_original': total_original,
        'ahorro': Decimal('0.00'),
        'tipo_aplicado': None,
        'descripcion': None,
        'precio_unitario_final': None,
        'aviso': None,
    }

    # Helper para calcular total dado una promoción
    def _total_con_promocion(promo: Promocion) -> Decimal:
        tipo = (promo.tipo_descuento or '').upper().strip()
        if tipo == '2X1':
            entradas_a_pagar = (cantidad // 2) + (cantidad % 2)
            total = (precio_base * entradas_a_pagar).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return total
        if tipo == 'PORCENTAJE':
            pct = Decimal(promo.valor_descuento or 0) / Decimal(100)
            total = (precio_base * (Decimal(1) - pct) * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return total
        if tipo == 'MONTO_FIJO':
            monto = Decimal(promo.valor_descuento or 0)
            unit = precio_base - monto
            if unit < Decimal('0.00'):
                unit = Decimal('0.00')
            total = (unit * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return total
        # Fallback: sin descuento
        return total_original

    # 1) Si viene promoción específica (cupón/session), aplicar directamente
    if promocion_especifica:
        logger.info(f'[PROMO] Aplicando promoción específica: {promocion_especifica.codigo}')
        promo_aplicada = promocion_especifica
        total_final = _total_con_promocion(promo_aplicada)
        detalle['ahorro'] = total_original - total_final
        detalle['tipo_aplicado'] = (promo_aplicada.tipo_descuento or '').upper()
        detalle['descripcion'] = promo_aplicada.nombre
        detalle['precio_unitario_final'] = (total_final / cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if cantidad > 0 else precio_base
        if detalle['tipo_aplicado'] == '2X1' and (cantidad % 2 != 0):
            detalle['aviso'] = 'Tenés 2x1: agregá una entrada más para aprovecharla al máximo.'
        logger.info(f'[PROMO] Total: ${total_final}, Ahorro: ${detalle["ahorro"]}')
        return total_final, promo_aplicada, detalle

    # 2) Buscar promociones automáticas válidas para la función
    from promociones.models.funcionPromocion import FuncionPromocion
    candidatos = list(Promocion.objects.filter(es_automatica=True))
    logger.info(f'[PROMO] Evaluando {len(candidatos)} promociones automáticas')
    
    candidatos_validos = []
    for p in candidatos:
        logger.debug(f'[PROMO] Evaluando {p.codigo}: vigencia {p.fecha_inicio} a {p.fecha_fin}, '
                    f'días="{p.dias_semana}"')
        
        # Primero validar reglas generales (fechas, días, género, estreno, acepta_promociones)
        if not es_promocion_valida_para_funcion(p, funcion):
            logger.debug(f'[PROMO] {p.codigo} NO válida según reglas generales')
            continue

        # Si existen filas en FuncionPromocion para esta promoción, requerimos que
        # la promoción esté vinculada explícitamente a la función o a la película.
        tiene_vinculos = FuncionPromocion.objects.filter(promocion=p).exists()
        if tiene_vinculos:
            vinculada = FuncionPromocion.objects.filter(promocion=p).filter(models.Q(funcion=funcion) | models.Q(pelicula=funcion.pelicula)).exists()
            if not vinculada:
                # La promo existe pero no está vinculada a esta función/película
                logger.debug(f'[PROMO] {p.codigo} tiene vínculos pero no está vinculada a esta función/película')
                continue
            logger.debug(f'[PROMO] {p.codigo} vinculada explícitamente')
        else:
            logger.debug(f'[PROMO] {p.codigo} sin vínculos, aplica a todas las funciones válidas')

        candidatos_validos.append(p)
        logger.info(f'[PROMO] ✓ {p.codigo} es candidata válida')

    if not candidatos_validos:
        # No hay promociones automáticas aplicables
        logger.info(f'[PROMO] No hay promociones válidas. Precio regular: ${total_original}')
        detalle['descripcion'] = 'Precio regular'
        detalle['precio_unitario_final'] = precio_base
        return total_original, None, detalle

    # 3) Elegir la promoción que deje el total más bajo (mayor beneficio)
    mejores = []
    for p in candidatos_validos:
        try:
            total_p = _total_con_promocion(p)
            mejores.append((total_p, p))
        except Exception:
            logger.exception('Error calculando total para promoción %s', getattr(p, 'pk', None))

    if not mejores:
        detalle['descripcion'] = 'Precio regular'
        detalle['precio_unitario_final'] = precio_base
        return total_original, None, detalle

    mejores.sort(key=lambda x: x[0])
    total_final, promo_aplicada = mejores[0]

    detalle['ahorro'] = total_original - total_final
    detalle['tipo_aplicado'] = (promo_aplicada.tipo_descuento or '').upper()
    detalle['descripcion'] = promo_aplicada.nombre
    detalle['precio_unitario_final'] = (total_final / cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if cantidad > 0 else precio_base
    if detalle['tipo_aplicado'] == '2X1' and (cantidad % 2 != 0):
        detalle['aviso'] = 'Tenés 2x1: agregá una entrada más para aprovecharla al máximo.'

    logger.info(f'[PROMO] ✓ Aplicando {promo_aplicada.codigo}: Total ${total_final}, Ahorro ${detalle["ahorro"]}')
    return total_final, promo_aplicada, detalle

    # Fin de calcular_precio_final


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
            logger.debug(f'[VALIDACION] Promoción None, retornando False')
            return False

        logger.debug(f'[VALIDACION] Validando {promocion.codigo} para función {funcion.id}')

        # 1. Vigencia por fechas
        hoy = timezone.localdate()
        if promocion.fecha_inicio and promocion.fecha_fin:
            en_rango = promocion.fecha_inicio <= hoy <= promocion.fecha_fin
            logger.debug(f'[VALIDACION] Fechas: {promocion.fecha_inicio} <= {hoy} <= {promocion.fecha_fin} = {en_rango}')
            if not en_rango:
                logger.debug(f'[VALIDACION] ✗ {promocion.codigo} fuera de vigencia')
                return False

        # 2. VALIDACIÓN DE DÍAS (MEJORADA CON LOGS)
        # Obtenemos el día de la función (0=Lunes, 6=Domingo)
        dia_funcion = funcion.fecha_hora.weekday()
        dia_nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        
        dias_configurados = promocion.dias_semana
        logger.debug(f'[VALIDACION] Día función: {dia_funcion} ({dia_nombres[dia_funcion]}), '
                    f'Días config: "{dias_configurados}" (tipo: {type(dias_configurados).__name__})')
        
        # Caso A: Es None o vacío -> Aplica todos los días
        if not dias_configurados:
            logger.debug(f'[VALIDACION] Días vacíos, aplica todos los días')
            pass 
            
        # Caso B: Es una lista (comportamiento normal de MultiSelectField)
        elif isinstance(dias_configurados, list):
            # Convertimos todo a string para comparar seguro ('0' vs 0)
            dias_str = [str(d) for d in dias_configurados]
            logger.debug(f'[VALIDACION] Días como lista: {dias_str}')
            if str(dia_funcion) not in dias_str:
                logger.debug(f'[VALIDACION] ✗ Día {dia_funcion} no está en {dias_str}')
                return False
                
        # Caso C: Es un string (comportamiento legacy o raw)
        elif isinstance(dias_configurados, str):
            # Limpiamos y convertimos '0, 1' a ['0', '1']
            dias_str = [d.strip() for d in dias_configurados.split(',') if d.strip()]
            logger.debug(f'[VALIDACION] Días como string parseado: {dias_str}')
            if dias_str and str(dia_funcion) not in dias_str:
                logger.debug(f'[VALIDACION] ✗ Día {dia_funcion} no está en {dias_str}')
                return False
        
        logger.debug(f'[VALIDACION] ✓ Día {dia_funcion} válido')

        # 3. Género requerido (Si aplica)
        if promocion.genero_requerido:
            # funcion.pelicula.generos es ManyToMany? O ForeignKey?
            # Ajusta según tu modelo exacto. Asumiendo ManyToMany:
            tiene_genero = funcion.pelicula.generos.filter(pk=promocion.genero_requerido.pk).exists()
            logger.debug(f'[VALIDACION] Género requerido: {promocion.genero_requerido}, película tiene: {tiene_genero}')
            if not tiene_genero:
                logger.debug(f'[VALIDACION] ✗ Género no coincide')
                return False

        # 4. Estreno
        es_estreno = getattr(funcion.pelicula, 'es_estreno', False)
        if es_estreno:
            logger.debug(f'[VALIDACION] Es estreno, aplica_en_estrenos={promocion.aplica_en_estrenos}')
            if not promocion.aplica_en_estrenos:
                logger.debug(f'[VALIDACION] ✗ Es estreno y promo no aplica en estrenos')
                return False

        # 5. La película debe aceptar promociones
        acepta_promos = getattr(funcion.pelicula, 'acepta_promociones', True)
        logger.debug(f'[VALIDACION] Película acepta_promociones={acepta_promos}')
        if not acepta_promos:
            logger.debug(f'[VALIDACION] ✗ Película no acepta promociones')
            return False

        logger.debug(f'[VALIDACION] ✓ {promocion.codigo} VÁLIDA para función {funcion.id}')
        return True

    except Exception as e:
        logger.exception(f'[VALIDACION] ✗ ERROR validando promo {promocion.pk}: {str(e)}')
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

    # Excluir políticas con activar_por_ocupacion=True (esas son solo para el cron)
    politicas = PoliticaPromocion.objects.filter(activa=True, activar_por_ocupacion=False)
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

    # Ordenar por prioridad: 1 = máxima prioridad (primero), números altos = menor prioridad (último)
    # En caso de empate, se usa -p.id (IDs más recientes primero)
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
