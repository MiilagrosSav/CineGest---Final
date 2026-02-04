# GitHub Actions - Yield Management Automático

## 🎯 Configuración

Este workflow ejecuta automáticamente el comando de yield management cada hora.

### 📝 Pasos para activar:

1. **Configurar Secrets en GitHub:**
   - Ve a tu repositorio → Settings → Secrets and variables → Actions
   - Crea estos secrets:
     - `DJANGO_SECRET_KEY`: Tu SECRET_KEY de Django
     - `DATABASE_URL`: URL de conexión a tu base de datos
     - `NGROK_URL`: URL pública de tu ngrok (ej: https://tu-dominio.ngrok-free.app)

2. **Hacer push de los archivos:**
   ```bash
   git add .github/workflows/
   git commit -m "Add: GitHub Actions para yield management automático"
   git push
   ```

3. **Verificar ejecución:**
   - Ve a tu repo → Actions tab
   - Verás el workflow "Yield Management Automático"
   - Puedes ejecutarlo manualmente con "Run workflow"

### ⚙️ Configuración del Cron

El workflow está configurado para ejecutarse:
- **Frecuencia:** Cada hora a los 5 minutos (00:05, 01:05, 02:05, etc.)
- **Timezone:** UTC (ajusta según necesites)

Para cambiar la frecuencia, edita la línea `cron:` en `yield-management.yml`:
```yaml
# Cada 2 horas
- cron: '5 */2 * * *'

# Cada 30 minutos
- cron: '*/30 * * * *'

# Solo de lunes a viernes a las 10am y 6pm UTC
- cron: '0 10,18 * * 1-5'
```

### 📊 Monitoreo

- Logs disponibles en: Actions tab → Workflow run específico
- Notificaciones por email si falla (configurable)
- Cada ejecución queda registrada con su salida completa

### 🔧 Troubleshooting

**Error: "Secret not found"**
→ Verifica que hayas creado todos los secrets requeridos

**Error: "Database connection failed"**
→ Asegúrate de que tu base de datos sea accesible desde Internet o usa una DB en la nube

**Error: "Module not found"**
→ Verifica que requirements.txt contenga todas las dependencias

### 💡 Alternativas si no funciona

Si GitHub Actions no funciona para tu caso, considera:
1. **Render Cron Jobs** (plan de pago)
2. **Railway Cron Jobs** (plan de pago)
3. **Google Cloud Scheduler** (plan gratuito limitado)
4. **Task Scheduler en Windows** (local, requiere PC encendida)

### 🚨 Importante

- La base de datos debe ser accesible desde Internet
- ngrok debe estar corriendo 24/7 o usar un dominio permanente
- Considera migrar a PostgreSQL en la nube (Supabase, Railway, etc.)
