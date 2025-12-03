"""
Simulador de Cron para Yield Management
Ejecuta el comando cada 2 minutos automáticamente
Presiona Ctrl+C para detener
"""
import os
import sys
import time
import subprocess
from datetime import datetime

# Configurar encoding UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Configuración
INTERVALO_SEGUNDOS = 120  # 2 minutos
COMANDO = ['python', 'manage.py', 'ejecutar_yield_management', '--test-mode', '-v', '2']

def ejecutar_comando():
    """Ejecuta el comando de yield management"""
    print("\n" + "="*70)
    print(f"🤖 EJECUTANDO CRON - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    try:
        resultado = subprocess.run(
            COMANDO,
            cwd=os.getcwd(),
            capture_output=False,
            text=True
        )
        
        print("\n" + "="*70)
        if resultado.returncode == 0:
            print("✅ Ejecución completada exitosamente")
        else:
            print(f"⚠️  Ejecución terminó con código: {resultado.returncode}")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Error ejecutando comando: {e}")

def main():
    print("\n" + "🎬 SIMULADOR DE CRON - YIELD MANAGEMENT ".center(70, "="))
    print(f"\n⏰ Intervalo: cada {INTERVALO_SEGUNDOS//60} minutos")
    print(f"📍 Directorio: {os.getcwd()}")
    print(f"🚀 Comando: {' '.join(COMANDO)}")
    print("\n💡 Presiona Ctrl+C para detener\n")
    print("="*70)
    
    iteracion = 0
    
    try:
        while True:
            iteracion += 1
            print(f"\n\n{'📊 ITERACIÓN #' + str(iteracion) + ' ':=^70}\n")
            
            ejecutar_comando()
            
            # Esperar hasta la próxima ejecución
            print(f"\n⏳ Esperando {INTERVALO_SEGUNDOS//60} minutos hasta la próxima ejecución...")
            print(f"   Próxima ejecución: {datetime.fromtimestamp(time.time() + INTERVALO_SEGUNDOS).strftime('%H:%M:%S')}")
            
            time.sleep(INTERVALO_SEGUNDOS)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("🛑 Simulador detenido por el usuario")
        print(f"📊 Total de ejecuciones: {iteracion}")
        print("="*70 + "\n")
        sys.exit(0)

if __name__ == '__main__':
    main()
