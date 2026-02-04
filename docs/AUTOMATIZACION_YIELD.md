# 🤖 Automatización del Yield Management

## Problema

El comando `ejecutar_yield_management` necesita ejecutarse cada hora automáticamente, sin depender de que una computadora esté encendida.

## Soluciones Implementadas

### ✅ Solución Principal: GitHub Actions

**Archivo:** `.github/workflows/yield-management.yml`

**Características:**
- Se ejecuta cada hora automáticamente
- Gratis hasta 2000 minutos/mes
- Logs visibles en el repositorio
- Ejecución manual disponible

**Requisitos:**
1. Base de datos accesible desde Internet (considera Supabase, Railway, o PostgreSQL en la nube)
2. URL pública estable (ngrok permanente o dominio propio)
3. Secrets configurados en GitHub

**Setup:**
```bash
# 1. Agregar workflows al repositorio
git add .github/workflows/
git commit -m "Add: Automatización yield management con GitHub Actions"
git push

# 2. Configurar secrets en GitHub:
# - DJANGO_SECRET_KEY
# - DATABASE_URL  
# - NGROK_URL
```

### 🔄 Alternativa 1: Windows Task Scheduler (Local)

Si necesitas ejecutar localmente mientras desarrollas:

**Archivo:** `scripts/setup_windows_scheduler.ps1`

```powershell
# Ejecutar como Administrador
$action = New-ScheduledTaskAction -Execute "python" -Argument "manage.py ejecutar_yield_management --verbosity=2" -WorkingDirectory "E:\saval\jeje\CineGest---Final"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "CineGest-YieldManagement" -Action $action -Trigger $trigger -Description "Ejecuta yield management cada hora"
```

**Desventaja:** Requiere PC encendida 24/7.

### 🌐 Alternativa 2: Render Cron Jobs

Si decides usar un hosting:

**Archivo:** `render.yaml` (agregar a la raíz)

```yaml
services:
  - type: web
    name: cinegest
    env: python
    buildCommand: "pip install -r requirements.txt && python manage.py migrate"
    startCommand: "gunicorn trabajofinal.wsgi:application"
    
  - type: cron
    name: yield-management-cron
    env: python
    schedule: "0 * * * *"  # Cada hora
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python manage.py ejecutar_yield_management"
```

**Costo:** ~$7/mes por el cron job.

### 🐍 Alternativa 3: PythonAnywhere

**Setup:**
1. Sube tu proyecto a PythonAnywhere
2. Ve a Tasks → Schedule a new task
3. Comando: `cd ~/cinegest && python manage.py ejecutar_yield_management`
4. Frecuencia: Cada hora

**Limitación:** Solo 1 tarea programada en plan gratuito.

## Recomendación Final

Para producción, la mejor combinación es:

1. **Hosting:** Railway o Render (base de datos + app Django)
2. **Cron:** GitHub Actions (gratis) o Render Cron Jobs (integrado)
3. **Emails:** MailCrab (desarrollo) → SendGrid/Mailgun (producción)

### Migración sugerida a la nube:

```bash
# 1. Base de datos: Supabase (PostgreSQL gratis)
DATABASE_URL=postgresql://user:pass@db.supabase.co:5432/dbname

# 2. Deployment: Railway
railway link
railway up

# 3. Cron: GitHub Actions (ya configurado)
# Se conectará a tu Railway deployment automáticamente
```

## Testing

### Probar el comando localmente:
```bash
# Dry run (sin enviar emails)
python manage.py ejecutar_yield_management --dry-run --verbosity=2

# Test mode (envía emails de prueba)
python manage.py ejecutar_yield_management --test-mode --verbosity=2

# Producción
python manage.py ejecutar_yield_management --verbosity=2
```

### Probar GitHub Actions:
1. Ve a tu repo → Actions
2. Selecciona "Yield Management Automático"
3. Click en "Run workflow"
4. Revisa los logs

## Monitoreo

### Ver últimas ejecuciones:
```bash
# Local
tail -f logs/yield_management.log

# GitHub Actions
# Ve a: Repository → Actions → Workflow runs
```

### Métricas importantes:
- Funciones analizadas
- Cupones generados
- Emails enviados
- Errores encontrados

## Troubleshooting

### Error: "Database not accessible"
**Solución:** Migra a una base de datos en la nube (Supabase, Railway, etc.)

### Error: "NGROK_URL not configured"
**Solución:** Usa un dominio permanente o configura ngrok con autenticación

### Error: "GitHub Actions minutes exceeded"
**Solución:** Reducir frecuencia a cada 2 horas o usar Render Cron Jobs

### Emails no se envían
**Verificar:**
1. MailCrab está corriendo (desarrollo)
2. EMAIL_BACKEND configurado correctamente
3. SITE_BASE_URL apunta a tu dominio público
4. Hay políticas activas con `horas_antes_de_funcion` configurado

## Próximos Pasos

1. [ ] Configurar GitHub Actions secrets
2. [ ] Hacer push del workflow
3. [ ] Probar ejecución manual
4. [ ] Monitorear primera ejecución automática
5. [ ] (Opcional) Migrar base de datos a la nube
6. [ ] (Opcional) Configurar notificaciones de fallo
