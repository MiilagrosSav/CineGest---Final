"""
Script para probar el sistema de notificaciones de CineGest.

Uso:
    python test_notificaciones.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
django.setup()

from core.services import notificacion_service
from accounts.models import Usuario, Cliente
from ventas.models import Venta, Intercambio
from cine.models import Funcion


def test_email_bienvenida():
    """Prueba el email de bienvenida"""
    print("\n" + "="*60)
    print("PROBANDO EMAIL DE BIENVENIDA")
    print("="*60)
    
    # Buscar un usuario de prueba
    usuario = Usuario.objects.filter(is_superuser=False).first()
    
    if not usuario:
        print("❌ No se encontró ningún usuario para probar")
        print("   Crea un usuario primero desde el admin o con createsuperuser")
        return False
    
    print(f"✅ Usuario encontrado: {usuario.username} ({usuario.email})")
    print(f"   Enviando email de bienvenida...")
    
    try:
        resultado = notificacion_service.enviar_bienvenida(usuario)
        if resultado:
            print(f"✅ Email de bienvenida enviado correctamente")
            print(f"   Revisa MailCrab en http://localhost:1080")
            return True
        else:
            print("❌ El email no se pudo enviar")
            return False
    except Exception as e:
        print(f"❌ Error al enviar email: {e}")
        return False


def test_email_compra():
    """Prueba el email de confirmación de compra"""
    print("\n" + "="*60)
    print("PROBANDO EMAIL DE CONFIRMACIÓN DE COMPRA")
    print("="*60)
    
    # Buscar una venta reciente
    venta = Venta.objects.filter(
        tipo_venta='VENTA'
    ).prefetch_related('entradas').order_by('-fecha_compra').first()

    # Si no hay ventas, intentar crear una venta de prueba automáticamente
    if not venta:
        print("⚠️ No se encontró ninguna venta. Intentando crear una venta de prueba automática...")
        try:
            from django.utils import timezone
            from cine.models.butaca import Butaca
            from ventas.models.entrada import Entrada

            cliente = Cliente.objects.first()
            funcion_obj = Funcion.objects.filter(fecha_hora__gt=timezone.now()).first()

            if not cliente or not funcion_obj:
                print("❌ No hay Cliente o Función disponible para crear la venta de prueba.")
                print("   Crea al menos un cliente y una función con butacas en el admin.")
                return False

            # Buscar una butaca disponible en alguna función futura
            butaca = None
            funcion_elegida = None
            funciones_futuras = Funcion.objects.filter(fecha_hora__gt=timezone.now()).order_by('fecha_hora')
            for f in funciones_futuras:
                butacas_en_sala = Butaca.objects.filter(sala=f.sala, es_pasillo=False)
                for b in butacas_en_sala:
                    if not Entrada.objects.filter(id_funcion=f, id_butaca=b).exists():
                        funcion_elegida = f
                        butaca = b
                        break
                if butaca:
                    break

            if not butaca or not funcion_elegida:
                print("❌ No hay butacas libres en funciones futuras para crear la entrada de prueba.")
                return False

            # Usar la función y la butaca encontradas
            funcion_obj = funcion_elegida

            # Crear la venta de prueba
            venta = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='ONLINE',
                estado='CONFIRMADA'
            )

            # Crear una entrada asociada
            entrada = Entrada.objects.create(
                id_venta=venta,
                id_funcion=funcion_obj,
                id_sala=funcion_obj.sala,
                id_butaca=butaca,
                id_pelicula=funcion_obj.pelicula,
                estado='VENDIDA'
            )

            print(f"✅ Venta de prueba creada: #{venta.id_venta} - Entrada #{entrada.id_entrada} (Butaca {butaca})")
        except Exception as e:
            print(f"❌ Error creando venta de prueba: {e}")
            import traceback
            traceback.print_exc()
            return False

    print(f"✅ Venta encontrada: #{venta.id_venta}")
    print(f"   Cliente: {venta.id_cliente.usuario.email}")
    print(f"   Enviando email de confirmación de compra...")

    try:
        resultado = notificacion_service.enviar_confirmacion_compra(venta)
        if resultado:
            print(f"✅ Email de confirmación enviado correctamente")
            print(f"   Revisa MailCrab en http://localhost:1080")
            return True
        else:
            print("❌ El email no se pudo enviar")
            return False
    except Exception as e:
        print(f"❌ Error al enviar email: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_intercambio():
    """Prueba el email de confirmación de intercambio"""
    print("\n" + "="*60)
    print("PROBANDO EMAIL DE CONFIRMACIÓN DE INTERCAMBIO")
    print("="*60)
    
    # Buscar un intercambio reciente
    intercambio = Intercambio.objects.select_related(
        'venta',
        'funcion_origen',
        'funcion_destino'
    ).order_by('-fecha_intercambio').first()
    
    if not intercambio:
        print("❌ No se encontró ningún intercambio para probar")
        print("   Realiza un intercambio primero desde la aplicación")
        return False
    
    print(f"✅ Intercambio encontrado: #{intercambio.id_intercambio}")
    print(f"   Venta: #{intercambio.venta.id_venta}")
    print(f"   Cliente: {intercambio.usuario_email}")
    print(f"   Enviando email de confirmación de intercambio...")
    
    try:
        resultado = notificacion_service.enviar_confirmacion_intercambio(
            venta=intercambio.venta,
            intercambio=intercambio,
            funcion_origen=intercambio.funcion_origen,
            funcion_destino=intercambio.funcion_destino
        )
        if resultado:
            print(f"✅ Email de intercambio enviado correctamente")
            print(f"   Revisa MailCrab en http://localhost:1080")
            return True
        else:
            print("❌ El email no se pudo enviar")
            return False
    except Exception as e:
        print(f"❌ Error al enviar email: {e}")
        import traceback
        traceback.print_exc()
        return False


def verificar_mailcrab():
    """Verifica que MailCrab esté corriendo"""
    import socket
    
    print("\n" + "="*60)
    print("VERIFICANDO MAILCRAB")
    print("="*60)
    
    try:
        # Intentar conectar al puerto SMTP de MailCrab
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        resultado = sock.connect_ex(('localhost', 1025))
        sock.close()
        
        if resultado == 0:
            print("✅ MailCrab está corriendo en puerto 1025 (SMTP)")
            print("✅ Web UI disponible en http://localhost:1080")
            return True
        else:
            print("❌ MailCrab NO está corriendo")
            print("   Inicia MailCrab con:")
            print("   docker run --name mailcrab -p 1080:1080 -p 1025:1025 -d marlonb/mailcrab:latest")
            return False
    except Exception as e:
        print(f"❌ Error verificando MailCrab: {e}")
        return False


def main():
    """Función principal"""
    print("\n" + "="*60)
    print("🧪 TEST DE SISTEMA DE NOTIFICACIONES - CINEGEST")
    print("="*60)
    
    # 1. Verificar MailCrab
    if not verificar_mailcrab():
        print("\n⚠️  Detén la ejecución si MailCrab no está corriendo")
        respuesta = input("¿Continuar de todas formas? (s/n): ")
        if respuesta.lower() != 's':
            return
    
    # 2. Probar emails
    resultados = {
        'bienvenida': test_email_bienvenida(),
        'compra': test_email_compra(),
        'intercambio': test_email_intercambio(),
    }
    
    # 3. Resumen
    print("\n" + "="*60)
    print("RESUMEN DE PRUEBAS")
    print("="*60)
    
    for tipo, resultado in resultados.items():
        icono = "✅" if resultado else "❌"
        print(f"{icono} Email de {tipo}: {'OK' if resultado else 'FALLÓ'}")
    
    exitosos = sum(resultados.values())
    total = len(resultados)
    
    print(f"\n📊 Resultado: {exitosos}/{total} pruebas exitosas")
    
    if exitosos == total:
        print("🎉 ¡Todas las pruebas pasaron!")
    elif exitosos > 0:
        print("⚠️  Algunas pruebas fallaron. Revisa los detalles arriba.")
    else:
        print("❌ Todas las pruebas fallaron. Verifica la configuración.")
    
    print("\n" + "="*60)
    print("📧 Revisa los emails en: http://localhost:1080")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
