"""
URL configuration for trabajofinal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings          # Importa settings
from django.conf.urls.static import static  # Importa static
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False), name='index'),  # Redirige la raíz al login
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=False)),  # Redirige /login a /accounts/login/
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('promociones/', include('promociones.urls', namespace='promociones')),
    path('', include('cine.urls', namespace='cine')), # URLs de cine (películas y salas) - cambiado de 'peliculas/' a 'cine/'
    path('ventas/', include('ventas.urls', namespace='ventas')),  # URLs de ventas y pagos
    path('auditoria/', include('auditoria.urls', namespace='auditoria')),
    path('oauth/', include('social_django.urls', namespace='social')),  # Añade esta línea para las URLs de autenticación social
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
   
