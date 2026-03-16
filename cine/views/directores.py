from django.views.generic import ListView, UpdateView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.db.models.deletion import ProtectedError
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string

from cine.mixins import AdminRequiredMixin
from cine.models import Director, Pelicula
from cine.forms import DirectorForm


class DirectorListView(AdminRequiredMixin, ListView):
    """
    Lista de directores para gestión administrativa.
    Mismo patrón de interacción que pelicula_list: búsqueda, orden y paginación.
    """
    model = Director
    template_name = 'cine/directores_list.html'
    context_object_name = 'directores'
    paginate_by = 10

    def get_queryset(self):
        queryset = Director.objects.annotate(
            total_peliculas=Coalesce(Count('peliculas', distinct=True), 0)
        )

        search = (self.request.GET.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) | Q(apellido__icontains=search)
            )

        orden = self.request.GET.get('orden', 'apellido')
        orden_mapping = {
            'nombre': 'nombre',
            'nombre_desc': '-nombre',
            'apellido': 'apellido',
            'apellido_desc': '-apellido',
            'fecha_nacimiento': 'fecha_nacimiento',
            'fecha_nacimiento_desc': '-fecha_nacimiento',
            'total_peliculas': 'total_peliculas',
            'total_peliculas_desc': '-total_peliculas',
        }
        queryset = queryset.order_by(orden_mapping.get(orden, 'apellido'), 'nombre')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_search'] = self.request.GET.get('search', '')
        context['filtro_orden'] = self.request.GET.get('orden', 'apellido')
        return context

    def render_to_response(self, context, **response_kwargs):
        request = self.request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.shortcuts import render
            return render(request, 'cine/_director_table.html', context)
        return super().render_to_response(context, **response_kwargs)


class _DirectorMergeMixin:
    @staticmethod
    def _normalizar(valor):
        return ' '.join((valor or '').strip().split()).title()

    def _buscar_existente(self, nombre, apellido, exclude_pk=None):
        qs = Director.objects.filter(nombre__iexact=nombre, apellido__iexact=apellido)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.first()

    def _fusionar_directores(self, director_actual, director_existente, fecha_nacimiento_nueva=None):
        with transaction.atomic():
            total_reasignadas = Pelicula.objects.filter(director=director_actual).update(director=director_existente)

            update_fields = []
            if fecha_nacimiento_nueva and not director_existente.fecha_nacimiento:
                director_existente.fecha_nacimiento = fecha_nacimiento_nueva
                update_fields.append('fecha_nacimiento')

            # Preservar metadata técnica si existe en el registro viejo
            if director_actual.tmdb_id and not director_existente.tmdb_id:
                director_existente.tmdb_id = director_actual.tmdb_id
                update_fields.append('tmdb_id')

            if director_actual.biografia and not director_existente.biografia:
                director_existente.biografia = director_actual.biografia
                update_fields.append('biografia')

            if update_fields:
                director_existente.save(update_fields=update_fields)

            director_actual.soft_delete()

        return total_reasignadas, director_existente


class DirectorCreateView(AdminRequiredMixin, _DirectorMergeMixin, CreateView):
    model = Director
    form_class = DirectorForm
    template_name = 'cine/director_form.html'
    success_url = reverse_lazy('cine:gestionar_directores')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicion'] = False
        return context

    def form_valid(self, form):
        nombre = self._normalizar(form.cleaned_data.get('nombre'))
        apellido = self._normalizar(form.cleaned_data.get('apellido'))
        fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')

        existente = self._buscar_existente(nombre, apellido)
        if existente:
            update_fields = []
            if fecha_nacimiento and not existente.fecha_nacimiento:
                existente.fecha_nacimiento = fecha_nacimiento
                update_fields.append('fecha_nacimiento')
            if update_fields:
                existente.save(update_fields=update_fields)

            messages.warning(
                self.request,
                f'Ya existía el director "{existente}". No se creó duplicado.'
            )
            return redirect(self.success_url)

        self.object = form.save()
        messages.success(self.request, f'Director "{self.object}" creado correctamente.')
        return redirect(self.success_url)


class DirectorUpdateView(AdminRequiredMixin, _DirectorMergeMixin, UpdateView):
    """
    Edición de director con lógica de fusión (merge) si ya existe otro
    director con el mismo nombre+apellido.
    """
    model = Director
    form_class = DirectorForm
    template_name = 'cine/director_form.html'
    success_url = reverse_lazy('cine:gestionar_directores')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_edicion'] = True
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('_action') == 'delete':
            director = self.get_object()
            director_nombre = str(director)
            try:
                director.soft_delete()
                messages.success(request, f'Director "{director_nombre}" eliminado correctamente.')
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'ok': True}, status=200)
            except ProtectedError:
                total = Pelicula.objects.filter(director=director).count()
                mensaje = (
                    f'No se puede eliminar "{director_nombre}" porque tiene {total} película(s) vinculada(s). '
                    f'Primero reasigna esas películas (por ejemplo, usando la fusión al editar).'
                )
                messages.error(request, mensaje)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'ok': False, 'error': mensaje}, status=400)
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        director_actual = self.get_object()

        nombre_nuevo = self._normalizar(form.cleaned_data.get('nombre'))
        apellido_nuevo = self._normalizar(form.cleaned_data.get('apellido'))
        fecha_nacimiento_nueva = form.cleaned_data.get('fecha_nacimiento')

        director_existente = self._buscar_existente(
            nombre_nuevo,
            apellido_nuevo,
            exclude_pk=director_actual.pk,
        )

        if director_existente:
            total_reasignadas, director_existente = self._fusionar_directores(
                director_actual,
                director_existente,
                fecha_nacimiento_nueva,
            )

            messages.success(
                self.request,
                (
                    f'Se fusionaron directores: las {total_reasignadas} película(s) de "{director_actual}" '
                    f'ahora apuntan a "{director_existente}".'
                )
            )
            return redirect(self.success_url)

        self.object = form.save()
        messages.success(self.request, f'Director "{self.object}" actualizado correctamente.')
        return redirect(self.success_url)


class DirectorCrearAjaxView(AdminRequiredMixin, View):
    """
    AJAX endpoint: crea un director directamente en la BD desde el modal del
    formulario de película. Retorna JSON {ok, id, nombre_completo, ya_existia}.
    """

    @staticmethod
    def _normalizar(valor):
        return ' '.join((valor or '').strip().split()).title()

    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Solicitud no permitida.'}, status=400)

        nombre = self._normalizar(request.POST.get('nombre', ''))
        apellido = self._normalizar(request.POST.get('apellido', ''))
        fecha_nacimiento_str = request.POST.get('fecha_nacimiento', '').strip()
        biografia = (request.POST.get('biografia', '') or '').strip()

        if not nombre or not apellido:
            return JsonResponse({'ok': False, 'error': 'Nombre y apellido son obligatorios.'}, status=400)

        # Reusar director existente con mismo nombre en lugar de crear duplicado
        existente = Director.objects.filter(
            nombre__iexact=nombre,
            apellido__iexact=apellido,
        ).first()
        if existente:
            return JsonResponse({
                'ok': True,
                'id': existente.pk,
                'nombre_completo': str(existente),
                'ya_existia': True,
            })

        fecha_nacimiento = None
        if fecha_nacimiento_str:
            from datetime import date as _date
            try:
                fecha_nacimiento = _date.fromisoformat(fecha_nacimiento_str)
            except ValueError:
                pass

        director = Director.objects.create(
            nombre=nombre,
            apellido=apellido,
            fecha_nacimiento=fecha_nacimiento,
            biografia=biografia,
        )
        return JsonResponse({
            'ok': True,
            'id': director.pk,
            'nombre_completo': str(director),
            'ya_existia': False,
        })


class DirectorDeleteView(AdminRequiredMixin, View):
    template_name = 'cine/director_delete_modal.html'
    success_url = reverse_lazy('cine:gestionar_directores')

    def _es_ajax(self, request):
        return request.headers.get('x-requested-with') == 'XMLHttpRequest'

    def _obtener_director(self, pk):
        return Director.objects.filter(pk=pk).first()

    def _contexto_eliminacion(self, director):
        peliculas_qs = Pelicula.all_objects.filter(director=director).order_by('titulo')
        total = peliculas_qs.count()
        activas = peliculas_qs.filter(activo=True).count()
        inactivas = total - activas
        peliculas_muestra = list(peliculas_qs.values_list('titulo', flat=True)[:5])

        return {
            'object': director,
            'director': director,
            'puede_eliminar': total == 0,
            'total_peliculas': total,
            'peliculas_activas': activas,
            'peliculas_inactivas': inactivas,
            'peliculas_muestra': peliculas_muestra,
            'peliculas_restantes': max(total - len(peliculas_muestra), 0),
        }

    def _render_modal(self, request, context):
        html = render_to_string(self.template_name, context=context, request=request)
        return HttpResponse(html)

    def get(self, request, pk):
        director = self._obtener_director(pk)
        if director is None:
            mensaje = 'El director seleccionado ya no existe (posible fusión o eliminación previa).'
            messages.warning(request, mensaje)
            if self._es_ajax(request):
                return JsonResponse(
                    {'ok': False, 'error': mensaje, 'redirect_url': str(self.success_url)},
                    status=404,
                )
            return redirect(self.success_url)

        contexto = self._contexto_eliminacion(director)
        if self._es_ajax(request):
            return self._render_modal(request, contexto)
        return redirect(self.success_url)

    def post(self, request, pk):
        director = self._obtener_director(pk)
        if director is None:
            mensaje = 'El director seleccionado ya no existe (posible fusión o eliminación previa).'
            messages.warning(request, mensaje)
            if self._es_ajax(request):
                return JsonResponse(
                    {'ok': False, 'error': mensaje, 'redirect_url': str(self.success_url)},
                    status=404,
                )
            return redirect(self.success_url)

        director_nombre = str(director)

        try:
            if Pelicula.all_objects.filter(director=director).exists():
                contexto = self._contexto_eliminacion(director)
                mensaje = (
                    f'No se puede eliminar "{director_nombre}" porque tiene '
                    f'{contexto["total_peliculas"]} película(s) vinculada(s).'
                )
                messages.error(request, mensaje)
                if self._es_ajax(request):
                    return JsonResponse(
                        {
                            'ok': False,
                            'error': mensaje,
                            'html': render_to_string(self.template_name, context=contexto, request=request),
                        },
                        status=409,
                    )
                return redirect(self.success_url)

            director.soft_delete()
            messages.success(request, f'Director "{director_nombre}" eliminado correctamente.')
            if self._es_ajax(request):
                return JsonResponse({'ok': True, 'redirect_url': str(self.success_url)})
        except ProtectedError:
            contexto = self._contexto_eliminacion(director)
            mensaje = (
                f'No se puede eliminar "{director_nombre}" porque tiene {contexto["total_peliculas"]} película(s) vinculada(s). '
                f'Primero reasigna esas películas (por ejemplo, usando la fusión al editar).'
            )
            messages.error(request, mensaje)
            if self._es_ajax(request):
                return JsonResponse(
                    {
                        'ok': False,
                        'error': mensaje,
                        'html': render_to_string(self.template_name, context=contexto, request=request),
                    },
                    status=409,
                )

        return redirect(self.success_url)
