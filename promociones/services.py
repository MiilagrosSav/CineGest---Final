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
    logger.info(f'[PROMO] ====== INICIO DEBUG PROMOCIONES ======')
    logger.info(f'[PROMO] Función ID: {funcion.id}')
    logger.info(f'[PROMO] Película: {funcion.pelicula.titulo} (ID={funcion.pelicula.pk})')
    logger.info(f'[PROMO] Fecha función: {funcion.fecha_hora}')
    logger.info(f'[PROMO] Estado función: {funcion.estado}')
    logger.info(f'[PROMO] Película activo: {funcion.pelicula.activo}')
    logger.info(f'[PROMO] =======================================')

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

    # 1) Si viene promoción específica (cupón/session), aplicar directamente.
    # El llamador (yield management, intercambio, sesión activada) ya validó la
    # elegibilidad del cliente/función al generar el cupón. Re-validar aquí con
    # es_promocion_valida_para_funcion puede producir falsos negativos (sin vínculos,
    # días de semana, géneros, etc.) que no corresponden al flujo de cupón personalizado.
    # Solo se verifica que la promo no fue globalmente desactivada por un admin.
    if promocion_especifica:
        print(f"[YIELD DEBUG] calcular_precio_final: promo_especifica='{promocion_especifica.codigo}' "
              f"tipo={promocion_especifica.tipo_descuento} es_automatica={promocion_especifica.es_automatica} "
              f"activo={promocion_especifica.activo} "
              f"vigencia={promocion_especifica.fecha_inicio}→{promocion_especifica.fecha_fin}")
        logger.info(f'[PROMO] Aplicando promoción específica: {promocion_especifica.codigo}')

        if not getattr(promocion_especifica, 'activo', True):
            print(f"[YIELD DEBUG] Promo '{promocion_especifica.codigo}' está INACTIVA. Precio normal.")
            logger.warning(f'[PROMO] Promo específica {promocion_especifica.codigo} está inactiva. Precio normal.')
            detalle['aviso'] = f'La promoción "{promocion_especifica.nombre}" fue desactivada.'
            return total_original, None, detalle

        promo_aplicada = promocion_especifica
        total_final = _total_con_promocion(promo_aplicada)
        detalle['ahorro'] = total_original - total_final
        detalle['tipo_aplicado'] = (promo_aplicada.tipo_descuento or '').upper()
        detalle['descripcion'] = promo_aplicada.nombre
        detalle['precio_unitario_final'] = (total_final / cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if cantidad > 0 else precio_base
        if detalle['tipo_aplicado'] == '2X1' and (cantidad % 2 != 0):
            detalle['aviso'] = 'Tenés 2x1: agregá una entrada más para aprovecharla al máximo.'
        print(f"[YIELD DEBUG] calcular_precio_final resultado: total={total_final} ahorro={detalle['ahorro']}")
        logger.info(f'[PROMO] Total: ${total_final}, Ahorro: ${detalle["ahorro"]}')
        return total_final, promo_aplicada, detalle

    # 2) Buscar mejor promoción automática con jerarquía de especificidad
    # Prioridad 1: promos con VinculoPromocional → Prioridad 2: globales.
    # Si existen promos específicas, las globales son ignoradas (Regla de Oro).
    logger.info(f'[PROMO] Buscando mejor promoción automática con prioridad...')
    promo_aplicada, es_especifica = obtener_mejor_promocion(funcion)

    if not promo_aplicada:
        logger.warning(f'❌ [PROMO] No hay promociones válidas. Precio regular: ${total_original}')
        logger.warning(f'🔍 [PROMO] ====== FIN DEBUG PROMOCIONES ======')
        detalle['descripcion'] = 'Precio regular'
        detalle['precio_unitario_final'] = precio_base
        return total_original, None, detalle

    logger.warning(f'✅ [PROMO] APLICANDO: {promo_aplicada.codigo} ({promo_aplicada.nombre})'
                   f' | específica={es_especifica}')

    total_final = _total_con_promocion(promo_aplicada)

    detalle['ahorro'] = total_original - total_final
    detalle['tipo_aplicado'] = (promo_aplicada.tipo_descuento or '').upper()
    detalle['descripcion'] = promo_aplicada.nombre
    detalle['precio_unitario_final'] = (total_final / cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if cantidad > 0 else precio_base
    if detalle['tipo_aplicado'] == '2X1' and (cantidad % 2 != 0):
        detalle['aviso'] = 'Tenés 2x1: agregá una entrada más para aprovecharla al máximo.'

    logger.warning(f'✅ [PROMO] APLICANDO: {promo_aplicada.codigo} ({promo_aplicada.nombre})')
    logger.warning(f'✅ [PROMO] Total: ${total_final} | Ahorro: ${detalle["ahorro"]}')
    logger.warning(f'🔍 [PROMO] ====== FIN DEBUG PROMOCIONES ======')
    return total_final, promo_aplicada, detalle

    # Fin de calcular_precio_final


def tiene_vinculo_especifico(promocion) -> bool:
    """
    Devuelve True si la promoción tiene al menos un VinculoPromocional
    (está ligada a una película o función concreta).
    Las promos sin vínculos se consideran 'globales'.
    """
    from promociones.models.vinculo_promocional import VinculoPromocional
    return VinculoPromocional.objects.filter(promocion=promocion).exists()


def obtener_mejor_promocion(funcion):
    """
    Busca la MEJOR promoción automática para una función siguiendo la jerarquía
    de especificidad:

    Prioridad 1 (Alta): Promociones con Vínculo Específico (vinculadas a esta
                        función o película).
    Prioridad 2 (Baja): Promociones Globales (sin VinculoPromocional).

    Regla de Oro: si existen promos específicas, las globales son ignoradas
    completamente — no se suman ni se usan como fallback.

    Dentro de cada nivel se elige la que produce el mayor ahorro (menor costo
    unitario al cliente).

    Retorna: (Promocion | None, es_especifica: bool)
    """
    from promociones.models.promocion import Promocion
    from decimal import Decimal

    candidatos = list(Promocion.objects.filter(
        es_automatica=True,
        activo=True,
        fecha_baja__isnull=True,
    ))

    validas = [p for p in candidatos if es_promocion_valida_para_funcion(p, funcion)]
    if not validas:
        return None, False

    precio_base = Decimal(funcion.precio_base)

    def _unit_cost(promo):
        tipo = (promo.tipo_descuento or '').upper().strip()
        if tipo == '2X1':
            return precio_base / Decimal(2)
        if tipo == 'PORCENTAJE':
            pct = Decimal(promo.valor_descuento or 0) / Decimal(100)
            return precio_base * (Decimal(1) - pct)
        if tipo == 'MONTO_FIJO':
            unit = precio_base - Decimal(promo.valor_descuento or 0)
            return max(unit, Decimal('0.00'))
        return precio_base

    # Separar por especificidad
    especificas = [p for p in validas if tiene_vinculo_especifico(p)]
    globales    = [p for p in validas if not tiene_vinculo_especifico(p)]

    # Regla de Oro: si hay específicas, las globales no compiten
    pool = especificas if especificas else globales
    if not pool:
        return None, False

    best = min(pool, key=_unit_cost)
    return best, bool(especificas)


def obtener_mejor_promocion_global(funcion):
    """Retorna la mejor promoción automática GLOBAL (sin vínculo específico) para una función."""
    from promociones.models.promocion import Promocion
    from decimal import Decimal

    candidatos = list(Promocion.objects.filter(
        es_automatica=True,
        activo=True,
        fecha_baja__isnull=True,
    ))

    validas = [p for p in candidatos if es_promocion_valida_para_funcion(p, funcion)]
    globales = [p for p in validas if not tiene_vinculo_especifico(p)]
    if not globales:
        return None

    precio_base = Decimal(funcion.precio_base)

    def _unit_cost(promo):
        tipo = (promo.tipo_descuento or '').upper().strip()
        if tipo == '2X1':
            return precio_base / Decimal(2)
        if tipo == 'PORCENTAJE':
            pct = Decimal(promo.valor_descuento or 0) / Decimal(100)
            return precio_base * (Decimal(1) - pct)
        if tipo == 'MONTO_FIJO':
            unit = precio_base - Decimal(promo.valor_descuento or 0)
            return max(unit, Decimal('0.00'))
        return precio_base

    return min(globales, key=_unit_cost)


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
            logger.warning(f'🔍 [VALIDACION] Promoción None, retornando False')
            return False

        logger.warning(f'🔍 [VALIDACION] ===== Validando {promocion.codigo} para función {funcion.id} =====')

        # 1. Vigencia por fechas - ✅ CORRECCIÓN CRÍTICA: Validar que la promoción esté vigente HOY
        # La promoción debe estar activa el día de la COMPRA, no el día de la función
        # Esto previene que promociones futuras se apliquen en preventas
        fecha_hoy = timezone.now().date()
        fecha_funcion = funcion.fecha_hora.date()
        
        if promocion.fecha_inicio and promocion.fecha_fin:
            # Verificar vigencia en la FECHA DE LA FUNCIÓN (no en la fecha de compra):
            # una promo puede estar configurada para el día de la función aunque se compre antes.
            vigente_en_funcion = promocion.fecha_inicio <= fecha_funcion <= promocion.fecha_fin
            logger.warning(
                f'🔍 [VALIDACION] Vigencia en función: {promocion.fecha_inicio} <= {fecha_funcion} (func) <= {promocion.fecha_fin} = {vigente_en_funcion}'
            )

            if not vigente_en_funcion:
                logger.warning(
                    f'❌ [VALIDACION] {promocion.codigo} NO vigente en fecha de función ({fecha_funcion}). '
                    f'Rango: {promocion.fecha_inicio} – {promocion.fecha_fin}'
                )
                return False

            logger.warning(f'✅ [VALIDACION] Promoción vigente en fecha de función')
        else:
            logger.warning(f'🔍 [VALIDACION] Sin restricción de fechas')

        # 2. VALIDACIÓN DE DÍAS (MEJORADA CON LOGS)
        # Obtenemos el día de la función (0=Lunes, 6=Domingo)
        dia_funcion = funcion.fecha_hora.weekday()
        dia_nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        
        dias_configurados = promocion.dias_semana
        logger.warning(f'🔍 [VALIDACION] Día función: {dia_funcion} ({dia_nombres[dia_funcion]}), '
                    f'Días config: "{dias_configurados}" (tipo: {type(dias_configurados).__name__})')
        
        # Caso A: Es None o vacío -> Aplica todos los días
        if not dias_configurados:
            logger.warning(f'🔍 [VALIDACION] Días vacíos, aplica todos los días')
            pass 
            
        # Caso B: Es una lista (comportamiento normal de MultiSelectField)
        elif isinstance(dias_configurados, list):
            # Convertimos todo a string para comparar seguro ('0' vs 0)
            dias_str = [str(d) for d in dias_configurados]
            logger.warning(f'🔍 [VALIDACION] Días como lista: {dias_str}')
            if str(dia_funcion) not in dias_str:
                logger.warning(f'❌ [VALIDACION] Día {dia_funcion} no está en {dias_str}')
                return False
                
        # Caso C: Es un string (comportamiento legacy o raw)
        elif isinstance(dias_configurados, str):
            # Limpiamos y convertimos '0, 1' a ['0', '1']
            dias_str = [d.strip() for d in dias_configurados.split(',') if d.strip()]
            logger.warning(f'🔍 [VALIDACION] Días como string parseado: {dias_str}')
            if dias_str and str(dia_funcion) not in dias_str:
                logger.warning(f'❌ [VALIDACION] Día {dia_funcion} no está en {dias_str}')
                return False
        
        logger.warning(f'✅ [VALIDACION] Día {dia_funcion} válido')

        # 3. Género requerido (Si aplica)
        if promocion.genero_requerido:
            # funcion.pelicula.generos es ManyToMany? O ForeignKey?
            # Ajusta según tu modelo exacto. Asumiendo ManyToMany:
            tiene_genero = funcion.pelicula.generos.filter(pk=promocion.genero_requerido.pk).exists()
            logger.warning(f'🔍 [VALIDACION] Género requerido: {promocion.genero_requerido}, película tiene: {tiene_genero}')
            if not tiene_genero:
                logger.warning(f'❌ [VALIDACION] Género no coincide')
                return False
        else:
            logger.warning(f'🔍 [VALIDACION] Sin restricción de género')

        # 4. Estreno
        es_estreno = getattr(funcion.pelicula, 'es_estreno', False)
        if es_estreno:
            logger.warning(f'🔍 [VALIDACION] Es estreno, aplica_en_estrenos={promocion.aplica_en_estrenos}')
            if not promocion.aplica_en_estrenos:
                logger.warning(f'❌ [VALIDACION] Es estreno y promo no aplica en estrenos')
                return False
        else:
            logger.warning(f'🔍 [VALIDACION] No es estreno')

        # 5. La película debe aceptar promociones
        acepta_promos = getattr(funcion.pelicula, 'acepta_promociones', True)
        logger.warning(f'🔍 [VALIDACION] Película acepta_promociones={acepta_promos}')
        if not acepta_promos:
            logger.warning(f'❌ [VALIDACION] Película no acepta promociones')
            return False

        # ✅ VALIDACIÓN DE FORMATOS APLICABLES (NUEVA)
        # Si la promoción tiene formatos específicos configurados, la función debe tener al menos uno de ellos
        formatos_promo = promocion.formatos_aplicables.all()
        if formatos_promo.exists():
            # Regla de negocio:
            # - STANDARD es neutro (no bloquea ni habilita por si solo).
            # - Todos los formatos relevantes de la función deben estar cubiertos por la promo.
            #   funcion_relevantes ⊆ formatos_promo.
            from cine.models.funcion_formato import FuncionFormato
            formatos_funcion = FuncionFormato.objects.filter(funcion=funcion).select_related('formato')
            formatos_promo_ids = set(formatos_promo.values_list('id', flat=True))

            formatos_funcion_relevantes_ids = set()
            formatos_funcion_relevantes_nombres = []
            for ff in formatos_funcion:
                nombre_formato = (ff.formato.nombre or '').strip().upper()
                if 'STANDARD' in nombre_formato:
                    continue
                formatos_funcion_relevantes_ids.add(ff.formato_id)
                formatos_funcion_relevantes_nombres.append(ff.formato.nombre)

            logger.warning(f'🔍 [VALIDACION] Formatos de promoción: {[f.nombre for f in formatos_promo]}')
            logger.warning(f'🔍 [VALIDACION] Formatos relevantes de función #{funcion.pk}: {formatos_funcion_relevantes_nombres}')

            if not formatos_funcion_relevantes_ids.issubset(formatos_promo_ids):
                logger.warning(
                    f'❌ [VALIDACION] {promocion.codigo} no cubre todos los formatos relevantes de la función '
                    f'(STANDARD se ignora).'
                )
                logger.warning('❌ [VALIDACION] RECHAZADA por formatos incompatibles')
                logger.warning('🔍 [VALIDACION] ================================================')
                return False

            logger.warning(f'✅ [VALIDACION] {promocion.codigo} cubre todos los formatos relevantes de la función')
        else:
            logger.warning('🔍 [VALIDACION] Sin restricción de formatos (aplica a todos)')

        # ✅ VALIDACIÓN DE VÍNCULOS ESPECÍFICOS (CRÍTICO)
        # Si la promoción tiene vínculos específicos, debe estar vinculada a esta función o película
        from promociones.models.vinculo_promocional import VinculoPromocional
        
        tiene_vinculos = VinculoPromocional.objects.filter(promocion=promocion).exists()
        logger.warning(f'🔍 [VALIDACION] Tiene vínculos específicos: {tiene_vinculos}')
        
        if tiene_vinculos:
            # Mostrar todos los vínculos para debugging
            vinculos_existentes = VinculoPromocional.objects.filter(promocion=promocion).select_related('funcion__pelicula', 'pelicula')
            logger.warning(f'🔍 [VALIDACION] Vínculos de {promocion.codigo}:')
            for v in vinculos_existentes:
                if v.funcion:
                    logger.warning(f'   📌 Función #{v.funcion.pk}: {v.funcion.pelicula.titulo} '
                                 f'({v.funcion.fecha_hora.strftime("%d/%m/%Y %H:%M")}) - Activo: {v.funcion.activo}')
                if v.pelicula:
                    logger.warning(f'   📌 Película: "{v.pelicula.titulo}" (ID={v.pelicula.pk}) - Activo: {v.pelicula.activo}')
            
            # Verificar si está vinculada a esta función/película ACTIVA
            logger.warning(f'🔍 [VALIDACION] Verificando si aplica a función #{funcion.pk} con película "{funcion.pelicula.titulo}" (ID={funcion.pelicula.pk})')
            
            vinculada = VinculoPromocional.objects.filter(
                promocion=promocion
            ).filter(
                models.Q(funcion=funcion, funcion__activo=True) | 
                models.Q(pelicula=funcion.pelicula, pelicula__activo=True)
            ).exists()
            
            if not vinculada:
                logger.warning(f'❌ [VALIDACION] {promocion.codigo} tiene vínculos específicos pero NO está vinculada a esta función/película')
                logger.warning(f'❌ [VALIDACION] RECHAZADA por vínculos específicos')
                logger.warning(f'🔍 [VALIDACION] ================================================')
                return False
            
            logger.warning(f'✅ [VALIDACION] {promocion.codigo} vinculada explícitamente a esta función/película')

        logger.warning(f'✅ [VALIDACION] {promocion.codigo} VÁLIDA para función {funcion.id}')
        logger.warning(f'🔍 [VALIDACION] ================================================')
        return True

    except Exception as e:
        logger.exception(f'❌ [VALIDACION] ERROR validando promo {promocion.pk}: {str(e)}')
        return False


from datetime import time
from datetime import timedelta
from typing import Optional
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from core.services import notificacion_service
import django.db.models as models

from promociones.models.politicaPromocion import PoliticaPromocion
from promociones.models.vinculo_promocional import VinculoPromocional
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


def procesar_butaca_liberada(funcion_objeto, cliente_excluido: Optional[Cliente] = None, ignorar_ventana: bool = False):
    """
    Flujo exacto solicitado:

    1) Buscar PoliticaPromocion activa que coincida con el género de la película y cuyo rango horario incluya
       la hora de la función liberada.
    2) Obtener la promocion_a_otorgar y verificar en VinculoPromocional que la promoción aplica a la función
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
    # Además filtrar por promoción vigente: activo=True Y fecha_fin >= hoy,
    # para que promociones vencidas naturalmente no disparen políticas aunque
    # la política aún figure como activa=True en BD.
    _hoy = timezone.now().date()
    politicas = PoliticaPromocion.objects.filter(
        activa=True,
        activar_por_ocupacion=False,
        promocion_a_otorgar__activo=True,
        promocion_a_otorgar__fecha_fin__gte=_hoy,
    )
    # Filtrar por género: si la película tiene géneros, permitir políticas cuyo genero_pelicula
    # esté en esa lista o políticas sin género especificado.
    if pelicula_generos:
        politicas = politicas.filter(models.Q(genero_pelicula__in=pelicula_generos) | models.Q(genero_pelicula__isnull=True))

    respuestas = []

    total_politicas_activas = politicas.count()
    logger.info('[INTERCAMBIO-PROMO] Función %s | Película: "%s" | Géneros: %s | Hora: %s',
                funcion_objeto.pk, pelicula.titulo,
                [g.nombre for g in pelicula_generos], hora_funcion)
    logger.info('[INTERCAMBIO-PROMO] Políticas activas encontradas (sin filtro horario): %d', total_politicas_activas)

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

    logger.info('[INTERCAMBIO-PROMO] Políticas que coinciden en horario+día+género: %d', len(politicas_match))
    for pm in politicas_match:
        logger.info('  -> Política "%s" (ID=%s, prioridad=%s)', pm.nombre, pm.pk, pm.prioridad)

    # Si no hay políticas coincidentes, devolvemos vacío
    if not politicas_match:
        logger.warning('[INTERCAMBIO-PROMO] Sin políticas coincidentes para función %s. '
                       'Verificar rangos horarios (%s), días de semana (weekday=%d) y géneros.',
                       funcion_objeto.pk, hora_funcion, weekday)
        return respuestas

    # Para el envío de emails sólo consideramos políticas cuya promoción asociada
    # NO sea automática (es_automatica == False). Si no hay políticas no-automáticas
    # entre las que coinciden, no hacemos envíos desde este flujo.
    politicas_para_envio = []
    for p in politicas_match:
        try:
            promo = getattr(p, 'promocion_a_otorgar', None)
            if promo is None:
                logger.warning('[INTERCAMBIO-PROMO] Política "%s" (ID=%s) sin promoción asignada, omitiendo.', p.nombre, p.pk)
                continue

            # Validación lazy de vigencia: si la promoción expiró o fue desactivada
            # sin que nadie guardara el modelo, la detectamos aquí y desactivamos la política.
            promo_vencida = (
                not promo.activo
                or (promo.fecha_fin is not None and promo.fecha_fin < timezone.now().date())
            )
            if promo_vencida:
                logger.warning(
                    '[INTERCAMBIO-PROMO] Política "%s" (ID=%s): su promoción "%s" está inactiva/vencida '
                    '(activo=%s, fecha_fin=%s). Auto-desactivando política.',
                    p.nombre, p.pk, promo.codigo, promo.activo, promo.fecha_fin,
                )
                PoliticaPromocion.objects.filter(pk=p.pk).update(activa=False)
                continue

            if not promo.es_automatica:
                politicas_para_envio.append(p)
        except Exception:
            # En caso de error leyendo la promoción, omitir esta política para envío
            logger.exception('Error leyendo promocion_a_otorgar para PoliticaPromocion %s', getattr(p, 'pk', None))

    logger.info('[INTERCAMBIO-PROMO] Políticas con promociones tipo cupón (es_automatica=False): %d', len(politicas_para_envio))
    if not politicas_para_envio:
        # No hay políticas con promociones tipo cupón aplicables -> no enviamos
        logger.warning('[INTERCAMBIO-PROMO] NINGUNA política tiene una promoción tipo cupón (es_automatica=False). '
                       'Verificar que la promoción asignada en PoliticaPromocion tenga es_automatica=False. '
                       'Políticas evaluadas: %s',
                       [(p.nombre, getattr(p.promocion_a_otorgar, 'codigo', 'N/A'),
                         getattr(p.promocion_a_otorgar, 'es_automatica', 'N/A')) for p in politicas_match])
        return respuestas

    # ─── Regla de Exclusión de Cupones ───────────────────────────────────────
    # Si la función ya tiene una promoción automática de Vínculo Específico activa,
    # los cupones (de intercambio/ocupación) son incompatibles: no se envían.
    try:
        promo_auto, es_auto_especifica = obtener_mejor_promocion(funcion_objeto)
        if es_auto_especifica:
            logger.info(
                '[INTERCAMBIO-PROMO] Función %s tiene promo de vínculo específico activa (%s). '
                'Cupones omitidos por incompatibilidad.',
                funcion_objeto.pk, getattr(promo_auto, 'codigo', ''))
            respuestas.append({'politica': None, 'status': 'bloqueado_por_vinculo_especifico'})
            return respuestas
    except Exception:
        logger.exception('[INTERCAMBIO-PROMO] Error verificando promo específica para función %s', funcion_objeto.pk)
    # ─────────────────────────────────────────────────────────────────────────

    # Ordenar por prioridad: 1 = máxima prioridad (primero), números altos = menor prioridad (último)
    # En caso de empate, se usa -p.id (IDs más recientes primero)
    politicas_ordenadas = sorted(politicas_para_envio, key=lambda p: (p.prioridad, -p.id))
    
    # Log de ranking de prioridades
    logger.info('='*50)
    logger.info('🏆 RANKING DE PRIORIDADES para funcion %s:', getattr(funcion_objeto, 'pk', None))
    for p in politicas_ordenadas:
        logger.info('   -> %s (Prioridad: %d)', p.nombre, p.prioridad)
    logger.info('='*50)

    # Tomamos la ganadora (la primera de la lista)
    politica = politicas_ordenadas[0]
    # YIELD MANAGEMENT: Filtro de tiempo
    # Si la política define horas_antes_de_funcion, verificar que estemos dentro de la ventana de urgencia.
    # Se omite este chequeo cuando la llamada viene de un intercambio (ignorar_ventana=True),
    # ya que cuando una butaca se libera hay que notificar de inmediato sin importar la antelación.
    if politica.horas_antes_de_funcion and not ignorar_ventana:
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

    # Verificar existencia en VinculoPromocional
    # Para promociones tipo cupón (es_automatica=False): el vínculo no es obligatorio;
    # se verifica solo el genero_requerido si fue configurado.
    # Para promociones automáticas (es_automatica=True): debe tener vínculo explícito.
    es_automatica = getattr(promocion, 'es_automatica', False)
    if es_automatica:
        aplica = VinculoPromocional.objects.filter(promocion=promocion).filter(
            Q(funcion=funcion_objeto) | Q(pelicula=pelicula)
        ).exists()
        if not aplica:
            # Fallback: si no hay vínculo explícito, intentar por genero_requerido
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
    else:
        # Cupón no-automático: verificar solo genero_requerido si está configurado
        genero_req = getattr(promocion, 'genero_requerido', None)
        if genero_req is None:
            aplica = True
        else:
            aplica = pelicula.generos.filter(pk=genero_req.pk).exists()
            if not aplica:
                logger.info('Promo cupón %s: genero_requerido=%s no coincide con géneros de la película', promocion.pk, genero_req)

    logger.info('procesar_butaca_liberada: aplica=%s (es_automatica=%s) para promocion %s', aplica, es_automatica, getattr(promocion, 'pk', None))

    if not aplica:
        respuestas.append({'politica': politica, 'status': 'promo_no_valida'})
        logger.info('promocion %s no aplicable a funcion %s; abortando envio', getattr(promocion, 'pk', None), getattr(funcion_objeto, 'pk', None))
        return respuestas

    # Targeting: buscar clientes con historial y elegibles para cupones.
    # Reglas de elegibilidad de cupones: DNI cargado + consentimiento de marketing/notificaciones.
    candidatos = Cliente.objects.filter(
        ventas__entradas__isnull=False,
        acepta_marketing=True,
        usuario__is_active=True,
        usuario__dni__isnull=False,
    ).exclude(usuario__dni__exact='')
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
    logger.info('[INTERCAMBIO-PROMO] === RESUMEN PRE-ENVÍO ===')
    logger.info('[INTERCAMBIO-PROMO] Política elegida: "%s" (ID=%s, prioridad=%d)',
                politica.nombre, politica.pk, politica.prioridad)
    logger.info('[INTERCAMBIO-PROMO] Promoción a otorgar: "%s" (código=%s, es_automatica=%s)',
                getattr(promocion, 'nombre', 'N/A'), getattr(promocion, 'codigo', 'N/A'),
                getattr(promocion, 'es_automatica', 'N/A'))
    logger.info('[INTERCAMBIO-PROMO] Token UUID: se generará con uuid.uuid4 por defecto del modelo')
    logger.info('[INTERCAMBIO-PROMO] Candidatos encontrados: %d (cliente excluido: %s)',
                total_candidatos, getattr(cliente_excluido, 'pk', None) if cliente_excluido else 'ninguno')
    logger.info('[INTERCAMBIO-PROMO] politicas_match=%s', [p.pk for p in politicas_match])
    if total_candidatos == 0:
        logger.warning('[INTERCAMBIO-PROMO] Sin candidatos. Verificar que existan Clientes con Ventas+Entradas '
                       'que coincidan con género=%s o rango horario [%s - %s].',
                       [g.nombre for g in pelicula_generos], politica.hora_inicio_rango, politica.hora_fin_rango)

    for cliente in candidatos:
        # TODO: DESCOMENTAR EN PRODUCCIÓN - Verificar límite de cupones activos por cliente (max 3)
        # cupones_activos = CuponGenerado.objects.filter(
        #     cliente=cliente,
        #     usado=False,
        #     expira_en__gte=timezone.now()
        # ).count()
        # 
        # if cupones_activos >= 3:
        #     logger.info('Cliente %s ya tiene %d cupones activos, omitiendo envío', 
        #                getattr(cliente, 'pk', None), cupones_activos)
        #     continue
        
        try:
            # Sólo enviar si la promoción asociada no es automática (es_automatica == False).
            # (Chequeo defensivo: politicas_para_envio ya filtró esto, pero por seguridad)
            if getattr(promocion, 'es_automatica', False):
                logger.info('Promocion %s es automática; no se envía email de oferta.', getattr(promocion, 'pk', None))
                continue

            # Usar transaction.atomic() para garantizar que el cupón solo persista
            # si el email se envía correctamente.
            with transaction.atomic():
                # Calcular expiración usando el valor configurado en la política (NO hardcodeado)
                ahora = timezone.now()
                expira = ahora + timedelta(minutes=politica.minutos_validez)

                cupon = CuponGenerado.objects.create(
                    cliente=cliente,
                    politica_origen=politica,
                    expira_en=expira,
                    funcion_origen=funcion_objeto
                )
                logger.info('[INTERCAMBIO-PROMO] Cupón creado: token=%s, cliente=%s, expira=%s',
                            cupon.token, getattr(cliente, 'pk', None), expira)

                # Construir link usando SITE_URL de settings o fallback a localhost
                base = getattr(settings, 'SITE_URL', getattr(settings, 'SITE_BASE_URL', 'https://uncategorized-noncommodiously-floy.ngrok-free.dev')).rstrip('/')
                link = f"{base}/promociones/activar/{cupon.token}"

                logger.info('[INTERCAMBIO-PROMO] Enviando email a cliente=%s (%s) | link=%s',
                            getattr(cliente, 'pk', None),
                            getattr(getattr(cliente, 'usuario', None), 'email', 'sin-email'),
                            link)
                try:
                    sent = notificacion_service.enviar_oferta_promocion(
                        cliente=cliente,
                        promocion=promocion,
                        cupon=cupon,
                        link=link,
                        funcion=funcion_objeto
                    )
                except Exception as email_exc:
                    logger.error('[INTERCAMBIO-PROMO] Excepción al enviar email a cliente=%s: %s',
                                 getattr(cliente, 'pk', None), email_exc, exc_info=True)
                    raise  # propagar para que transaction.atomic() haga rollback del cupón

                if sent:
                    enviados += 1
                    logger.info('[INTERCAMBIO-PROMO] ✅ Email enviado a cliente=%s (cupón=%s)',
                                getattr(cliente, 'pk', None), cupon.token)
                else:
                    # Si falla envío, hacer rollback del cupón creado
                    logger.error('[INTERCAMBIO-PROMO] ❌ notificacion_service retornó False para cliente=%s. '
                                 'Revisar logs de SMTP/template. Haciendo rollback del cupón.',
                                 getattr(cliente, 'pk', None))
                    raise Exception(f"enviar_oferta_promocion retornó False para cliente {getattr(cliente, 'pk', None)}")
        except Exception as e:
            # transaction.atomic() ya hizo rollback del cupón si fue creado.
            # Solo registramos el fallo y continuamos con el siguiente cliente.
            logger.error('[INTERCAMBIO-PROMO] ❌ Fallo procesando cliente=%s: %s',
                         getattr(cliente, 'pk', None), str(e), exc_info=True)

    logger.info('procesar_butaca_liberada resultado: politica=%s promocion=%s candidatos=%d enviados=%d', getattr(politica, 'pk', None), getattr(promocion, 'pk', None), total_candidatos, enviados)
    respuestas.append({'politica': politica, 'status': 'procesada', 'candidatos': total_candidatos, 'enviados': enviados})
    return respuestas
