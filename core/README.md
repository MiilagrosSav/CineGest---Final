# Core App - CineGest

App centralizada para servicios compartidos y funcionalidades transversales del sistema.

## 📦 Contenido

### 📧 Sistema de Notificaciones
Servicio centralizado para envío de emails:
- Email de bienvenida (registro)
- Email de confirmación de compra
- Email de confirmación de intercambio

Ver documentación completa: [`docs/SISTEMA_NOTIFICACIONES.md`](../docs/SISTEMA_NOTIFICACIONES.md)

## 🚀 Uso Rápido

```python
from core.services import notificacion_service

# Enviar email de bienvenida
notificacion_service.enviar_bienvenida(usuario)

# Enviar confirmación de compra
notificacion_service.enviar_confirmacion_compra(venta, request)

# Enviar confirmación de intercambio
notificacion_service.enviar_confirmacion_intercambio(
    venta=venta,
    intercambio=intercambio,
    funcion_origen=funcion_origen,
    funcion_destino=funcion_destino,
    request=request
)
```

## 🧪 Testing

```powershell
# Desde la raíz del proyecto
python test_notificaciones.py
```

Asegúrate de tener MailCrab corriendo:
```powershell
docker run --name mailcrab -p 1080:1080 -p 1025:1025 -d marlonb/mailcrab:latest
```

Web UI: http://localhost:1080

## 📚 Documentación

- [Sistema de Notificaciones](../docs/SISTEMA_NOTIFICACIONES.md) - Guía completa
- [Migración de Notificaciones](../docs/MIGRACION_NOTIFICACIONES.md) - Detalles de la refactorización

## 🏗️ Estructura

```
core/
├── services/
│   ├── __init__.py
│   └── notificaciones.py         # NotificacionService
├── templates/
│   └── core/
│       └── emails/
│           ├── bienvenida.html
│           ├── bienvenida.txt
│           ├── confirmacion_compra.html
│           ├── confirmacion_compra.txt
│           ├── confirmacion_intercambio.html
│           └── confirmacion_intercambio.txt
└── views/
    └── __init__.py
```

## 🔮 Futuras Funcionalidades

- Sistema de caché
- Utilidades de validación
- Logging centralizado
- Métricas y monitoreo
- Helpers comunes
