"""
Script para iniciar Django con ngrok para hacer el servidor accesible públicamente.
Esto es necesario para que Mercado Pago pueda enviar las notificaciones de pago.
"""
import os
import sys
from pyngrok import ngrok

def start_ngrok():
    # Iniciar ngrok en el puerto 8000
    print("🚀 Iniciando ngrok...")
    public_url = ngrok.connect(8000, bind_tls=True)
    print(f"\n{'='*60}")
    print(f"✅ NGROK INICIADO CORRECTAMENTE")
    print(f"{'='*60}")
    print(f"🌐 URL Pública: {public_url}")
    print(f"{'='*60}")
    print(f"\n⚠️  IMPORTANTE: Usa esta URL en lugar de localhost")
    print(f"   Ejemplo: {public_url}/admin")
    print(f"            {public_url}/ventas/cartelera")
    print(f"\n📝 Esta URL pública permite que Mercado Pago envíe")
    print(f"   las notificaciones de pago correctamente.\n")
    
    # Actualizar settings con la URL de ngrok
    try:
        from django.conf import settings
        # Agregar la URL de ngrok a ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS
        ngrok_host = public_url.replace('https://', '').replace('http://', '')
        if ngrok_host not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append(ngrok_host)
        if public_url not in settings.CSRF_TRUSTED_ORIGINS:
            settings.CSRF_TRUSTED_ORIGINS.append(public_url)
        print(f"✅ Configuración actualizada automáticamente\n")
    except:
        pass
    
    return public_url

if __name__ == "__main__":
    try:
        # Iniciar ngrok
        public_url = start_ngrok()
        
        # Mantener el script corriendo
        print("Presiona Ctrl+C para detener ngrok...\n")
        import threading
        import time
        
        # Mantener el hilo principal activo
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Deteniendo ngrok...")
        ngrok.kill()
        print("✅ Ngrok detenido\n")
        sys.exit(0)
