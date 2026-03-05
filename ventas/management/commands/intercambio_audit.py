"""
Management command para consultar datos de auditoría de intercambios.

Uso:
    python manage.py intercambio_audit <intercambio_id>
    python manage.py intercambio_audit --user email@ejemplo.com
    python manage.py intercambio_audit --export
    python manage.py intercambio_audit --detect-suspicious
"""

from django.core.management.base import BaseCommand, CommandError
from ventas.models import Intercambio
from ventas.utils.audit_helpers import (
    get_intercambio_audit_data,
    get_user_intercambios_with_audit,
    export_intercambios_audit_csv,
    detectar_intercambios_sospechosos,
    print_intercambio_audit_report
)


class Command(BaseCommand):
    help = 'Consulta datos de auditoría de intercambios desde django-simple-history'

    def add_arguments(self, parser):
        # Argumento posicional: ID del intercambio
        parser.add_argument(
            'intercambio_id',
            nargs='?',
            type=int,
            help='ID del intercambio a consultar'
        )
        
        # Opciones
        parser.add_argument(
            '--user',
            type=str,
            help='Email del usuario para ver todos sus intercambios'
        )
        
        parser.add_argument(
            '--export',
            action='store_true',
            help='Exportar todos los intercambios a CSV'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            default='intercambios_audit.csv',
            help='Nombre del archivo CSV de salida (default: intercambios_audit.csv)'
        )
        
        parser.add_argument(
            '--detect-suspicious',
            action='store_true',
            help='Detectar actividad sospechosa (múltiples usuarios desde misma IP, etc.)'
        )
        
        parser.add_argument(
            '--ip',
            type=str,
            help='Buscar intercambios desde una IP específica'
        )
    
    def handle(self, *args, **options):
        # Opción 1: Ver intercambio específico
        if options['intercambio_id']:
            self.show_intercambio_audit(options['intercambio_id'])
        
        # Opción 2: Ver intercambios de un usuario
        elif options['user']:
            self.show_user_intercambios(options['user'])
        
        # Opción 3: Exportar a CSV
        elif options['export']:
            self.export_to_csv(options['output'])
        
        # Opción 4: Detectar actividad sospechosa
        elif options['detect_suspicious']:
            self.detect_suspicious()
        
        # Opción 5: Buscar por IP
        elif options['ip']:
            self.find_by_ip(options['ip'])
        
        else:
            self.stdout.write(self.style.WARNING('Uso: python manage.py intercambio_audit <intercambio_id>'))
            self.stdout.write('Opciones disponibles:')
            self.stdout.write('  --user <email>         Ver intercambios de un usuario')
            self.stdout.write('  --export               Exportar todos a CSV')
            self.stdout.write('  --detect-suspicious    Detectar actividad sospechosa')
            self.stdout.write('  --ip <ip_address>      Buscar por IP')
    
    def show_intercambio_audit(self, intercambio_id):
        """Muestra auditoría completa de un intercambio"""
        try:
            print_intercambio_audit_report(intercambio_id)
        except Intercambio.DoesNotExist:
            raise CommandError(f'Intercambio #{intercambio_id} no existe')
    
    def show_user_intercambios(self, email):
        """Muestra todos los intercambios de un usuario con auditoría"""
        intercambios = get_user_intercambios_with_audit(email)
        
        if not intercambios:
            self.stdout.write(self.style.WARNING(f'No se encontraron intercambios para {email}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n🔍 Intercambios de {email}: {len(intercambios)} encontrados\n'))
        
        for i in intercambios:
            self.stdout.write(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.stdout.write(f"ID: #{i['id']} | {i['fecha'].strftime('%d/%m/%Y %H:%M')}")
            self.stdout.write(f"Venta: #{i['venta_id']}")
            self.stdout.write(f"Estado: {i['estado']} | Motivo: {i['motivo']}")
            self.stdout.write(f"Función origen:  {i['funcion_origen']}")
            self.stdout.write(f"Función destino: {i['funcion_destino']}")
            
            # Auditoría
            self.stdout.write(self.style.WARNING('\n📋 Auditoría:'))
            self.stdout.write(f"  IP: {i['ip'] or '(no disponible)'}")
            self.stdout.write(f"  Usuario Django: {i['created_by'] or '(no disponible)'}")
            
            if i['user_agent']:
                ua_short = i['user_agent'][:60] + '...' if len(i['user_agent']) > 60 else i['user_agent']
                self.stdout.write(f"  User-Agent: {ua_short}")
            
            self.stdout.write("")
    
    def export_to_csv(self, output_path):
        """Exporta intercambios a CSV"""
        self.stdout.write(f'Exportando intercambios a {output_path}...')
        
        try:
            count = export_intercambios_audit_csv(output_path)
            self.stdout.write(self.style.SUCCESS(f'✅ {count} intercambios exportados exitosamente'))
            self.stdout.write(f'Archivo: {output_path}')
        except Exception as e:
            raise CommandError(f'Error al exportar: {e}')
    
    def detect_suspicious(self):
        """Detecta actividad sospechosa"""
        self.stdout.write('🔍 Analizando intercambios en busca de actividad sospechosa...\n')
        
        results = detectar_intercambios_sospechosos()
        
        # Múltiples usuarios desde misma IP
        multi_users = results['multiple_users_same_ip']
        if multi_users:
            self.stdout.write(self.style.WARNING(f'⚠️  IPs con múltiples usuarios ({len(multi_users)}):'))
            for ip, users in multi_users[:10]:  # Top 10
                self.stdout.write(f'  {ip}: {len(users)} usuarios diferentes')
                for user in users[:5]:  # Primeros 5
                    self.stdout.write(f'    - {user}')
                if len(users) > 5:
                    self.stdout.write(f'    ... y {len(users) - 5} más')
            self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('✅ No se encontraron IPs con múltiples usuarios'))
        
        # Alto volumen desde mismas IPs
        high_freq = results['high_frequency_ips']
        if high_freq:
            self.stdout.write(self.style.WARNING(f'⚠️  IPs con alto volumen de intercambios ({len(high_freq)}):'))
            for ip, count in high_freq[:10]:  # Top 10
                self.stdout.write(f'  {ip}: {count} intercambios')
            self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('✅ No se encontraron IPs con alto volumen'))
        
        if not multi_users and not high_freq:
            self.stdout.write(self.style.SUCCESS('\n✅ No se detectó actividad sospechosa'))
    
    def find_by_ip(self, ip_address):
        """Busca intercambios por IP"""
        from ventas.utils.audit_helpers import find_intercambios_by_ip
        
        self.stdout.write(f'🔍 Buscando intercambios desde IP {ip_address}...\n')
        
        results = find_intercambios_by_ip(ip_address)
        
        if not results:
            self.stdout.write(self.style.WARNING(f'No se encontraron intercambios desde {ip_address}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'✅ {len(results)} intercambios encontrados:\n'))
        
        for intercambio in results:
            self.stdout.write(f"ID: #{intercambio.id_intercambio}")
            self.stdout.write(f"  Fecha: {intercambio.fecha_intercambio.strftime('%d/%m/%Y %H:%M')}")
            self.stdout.write(f"  Usuario: {intercambio.usuario_email}")
            self.stdout.write(f"  Venta: #{intercambio.venta.id_venta}")
            self.stdout.write(f"  Estado: {intercambio.estado}")
            self.stdout.write("")
