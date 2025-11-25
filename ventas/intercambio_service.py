"""
Servicio mejorado para la lógica de intercambio de entradas.

Este módulo centraliza toda la lógica de negocio relacionada con intercambios,
incluyendo validaciones, transacciones, auditoría y notificaciones.
"""

import logging
import time
from typing import Tuple, Optional, List
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.utils import timezone

from ventas.models import Venta, Entrada, Intercambio
from ventas.models.politica_reembolso import PoliticaReembolso
from cine.models import Funcion, Butaca
from ventas.constants import EstadoEntrada, ConfigIntercambio, MotivoIntercambio


logger = logging.getLogger(__name__)


class IntercambioError(Exception):
    """Excepción base para errores de intercambio"""
    pass


class IntercambioValidacionError(IntercambioError):
    """Error de validación de reglas de negocio"""
    pass


class IntercambioDisponibilidadError(IntercambioError):
    """Error por falta de disponibilidad"""
    pass


class IntercambioService:
    """
    Servicio que encapsula toda la lógica de intercambio de entradas.
    
    Responsabilidades:
    - Validar políticas y restricciones
    - Gestionar transacciones de DB con retry logic
    - Registrar auditoría (modelo Intercambio)
    - Enviar notificaciones por email
    """
    
    def __init__(self):
        self.logger = logger
    
    def obtener_politica_activa(self) -> Optional[PoliticaReembolso]:
        """Obtiene la política de intercambio activa"""
        try:
            return PoliticaReembolso.objects.filter(activo=True).first()
        except Exception as e:
            self.logger.error(f"Error obteniendo política activa: {e}")
            return None
    
    def validar_intercambio(
        self,
        venta: Venta,
        funcion_destino: Funcion,
        politica: Optional[PoliticaReembolso] = None
    ) -> Tuple[bool, str]:
        """
        Valida si un intercambio es posible según las reglas de negocio.
        
        Args:
            venta: La venta original
            funcion_destino: La función a la que se quiere cambiar
            politica: Política activa (si no se provee, se obtiene automáticamente)
        
        Returns:
            Tuple[bool, str]: (es_valido, mensaje_error)
        """
        # Obtener política si no se proveyó
        if politica is None:
            politica = self.obtener_politica_activa()
        
        # Validar que existe política
        if not politica:
            return (False, 'No hay política de intercambio configurada.')
        
        # Validar política permite intercambios
        if not politica.permitir_intercambio:
            return (False, 'Los intercambios están deshabilitados por la política vigente.')
        
        # Validar venta tiene entradas
        entradas = venta.entradas.filter(estado__in=EstadoEntrada.ESTADOS_ACTIVOS)
        if not entradas.exists():
            return (False, 'La compra no tiene entradas activas para intercambiar.')
        
        # Obtener función original
        funcion_origen = entradas.first().id_funcion
        
        # Validar tiempo de anticipación
        ahora = timezone.now()
        horas_minimas = politica.dias_antes_minimo * 24
        horas_restantes = (funcion_origen.fecha_hora - ahora).total_seconds() / 3600.0
        
        if horas_restantes < horas_minimas:
            return (False, f'Los intercambios requieren al menos {politica.dias_antes_minimo} día(s) de anticipación.')
        
        # Validar que la función destino es futura
        if funcion_destino.fecha_hora <= ahora:
            return (False, 'La función seleccionada ya pasó o está en curso.')
        
        # Validar mismo precio
        if funcion_origen.precio_base != funcion_destino.precio_base:
            return (False, 'Solo puedes intercambiar por funciones del mismo precio.')
        
        # Validar límite de intercambios
        puede, mensaje = Intercambio.puede_intercambiar(venta, politica)
        if not puede:
            return (False, mensaje)
        
        return (True, '')
    
    def verificar_disponibilidad(
        self,
        funcion: Funcion,
        cantidad_requerida: int,
        butacas_seleccionadas: Optional[List[int]] = None
    ) -> Tuple[bool, str, List[Butaca]]:
        """
        Verifica disponibilidad de butacas en una función.
        
        Args:
            funcion: Función objetivo
            cantidad_requerida: Cantidad de butacas necesarias
            butacas_seleccionadas: IDs de butacas específicas (opcional)
        
        Returns:
            Tuple[bool, str, List[Butaca]]: (disponible, mensaje, butacas_disponibles)
        """
        # Obtener butacas ocupadas
        ocupadas_ids = set(
            Entrada.objects.filter(
                id_funcion=funcion,
                estado__in=EstadoEntrada.ESTADOS_OCUPADOS
            ).values_list('id_butaca_id', flat=True)
        )
        
        if butacas_seleccionadas:
            # Validar butacas específicas
            butacas = list(
                Butaca.objects.filter(
                    id__in=butacas_seleccionadas,
                    sala=funcion.sala,
                    es_pasillo=False
                )
            )
            
            if len(butacas) != len(butacas_seleccionadas):
                return (False, 'Algunas butacas seleccionadas no existen.', [])
            
            # Verificar que ninguna esté ocupada
            for butaca in butacas:
                if butaca.id in ocupadas_ids:
                    return (False, f'La butaca {butaca.fila}{butaca.numero} ya está ocupada.', [])
            
            return (True, '', butacas)
        else:
            # Obtener butacas disponibles automáticamente
            disponibles = list(
                Butaca.objects.filter(
                    sala=funcion.sala,
                    es_pasillo=False
                ).exclude(
                    id__in=ocupadas_ids
                ).order_by('fila', 'numero')[:cantidad_requerida]
            )
            
            if len(disponibles) < cantidad_requerida:
                return (
                    False,
                    f'Solo hay {len(disponibles)} butaca(s) disponible(s), se requieren {cantidad_requerida}.',
                    []
                )
            
            return (True, '', disponibles)
    
    def ejecutar_intercambio(
        self,
        venta: Venta,
        funcion_destino: Funcion,
        butacas: List[Butaca],
        motivo: str = MotivoIntercambio.OTRO,
        request=None
    ) -> Tuple[bool, str, Optional[Intercambio]]:
        """
        Ejecuta el intercambio de entradas con retry logic y auditoría completa.
        
        Args:
            venta: Venta a intercambiar
            funcion_destino: Nueva función
            butacas: Lista de butacas asignadas
            motivo: Motivo del intercambio
            request: Request HTTP (para auditoría de IP/user-agent)
        
        Returns:
            Tuple[bool, str, Optional[Intercambio]]: (exitoso, mensaje, registro_intercambio)
        """
        politica = self.obtener_politica_activa()
        
        # Validar antes de intentar
        es_valido, mensaje = self.validar_intercambio(venta, funcion_destino, politica)
        if not es_valido:
            self.logger.warning(f"Validación fallida para venta {venta.id_venta}: {mensaje}")
            return (False, mensaje, None)
        
        # Obtener entradas activas
        entradas_activas = venta.entradas.filter(estado__in=EstadoEntrada.ESTADOS_ACTIVOS)
        funcion_origen = entradas_activas.first().id_funcion
        cantidad = entradas_activas.count()
        
        # Retry logic para manejar race conditions
        for intento in range(ConfigIntercambio.MAX_REINTENTOS):
            try:
                with transaction.atomic():
                    # 1. Lock de butacas seleccionadas
                    butacas_locked = list(
                        Butaca.objects.select_for_update().filter(
                            id__in=[b.id for b in butacas]
                        )
                    )
                    
                    # 2. Verificar nuevamente disponibilidad con lock
                    ocupadas = Entrada.objects.select_for_update().filter(
                        id_funcion=funcion_destino,
                        id_butaca_id__in=[b.id for b in butacas_locked],
                        estado__in=EstadoEntrada.ESTADOS_OCUPADOS
                    ).exists()
                    
                    if ocupadas:
                        raise IntercambioDisponibilidadError(
                            'Una o más butacas fueron ocupadas por otra transacción.'
                        )
                    
                    # 3. Cancelar entradas antiguas
                    entradas_canceladas = entradas_activas.select_for_update().update(
                        estado=EstadoEntrada.CANCELADA
                    )
                    
                    self.logger.info(
                        f"Canceladas {entradas_canceladas} entradas de venta {venta.id_venta}"
                    )
                    
                    # 4. Crear nuevas entradas
                    nuevas_entradas = []
                    for butaca in butacas_locked:
                        # 1. LIMPIEZA: Borramos entradas viejas (zombies) que estorben
                        Entrada.objects.filter(
                            id_funcion=funcion_destino,
                            id_butaca=butaca,
                            estado__in=[EstadoEntrada.CANCELADA, EstadoEntrada.EXPIRADA] 
                        ).delete()
                        # 2. CREACIÓN: Nueva entrada
                        entrada = Entrada.objects.create(
                            id_venta=venta,
                            id_funcion=funcion_destino,
                            id_sala=funcion_destino.sala,
                            id_butaca=butaca,
                            id_pelicula=funcion_destino.pelicula,
                            estado=EstadoEntrada.RESERVADA
                        )
                        nuevas_entradas.append(entrada)
                    
                    self.logger.info(
                        f"Creadas {len(nuevas_entradas)} nuevas entradas para venta {venta.id_venta}"
                    )
                    
                    # 5. Registrar intercambio en auditoría
                    intercambio = Intercambio.objects.create(
                        venta=venta,
                        funcion_origen=funcion_origen,
                        funcion_destino=funcion_destino,
                        motivo=motivo,
                        estado='COMPLETADO',
                        cantidad_entradas=cantidad,
                        penalidad_aplicada=Decimal('0.00'),
                        usuario_email=venta.id_cliente.usuario.email,
                        ip_address=self._get_client_ip(request) if request else None,
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if request else None,
                        notas=f"Intercambio automático de {cantidad} entrada(s)"
                    )
                    
                    self.logger.info(
                        f"Intercambio #{intercambio.id_intercambio} registrado exitosamente"
                    )
                
                # 6. Enviar email de confirmación (fuera de la transacción)
                try:
                    from core.services import notificacion_service
                    notificacion_service.enviar_confirmacion_intercambio(
                        venta=venta,
                        intercambio=intercambio,
                        funcion_origen=funcion_origen,
                        funcion_destino=funcion_destino,
                        request=request
                    )
                except Exception as e:
                    self.logger.error(f"Error enviando email para intercambio {intercambio.id_intercambio}: {e}")
                    # No fallar el intercambio por error de email
                
                # Después del envío de confirmación, procesar butacas liberadas para marketing de recupero
                try:
                    from promociones.services import procesar_butaca_liberada
                    # cliente_excluido: el cliente de la venta que liberó las butacas
                    procesar_butaca_liberada(funcion_origen, cliente_excluido=venta.id_cliente)
                except Exception as e:
                    self.logger.error(f"Error procesando butaca liberada para marketing: {e}")

                return (True, 'Intercambio realizado con éxito.', intercambio)
            
            except IntegrityError as e:
                # Race condition: butaca fue ocupada entre verificación y creación
                self.logger.warning(
                    f"IntegrityError en intento {intento + 1}/{ConfigIntercambio.MAX_REINTENTOS} "
                    f"para venta {venta.id_venta}: {e}"
                )
                
                if intento < ConfigIntercambio.MAX_REINTENTOS - 1:
                    time.sleep(ConfigIntercambio.TIEMPO_REINTENTO)
                    continue
                else:
                    return (False, 'No se pudo completar el intercambio. Por favor, intenta nuevamente.', None)
            
            except IntercambioDisponibilidadError as e:
                self.logger.warning(f"Disponibilidad perdida para venta {venta.id_venta}: {e}")
                return (False, str(e), None)
            
            except Exception as e:
                self.logger.error(f"Error inesperado en intercambio venta {venta.id_venta}: {e}", exc_info=True)
                return (False, f'Error al procesar el intercambio: {str(e)}', None)
        
        return (False, 'No se pudo completar el intercambio después de varios intentos.', None)
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Obtiene la IP del cliente desde el request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Instancia singleton del servicio
intercambio_service = IntercambioService()
