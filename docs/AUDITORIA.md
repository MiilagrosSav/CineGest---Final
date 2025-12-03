# Sistema de Auditoría - CineGest

## Resumen

El sistema de auditoría usa **django-simple-history** para rastrear cambios en modelos críticos. Los datos se almacenan en dos niveles:

1. **Tablas `historical_*`** (una por modelo) - Conservan TODO el historial
2. **Tabla `AuditEntry`** (consolidada) - Vista unificada para consultas rápidas

## ¿Por qué no es inmanejable?

### Arquitectura de dos niveles

```
┌─────────────────────────────────────────────────┐
│  Modelos con HistoricalRecords()               │
│  (Venta, Pago, Promocion, etc.)                │
└────────────────┬────────────────────────────────┘
                 │
                 │ django-simple-history
                 ▼
┌─────────────────────────────────────────────────┐
│  Tablas historical_* (separadas por modelo)    │
│  - historical_venta                             │
│  - historical_pago                              │
│  - historical_promocion                         │
│  etc. (NUNCA se limpian automáticamente)       │
└────────────────┬────────────────────────────────┘
                 │
                 │ señal post_save
                 ▼
┌─────────────────────────────────────────────────┐
│  AuditEntry (tabla consolidada)                │
│  - Se puede limpiar automáticamente             │
│  - Configuración de retención                   │
│  - Exclusión de modelos                         │
└─────────────────────────────────────────────────┘
```

### Ventajas

1. **Las tablas `historical_*` conservan TODO**: Nunca pierdes datos históricos
2. **`AuditEntry` es solo para consultas rápidas**: Puedes limpiarla sin perder historial
3. **Recuperación de datos**: Si limpias `AuditEntry`, puedes regenerarla desde `historical_*`

## Configuración

### 1. Configurar retención (Admin)

Ir a: **Admin → Auditoría → Configuración de Auditoría**

```python
retention_days = 90              # Días que se mantienen en AuditEntry
auto_cleanup_enabled = False     # Activar limpieza automática
excluded_models = "venta,pago"   # Modelos a excluir (separados por comas)
```

### 2. Comandos disponibles

#### Ver estadísticas
```bash
python manage.py audit_stats
```

Muestra:
- Total de registros
- Actividad reciente (7 y 30 días)
- Top modelos auditados
- Configuración actual

#### Limpiar registros antiguos
```bash
# Simular (no elimina nada)
python manage.py cleanup_audit --dry-run

# Limpiar con política por defecto (90 días)
python manage.py cleanup_audit

# Limpiar personalizando retención
python manage.py cleanup_audit --days 30
```

## Modelos auditados

✅ Modelos con auditoría completa:
- `Venta`
- `Entrada`
- `Pago`
- `Intercambio`
- `CuponGenerado`
- `ConfiguracionCine`
- `PoliticaPromocion`
- `Promocion`
- `Usuario` (accounts)
- `Funcion`
- `Sala`
- `Pelicula`

## Cron Jobs recomendados

### Limpieza mensual automática

**Linux/Mac (crontab):**
```bash
# Ejecutar el 1ro de cada mes a las 3 AM
0 3 1 * * cd /path/to/project && python manage.py cleanup_audit --days 90
```

**Windows (Task Scheduler):**
```powershell
# Crear tarea programada
$action = New-ScheduledTaskAction -Execute "python" -Argument "manage.py cleanup_audit --days 90" -WorkingDirectory "E:\saval\jeje\CineGest---Final"
$trigger = New-ScheduledTaskTrigger -Monthly -At 3am
Register-ScheduledTask -TaskName "CineGest-AuditCleanup" -Action $action -Trigger $trigger
```

## Consultas útiles

### Ver historial completo de un objeto
```python
from ventas.models import Venta

venta = Venta.objects.get(id_venta=123)

# Ver todos los cambios
for record in venta.history.all():
    print(f"{record.history_date}: {record.history_type} por {record.history_user}")
    
# Ver diferencias entre versiones
history = venta.history.all()
delta = history[0].diff_against(history[1])
for change in delta.changes:
    print(f"{change.field}: {change.old} → {change.new}")
```

### Restaurar versión anterior
```python
# Obtener versión anterior
old_version = venta.history.all()[1]

# Restaurar
old_version.instance.save()
```

### Buscar quién hizo un cambio
```python
from auditoria.models import AuditEntry

# Buscar cambios de un usuario
cambios = AuditEntry.objects.filter(
    history_user__username='admin',
    model_name='venta'
)

# Buscar cambios en un período
from datetime import datetime, timedelta
hace_7_dias = datetime.now() - timedelta(days=7)

cambios_recientes = AuditEntry.objects.filter(
    history_date__gte=hace_7_dias,
    history_type='~'  # Solo actualizaciones
)
```

## Rendimiento

### Índices optimizados

La tabla tiene índices en:
- `history_date + model_name`
- `model_name + object_id`
- `history_user + history_date`

### Tamaño estimado

Con 1000 transacciones/día:
- `AuditEntry` (90 días): ~90K registros = ~100 MB
- Tablas `historical_*`: Acumulativo, pero distribuido

### Recomendaciones

1. **Si tienes > 100K registros**: Ejecutar `cleanup_audit` mensualmente
2. **Modelos de bajo valor**: Agregar a `excluded_models`
3. **Archivado de largo plazo**: Exportar `historical_*` a data warehouse

## Troubleshooting

### ¿Demasiados registros?
```bash
# Ver qué modelos ocupan más espacio
python manage.py audit_stats

# Excluir modelos de bajo valor
# Admin → AuditConfig → excluded_models = "entrada,butaca"
```

### ¿Cómo recuperar AuditEntry si la borré?
```python
# Script para regenerar desde historical_*
python manage.py shell

from django.apps import apps
from auditoria.models import AuditEntry

# Esto se puede hacer si se borra AuditEntry por error
# Las señales recrearán registros en nuevas operaciones
```

### ¿Necesito más retención?
```bash
# Cambiar en Admin o por código
from auditoria.models import AuditConfig
config = AuditConfig.load()
config.retention_days = 180  # 6 meses
config.save()
```

## Seguridad

- ❌ No almacena contraseñas (excluidas por simple-history)
- ✅ Solo administradores pueden ver auditoría
- ✅ Registros inmutables (no se pueden editar)
- ✅ Rastreo de usuario que hizo cada cambio
