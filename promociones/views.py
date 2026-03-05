from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models, transaction
from django.utils import timezone as dj_tz

from .models.promocion import Promocion
from .models.politicaPromocion import PoliticaPromocion
from .models.cuponGenerado import CuponGenerado
from .forms import PoliticaPromocionForm, PromocionForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import Http404
from cine.mixins import AdminRequiredMixin, ProtectedDeleteMixin

import uuid
from django.contrib import messages
from django.urls import reverse
import logging
from io import StringIO
from django.core.management import call_command

logger = logging.getLogger(__name__)


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

    # Métricas adicionales
    cupones_total = CuponGenerado.objects.count()
    cupones_usados = CuponGenerado.objects.filter(usado=True).count()
    cupones_disponibles = CuponGenerado.objects.filter(usado=False, expira_en__gte=timezone.now()).count()
    tasa_conversion = round((cupones_usados / cupones_total * 100), 1) if cupones_total > 0 else 0

    context = {
        'promociones_count': Promocion.objects.count(),
        'promociones_automaticas': Promocion.objects.filter(es_automatica=True).count(),
        'promociones_cupon': Promocion.objects.filter(es_automatica=False).count(),
        'politicas_count': PoliticaPromocion.objects.count(),
        'politicas_activas': PoliticaPromocion.objects.filter(activa=True).count(),
        'politicas_inactivas': PoliticaPromocion.objects.filter(activa=False).count(),
        'cupones_recientes': cupones_recientes,
        'cupones_total': cupones_total,
        'cupones_usados': cupones_usados,
        'cupones_disponibles': cupones_disponibles,
        'tasa_conversion': tasa_conversion,
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


class PoliticaPromocionDeleteView(ProtectedDeleteMixin, AdminRequiredMixin, DeleteView):
    model = PoliticaPromocion
    template_name = 'promociones/politica_confirm_delete.html'
    success_url = reverse_lazy('promociones:politica_list')
    
    # Configuración para ProtectedDeleteMixin
    protected_filter_field = 'politica_origen'
    related_name = 'cupón(es) generado(s)'
    
    @property
    def protected_model(self):
        from .models.cuponGenerado import CuponGenerado
        return CuponGenerado

    def get_context_data(self, **kwargs):
        from .models.cuponGenerado import CuponGenerado
        context = super().get_context_data(**kwargs)
        politica = self.get_object()
        
        # Verificar si tiene cupones generados
        cupones = CuponGenerado.objects.filter(politica_origen=politica)
        
        context['tiene_cupones'] = cupones.exists()
        context['total_cupones'] = cupones.count()
        context['puede_eliminar'] = not cupones.exists()
        
        if cupones.exists():
            context['cupones_usados'] = cupones.filter(usado=True).count()
            context['cupones_disponibles'] = cupones.filter(usado=False).count()
        
        return context
    
    def get_protected_message_parts(self, obj, protected_objects):
        """Sobrescribe para agregar detalles de cupones usados/disponibles."""
        mensaje_partes = [
            f'No se puede eliminar la política "{obj.nombre}" porque está asociada a:',
            f'<br><strong>• {protected_objects.count()} cupón(es) generado(s)</strong>'
        ]
        
        usados = protected_objects.filter(usado=True).count()
        disponibles = protected_objects.filter(usado=False).count()
        if usados:
            mensaje_partes.append(f'  - {usados} usado(s)')
        if disponibles:
            mensaje_partes.append(f'  - {disponibles} disponible(s)')
        
        return mensaje_partes
    
    def get_alternative_messages(self):
        """Sobrescribe para personalizar alternativas específicas de políticas."""
        return [
            '<br><br><strong>Alternativas:</strong>',
            '1. Los cupones están vinculados a esta política y no pueden eliminarse',
            '2. Marcar la política como inactiva en lugar de eliminarla'
        ]


# Vistas CRUD para Promociones
class PromocionListView(AdminRequiredMixin, ListView):
    model = Promocion
    template_name = 'promociones/promocion_list.html'
    context_object_name = 'promociones'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # ✅ OPTIMIZACIÓN: Prefetch vínculos para mostrar en tabla
        qs = qs.prefetch_related('vinculos')
        
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
        
        # ✅ Filtro por estado (activas/inactivas/vencidas/todas)
        estado = self.request.GET.get('estado', 'activas').strip()
        hoy = timezone.now().date()
        
        if estado == 'activas':
            # Promociones activas y vigentes (activo=True y fecha_fin >= hoy)
            qs = qs.filter(activo=True, fecha_fin__gte=hoy)
        elif estado == 'inactivas':
            # Promociones desactivadas manualmente (activo=False)
            qs = qs.filter(activo=False)
        elif estado == 'vencidas':
            # Promociones que ya pasaron su fecha (fecha_fin < hoy)
            qs = qs.filter(fecha_fin__lt=hoy)
        # Si estado == 'todas', no filtrar
        
        return qs.order_by('-fecha_inicio')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_search'] = self.request.GET.get('search', '')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', 'activas')
        
        # Contar promociones inactivas y vencidas para badges
        hoy = timezone.now().date()
        ctx['promociones_inactivas_count'] = Promocion.objects.filter(activo=False).count()
        ctx['promociones_vencidas_count'] = Promocion.objects.filter(fecha_fin__lt=hoy).count()
        
        return ctx
    
    def render_to_response(self, context, **response_kwargs):
        # Si es una petición AJAX, devolver solo la tabla parcial
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.template_name = 'promociones/_promocion_table.html'
        return super().render_to_response(context, **response_kwargs)


class PromocionHistorialView(AdminRequiredMixin, ListView):
    """
    Vista dedicada al historial de promociones vencidas.
    Muestra solo promociones cuya fecha_fin ya pasó.
    """
    model = Promocion
    template_name = 'promociones/promocion_historial.html'
    context_object_name = 'promociones'
    paginate_by = 20
    
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.prefetch_related('vinculos')
        
        # Solo promociones vencidas
        hoy = timezone.now().date()
        qs = qs.filter(fecha_fin__lt=hoy)
        
        # Filtro por búsqueda
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(nombre__icontains=search) | 
                models.Q(codigo__icontains=search)
            )
        
        # Filtro por tipo
        tipo = self.request.GET.get('tipo', '').strip()
        if tipo == 'auto':
            qs = qs.filter(es_automatica=True)
        elif tipo == 'cupon':
            qs = qs.filter(es_automatica=False)
        
        return qs.order_by('-fecha_fin')  # Las más recientes primero
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_search'] = self.request.GET.get('search', '')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        ctx['es_historial'] = True  # Para que el template sepa que es historial
        return ctx


class PromocionCreateView(AdminRequiredMixin, CreateView):
    model = Promocion
    form_class = PromocionForm
    template_name = 'promociones/promocion_form.html'
    success_url = reverse_lazy('promociones:promocion_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Crear Promoción'
        ctx['nombre_boton'] = 'Crear'
        
        # ✅ Agregar formset de vínculos
        from .forms import VinculoPromocionalFormSet
        if self.request.POST:
            ctx['vinculo_formset'] = VinculoPromocionalFormSet(self.request.POST, instance=self.object)
        else:
            ctx['vinculo_formset'] = VinculoPromocionalFormSet(instance=self.object)
        
        return ctx

    def form_valid(self, form):
        from django.db import transaction
        from .forms import VinculoPromocionalFormSet
        context = self.get_context_data()
        vinculo_formset = context['vinculo_formset']
        
        # 🔍 DEBUG: Mostrar errores del formset si no es válido
        if not vinculo_formset.is_valid():
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ FORMSET NO VÁLIDO - Errores: {vinculo_formset.errors}")
            logger.error(f"❌ FORMSET Non-form errors: {vinculo_formset.non_form_errors()}")
            messages.error(self.request, f'❌ Error en vínculos: {vinculo_formset.errors}')
            return self.form_invalid(form)
        
        # Validar formset
        # ✅ Usar transaction.atomic() para asegurar integridad
        with transaction.atomic():
            self.object = form.save()
            vinculo_formset.instance = self.object
            vinculo_formset.save()
        messages.success(self.request, f'Promoción "{self.object.nombre}" creada exitosamente.')
        return redirect(self.success_url)
    
    def post(self, request, *args, **kwargs):
        """
        ✅ CORRECCIÓN: Interceptar POST para verificar vínculos ANTES de validar el formulario.
        Esto permite que model.clean() sepa que habrá vínculos específicos.
        """
        from django.core.exceptions import ValidationError
        
        self.object = None
        form = self.get_form()
        
        try:
            from .forms import VinculoPromocionalFormSet
            vinculo_formset = VinculoPromocionalFormSet(self.request.POST, instance=self.object)
            
            # Verificar si hay vínculos pendientes en el formset
            tiene_vinculos_pendientes = False
            if vinculo_formset.is_valid():
                tiene_vinculos_pendientes = any(
                    vinculo_form.cleaned_data and not vinculo_form.cleaned_data.get('DELETE', False)
                    for vinculo_form in vinculo_formset
                )
            
            # ✅ FIX: Setear flag en el formulario Y en la instancia ANTES de validar
            if tiene_vinculos_pendientes:
                form._tiene_vinculos_pendientes = True
                if hasattr(form, 'instance'):
                    form.instance._tiene_vinculos_pendientes = True
            
            # Ahora validar el formulario (que llamará a model.clean())
            if form.is_valid():
                return self.form_valid(form)
            else:
                # 🔍 DEBUG: Mostrar errores del formulario
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ FORMULARIO NO VÁLIDO - Errores: {form.errors}")
                messages.error(self.request, f'❌ Revisa los campos del formulario. Errores: {form.errors.as_text()}')
                return self.form_invalid(form)
                
        except ValidationError as ve:
            # ✅ FIX: Mostrar errores de validación del modelo correctamente
            if hasattr(ve, 'error_dict'):
                for field, errors in ve.error_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            else:
                form.add_error(None, str(ve))
            return self.form_invalid(form)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error inesperado al crear promoción: {str(e)}", exc_info=True)
            messages.error(self.request, f'❌ Error inesperado: {str(e)}')
            return self.form_invalid(form)


class PromocionUpdateView(AdminRequiredMixin, UpdateView):
    model = Promocion
    form_class = PromocionForm
    template_name = 'promociones/promocion_form.html'
    success_url = reverse_lazy('promociones:promocion_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo_pagina'] = 'Editar Promoción'
        ctx['nombre_boton'] = 'Guardar cambios'
        
        # ✅ Agregar formset de vínculos
        from .forms import VinculoPromocionalFormSet
        if self.request.POST:
            ctx['vinculo_formset'] = VinculoPromocionalFormSet(self.request.POST, instance=self.object)
        else:
            ctx['vinculo_formset'] = VinculoPromocionalFormSet(instance=self.object)
        
        return ctx

    def form_valid(self, form):
        from django.db import transaction
        from .forms import VinculoPromocionalFormSet
        context = self.get_context_data()
        vinculo_formset = context['vinculo_formset']
        
        # 🔍 DEBUG: Mostrar errores del formset si no es válido
        if not vinculo_formset.is_valid():
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ FORMSET NO VÁLIDO - Errores: {vinculo_formset.errors}")
            logger.error(f"❌ FORMSET Non-form errors: {vinculo_formset.non_form_errors()}")
            messages.error(self.request, f'❌ Error en vínculos: {vinculo_formset.errors}')
            return self.form_invalid(form)
        
        # Validar formset
        # ✅ Usar transaction.atomic() para asegurar integridad
        with transaction.atomic():
            self.object = form.save()
            vinculo_formset.instance = self.object
            vinculo_formset.save()
        messages.success(self.request, f'Promoción "{self.object.nombre}" actualizada exitosamente.')
        return redirect(self.success_url)
    
    def post(self, request, *args, **kwargs):
        """
        ✅ CORRECCIÓN: Interceptar POST para verificar vínculos ANTES de validar el formulario.
        """
        from django.core.exceptions import ValidationError
        
        self.object = self.get_object()
        form = self.get_form()
        
        try:
            from .forms import VinculoPromocionalFormSet
            vinculo_formset = VinculoPromocionalFormSet(self.request.POST, instance=self.object)
            
            # Verificar si hay vínculos pendientes en el formset
            tiene_vinculos_pendientes = False
            if vinculo_formset.is_valid():
                tiene_vinculos_pendientes = any(
                    vinculo_form.cleaned_data and not vinculo_form.cleaned_data.get('DELETE', False)
                    for vinculo_form in vinculo_formset
                )
            
            # ✅ FIX: Setear flag en el formulario Y en la instancia ANTES de validar
            if tiene_vinculos_pendientes:
                form._tiene_vinculos_pendientes = True
                if hasattr(form, 'instance'):
                    form.instance._tiene_vinculos_pendientes = True
            
            # Ahora validar el formulario
            if form.is_valid():
                return self.form_valid(form)
            else:
                # 🔍 DEBUG: Mostrar errores del formulario
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ FORMULARIO NO VÁLIDO - Errores: {form.errors}")
                messages.error(self.request, f'❌ Revisa los campos del formulario. Errores: {form.errors.as_text()}')
                return self.form_invalid(form)
                
        except ValidationError as ve:
            # ✅ FIX: Mostrar errores de validación del modelo correctamente
            if hasattr(ve, 'error_dict'):
                for field, errors in ve.error_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            else:
                form.add_error(None, str(ve))
            return self.form_invalid(form)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error inesperado al actualizar promoción: {str(e)}", exc_info=True)
            messages.error(self.request, f'❌ Error inesperado: {str(e)}')
            return self.form_invalid(form)


class PromocionDeleteView(ProtectedDeleteMixin, AdminRequiredMixin, DeleteView):
    model = Promocion
    template_name = 'promociones/promocion_confirm_delete.html'
    success_url = reverse_lazy('promociones:promocion_list')
    
    # Configuración para ProtectedDeleteMixin
    protected_filter_field = 'promocion_a_otorgar'
    related_name = 'política(s) de promoción'
    
    def get_queryset(self):
        """
        Usar all_objects para permitir acceso a promociones ya eliminadas (soft delete).
        Esto previene 404 al acceder a la página de confirmación de eliminación.
        """
        return Promocion.all_objects.all()
    
    @property
    def protected_model(self):
        from .models.politicaPromocion import PoliticaPromocion
        return PoliticaPromocion

    def get_context_data(self, **kwargs):
        from .models.politicaPromocion import PoliticaPromocion
        context = super().get_context_data(**kwargs)
        promocion = self.get_object()
        
        # ✅ OPTIMIZACIÓN: Usar only() para limitar campos cargados
        politicas = PoliticaPromocion.objects.filter(
            promocion_a_otorgar=promocion
        ).only('id', 'activa')
        
        context['tiene_politicas'] = politicas.exists()
        context['total_politicas'] = politicas.count()
        context['puede_eliminar'] = not politicas.exists()
        
        if politicas.exists():
            context['politicas_activas'] = politicas.filter(activa=True).count()
            context['politicas_inactivas'] = politicas.filter(activa=False).count()
        
        return context
    
    def delete(self, request, *args, **kwargs):
        """Pasar usuario al soft delete para auditoría"""
        from django.shortcuts import redirect
        from django.contrib import messages
        
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Llamar a soft_delete con el usuario para registro de auditoría
        if hasattr(self.object, 'soft_delete'):
            self.object.soft_delete(user=request.user)
        else:
            self.object.delete()
        
        messages.success(
            request,
            f'✓ La promoción "{self.object.nombre}" ha sido eliminada exitosamente.'
        )
        return redirect(success_url)
    
    def get_protected_message_parts(self, obj, protected_objects):
        """Sobrescribe para agregar detalles de políticas activas/inactivas."""
        mensaje_partes = [
            f'No se puede eliminar la promoción "{obj.nombre}" porque está asociada a:',
            f'<br><strong>• {protected_objects.count()} política(s) de promoción</strong>'
        ]
        
        activas = protected_objects.filter(activa=True).count()
        inactivas = protected_objects.filter(activa=False).count()
        if activas:
            mensaje_partes.append(f'  - {activas} activa(s)')
        if inactivas:
            mensaje_partes.append(f'  - {inactivas} inactiva(s)')
        
        return mensaje_partes
    
    def get_alternative_messages(self):
        """Sobrescribe para personalizar alternativas específicas de promociones."""
        return [
            '<br><br><strong>Alternativas:</strong>',
            '1. Eliminar o modificar las políticas de promoción que la referencian',
            '2. Marcar la promoción como inactiva en lugar de eliminarla'
        ]


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
        if dj_tz.is_naive(cupon.expira_en):
            expira = dj_tz.make_aware(cupon.expira_en)
        else:
            expira = cupon.expira_en    

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
    except Exception:
        request.session['promo_activa_id'] = None

    request.session['promo_token'] = str(cupon.token)
    
    # ✅ CORRECCIÓN: Usar transaction.atomic() para garantizar consistencia
    with transaction.atomic():
        try:
            request.session.modified = True
            request.session.save()
            logger.debug('[PROMO ACT] Sesión guardada con promo_activa_id=%s promo_token=%s', request.session.get('promo_activa_id'), request.session.get('promo_token'))
        except Exception:
            logger.exception('Error al guardar sesión')
            raise  # Rollback si falla guardado de sesión

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


@login_required
def verificar_ocupacion_salas(request):
    """
    Ejecuta manualmente el análisis de ocupación de salas y devuelve los resultados.
    Solo accesible por administradores.
    """
    user = request.user
    if not (user.is_superuser or getattr(user, 'rol', None) == 'admin'):
        return JsonResponse({'error': 'Acceso denegado'}, status=403)

    try:
        from cine.models import Funcion
        from datetime import timedelta
        
        # ✅ ANÁLISIS PREVIO: Obtener contexto antes de ejecutar
        ahora = timezone.now()
        
        # Verificar políticas activas y sus configuraciones
        politicas_auto = PoliticaPromocion.objects.filter(
            activa=True,
            activar_por_ocupacion=True
        ).select_related('promocion_a_otorgar')
        
        # 🔍 DIAGNÓSTICO DETALLADO: Verificar cada paso del filtrado
        total_politicas = PoliticaPromocion.objects.count()
        politicas_activas = PoliticaPromocion.objects.filter(activa=True).count()
        politicas_con_toggle = politicas_auto.count()  # Activas + toggle habilitado
        
        # Filtrar las que SÍ tienen promoción activa (usando all_objects para bypass del manager)
        from promociones.models.promocion import Promocion
        politicas_con_promo_activa = []
        politicas_con_promo_inactiva = []
        
        for pol in politicas_auto:
            # Verificar si la promoción está activa (usar all_objects para acceso directo)
            if pol.promocion_a_otorgar:
                promo = Promocion.all_objects.filter(pk=pol.promocion_a_otorgar.pk).first()
                if promo and promo.activo:
                    politicas_con_promo_activa.append(pol)
                else:
                    politicas_con_promo_inactiva.append({
                        'politica': pol.nombre,
                        'promocion': pol.promocion_a_otorgar.codigo if pol.promocion_a_otorgar else 'SIN PROMOCIÓN',
                        'promo_activo': promo.activo if promo else None,
                        'promo_exists': promo is not None
                    })
            else:
                # Política sin promoción asignada
                politicas_con_promo_inactiva.append({
                    'politica': pol.nombre,
                    'promocion': 'SIN PROMOCIÓN ASIGNADA',
                    'promo_activo': None,
                    'promo_exists': False
                })
        
        contexto = {
            'tiene_politicas': len(politicas_con_promo_activa) > 0,
            'num_politicas': len(politicas_con_promo_activa),
            'ventana_maxima': 0,
            'cupones_recientes': 0,
            'funciones_con_oferta': 0,
            # Diagnóstico
            'total_politicas': total_politicas,
            'politicas_activas': politicas_activas,
            'politicas_con_toggle': politicas_con_toggle,
            'politicas_con_promo_inactiva': politicas_con_promo_inactiva,
        }
        
        if contexto['tiene_politicas']:
            # Calcular ventana de tiempo máxima
            contexto['ventana_maxima'] = max([p.horas_anticipacion for p in politicas_con_promo_activa])
            
            # Contar funciones que ya tienen oferta activa
            fin_ventana = ahora + timedelta(hours=contexto['ventana_maxima'])
            contexto['funciones_con_oferta'] = Funcion.objects.filter(
                fecha_hora__gte=ahora,
                fecha_hora__lte=fin_ventana,
                estado_promocion='OFERTA_ACTIVA'
            ).count()
            
            # Contar cupones generados en las últimas 24 horas
            hace_24h = ahora - timedelta(hours=24)
            contexto['cupones_recientes'] = CuponGenerado.objects.filter(
                creado_en__gte=hace_24h
            ).count()
        
        # ✅ OPTIMIZACIÓN: Usar verbosity=1 en lugar de 2 para menor overhead
        out = StringIO()
        call_command('ejecutar_yield_management', verbosity=1, stdout=out)
        output = out.getvalue()
        
        # Parsear información relevante del output
        lines = output.split('\n')
        resultado = {
            'success': True,
            'politicas_activas': 0,
            'funciones_evaluadas': 0,
            'ofertas_activadas': 0,
            'cupones_generados': 0,
            'emails_enviados': 0,
            'mensaje': '',  # Mensaje amigable para el usuario
            'detalles': '',  # Información adicional contextual
        }
        
        # Parsear métricas
        for line in lines:
            if 'Políticas activas encontradas:' in line:
                try:
                    resultado['politicas_activas'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Funciones evaluadas:' in line:
                try:
                    resultado['funciones_evaluadas'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Funciones con oferta activada:' in line:
                try:
                    resultado['ofertas_activadas'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Cupones generados:' in line:
                try:
                    resultado['cupones_generados'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Emails enviados:' in line:
                try:
                    resultado['emails_enviados'] = int(line.split(':')[1].strip())
                except:
                    pass
        
        # ✅ MEJORA: Generar mensaje amigable e informativo según resultados y contexto
        if resultado['cupones_generados'] > 0:
            resultado['mensaje'] = f"¡Promociones activadas! Se enviaron {resultado['emails_enviados']} emails a clientes para {resultado['ofertas_activadas']} función(es) con baja ocupación."
            resultado['detalles'] = f"Los cupones expiran según la configuración de cada política (típicamente 60 minutos)."
            
        elif resultado['funciones_evaluadas'] > 0:
            # Hay funciones pero no necesitan promociones
            resultado['mensaje'] = f"✅ Todo bajo control: Se analizaron {resultado['funciones_evaluadas']} función(es) y todas tienen ocupación satisfactoria."
            if contexto['funciones_con_oferta'] > 0:
                resultado['detalles'] = f"Hay {contexto['funciones_con_oferta']} función(es) con ofertas ya activas. "
            if contexto['cupones_recientes'] > 0:
                resultado['detalles'] += f"Se generaron {contexto['cupones_recientes']} cupones en las últimas 24 horas."
            else:
                resultado['detalles'] = f"Las políticas activas revisan funciones en las próximas {contexto['ventana_maxima']} horas con umbrales de ocupación configurados."
                
        elif resultado['politicas_activas'] == 0 or contexto['num_politicas'] == 0:
            # 🔍 DIAGNÓSTICO: Explicar por qué no hay políticas detectadas
            resultado['mensaje'] = "⚙️ Sistema en espera: No se detectaron políticas con análisis automático habilitado."
            
            # Generar detalles de diagnóstico
            if contexto['total_politicas'] == 0:
                resultado['detalles'] = "No hay políticas creadas aún. Crea una política nueva desde el menú de Políticas."
            elif contexto['politicas_activas'] == 0:
                resultado['detalles'] = f"Tienes {contexto['total_politicas']} política(s) pero todas están inactivas. Actívalas editándolas y marcando el switch 'Activa'."
            elif contexto['politicas_con_toggle'] == 0:
                resultado['detalles'] = f"Tienes {contexto['politicas_activas']} política(s) activa(s), pero ninguna tiene habilitado el toggle '⚡ Ocupación Automática'. Edita la política y activa ese toggle para habilitar el análisis automático."
            elif len(contexto['politicas_con_promo_inactiva']) > 0:
                # 🔍 DIAGNÓSTICO ESPECÍFICO: Mostrar qué promociones están inactivas
                detalles_promos = []
                for info in contexto['politicas_con_promo_inactiva'][:5]:  # Máximo 5 ejemplos
                    if info['promo_exists'] is False:
                        detalles_promos.append(f"'{info['politica']}' → {info['promocion']}")
                    elif info['promo_activo'] is False:
                        detalles_promos.append(f"'{info['politica']}' → Promoción '{info['promocion']}' (INACTIVA)")
                    elif info['promo_activo'] is None:
                        detalles_promos.append(f"'{info['politica']}' → Promoción '{info['promocion']}' (NO ENCONTRADA EN BD)")
                
                resultado['detalles'] = f"Tienes {contexto['politicas_con_toggle']} política(s) con análisis automático habilitado.\n\n"
                resultado['detalles'] += f"⚠️ Problemas detectados ({len(contexto['politicas_con_promo_inactiva'])} política(s)):\n\n"
                resultado['detalles'] += '\n'.join(f"• {d}" for d in detalles_promos)
                resultado['detalles'] += "\n\n💡 Solución:\n"
                resultado['detalles'] += "1. Ve a Promociones → Lista de promociones\n"
                resultado['detalles'] += "2. Busca la promoción indicada\n"
                resultado['detalles'] += "3. Edita y marca el campo 'Activo' (switch verde)\n"
                resultado['detalles'] += "4. Guarda los cambios"
            else:
                resultado['detalles'] = "Configuración detectada pero no se pudieron procesar las políticas. Contacta al administrador."
            
        else:
            # Hay políticas pero no hay funciones en la ventana
            resultado['mensaje'] = f"📅 Sin funciones para analizar en este momento."
            resultado['detalles'] = f"Las {contexto['num_politicas']} política(s) activa(s) revisan funciones en las próximas {contexto['ventana_maxima']} horas. "
            if contexto['funciones_con_oferta'] > 0:
                resultado['detalles'] += f"Hay {contexto['funciones_con_oferta']} función(es) con ofertas ya activas (no se repiten envíos). "
            if contexto['cupones_recientes'] > 0:
                resultado['detalles'] += f"Se generaron {contexto['cupones_recientes']} cupones en las últimas 24 horas."
        
        return JsonResponse(resultado)
        
    except Exception as e:
        logger.error(f'Error al ejecutar análisis de ocupación: {e}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
