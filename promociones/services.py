from decimal import Decimal
from django.utils import timezone
from django.db import models


def calcular_precio_final(funcion, cantidad_entradas):
    """
    Calcula el precio final para una función y una cantidad de entradas aplicando
    promociones automáticas vinculadas mediante FuncionPromocion.

    Retorna una tupla: (total_decimal, promocion_aplicada_or_None, detalle_dict)
    detalle_dict incluye keys: 'precio_unitario_final', 'tipo_aplicado', 'descripcion'
    """
    from promociones.models.funcionPromocion import FuncionPromocion
    from promociones.models.promocion import Promocion
    from promociones.models.politicaPromocion import PoliticaPromocion
    from decimal import Decimal, ROUND_HALF_UP

    precio_base = Decimal(funcion.precio_base)
    cantidad = int(cantidad_entradas)
    hoy = timezone.localdate()
    ahora = funcion.fecha_hora

    # Buscar promociones automáticas vinculadas a la función o a su película
    candidatos_qs = FuncionPromocion.objects.filter(
        models.Q(funcion=funcion) | models.Q(pelicula=funcion.pelicula),
        promocion__es_automatica=True
    ).select_related('promocion')

    mejores = []  # lista de tuples (total, promocion, detalle)

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
            # cada par paga 1 entrada
            pares = cantidad // 2
            restantes = cantidad - pares * 2
            total = (precio_base * (pares + restantes)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
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

    # Ordenar por prioridad descendente y tomar la primera
    politica = sorted(politicas_match, key=lambda p: p.prioridad, reverse=True)[0]

    promocion = politica.promocion_a_otorgar

    # Verificar existencia en FuncionPromocion
    aplica = FuncionPromocion.objects.filter(promocion=promocion).filter(
        Q(funcion=funcion_objeto) | Q(pelicula=pelicula)
    ).exists()

    if not aplica:
        respuestas.append({'politica': politica, 'status': 'promo_no_valida'})
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
    for cliente in candidatos:
        # calcular expiración
        ahora = timezone.now()
        expira = ahora + timedelta(minutes=getattr(politica, 'minutos_validez', 60))

        cupon = CuponGenerado.objects.create(
            cliente=cliente,
            politica_origen=politica,
            expira_en=expira
        )

        # Construir link (fallback local si no hay setting)
        base = getattr(settings, 'SITE_BASE_URL', 'http://localhost:8000')
        link = f"{base}/promociones/redeem/{cupon.token}"

        # Envío usando NotificacionService y plantillas HTML/texto
        try:
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
            pass

    respuestas.append({'politica': politica, 'status': 'procesada', 'candidatos': candidatos.count(), 'enviados': enviados})
    return respuestas
