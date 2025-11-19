"""
Script para verificar la instalación y configuración del sistema de intercambio

Ejecutar con: python manage.py shell < check_intercambio.py
o
python manage.py shell
>>> exec(open('check_intercambio.py').read())
"""

def verificar_sistema_intercambio():
    """Verifica que todos los componentes estén correctamente instalados"""
    
    print("=" * 70)
    print("🔍 VERIFICACIÓN DEL SISTEMA DE INTERCAMBIO")
    print("=" * 70)
    print()
    
    errores = []
    warnings = []
    
    # 1. Verificar imports
    print("1️⃣  Verificando imports...")
    try:
        from ventas.models import Intercambio
        print("   ✅ Modelo Intercambio importado")
    except ImportError as e:
        errores.append(f"❌ No se puede importar Intercambio: {e}")
        print(f"   ❌ Error: {e}")
    
    try:
        from ventas.constants import EstadoEntrada, MotivoIntercambio, ConfigIntercambio
        print("   ✅ Constantes importadas")
    except ImportError as e:
        errores.append(f"❌ No se pueden importar constantes: {e}")
        print(f"   ❌ Error: {e}")
    
    try:
        from ventas.intercambio_service import intercambio_service
        print("   ✅ IntercambioService importado")
    except ImportError as e:
        errores.append(f"❌ No se puede importar IntercambioService: {e}")
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 2. Verificar tabla en DB
    print("2️⃣  Verificando base de datos...")
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ventas_intercambio'"
            )
            result = cursor.fetchone()
            if result:
                print("   ✅ Tabla ventas_intercambio existe")
            else:
                errores.append("❌ Tabla ventas_intercambio no existe")
                print("   ❌ Tabla no existe - ejecuta: python manage.py migrate")
    except Exception as e:
        warnings.append(f"⚠️  No se pudo verificar tabla (puede ser PostgreSQL): {e}")
        print(f"   ⚠️  {e}")
    
    print()
    
    # 3. Verificar configuración de email
    print("3️⃣  Verificando configuración de email...")
    try:
        from django.conf import settings
        
        print(f"   📧 EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        print(f"   📧 EMAIL_HOST: {settings.EMAIL_HOST}")
        print(f"   📧 EMAIL_PORT: {settings.EMAIL_PORT}")
        print(f"   📧 DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        
        if settings.EMAIL_HOST == 'localhost' and settings.EMAIL_PORT == 1025:
            print("   ✅ Configurado para MailCrab")
            print("   💡 Recuerda iniciar MailCrab: mailcrab")
        else:
            warnings.append("⚠️  No está configurado para MailCrab")
    except Exception as e:
        errores.append(f"❌ Error en configuración de email: {e}")
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 4. Verificar política activa
    print("4️⃣  Verificando políticas de intercambio...")
    try:
        from ventas.models import PoliticaReembolso
        
        politicas_activas = PoliticaReembolso.objects.filter(activo=True)
        count = politicas_activas.count()
        
        if count == 0:
            warnings.append("⚠️  No hay políticas activas")
            print("   ⚠️  No hay políticas activas")
            print("   💡 Crea una desde /admin/ventas/politicareembolso/")
        elif count == 1:
            politica = politicas_activas.first()
            print(f"   ✅ Política activa: {politica.nombre}")
            print(f"      - Permite intercambio: {politica.permitir_intercambio}")
            print(f"      - Días mínimos: {politica.dias_antes_minimo}")
            print(f"      - Max cambios: {politica.max_cambios_por_compra}")
        else:
            warnings.append(f"⚠️  Hay {count} políticas activas (debería ser 1)")
            print(f"   ⚠️  Hay {count} políticas activas")
    except Exception as e:
        errores.append(f"❌ Error verificando políticas: {e}")
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 5. Test de servicio
    print("5️⃣  Probando IntercambioService...")
    try:
        from ventas.intercambio_service import intercambio_service
        
        politica = intercambio_service.obtener_politica_activa()
        if politica:
            print(f"   ✅ Servicio puede obtener política: {politica.nombre}")
        else:
            print("   ⚠️  Servicio no encuentra política activa")
        
        # Test de constantes
        from ventas.constants import EstadoEntrada
        print(f"   ✅ Constantes disponibles: {len(EstadoEntrada.ESTADOS_OCUPADOS)} estados ocupados")
        
    except Exception as e:
        errores.append(f"❌ Error probando servicio: {e}")
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 6. Verificar templates (ahora en core app)
    print("6️⃣  Verificando templates de email...")
    try:
        from django.template.loader import get_template
        
        html_template = get_template('core/emails/confirmacion_intercambio.html')
        txt_template = get_template('core/emails/confirmacion_intercambio.txt')
        
        print("   ✅ Template HTML encontrado (core/emails)")
        print("   ✅ Template TXT encontrado (core/emails)")
    except Exception as e:
        errores.append(f"❌ Templates de email no encontrados: {e}")
        print(f"   ❌ Error: {e}")
    
    print()
    
    # 7. Test de email (opcional)
    print("7️⃣  Test de envío de email...")
    respuesta = input("   ¿Quieres probar envío de email? (s/n): ").lower().strip()
    if respuesta == 's':
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            send_mail(
                '✅ Test Sistema de Intercambio',
                'Si recibes este email, la configuración está correcta.',
                settings.DEFAULT_FROM_EMAIL,
                ['test@example.com'],
            )
            print("   ✅ Email enviado")
            print("   💡 Verifica en http://localhost:1080 (MailCrab)")
        except Exception as e:
            errores.append(f"❌ Error enviando email: {e}")
            print(f"   ❌ Error: {e}")
    else:
        print("   ⏭️  Test de email omitido")
    
    print()
    print("=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)
    
    if not errores and not warnings:
        print("✅ TODO CORRECTO - Sistema listo para usar")
    else:
        if errores:
            print(f"\n❌ ERRORES CRÍTICOS ({len(errores)}):")
            for error in errores:
                print(f"   {error}")
        
        if warnings:
            print(f"\n⚠️  ADVERTENCIAS ({len(warnings)}):")
            for warning in warnings:
                print(f"   {warning}")
    
    print()
    print("📚 Próximos pasos:")
    print("   1. Si hay errores, ejecuta: python manage.py migrate")
    print("   2. Si no hay política, créala en /admin/ventas/politicareembolso/")
    print("   3. Inicia MailCrab: mailcrab")
    print("   4. Inicia servidor: python manage.py runserver")
    print("   5. Prueba el flujo de intercambio")
    print()
    print("📖 Ver documentación completa en:")
    print("   - docs/INTERCAMBIO_MEJORES_PRACTICAS.md")
    print("   - docs/MAILCRAB_SETUP.md")
    print("   - docs/MIGRACION_INTERCAMBIO.md")
    print()


if __name__ == '__main__':
    verificar_sistema_intercambio()
