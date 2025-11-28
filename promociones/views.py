from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models

from .models.promocion import Promocion
from .models.politicaPromocion import PoliticaPromocion
from .models.cuponGenerado import CuponGenerado
from .forms import PoliticaPromocionForm, PromocionForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import Http404

import uuid
from django.contrib import messages
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que requiere que el usuario sea admin o superuser"""
    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user, 'rol', None) == 'admin'


@login_required
def dashboard_promociones(request):
    # Solo accesible por administradores (rol == 'admin' o superuser)
    user = request.user
    if not (user.is_superuser or getattr(user, 'rol', None) == 'admin'):
        return HttpResponseForbidden('Acceso denegado')

    # Información rápida para mostrar en el dashboard de promociones
    # Para evitar cargas de atributos que puedan requerir columnas removidas en la tabla
    # `clientes`, consultamos solo los campos necesarios y pasamos diccionarios al template.
    cupones_qs = CuponGenerado.objects.select_related('politica_origen', 'cliente__usuario').order_by('-creado_en')[:10]
    cupones_recientes = list(cupones_qs.values(
        'token', 'politica_origen__nombre', 'usado', 'creado_en', 'cliente__usuario__email'
    ))

    context = {
        'promociones_count': Promocion.objects.count(),
        'politicas_count': PoliticaPromocion.objects.count(),
        'cupones_recientes': cupones_recientes,
    }

    return render(request, 'promociones/dashboard.html', context)


# Vistas CRUD para Políticas de Promoción
class PoliticaPromocionListView(AdminRequiredMixin, ListView):
    model = PoliticaPromocion
    template_name = 'promociones/politica_list.html'
    context_object_name = 'politicas'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtro por búsqueda (nombre de política o nombre de promoción vinculada)
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(nombre__icontains=search) | 
                models.Q(promocion_a_otorgar__nombre__icontains=search) |
                models.Q(promocion_a_otorgar__codigo__icontains=search)
            )
        
        # Filtro por estado (activa/inactiva)
        estado = self.request.GET.get('estado', '').strip()
        if estado == 'activa':
            qs = qs.filter(activa=True)
        elif estado == 'inactiva':
            qs = qs.filter(activa=False)
        
        return qs.order_by('-activa', 'nombre')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_search'] = self.request.GET.get('search', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', '')
        return ctx
    
    def render_to_response(self, context, **response_kwargs):
        # Si es una petición AJAX, devolver solo la tabla parcial
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.template_name = 'promociones/_politica_table.html'
        return super().render_to_response(context, **response_kwargs)


class PoliticaPromocionCreateView(AdminRequiredMixin, CreateView):
    model = PoliticaPromocion
    form_class = PoliticaPromocionForm
    template_name = 'promociones/politica_form.html'
    success_url = reverse_lazy('promociones:politica_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Política de Promoción'
        ctx['nombre_boton'] = 'Crear'
        # Mapa de promociones para el JS (id -> es_automatica)
        ctx['promociones_map'] = {p.pk: bool(p.es_automatica) for p in Promocion.objects.all()}
        return ctx


class PoliticaPromocionUpdateView(AdminRequiredMixin, UpdateView):
    model = PoliticaPromocion
    form_class = PoliticaPromocionForm
    template_name = 'promociones/politica_form.html'
    success_url = reverse_lazy('promociones:politica_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Política de Promoción'
        ctx['nombre_boton'] = 'Guardar cambios'
        ctx['promociones_map'] = {p.pk: bool(p.es_automatica) for p in Promocion.objects.all()}
        return ctx


class PoliticaPromocionDeleteView(AdminRequiredMixin, DeleteView):
    model = PoliticaPromocion
    template_name = 'promociones/politica_confirm_delete.html'
    success_url = reverse_lazy('promociones:politica_list')


# Vistas CRUD para Promociones
class PromocionListView(AdminRequiredMixin, ListView):
    model = Promocion
    template_name = 'promociones/promocion_list.html'
    context_object_name = 'promociones'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtro por búsqueda (nombre, código)
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(nombre__icontains=search) | 
                models.Q(codigo__icontains=search)
            )
        
        # Filtro por tipo (automática o cupón)
        tipo = self.request.GET.get('tipo', '').strip()
        if tipo == 'auto':
            qs = qs.filter(es_automatica=True)
        elif tipo == 'cupon':
            qs = qs.filter(es_automatica=False)
        
        return qs.order_by('-fecha_inicio')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_search'] = self.request.GET.get('search', '')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        return ctx
    
    def render_to_response(self, context, **response_kwargs):
        # Si es una petición AJAX, devolver solo la tabla parcial
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.template_name = 'promociones/_promocion_table.html'
        return super().render_to_response(context, **response_kwargs)


class PromocionCreateView(AdminRequiredMixin, CreateView):
    model = Promocion
    form_class = PromocionForm
    template_name = 'promociones/promocion_form.html'
    success_url = reverse_lazy('promociones:promocion_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Promoción'
        ctx['nombre_boton'] = 'Crear'
        return ctx


class PromocionUpdateView(AdminRequiredMixin, UpdateView):
    model = Promocion
    form_class = PromocionForm
    template_name = 'promociones/promocion_form.html'
    success_url = reverse_lazy('promociones:promocion_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Promoción'
        ctx['nombre_boton'] = 'Guardar cambios'
        return ctx


class PromocionDeleteView(AdminRequiredMixin, DeleteView):
    model = Promocion
    template_name = 'promociones/promocion_confirm_delete.html'
    success_url = reverse_lazy('promociones:promocion_list')


@login_required
def promocion_is_automatica(request, pk):
    """Endpoint pequeño que devuelve si una promoción es automática (JSON)."""
    if not (request.user.is_superuser or getattr(request.user, 'rol', None) == 'admin'):
        return JsonResponse({'error': 'forbidden'}, status=403)
    promocion = get_object_or_404(Promocion, pk=pk)
    return JsonResponse({'es_automatica': bool(promocion.es_automatica)})


def redeem_cupon(request, token):
    """Endpoint público que permite canjear un cupón mediante su token UUID.

    Marca el cupón como usado si es válido y no expirado y muestra un mensaje.
    """
    try:
        token_uuid = uuid.UUID(str(token))
    except Exception:
        raise Http404('Token inválido')

    from .models.cuponGenerado import CuponGenerado

    cupon = CuponGenerado.objects.select_related('politica_origen__promocion_a_otorgar').filter(token=token_uuid).first()
    if not cupon:
        return render(request, 'promociones/redeem.html', {'estado': 'not_found'})

    # comprobar expiración
    ahora = timezone.now()
    if cupon.expira_en and cupon.expira_en < ahora:
        return render(request, 'promociones/redeem.html', {'estado': 'expirado'})

    # marcar como usado y mostrar promo
    cupon.usado = True
    cupon.save()

    promocion = None
    try:
        promocion = cupon.politica_origen.promocion_a_otorgar
    except Exception:
        promocion = None

    return render(request, 'promociones/redeem.html', {'estado': 'ok', 'promocion': promocion})


def activar_promocion_por_link(request, token):
    """Recibe un token en URL pública, valida y activa la promoción en la sesión del usuario.

    Comportamiento:
    - Si token inválido o no existe -> 404
    - Si ya usado -> render con estado 'used'
    - Si expiró -> render con estado 'expirado'
    - Si válido -> guarda `promo_activa_id` y `promo_token` en `request.session`, marca el cupón como usado, redirige a cartelera con mensaje de éxito
    """
    try:
        token_uuid = uuid.UUID(str(token))
    except Exception:
        raise Http404('Token inválido')

    cupon = CuponGenerado.objects.select_related('politica_origen__promocion_a_otorgar').filter(token=token_uuid).first()
    if not cupon:
        raise Http404('Token no encontrado')

    # Depuración: mostrar tiempos y estado usado
    try:
        logger.debug("[PROMO ACT] Hora Actual Server: %s", timezone.now().isoformat())
        logger.debug("[PROMO ACT] Hora Expiracion Cupón (raw): %r", cupon.expira_en)
        logger.debug("[PROMO ACT] ¿Está Usado?: %s", cupon.usado)
    except Exception:
        logger.exception('Error al loggear estado del cupón')

    # Si ya fue usado
    if cupon.usado:
        return render(request, 'promociones/redeem.html', {'estado': 'used'})

    # Comprobar expiración asegurando awareness
    ahora = timezone.now()
    expira = None
    if cupon.expira_en:
        expira = cupon.expira_en
        try:
            from django.utils import timezone as dj_tz
            if dj_tz.is_naive(expira):
                expira = dj_tz.make_aware(expira, dj_tz.get_default_timezone())
        except Exception:
            pass

    try:
        logger.debug("[PROMO ACT] Hora Expiracion Cupón (aware): %r", expira)
    except Exception:
        logger.exception('Error al loggear expiracion aware')

    if expira and expira < ahora:
        return render(request, 'promociones/redeem.html', {'estado': 'expirado'})

    # Guardar promoción y token en sesión (antes de marcar usado)
    promocion = None
    try:
        promocion = cupon.politica_origen.promocion_a_otorgar
        if promocion:
            request.session['promo_activa_id'] = promocion.pk
            request.session['promo_activada_timestamp'] = timezone.now().isoformat()
            logger.debug('[PROMO ACT] Seteando session promo_activa_id=%s promo_token=%s para usuario=%s', promocion.pk, str(cupon.token), getattr(request.user, 'pk', None))
            try:
                print(f"[PROMO ACT - PRINT] setting session promo_activa_id={promocion.pk} promo_token={str(cupon.token)} user={getattr(request.user,'pk',None)}")
            except Exception:
                pass
    except Exception:
        request.session['promo_activa_id'] = None

    request.session['promo_token'] = str(cupon.token)
    try:
        request.session.modified = True
        request.session.save()
        logger.debug('[PROMO ACT] Sesión guardada con promo_activa_id=%s promo_token=%s', request.session.get('promo_activa_id'), request.session.get('promo_token'))
        try:
            print(f"[PROMO ACT - PRINT] session saved promo_activa_id={request.session.get('promo_activa_id')} promo_token={request.session.get('promo_token')}")
        except Exception:
            pass
    except Exception:
        logger.exception('Error al guardar sesión')

    # Marcar como usado sólo después de guardar la sesión
    cupon.usado = True
    cupon.save()
    try:
        logger.debug("[PROMO ACT] Cupón %s marcado como usado a las %s", cupon.token, timezone.now().isoformat())
    except Exception:
        logger.exception('Error al loggear marcado como usado')

    messages.success(request, '¡Promoción activada! Elige tu película')
    # Si el cupón tiene función origen, dirigir directamente a selección de butacas (yield management)
    try:
        if getattr(cupon, 'funcion_origen', None):
            funcion_id = cupon.funcion_origen.id
            logger.info(f'[PROMO ACT] Redirigiendo a función {funcion_id} (yield management)')
            return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    except Exception as e:
        logger.exception('Error al redirigir a función origen')

    # Si no tiene función origen, ir a cartelera (cupones normales)
    return redirect(reverse('cine:cartelera'))
