"""
Servicio de lógica de negocio para determinar la mejor promoción aplicable a una función.

Este módulo implementa el algoritmo de validación de promociones automáticas
según las reglas de negocio definidas en los modelos Promocion y Pelicula.
"""

from decimal import Decimal
from django.utils import timezone
from promociones.models.promocion import Promocion


def obtener_mejor_promocion(funcion_obj):
    """
    Determina la mejor promoción automática aplicable a una función dada.
    
    Algoritmo de Validación:
    1. Check Bloqueo: Si funcion.pelicula.acepta_promociones es False → Descartar
    2. Check Día: Si funcion.fecha.weekday() no está en promo.dias_semana → Descartar
    3. Check Estreno: Si funcion.pelicula.es_estreno es True Y promo.aplica_en_estrenos es False → Descartar
    4. Check Género: Si la promo tiene genero_requerido y no coincide con la película → Descartar
    5. Check Vigencia: Si la promo no está vigente en la fecha de la función → Descartar
    
    Args:
        funcion_obj (Funcion): Instancia de Funcion con pelicula, fecha_hora, etc.
    
    Returns:
        Promocion | None: La promoción con mayor beneficio económico, o None si ninguna aplica.
    """
    
    # Check Bloqueo Master: si la película no acepta promociones, retornar None inmediatamente
    if not funcion_obj.pelicula.acepta_promociones:
        return None
    
    # Obtener todas las promociones automáticas activas
    promociones_candidatas = Promocion.objects.filter(es_automatica=True)
    
    # Extraer datos de la función una sola vez
    fecha_funcion = funcion_obj.fecha_hora.date()
    dia_semana = funcion_obj.fecha_hora.weekday()  # 0=Lun, 6=Dom
    pelicula = funcion_obj.pelicula
    es_estreno = pelicula.es_estreno
    
    # Obtener géneros de la película (ManyToMany)
    generos_pelicula = set(pelicula.generos.values_list('pk', flat=True))
    
    promociones_validas = []
    
    for promo in promociones_candidatas:
        # Check Vigencia: la promoción debe estar vigente en la fecha de la función
        if not (promo.fecha_inicio <= fecha_funcion <= promo.fecha_fin):
            continue
        
        # Check Estreno: si la película es estreno y la promo NO aplica en estrenos → descartar
        if es_estreno and not promo.aplica_en_estrenos:
            continue
        
        # Check Género: si la promo requiere un género específico, verificar coincidencia
        if promo.genero_requerido_id is not None:
            if promo.genero_requerido_id not in generos_pelicula:
                continue
        
        # Check Día: obtener días permitidos de PoliticaPromocion relacionadas activas
        # (si la promo es automática, puede estar vinculada a políticas con restricción de días)
        # IMPORTANTE: PoliticaPromocion tiene dias_semana, NO Promocion directamente.
        # Como Promocion no tiene un campo dias_semana directo, debemos buscar las políticas
        # que otorgan esta promoción y verificar si alguna permite este día.
        
        # Buscar políticas activas que otorgan esta promoción
        # Excluir políticas de ocupación automática (esas son solo para el cron)
        from promociones.models.politicaPromocion import PoliticaPromocion
        politicas_asociadas = PoliticaPromocion.objects.filter(
            promocion_a_otorgar=promo,
            activa=True,
            activar_por_ocupacion=False
        )
        
        # Si no hay políticas asociadas, asumimos que la promoción aplica sin restricción de día
        # (esto puede ajustarse según la lógica de negocio requerida)
        if not politicas_asociadas.exists():
            # Sin políticas asociadas: la promoción aplica todos los días
            dias_permitidos = []  # Vacío = todos los días
        else:
            # Consolidar días permitidos de todas las políticas activas
            dias_permitidos = set()
            aplica_todos_dias = False
            for pol in politicas_asociadas:
                dias = pol.get_dias_list()
                if not dias:  # Vacío = todos los días
                    aplica_todos_dias = True
                    break
                dias_permitidos.update(dias)
            
            if not aplica_todos_dias and dia_semana not in dias_permitidos:
                continue  # La promoción no aplica en este día
        
        # Si llegamos aquí, la promoción es válida
        promociones_validas.append(promo)
    
    # Si no hay promociones válidas, retornar None
    if not promociones_validas:
        return None
    
    # Seleccionar la mejor promoción según el beneficio económico
    # Lógica simplificada: ordenar por valor_descuento descendente
    # (en una implementación real, calcular el descuento efectivo según tipo_descuento)
    
    mejor_promo = None
    mayor_beneficio = Decimal('0')
    
    for promo in promociones_validas:
        beneficio = calcular_beneficio(promo, funcion_obj.precio_base)
        if beneficio > mayor_beneficio:
            mayor_beneficio = beneficio
            mejor_promo = promo
    
    return mejor_promo


def calcular_beneficio(promo, precio_base):
    """
    Calcula el beneficio económico de aplicar una promoción a un precio base.
    
    Args:
        promo (Promocion): Instancia de Promocion
        precio_base (Decimal): Precio base de la entrada
    
    Returns:
        Decimal: Monto de descuento aplicado (para comparación)
    """
    if promo.tipo_descuento == 'PORCENTAJE':
        # valor_descuento es un porcentaje (0-100)
        if promo.valor_descuento:
            return (precio_base * promo.valor_descuento / Decimal('100'))
        return Decimal('0')
    
    elif promo.tipo_descuento == 'MONTO_FIJO':
        # valor_descuento es un monto fijo a descontar
        if promo.valor_descuento:
            return min(promo.valor_descuento, precio_base)  # No puede superar el precio
        return Decimal('0')
    
    elif promo.tipo_descuento == '2X1':
        # Descuento de 50% efectivo (un 50% del precio base)
        return precio_base * Decimal('0.5')
    
    return Decimal('0')
