"""
Script para iniciar Django con ngrok para hacer el servidor accesible públicamente.
Esto es necesario para que Mercado Pago pueda enviar las notificaciones de pago.
"""
import os
import sys
import socket
import time
from pyngrok import ngrok
from pyngrok.exception import PyngrokNgrokHTTPError


def _is_local_server_up(host="127.0.0.1", port=8000, timeout=1.0):
    """Return True if something is listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _connect_with_retry(port=8000):
    """Connect ngrok, retrying once if the reserved endpoint is in use."""
    try:
        return ngrok.connect(port, bind_tls=True)
    except PyngrokNgrokHTTPError as exc:
        # ERR_NGROK_334 means the account's endpoint is already online.
        if "ERR_NGROK_334" not in str(exc):
            raise

        print("⚠️  El endpoint de ngrok ya está en uso. Intentando liberar y reconectar...")
        ngrok.kill()
        time.sleep(2)
        return ngrok.connect(port, bind_tls=True)

def start_ngrok():
    if not _is_local_server_up(port=8000):
        print("❌ No hay servidor Django escuchando en http://127.0.0.1:8000")
        print("   En otra terminal ejecuta: python manage.py runserver 8000")
        print("   Luego vuelve a ejecutar este script.\n")
        raise RuntimeError("Django server is not running on port 8000")

    # Iniciar ngrok en el puerto 8000
    print("🚀 Iniciando ngrok...")
    tunnel = _connect_with_retry(8000)
    public_url = tunnel.public_url
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
        # Mantener el hilo principal activo
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Deteniendo ngrok...")
        ngrok.kill()
        print("✅ Ngrok detenido\n")
        sys.exit(0)
    except Exception as exc:
        print(f"\n❌ No se pudo iniciar ngrok: {exc}\n")
        sys.exit(1)
