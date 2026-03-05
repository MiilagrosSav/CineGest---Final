"""
Utilidad para consultar datos de auditoría (IP, User-Agent) desde django-simple-history.

Uso:
    from ventas.utils.audit_helpers import get_intercambio_audit_data
    
    data = get_intercambio_audit_data(intercambio_id=123)
    print(data['ip'])
    print(data['user_agent'])
"""

from typing import Dict, Optional, Any
from django.utils import timezone


def get_intercambio_audit_data(intercambio_id: int) -> Dict[str, Any]:
    """
    Obtiene datos completos de auditoría de un intercambio desde django-simple-history.
    
    Args:
        intercambio_id: ID del intercambio a consultar
    
    Returns:
        dict con claves:
            - ip: str o None
            - user_agent: str o None
            - created_by: User o None
            - created_at: datetime
            - modified_count: int (número de veces que se modificó)
            - last_modified_at: datetime o None
            - last_modified_by: User o None
    
    Raises:
        Intercambio.DoesNotExist: Si el intercambio no existe
    """
    from ventas.models import Intercambio
    
    intercambio = Intercambio.objects.get(id_intercambio=intercambio_id)
    
    # Obtener registro de creación (history_type = '+')
    creation_history = intercambio.history.filter(history_type='+').first()
    
    # Obtener última modificación (si existe)
    last_update = intercambio.history.filter(history_type='~').first()
    
    return {
        'ip': getattr(creation_history, '_request_ip', None) if creation_history else None,
        'user_agent': getattr(creation_history, '_request_user_agent', None) if creation_history else None,
        'created_by': creation_history.history_user if creation_history else None,
        'created_at': creation_history.history_date if creation_history else None,
        'modified_count': intercambio.history.filter(history_type='~').count(),
        'last_modified_at': last_update.history_date if last_update else None,
        'last_modified_by': last_update.history_user if last_update else None,
    }


def get_intercambio_creation_ip(intercambio_id: int) -> Optional[str]:
    """
    Obtiene solo la IP de creación de un intercambio.
    
    Args:
        intercambio_id: ID del intercambio
    
    Returns:
        str: IP address o None si no está disponible
    """
    data = get_intercambio_audit_data(intercambio_id)
    return data['ip']


def get_user_intercambios_with_audit(email: str) -> list:
    """
    Obtiene todos los intercambios de un usuario con datos de auditoría.
    
    Args:
        email: Email del usuario
    
    Returns:
        list de dict con datos de intercambio + auditoría
    """
    from ventas.models import Intercambio
    
    intercambios = Intercambio.objects.filter(usuario_email=email).order_by('-fecha_intercambio')
    
    result = []
    for intercambio in intercambios:
        audit_data = get_intercambio_audit_data(intercambio.id_intercambio)
        
        result.append({
            'id': intercambio.id_intercambio,
            'fecha': intercambio.fecha_intercambio,
            'venta_id': intercambio.venta.id_venta,
            'funcion_origen': str(intercambio.funcion_origen),
            'funcion_destino': str(intercambio.funcion_destino),
            'estado': intercambio.estado,
            'motivo': intercambio.get_motivo_display(),
            # Auditoría
            'ip': audit_data['ip'],
            'user_agent': audit_data['user_agent'],
            'created_by': str(audit_data['created_by']) if audit_data['created_by'] else None,
        })
    
    return result


def export_intercambios_audit_csv(output_path: str = 'intercambios_audit.csv'):
    """
    Exporta todos los intercambios con datos de auditoría a CSV.
    
    Args:
        output_path: Ruta del archivo CSV a generar
    
    Returns:
        int: Número de intercambios exportados
    """
    import csv
    from ventas.models import Intercambio
    
    intercambios = Intercambio.objects.all().order_by('-fecha_intercambio')
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Headers
        writer.writerow([
            'ID Intercambio',
            'Venta ID',
            'Fecha Intercambio',
            'Usuario Email',
            'IP',
            'User Agent',
            'Función Origen',
            'Función Destino',
            'Motivo',
            'Estado',
            'Cantidad Entradas',
            'Creado Por (Usuario Django)'
        ])
        
        # Data
        for intercambio in intercambios:
            audit_data = get_intercambio_audit_data(intercambio.id_intercambio)
            
            writer.writerow([
                intercambio.id_intercambio,
                intercambio.venta.id_venta,
                intercambio.fecha_intercambio.strftime('%Y-%m-%d %H:%M:%S'),
                intercambio.usuario_email,
                audit_data['ip'] or '',
                audit_data['user_agent'] or '',
                str(intercambio.funcion_origen),
                str(intercambio.funcion_destino),
                intercambio.get_motivo_display(),
                intercambio.estado,
                intercambio.cantidad_entradas,
                str(audit_data['created_by']) if audit_data['created_by'] else '',
            ])
    
    return intercambios.count()


def find_intercambios_by_ip(ip_address: str) -> list:
    """
    Encuentra intercambios realizados desde una IP específica.
    
    NOTA: Requiere que HistoryRequestMiddleware esté activo.
    
    Args:
        ip_address: IP a buscar (ej: "192.168.1.1")
    
    Returns:
        list de Intercambio objects
    """
    from ventas.models import Intercambio
    
    # Obtener todos los intercambios
    intercambios = Intercambio.objects.all()
    
    # Filtrar por IP usando history
    matches = []
    for intercambio in intercambios:
        audit_data = get_intercambio_audit_data(intercambio.id_intercambio)
        if audit_data['ip'] == ip_address:
            matches.append(intercambio)
    
    return matches


def detectar_intercambios_sospechosos():
    """
    Detecta posibles intercambios sospechosos (misma IP, múltiples usuarios).
    
    Returns:
        dict: {
            'multiple_users_same_ip': list de (ip, usernames),
            'high_frequency_ips': list de (ip, count)
        }
    """
    from ventas.models import Intercambio
    from collections import defaultdict
    
    ip_to_users = defaultdict(set)
    ip_counts = defaultdict(int)
    
    intercambios = Intercambio.objects.all()
    
    for intercambio in intercambios:
        audit_data = get_intercambio_audit_data(intercambio.id_intercambio)
        ip = audit_data['ip']
        
        if ip:
            ip_to_users[ip].add(intercambio.usuario_email)
            ip_counts[ip] += 1
    
    # IPs con múltiples usuarios diferentes
    multiple_users = [
        (ip, list(users)) 
        for ip, users in ip_to_users.items() 
        if len(users) > 1
    ]
    
    # IPs con alto volumen (>10 intercambios)
    high_frequency = [
        (ip, count) 
        for ip, count in ip_counts.items() 
        if count > 10
    ]
    
    return {
        'multiple_users_same_ip': multiple_users,
        'high_frequency_ips': sorted(high_frequency, key=lambda x: x[1], reverse=True)
    }


# ============================================================================
# MANAGEMENT COMMAND HELPERS
# ============================================================================

def print_intercambio_audit_report(intercambio_id: int):
    """
    Imprime reporte legible de auditoría para un intercambio.
    
    Útil para debugging y soporte al cliente.
    """
    from ventas.models import Intercambio
    
    intercambio = Intercambio.objects.get(id_intercambio=intercambio_id)
    audit_data = get_intercambio_audit_data(intercambio_id)
    
    print("=" * 70)
    print(f"REPORTE DE AUDITORÍA - Intercambio #{intercambio_id}")
    print("=" * 70)
    
    print(f"\n📋 INFORMACIÓN BÁSICA:")
    print(f"   Venta: #{intercambio.venta.id_venta}")
    print(f"   Usuario: {intercambio.usuario_email}")
    print(f"   Fecha: {intercambio.fecha_intercambio.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"   Estado: {intercambio.estado}")
    print(f"   Motivo: {intercambio.get_motivo_display()}")
    
    print(f"\n🎬 FUNCIONES:")
    print(f"   Origen:  {intercambio.funcion_origen}")
    print(f"   Destino: {intercambio.funcion_destino}")
    print(f"   Cantidad entradas: {intercambio.cantidad_entradas}")
    
    print(f"\n🔍 AUDITORÍA (django-simple-history):")
    print(f"   IP de creación: {audit_data['ip'] or '(no disponible)'}")
    print(f"   User-Agent: {audit_data['user_agent'][:80] if audit_data['user_agent'] else '(no disponible)'}")
    print(f"   Creado por (usuario Django): {audit_data['created_by'] or '(no disponible)'}")
    print(f"   Fecha de creación: {audit_data['created_at']}")
    
    print(f"\n📝 HISTORIAL DE CAMBIOS:")
    print(f"   Modificaciones: {audit_data['modified_count']}")
    if audit_data['modified_count'] > 0:
        print(f"   Última modificación: {audit_data['last_modified_at']}")
        print(f"   Modificado por: {audit_data['last_modified_by']}")
    
    # Mostrar historial completo
    print(f"\n📚 HISTORIAL DETALLADO:")
    for idx, history in enumerate(intercambio.history.all(), 1):
        symbol = {'+': '✨ CREADO', '~': '✏️ ACTUALIZADO', '-': '🗑️ ELIMINADO'}.get(history.history_type, history.history_type)
        print(f"   {idx}. {symbol}")
        print(f"      Fecha: {history.history_date.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"      Usuario: {history.history_user or '(sistema)'}")
        if history.history_change_reason:
            print(f"      Razón: {history.history_change_reason}")
    
    print("\n" + "=" * 70)


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == '__main__':
    """
    Ejemplos de uso de las funciones de auditoría.
    
    Ejecutar con: python manage.py shell < ventas/utils/audit_helpers.py
    """
    
    # Ejemplo 1: Obtener datos de auditoría de un intercambio
    # data = get_intercambio_audit_data(123)
    # print(f"IP: {data['ip']}")
    
    # Ejemplo 2: Exportar a CSV
    # count = export_intercambios_audit_csv('intercambios_2026.csv')
    # print(f"Exportados {count} intercambios")
    
    # Ejemplo 3: Buscar intercambios por IP
    # results = find_intercambios_by_ip('192.168.1.100')
    # for i in results:
    #     print(f"Intercambio #{i.id_intercambio} - {i.usuario_email}")
    
    # Ejemplo 4: Detectar actividad sospechosa
    # sospechosos = detectar_intercambios_sospechosos()
    # print("IPs con múltiples usuarios:", sospechosos['multiple_users_same_ip'])
    
    # Ejemplo 5: Reporte completo
    # print_intercambio_audit_report(123)
    
    print("✅ Helpers de auditoría cargados correctamente")
    print("📚 Ver documentación en el archivo para ejemplos de uso")
