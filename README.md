# CineGest - Sistema de Gestión de Cinema

Un sistema de gestión de cine desarrollado en Django con autenticación tradicional y OAuth2 de Google.

## 🚀 Características

- ✅ Autenticación de usuarios (registro, login, logout)
- ✅ Login con Google OAuth2
- ✅ Sistema de roles (Admin, Empleado, Cliente)
- ✅ Gestión de películas
- ✅ Gestión de empleados
- ✅ Dashboard personalizado por rol
- ✅ Interfaz responsive

## 📋 Requisitos

- Python 3.8+
- Django 5.2.6
- SQLite (incluido con Python)

## 🔧 Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/MiilagrosSav/CineGest---Final.git
cd CineGest---Final
```

### 2. Crear entorno virtual
```bash
python -m venv venv

# En Windows
venv\Scripts\activate

# En Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
# Copia el archivo de ejemplo
cp .env.example .env

# Edita .env con tus valores reales
# Especialmente necesario para Google OAuth2
```

### 5. Configurar la base de datos
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crear superusuario (opcional)
```bash
python manage.py createsuperuser
```

### 7. Ejecutar el servidor
```bash
python manage.py runserver
```

El servidor estará disponible en: http://127.0.0.1:8000/

## 🔑 Configuración de Google OAuth2

1. Ve a [Google Cloud Console](https://console.developers.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la API de Google+
4. Crea credenciales OAuth2
5. Configura las URLs de redirección:
   - `http://127.0.0.1:8000/auth/complete/google-oauth2/`
6. Copia las credenciales en tu archivo `.env`

## 📁 Estructura del Proyecto

```
CineGest---Final/
├── accounts/           # App de usuarios y autenticación
├── cine/              # App de gestión de películas
├── static/            # Archivos estáticos (CSS, JS, imágenes)
├── templates/         # Plantillas HTML
├── trabajofinal/      # Configuración principal del proyecto
├── .env.example       # Ejemplo de variables de entorno
├── .gitignore        # Archivos ignorados por Git
├── requirements.txt   # Dependencias del proyecto
└── manage.py         # Script de gestión de Django
```

## 🛡️ Seguridad

- ✅ Variables sensibles en `.env` (no versionadas)
- ✅ Secret key generada automáticamente
- ✅ Base de datos SQLite excluida del repositorio
- ✅ Debug deshabilitado en producción
- ✅ Validación de URLs de redirección OAuth2

## 🚀 Despliegue

Para producción, asegúrate de:

1. Cambiar `DEBUG=False` en tu `.env`
2. Configurar `ALLOWED_HOSTS` apropiadamente
3. Usar una base de datos robusta (PostgreSQL recomendado)
4. Configurar archivos estáticos con `collectstatic`
5. Usar HTTPS para OAuth2

## 🤝 Contribución

1. Fork el proyecto
2. Crea tu rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 👩‍💻 Autora

**Milagros Sav** - [@MiilagrosSav](https://github.com/MiilagrosSav)

# Variables de entorno requeridas para CineGest
#si tengo que cambiar en algun momento lo de google cloud
# Configuración de Django
DEBUG=True
SECRET_KEY=aca va el secret key
GOOGLE_CLIENT_ID=aca va el google client id
GOOGLE_CLIENT_SECRET=aca va el google client secret

# Base de datos (opcional, por defecto usa SQLite)
# DATABASE_URL=sqlite:///db.sqlite3