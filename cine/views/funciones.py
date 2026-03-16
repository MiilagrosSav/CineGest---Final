from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
from django.http import JsonResponse 
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import datetime, timedelta, date, time
from collections import Counter
import json
from cine.models import Funcion, Pelicula, Sala
from cine.forms import FuncionForm, FuncionBatchForm
from cine.mixins import AdminRequiredMixin
from django.db import transaction  


# --- Vistas del CRUD de Funciones ---
# READ: Vista para listar todas las funciones
class FuncionListView(AdminRequiredMixin, ListView):
    model = Funcion
    template_name = 'cine/funcion_list.html'
    context_object_name = 'funciones'
    paginate_by = 5
    
    def get_queryset(self):
        """Filtrar y ordenar funciones según parámetros de búsqueda"""
        # Primero marcar funciones pasadas como inactivas
        ahora = timezone.localtime(timezone.now())
        Funcion.objects.filter(
            fecha_hora__lt=ahora
        ).exclude(estado='INACTIVA').update(estado='INACTIVA')

        # Transición PREVENTA → ACTIVA: cuando llegó fecha_activacion o es el día de la función
        hoy = ahora.date()
        Funcion.objects.filter(
            estado='PREVENTA',
            fecha_hora__gte=ahora,
        ).filter(
            Q(fecha_activacion__lte=ahora) |
            Q(fecha_activacion__isnull=True, fecha_hora__date__lte=hoy)
        ).update(estado='ACTIVA')
        
        # Filtrar por estado: 'activas' (por defecto) o 'inactivas' (historial)
        estado = self.request.GET.get('estado', 'activas')
        
        # Para el historial, usar all_objects para incluir funciones soft-deleted
        if estado == 'inactivas':
            queryset = Funcion.all_objects.select_related('pelicula', 'sala').prefetch_related('formatos_funcion__formato')
            # Mostrar funciones pasadas O funciones marcadas como inactivas (soft-deleted o estado INACTIVA)
            queryset = queryset.filter(Q(fecha_hora__lt=ahora) | Q(activo=False) | Q(estado='INACTIVA'))
        else:
            queryset = Funcion.objects.select_related('pelicula', 'sala').prefetch_related('formatos_funcion__formato')
            # Mostrar solo funciones activas, futuras y que NO están marcadas como INACTIVA
            queryset = queryset.filter(fecha_hora__gte=ahora).exclude(estado='INACTIVA')
        
        # Filtro por búsqueda (ti­tulo de peli­cula, sala o formato)
        search = self.request.GET.get('search', '').strip()
        if search:
            # buscar por ti­tulo de peli­cula O nombre de sala O nombre de formato (case-insensitive)
            q = (
                Q(pelicula__titulo__icontains=search) | 
                Q(sala__nombre__icontains=search) |
                Q(formatos_funcion__formato__nombre__icontains=search)
            )
            # Si el termino es numerico, tambien buscar por numero de sala
            if search.isdigit():
                try:
                    q |= Q(sala__numero=int(search))
                except ValueError:
                    pass
            queryset = queryset.filter(q).distinct()  # distinct() evita duplicados por formatos multiples
        
        # Filtro por pelicula especi­fica
        pelicula_id = self.request.GET.get('pelicula', '').strip()
        if pelicula_id:
            queryset = queryset.filter(pelicula_id=pelicula_id)
        
        # Filtro por sala especifica
        sala_id = self.request.GET.get('sala', '').strip()
        if sala_id:
            queryset = queryset.filter(sala_id=sala_id)
        
        # Filtro por rango de fecha: fecha_inicio / fecha_fin
        fecha_inicio = self.request.GET.get('fecha_inicio', '').strip()
        fecha_fin = self.request.GET.get('fecha_fin', '').strip()
        try:
            if fecha_inicio:
                fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_hora__date__gte=fecha_inicio_obj)
            if fecha_fin:
                fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_hora__date__lte=fecha_fin_obj)
        except ValueError:
            # ignorar rango si formato invalido
            pass
        
        # Filtro por formato
        formato_id = self.request.GET.get('formato', '').strip()
        if formato_id:
            queryset = queryset.filter(formatos_funcion__formato_id=formato_id)
        
        # Filtro por estado de funcion (ACTIVA, PREVENTA, AGOTADA)
        estado_funcion = self.request.GET.get('estado_funcion', '').strip()
        if estado_funcion:
            queryset = queryset.filter(estado=estado_funcion)
        
        # Ordenamiento
        orden = self.request.GET.get('orden', 'fecha')
        orden_mapping = {
            'pelicula': 'pelicula__titulo',
            'pelicula_desc': '-pelicula__titulo',
            'sala': 'sala__numero',
            'sala_desc': '-sala__numero',
            'fecha': 'fecha_hora',
            'fecha_desc': '-fecha_hora',
            'precio': 'precio_base',
            'precio_desc': '-precio_base',
            'duracion': 'pelicula__duracion',
            'duracion_desc': '-pelicula__duracion',
        }
        queryset = queryset.order_by(orden_mapping.get(orden, 'fecha_hora'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Agregar parametros de busqueda al contexto"""
        from cine.models import Formato
        
        context = super().get_context_data(**kwargs)
        context['filtro_search'] = self.request.GET.get('search', '')
        context['filtro_pelicula'] = self.request.GET.get('pelicula', '')
        context['filtro_sala'] = self.request.GET.get('sala', '')
        
        # Manejar rango de fechas (YYYY-MM-DD) para inputs
        fecha_inicio = self.request.GET.get('fecha_inicio', '')
        fecha_fin = self.request.GET.get('fecha_fin', '')
        context['filtro_fecha_inicio'] = fecha_inicio
        context['filtro_fecha_fin'] = fecha_fin
        # Convertir a formato DD-MM-YYYY para mostrar al usuario (si es necesario)
        def _display(d):
            if not d:
                return ''
            try:
                return datetime.strptime(d, '%Y-%m-%d').date().strftime('%d-%m-%Y')
            except Exception:
                return ''
        context['filtro_fecha_inicio_display'] = _display(fecha_inicio)
        context['filtro_fecha_fin_display'] = _display(fecha_fin)
        
        context['filtro_formato'] = self.request.GET.get('formato', '')
        context['filtro_estado_funcion'] = self.request.GET.get('estado_funcion', '')
        context['filtro_orden'] = self.request.GET.get('orden', 'fecha')
        
        # Pasar listas para los selects
        context['peliculas'] = Pelicula.objects.all().order_by('titulo')
        context['salas'] = Sala.objects.all().order_by('numero')
        context['formatos'] = Formato.objects.all().order_by('nombre')
        
        # Indicar si se esta viendo historial (inactivas)
        context['is_history'] = (self.request.GET.get('estado', 'activas') == 'inactivas')
        context['filtro_estado'] = self.request.GET.get('estado', 'activas')
        
        return context

    def render_to_response(self, context, **response_kwargs):
        """Return only the table fragment for AJAX requests."""
        request = self.request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.shortcuts import render
            return render(request, 'cine/_funcion_table.html', context)
        return super().render_to_response(context, **response_kwargs)

# CREATE: Vista para mostrar el formulario de creacion

def _obtener_excepcion_para_fecha(configuracion, fecha):
    from cine.models import ExcepcionHorario

    return ExcepcionHorario.objects.filter(
        configuracion_cine=configuracion,
        fecha__lte=fecha
    ).filter(
        Q(fecha_fin__isnull=True, fecha=fecha) |
        Q(fecha_fin__gte=fecha)
    ).order_by('fecha').first()


def _obtener_motivo_cierre_dia(configuracion, fecha):
    excepcion = _obtener_excepcion_para_fecha(configuracion, fecha)
    if excepcion and excepcion.cerrado:
        return excepcion.descripcion or 'excepcion de horario'

    if excepcion and not excepcion.cerrado:
        return None

    horarios_dia = configuracion.get_horarios_dia(fecha.weekday())
    if not horarios_dia.exists():
        return 'horario regular (sin atencion configurada para ese dia)'

    return None


def _agregar_intervalo_agenda(agenda_por_fecha, fecha, intervalo):
    agenda_por_fecha.setdefault(fecha, [])
    agenda_por_fecha[fecha].append(intervalo)
    agenda_por_fecha[fecha].sort(key=lambda x: x['inicio'])


def _buscar_conflicto_intervalo(intervalos, inicio, fin, requiere_4d, tiene_4d, tiene_estandar, pelicula_id):
    for intervalo in intervalos:
        if inicio < intervalo['fin'] and fin > intervalo['inicio']:
            if inicio != intervalo['inicio']:
                intervalo['motivo_bisala'] = (
                    f'Conflicto de horario: La sala {intervalo.get("sala_nombre", "")}'.strip() +
                    f' ya está ocupada por "{intervalo.get("titulo", "otra función")}".'
                )
                return intervalo

            requiere_4d_otra = intervalo.get('requiere_4d')
            if intervalo.get('pelicula_id') == pelicula_id:
                if Funcion.permite_solape_bisala(requiere_4d, requiere_4d_otra, tiene_4d, tiene_estandar):
                    continue
                if requiere_4d is None or requiere_4d_otra is None:
                    intervalo['motivo_bisala'] = 'No se puede solapar sin definir formato de experiencia (4D o estandar).'
                elif requiere_4d and requiere_4d_otra:
                    intervalo['motivo_bisala'] = 'Ambas funciones requieren butacas 4D. El solape solo se permite cuando una es 4D y la otra estandar.'
                else:
                    intervalo['motivo_bisala'] = 'Ambas funciones son estandar. El solape solo se permite cuando una es 4D y la otra estandar.'
            else:
                intervalo['motivo_bisala'] = (
                    f'Conflicto de Proyección: La sala {intervalo.get("sala_nombre", "")}'.strip() +
                    f' ya tiene programada la película "{intervalo.get("titulo", "otra función")}" en este horario.'
                )
            return intervalo
    return None


def _registrar_omision(omisiones, fecha_obj, hora_obj, tipo, detalle):
    fecha_str = fecha_obj.strftime('%d/%m/%Y')
    hora_str = hora_obj.strftime('%H:%M') if hora_obj else None

    if hora_str:
        mensaje = f'{fecha_str} {hora_str}: {detalle}'
    else:
        mensaje = f'{fecha_str}: {detalle}'

    omisiones.append({
        'tipo': tipo,
        'fecha': fecha_str,
        'hora': hora_str,
        'detalle': detalle,
        'mensaje': mensaje,
    })


def _descripcion_tipo_omision(tipo):
    descripciones = {
        'antes_estreno': 'intento antes del estreno',
        'cine_cerrado': 'cine cerrado',
        'hora_pasada': 'fecha/hora pasada',
        'fuera_horario': 'fuera de horario de atencion',
        'solape_limpieza': 'solape con limpieza',
        'sala_ocupada': 'sala ocupada',
        'sala_sin_4d': 'sala sin butacas 4D',
        'sala_sin_estandar': 'sala sin butacas estandar',
    }
    return descripciones.get(tipo, tipo)


def _resumen_omisiones_por_tipo(omisiones):
    conteo = Counter(item['tipo'] for item in omisiones)
    partes = [
        f'{cantidad} por {_descripcion_tipo_omision(tipo)}'
        for tipo, cantidad in conteo.items()
    ]
    return ', '.join(partes)


def _procesar_carga_masiva_funciones(
    pelicula,
    sala,
    fechas_objetivo,
    horarios_obj_lista,
    precio,
    idioma,
    estado,
    fecha_activacion,
    formatos_seleccionados=None
):
    from cine.models import ConfiguracionCine

    configuracion = ConfiguracionCine.load()
    minutos_limpieza = configuracion.minutos_limpieza
    duracion_total = timedelta(minutes=pelicula.duracion + minutos_limpieza)
    current_tz = timezone.get_current_timezone()
    ahora = timezone.now()

    omisiones = []
    funciones_a_crear = []
    agenda_por_fecha = {}

    fechas_ordenadas = sorted(fechas_objetivo)
    horarios_ordenados = sorted(horarios_obj_lista)

    if not fechas_ordenadas:
        return [], [], 0

    funciones_existentes = Funcion.objects.select_for_update().filter(
        sala=sala,
        fecha_hora__date__gte=fechas_ordenadas[0],
        fecha_hora__date__lte=fechas_ordenadas[-1]
    ).select_related('pelicula').prefetch_related('formatos_funcion__formato').order_by('fecha_hora')

    requiere_4d = Funcion.requiere_4d_en_formatos(formatos_seleccionados)
    tiene_4d, tiene_estandar = Funcion.sala_tiene_butacas_para(sala)
    if requiere_4d is not None:
        if requiere_4d and not tiene_4d:
            for fecha_objetivo in fechas_ordenadas:
                for hora_obj in horarios_ordenados:
                    _registrar_omision(
                        omisiones,
                        fecha_objetivo,
                        hora_obj,
                        'sala_sin_4d',
                        'No se crea porque la sala no tiene butacas 4D.',
                    )
            omisiones_total = len(omisiones)
            return [], omisiones, omisiones_total

        if requiere_4d is False and not tiene_estandar:
            for fecha_objetivo in fechas_ordenadas:
                for hora_obj in horarios_ordenados:
                    _registrar_omision(
                        omisiones,
                        fecha_objetivo,
                        hora_obj,
                        'sala_sin_estandar',
                        'No se crea porque la sala no tiene butacas estandar.',
                    )
            omisiones_total = len(omisiones)
            return [], omisiones, omisiones_total

    for funcion_existente in funciones_existentes:
        inicio_existente = funcion_existente.fecha_hora
        fin_existente = inicio_existente + timedelta(
            minutes=funcion_existente.pelicula.duracion + minutos_limpieza
        )
        fecha_existente = timezone.localtime(inicio_existente).date() if timezone.is_aware(inicio_existente) else inicio_existente.date()
        _agregar_intervalo_agenda(
            agenda_por_fecha,
            fecha_existente,
            {
                'inicio': inicio_existente,
                'fin': fin_existente,
                'origen': 'existente',
                'titulo': funcion_existente.pelicula.titulo,
                'requiere_4d': Funcion.requiere_4d_en_formatos(funcion_existente.formatos_funcion.all()),
                'pelicula_id': funcion_existente.pelicula_id,
                'sala_nombre': sala.nombre,
            }
        )

    for fecha_objetivo in fechas_ordenadas:

        if fecha_objetivo < pelicula.fecha_estreno:
            for hora_obj in horarios_ordenados:
                _registrar_omision(
                    omisiones,
                    fecha_objetivo,
                    hora_obj,
                    'antes_estreno',
                    (
                        f'No se crea porque "{pelicula.titulo}" se estrena el '
                        f'{pelicula.fecha_estreno.strftime("%d/%m/%Y")}.'
                    ),
                )
            continue

        motivo_cierre = _obtener_motivo_cierre_dia(configuracion, fecha_objetivo)
        if motivo_cierre:
            for hora_obj in horarios_ordenados:
                _registrar_omision(
                    omisiones,
                    fecha_objetivo,
                    hora_obj,
                    'cine_cerrado',
                    f'No se crea porque el cine esta cerrado por: {motivo_cierre}.',
                )
            continue

        agenda_dia = agenda_por_fecha.setdefault(fecha_objetivo, [])

        for hora_obj in horarios_ordenados:
            fecha_hora = timezone.make_aware(
                datetime.combine(fecha_objetivo, hora_obj),
                current_tz
            )
            fin_funcion = fecha_hora + duracion_total

            if fecha_hora < ahora:
                _registrar_omision(
                    omisiones,
                    fecha_objetivo,
                    hora_obj,
                    'hora_pasada',
                    'No se crea porque la fecha y hora de inicio ya pasaron.',
                )
                continue

            es_valido, mensaje_error = configuracion.validar_rango_horario(
                fecha_hora,
                fin_funcion
            )
            if not es_valido:
                _registrar_omision(
                    omisiones,
                    fecha_objetivo,
                    hora_obj,
                    'fuera_horario',
                    f'No se crea porque queda fuera del horario permitido: {mensaje_error}',
                )
                continue

            conflicto = _buscar_conflicto_intervalo(
                agenda_dia,
                fecha_hora,
                fin_funcion,
                requiere_4d,
                tiene_4d,
                tiene_estandar,
                pelicula.id,
            )
            if conflicto:
                motivo_bisala = conflicto.get('motivo_bisala')
                motivo_bisala_texto = f' {motivo_bisala}' if motivo_bisala else ''
                if conflicto.get('origen') == 'nuevo':
                    fin_conflicto = conflicto.get('fin')
                    fin_conflicto_str = (
                        timezone.localtime(fin_conflicto).strftime('%H:%M')
                        if fin_conflicto and timezone.is_aware(fin_conflicto)
                        else fin_conflicto.strftime('%H:%M') if fin_conflicto else 'hora desconocida'
                    )
                    _registrar_omision(
                        omisiones,
                        fecha_objetivo,
                        hora_obj,
                        'solape_limpieza',
                        (
                            f'No se crea porque solapa con el tiempo de limpieza de la funcion anterior '
                            f'(la sala queda libre recien a las {fin_conflicto_str}).{motivo_bisala_texto}'
                        ),
                    )
                else:
                    inicio_conflicto = conflicto.get('inicio')
                    fin_conflicto = conflicto.get('fin')
                    if inicio_conflicto and timezone.is_aware(inicio_conflicto):
                        inicio_conflicto = timezone.localtime(inicio_conflicto)
                    if fin_conflicto and timezone.is_aware(fin_conflicto):
                        fin_conflicto = timezone.localtime(fin_conflicto)
                    inicio_conflicto_str = inicio_conflicto.strftime('%H:%M') if inicio_conflicto else 'hora desconocida'
                    fin_conflicto_str = fin_conflicto.strftime('%H:%M') if fin_conflicto else 'hora desconocida'
                    _registrar_omision(
                        omisiones,
                        fecha_objetivo,
                        hora_obj,
                        'sala_ocupada',
                        (
                            f'No se crea porque la Sala {sala.nombre} esta ocupada por '
                            f'"{conflicto.get("titulo", "otra funcion")}" entre '
                            f'{inicio_conflicto_str} y {fin_conflicto_str}.{motivo_bisala_texto}'
                        ),
                    )
                continue

            funcion_nueva = Funcion(
                pelicula=pelicula,
                sala=sala,
                fecha_hora=fecha_hora,
                precio_base=precio,
                idioma=idioma,
                estado=estado,
                fecha_activacion=fecha_activacion
            )
            funciones_a_crear.append(funcion_nueva)
            _agregar_intervalo_agenda(
                agenda_por_fecha,
                fecha_objetivo,
                {
                    'inicio': fecha_hora,
                    'fin': fin_funcion,
                    'origen': 'nuevo',
                    'titulo': pelicula.titulo,
                    'requiere_4d': requiere_4d,
                    'pelicula_id': pelicula.id,
                    'sala_nombre': sala.nombre,
                }
            )

    funciones_creadas = Funcion.objects.bulk_create(funciones_a_crear)
    omisiones_total = len(omisiones)
    return funciones_creadas, omisiones, omisiones_total


@ensure_csrf_cookie
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or getattr(u, 'rol', None) == 'admin'), login_url='/accounts/dashboard/')
def funcion_create_view(request):
    if request.method == 'POST':
        form = FuncionBatchForm(request.POST)
        if form.is_valid():
            pelicula = form.cleaned_data['pelicula']
            sala = form.cleaned_data['sala']
            fechas_objetivo = form.cleaned_data['fechas_objetivo']
            precio = form.cleaned_data['precio_base']
            idioma = form.cleaned_data.get('idioma')
            estado = form.cleaned_data.get('estado', 'ACTIVA')
            fecha_activacion_date = form.cleaned_data.get('fecha_activacion')

            fecha_activacion = None
            if fecha_activacion_date:
                fecha_activacion = timezone.make_aware(
                    datetime.combine(fecha_activacion_date, time(0, 0))
                )

            formato_visual = form.cleaned_data.get('formatos_visual')
            formato_pantalla = form.cleaned_data.get('formatos_pantalla')
            formato_experiencia = form.cleaned_data.get('formatos_experiencia')
            horarios_obj_lista = form.cleaned_data['horarios']
            formatos_seleccionados = [f for f in (formato_visual, formato_pantalla, formato_experiencia) if f]

            try:
                with transaction.atomic():
                    funciones_creadas, omisiones, omisiones_total = _procesar_carga_masiva_funciones(
                        pelicula=pelicula,
                        sala=sala,
                        fechas_objetivo=fechas_objetivo,
                        horarios_obj_lista=horarios_obj_lista,
                        precio=precio,
                        idioma=idioma,
                        estado=estado,
                        fecha_activacion=fecha_activacion,
                        formatos_seleccionados=formatos_seleccionados,
                    )

                    if any(funcion.pk is None for funcion in funciones_creadas):
                        fechas_hora_creadas = [funcion.fecha_hora for funcion in funciones_creadas]
                        funciones_creadas = list(
                            Funcion.objects.filter(
                                pelicula=pelicula,
                                sala=sala,
                                fecha_hora__in=fechas_hora_creadas
                            ).order_by('fecha_hora')
                        )

                    if formatos_seleccionados and funciones_creadas:
                        from cine.models import FuncionFormato

                        formatos_a_crear = []
                        for funcion in funciones_creadas:
                            for formato in formatos_seleccionados:
                                formatos_a_crear.append(
                                    FuncionFormato(funcion=funcion, formato=formato)
                                )
                        FuncionFormato.objects.bulk_create(formatos_a_crear)
            except Exception as e:
                form.add_error(None, f'No se pudo guardar el lote completo de funciones: {e}')
            else:
                total_funciones = len(funciones_creadas)
                if total_funciones > 0:
                    messages.success(request, f'Se crearon {total_funciones} funciones correctamente.')

                if omisiones:
                    for indice, omision in enumerate(omisiones, start=1):
                        messages.warning(
                            request,
                            f'Omitida {indice}/{omisiones_total}: {omision["mensaje"]}'
                        )

                if total_funciones > 0:
                    return redirect('cine:funcion_list')
                return redirect('cine:funcion_create')
    else:
        form = FuncionBatchForm()

    context = {
        'form': form,
        'titulo_pagina': 'Programar Nuevas Funciones (por Lote)',
        'nombre_boton': 'Crear Funciones'
    }
    return render(request, 'cine/funcion_form.html', context)


# UPDATE: Vista para mostrar el formulario de edicion
class FuncionUpdateView(AdminRequiredMixin, UpdateView):
    model = Funcion
    form_class = FuncionBatchForm  # Usar el mismo formulario que para creacion
    template_name = 'cine/funcion_form.html'
    success_url = reverse_lazy('cine:funcion_list')

    def dispatch(self, request, *args, **kwargs):
        """Validar que la funcion no haya terminado antes de permitir edicion"""
        # Necesitamos establecer self.object antes de validar
        self.object = self.get_object()
        funcion = self.object
        ahora = timezone.now()
        
        # Calcular hora de fin de la funcion
        duracion_pelicula = funcion.pelicula.duracion
        hora_fin = funcion.fecha_hora + timedelta(minutes=duracion_pelicula)
        
        # Si la funcion ya termino, no permitir edicion
        if hora_fin < ahora:
            messages.error(
                request,
                f'No se puede editar la función de "{funcion.pelicula.titulo}" porque ya finalizó '
                f'el {hora_fin.strftime("%d/%m/%Y a las %H:%M")}.'
            )
            return redirect('cine:funcion_list')
        
        return super(UpdateView, self).dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Sobrescribir para no pasar 'instance' a un Form (solo para ModelForm)"""
        kwargs = {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
            'funcion': self.object,  # Pasar la funcion para validar ventas
        }
        
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
        
        return kwargs
    
    def get_initial(self):
        """Inicializar el formulario con los datos de la función existente"""
        initial = super().get_initial()
        funcion = self.object
        
        # Separar fecha_hora en rango y dias
        initial['pelicula'] = funcion.pelicula.id
        initial['sala'] = funcion.sala.id
        fecha_local = timezone.localtime(funcion.fecha_hora) if timezone.is_aware(funcion.fecha_hora) else funcion.fecha_hora
        fecha_funcion = fecha_local.strftime('%Y-%m-%d')
        initial['fecha_inicio'] = fecha_funcion
        initial['fecha_fin'] = fecha_funcion
        initial['dias_semana'] = [str(fecha_local.weekday())]
        
        initial['precio_base'] = funcion.precio_base
        
        # Cargar los formatos actuales usando los IDs
        formatos_actuales = funcion.formatos_funcion.select_related('formato').all()
        visual = formatos_actuales.filter(formato__nombre__in=['2D', '3D']).first()
        pantalla = formatos_actuales.filter(formato__nombre__in=['Pantalla estándar', 'IMAX', 'ScreenX']).first()
        experiencia = formatos_actuales.filter(formato__nombre__in=['Experiencia estándar', '4D', 'D-BOX']).first()
        
        if visual:
            initial['formatos_visual'] = visual.formato.id
        if pantalla:
            initial['formatos_pantalla'] = pantalla.formato.id
        if experiencia:
            initial['formatos_experiencia'] = experiencia.formato.id
        
        # Cargar el idioma desde el campo directo de Funcion (no desde formatos)
        if funcion.idioma:
            initial['idioma'] = funcion.idioma
        
        # Cargar el estado de la funcion
        if funcion.estado:
            initial['estado'] = funcion.estado
        
        # Cargar la fecha de activaciónn si existe (para funciones en PREVENTA)
        if funcion.fecha_activacion:
            # Solo pasar la fecha, sin hora
            initial['fecha_activacion'] = funcion.fecha_activacion.strftime('%Y-%m-%d')

        # Fallbacks: si no encontró formatos, elegir una opción 'estándar' por categoria
        try:
            from cine.models.formato import Formato
            if not initial.get('formatos_visual'):
                fallback = Formato.objects.filter(nombre__in=['2D', '2D Estándar']).first() or Formato.objects.filter(categoria='VISUAL').order_by('nombre').first()
                if fallback:
                    initial['formatos_visual'] = fallback.id

            if not initial.get('formatos_pantalla'):
                fallback = Formato.objects.filter(nombre__icontains='estándar', categoria='PANTALLA').first() or Formato.objects.filter(categoria='PANTALLA').order_by('nombre').first()
                if fallback:
                    initial['formatos_pantalla'] = fallback.id

            if not initial.get('formatos_experiencia'):
                fallback = Formato.objects.filter(nombre__icontains='Estándar', categoria='EXPERIENCIA').first() or Formato.objects.filter(categoria='EXPERIENCIA').order_by('nombre').first()
                if fallback:
                    initial['formatos_experiencia'] = fallback.id
        except Exception:
            pass

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar Función'
        context['nombre_boton'] = 'Guardar Cambios'
        context['es_edicion'] = True
        
        # Agregar info de la funcion actual para el JavaScript (como JSON)
        funcion = self.object
        funcion_data = {
            'id': funcion.id,
            'pelicula_id': funcion.pelicula.id,
            'sala_id': funcion.sala.id,
            'fecha': funcion.fecha_hora.strftime('%Y-%m-%d'),
            'hora': funcion.fecha_hora.strftime('%H:%M'),
        }
        context['funcion_actual'] = json.dumps(funcion_data)
        
        return context
    
    def form_valid(self, form):
        """Actualizar la funcion con los datos del formulario batch"""
        from cine.models import FuncionFormato
        
        # No permitir modificar funciones con entradas vendidas
        if hasattr(form, '_tiene_entradas_vendidas') and form._tiene_entradas_vendidas:
            messages.error(
                self.request,
                'No se puede modificar una función con entradas vendidas. '
                'Por contrato con el cliente, esta información es INMUTABLE.'
            )
            return redirect('cine:funcion_list')
        
        # Validar nuevamente que la función no haya terminado
        ahora = timezone.now()
        duracion_pelicula = self.object.pelicula.duracion
        hora_fin = self.object.fecha_hora + timedelta(minutes=duracion_pelicula)
        
        if hora_fin < ahora:
            messages.error(
                self.request,
                'No se puede modificar una función que ya finalizó.'
            )
            return redirect('cine:funcion_list')
        
        # Obtener los datos del formulario
        pelicula = form.cleaned_data['pelicula']
        sala = form.cleaned_data['sala']
        fecha = form.cleaned_data['fecha_inicio']
        horarios = form.cleaned_data['horarios']  # Lista de objetos time
        precio_base = form.cleaned_data['precio_base']
        idioma = form.cleaned_data.get('idioma')  # String: 'DOBLADA', 'SUBTITULADA', 'NATIVA'
        estado = form.cleaned_data.get('estado', 'ACTIVA')  # String: 'ACTIVA', 'PREVENTA', 'AGOTADA'
        fecha_activacion_date = form.cleaned_data.get('fecha_activacion')  # Date opcional para PREVENTA
        
        # Convertir fecha de activación a datetime a las 00:00 si existe
        fecha_activacion = None
        if fecha_activacion_date:
            fecha_activacion = timezone.make_aware(
                datetime.combine(fecha_activacion_date, time(0, 0))
            )
        
        # En edición, tomar el primer horario seleccionado
        # (Si seleccionaron múltiples, solo se usará el primero para actualizar esta función)
        if isinstance(horarios, list) and len(horarios) > 0:
            horario = horarios[0]
        else:
            horario = horarios
        
        # Combinar fecha + horario en datetime
        fecha_hora = timezone.make_aware(datetime.combine(fecha, horario))
        
        # Actualizar la función
        self.object.pelicula = pelicula
        self.object.sala = sala
        self.object.fecha_hora = fecha_hora
        self.object.precio_base = precio_base
        self.object.idioma = idioma
        self.object.estado = estado
        self.object.fecha_activacion = fecha_activacion

        # Obtener los formatos seleccionados por categoria (solo los 3 formatos reales)
        formato_visual = form.cleaned_data.get('formatos_visual')
        formato_pantalla = form.cleaned_data.get('formatos_pantalla')
        formato_experiencia = form.cleaned_data.get('formatos_experiencia')

        try:
            with transaction.atomic():
                self.object._formatos_seleccionados = [
                    formato_visual,
                    formato_pantalla,
                    formato_experiencia,
                ]
                self.object.save()

                # Eliminar formatos antiguos
                self.object.formatos_funcion.all().delete()

                # Crear los nuevos formatos (solo los 3 formatos, no el idioma)
                for formato in (formato_visual, formato_pantalla, formato_experiencia):
                    if formato:
                        FuncionFormato.objects.create(funcion=self.object, formato=formato)
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                for field_name, field_errors in e.message_dict.items():
                    for error in field_errors:
                        if field_name in form.fields:
                            form.add_error(field_name, error)
                        else:
                            form.add_error(None, error)
            else:
                for error in e.messages:
                    form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(self.request, 'Funcion actualizada correctamente.')
        return redirect(self.success_url)

# DELETE: Vista para confirmar la eliminación
class FuncionDeleteView(AdminRequiredMixin, DeleteView):
    model = Funcion
    template_name = 'cine/funcion_confirm_delete.html'
    success_url = reverse_lazy('cine:funcion_list')
    
    def get_queryset(self):
        """
        Usar all_objects para permitir acceso a funciones ya eliminadas (soft delete).
        Esto previene 404 al acceder a la página de confirmación de eliminación.
        """
        return Funcion.all_objects.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funcion = self.get_object()
        
        # Verificar si tiene entradas asociadas
        from ventas.models import Entrada, Intercambio
        entradas = Entrada.objects.filter(id_funcion=funcion)
        intercambios_origen = Intercambio.objects.filter(funcion_origen=funcion)
        intercambios_destino = Intercambio.objects.filter(funcion_destino=funcion)
        
        tiene_entradas = entradas.exists()
        tiene_intercambios = intercambios_origen.exists() or intercambios_destino.exists()
        
        context['tiene_entradas'] = tiene_entradas
        context['total_entradas'] = entradas.count()
        context['tiene_intercambios'] = tiene_intercambios
        context['total_intercambios'] = intercambios_origen.count() + intercambios_destino.count()
        context['puede_eliminar'] = not (tiene_entradas or tiene_intercambios)
        
        # Contar entradas por estado
        if tiene_entradas:
            context['entradas_vendidas'] = entradas.filter(estado='VENDIDA').count()
            context['entradas_reservadas'] = entradas.filter(estado='RESERVADA').count()
            context['entradas_canceladas'] = entradas.filter(estado='CANCELADA').count()
        
        return context
    
    def delete(self, request, *args, **kwargs):
        """Sobrescribir delete para manejar ProtectedError y pasar usuario al soft delete"""
        from django.db.models.deletion import ProtectedError
        
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        try:
            # Llamar a soft_delete con el usuario para registro de auditorí­a
            if hasattr(self.object, 'soft_delete'):
                self.object.soft_delete(user=request.user)
            else:
                self.object.delete()
            
            messages.success(
                request,
                f'La función de "{self.object.pelicula.titulo}" del {self.object.fecha_hora.strftime("%d/%m/%Y %H:%M")} ha sido eliminada exitosamente.'
            )
            return redirect(success_url)
            
        except ProtectedError as e:
            # Extraer información de las entradas e intercambios protegidos
            protected_objects = e.protected_objects
            
            # Contar entradas e intercambios
            from ventas.models import Entrada, Intercambio
            entradas = [obj for obj in protected_objects if isinstance(obj, Entrada)]
            intercambios = [obj for obj in protected_objects if isinstance(obj, Intercambio)]
            
            # Construir mensaje detallado
            msg_parts = [
                f'No se puede eliminar la función de "{self.object.pelicula.titulo}" '
                f'del {self.object.fecha_hora.strftime("%d/%m/%Y a las %H:%M")} porque tiene:'
            ]
            
            if entradas:
                # Contar entradas por estado
                estados_count = {}
                for entrada in entradas:
                    estado = entrada.estado
                    estados_count[estado] = estados_count.get(estado, 0) + 1
                
                estados_str = ', '.join([f'{count} {estado}(S)' for estado, count in estados_count.items()])
                msg_parts.append(f'• {len(entradas)} entrada(s) asociada(s) [{estados_str}]')
            
            if intercambios:
                msg_parts.append(f'• {len(intercambios)} intercambio(s) asociado(s)')
            
            msg_parts.append('')
            msg_parts.append('¡ Para poder eliminar esta función, primero debe:')
            if entradas:
                msg_parts.append('   1. Cancelar o eliminar las entradas asociadas')
            if intercambios:
                msg_parts.append(f'   {"2" if entradas else "1"}. Cancelar o eliminar los intercambios asociados')
            
            messages.error(request, '\n'.join(msg_parts))
            return redirect('cine:funcion_list')


def _parse_dias_semana(dias_semana_raw):
    dias = []
    for item in dias_semana_raw:
        for value in str(item).split(','):
            value = value.strip()
            if not value:
                continue
            try:
                dia_int = int(value)
            except ValueError:
                raise ValueError('dias_semana inválido')
            if dia_int < 0 or dia_int > 6:
                raise ValueError('dias_semana inválido')
            dias.append(dia_int)
    return sorted(set(dias))


def _sort_hora_str(hora_str):
    horas, minutos = hora_str.split(':')
    return int(horas), int(minutos)


def _calcular_horarios_para_fecha(pelicula, sala, fecha, funcion_id=None, formato_experiencia_id=None):
    """
    Calcula horarios disponibles para una fecha puntual.
    Reutilizable por modo simple (una fecha) y modo rango.
    """
    from django.db.models import Q
    from cine.models import ConfiguracionCine, ExcepcionHorario

    if fecha < date.today():
        return {
            'horarios': [],
            'duracion_total': 0,
            'mensaje': 'La fecha no puede ser en el pasado.',
            'cerrado': True,
            'error': True
        }

    configuracion = ConfiguracionCine.load()
    minutos_limpieza = configuracion.minutos_limpieza
    duracion_total_minutos = pelicula.duracion + minutos_limpieza

    funciones_existentes = Funcion.objects.filter(
        sala=sala,
        fecha_hora__date=fecha
    ).select_related('pelicula').prefetch_related('formatos_funcion__formato').order_by('fecha_hora')

    if funcion_id:
        funciones_existentes = funciones_existentes.exclude(pk=funcion_id)

    requiere_4d_nueva = None
    if formato_experiencia_id:
        try:
            from cine.models import Formato
            formato_experiencia = Formato.objects.get(pk=formato_experiencia_id)
            requiere_4d_nueva = Funcion.requiere_4d_en_formatos([formato_experiencia])
        except (Formato.DoesNotExist, ValueError, TypeError):
            requiere_4d_nueva = None

    tiene_4d, tiene_estandar = Funcion.sala_tiene_butacas_para(sala)
    permite_solape_estandar_con_4d = (
        requiere_4d_nueva is False and tiene_4d and tiene_estandar
    )
    aviso_solape_bisala = False

    excepciones = ExcepcionHorario.objects.filter(
        configuracion_cine=configuracion,
        fecha__lte=fecha
    ).filter(
        Q(fecha_fin__isnull=True, fecha=fecha) |
        Q(fecha_fin__gte=fecha)
    )

    if excepciones.exists():
        excepcion = excepciones.first()

        if excepcion.cerrado:
            return {
                'horarios': [],
                'duracion_total': duracion_total_minutos,
                'mensaje': f'El cine esta cerrado el {fecha.strftime("%d/%m/%Y")}. Motivo: {excepcion.descripcion or "Cerrado"}',
                'cerrado': True
            }

        if not (excepcion.hora_apertura and excepcion.hora_cierre):
            return {
                'horarios': [],
                'duracion_total': duracion_total_minutos,
                'mensaje': 'Excepción de horario malformada.',
                'cerrado': True,
                'error': True
            }

        class HorarioExcepcional:
            def __init__(self, apertura, cierre):
                self.hora_apertura = apertura
                self.hora_cierre = cierre

        horarios_dia = [HorarioExcepcional(excepcion.hora_apertura, excepcion.hora_cierre)]
    else:
        dia_semana = fecha.weekday()
        horarios_dia = configuracion.get_horarios_dia(dia_semana)
        if not horarios_dia.exists():
            return {
                'horarios': [],
                'duracion_total': duracion_total_minutos,
                'mensaje': 'El cine esta cerrado ese dia.',
                'cerrado': True
            }

    horarios_disponibles = []
    horarios_solapados = set()
    ahora = timezone.localtime(timezone.now())
    hora_minima_naive = None
    if fecha == ahora.date():
        hora_minima = ahora + timedelta(minutes=30)
        hora_minima_naive = hora_minima.replace(tzinfo=None)

    for horario in horarios_dia:
        hora_actual = datetime.combine(fecha, horario.hora_apertura)
        hora_cierre = datetime.combine(fecha, horario.hora_cierre)

        if hora_minima_naive and hora_actual < hora_minima_naive:
            hora_actual = hora_minima_naive
            minutos = hora_actual.minute
            minutos_redondeados = ((minutos + 14) // 15) * 15
            if minutos_redondeados >= 60:
                hora_actual = hora_actual.replace(minute=0) + timedelta(hours=1)
            else:
                hora_actual = hora_actual.replace(minute=minutos_redondeados)

        while hora_actual <= hora_cierre:
            fin_funcion = hora_actual + timedelta(minutes=duracion_total_minutos)
            if fin_funcion.time() > horario.hora_cierre:
                break

            hay_solapamiento = False
            solape_permitido = False
            for funcion_existente in funciones_existentes:
                inicio_existente = funcion_existente.fecha_hora
                if timezone.is_aware(inicio_existente):
                    inicio_existente = timezone.localtime(inicio_existente).replace(tzinfo=None)

                fin_existente = inicio_existente + timedelta(
                    minutes=funcion_existente.pelicula.duracion + minutos_limpieza
                )

                if hora_actual < fin_existente and fin_funcion > inicio_existente:
                    requiere_4d_existente = Funcion.requiere_4d_en_formatos(
                        funcion_existente.formatos_funcion.all()
                    )
                    if (
                        permite_solape_estandar_con_4d
                        and requiere_4d_existente is True
                        and funcion_existente.pelicula_id == pelicula.id
                        and hora_actual == inicio_existente
                    ):
                        aviso_solape_bisala = True
                        solape_permitido = True
                        continue
                    if hora_actual != inicio_existente:
                        hay_solapamiento = True
                        break
                    hay_solapamiento = True
                    break

            if not hay_solapamiento:
                horario_str = hora_actual.strftime('%H:%M')
                if horario_str not in horarios_disponibles:
                    horarios_disponibles.append(horario_str)
                if solape_permitido:
                    horarios_solapados.add(horario_str)

            hora_actual += timedelta(minutes=15)

    mensaje_base = (
        f'Cada funcion dura {pelicula.duracion} min + {minutos_limpieza} min de limpieza '
        f'= {duracion_total_minutos} min total'
    )
    if aviso_solape_bisala:
        mensaje_base = (
            f'{mensaje_base}. Aviso: se habilitan horarios solapados porque '
            f'Experiencia estandar no usa butacas 4D y la pelicula es la misma.'
        )

    return {
        'horarios': horarios_disponibles,
        'duracion_total': duracion_total_minutos,
        'mensaje': mensaje_base,
        'horarios_solapados': sorted(horarios_solapados, key=_sort_hora_str),
        'cerrado': len(horarios_disponibles) == 0
    }


@login_required
def precheck_dias_semana_disponibles(request):
    """
    Pre-chequeo preventivo para el frontend.
    Deshabilita dias de semana que dentro del rango no tienen disponibilidad en ninguna fecha.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    pelicula_id = request.GET.get('pelicula_id')
    sala_id = request.GET.get('sala_id')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    formato_experiencia_id = request.GET.get('formato_experiencia_id')

    if not all([pelicula_id, sala_id, fecha_inicio_str, fecha_fin_str]):
        return JsonResponse({'error': 'Faltan parámetros'}, status=400)

    try:
        pelicula = Pelicula.objects.get(pk=pelicula_id)
        sala = Sala.objects.get(pk=sala_id)
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except (Pelicula.DoesNotExist, Sala.DoesNotExist):
        return JsonResponse({'error': 'Película o sala no encontrada'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido'}, status=400)

    if fecha_fin < fecha_inicio:
        return JsonResponse({'error': 'La fecha_fin debe ser igual o posterior a fecha_inicio.'}, status=400)

    dias_nombres = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
    respuesta_dias = []

    for dia in range(7):
        fechas_del_dia = []
        fecha_cursor = fecha_inicio
        while fecha_cursor <= fecha_fin:
            if fecha_cursor.weekday() == dia:
                fechas_del_dia.append(fecha_cursor)
            fecha_cursor += timedelta(days=1)

        if not fechas_del_dia:
            respuesta_dias.append({
                'dia': dia,
                'nombre': dias_nombres[dia],
                'disabled': True,
                'motivo': 'Sin fechas de este dia dentro del rango seleccionado.'
            })
            continue

        disponible_en_alguna = False
        cierres_totales = 0
        motivos = []

        for fecha in fechas_del_dia:
            resultado = _calcular_horarios_para_fecha(
                pelicula,
                sala,
                fecha,
                formato_experiencia_id=formato_experiencia_id,
            )
            horarios = resultado.get('horarios', [])
            mensaje = resultado.get('mensaje', 'Sin disponibilidad')

            if horarios:
                disponible_en_alguna = True
            else:
                motivos.append(f'{fecha.strftime("%d/%m/%Y")}: {mensaje}')
                if 'cerrad' in mensaje.lower():
                    cierres_totales += 1

        if disponible_en_alguna:
            respuesta_dias.append({
                'dia': dia,
                'nombre': dias_nombres[dia],
                'disabled': False,
                'motivo': ''
            })
            continue

        if cierres_totales == len(fechas_del_dia):
            motivo = 'Cine cerrado en todas las fechas de este dia.'
        else:
            motivo = 'Sin horarios disponibles en todas las fechas de este dia.'

        if motivos:
            motivo = f'{motivo} ({motivos[0]})'

        respuesta_dias.append({
            'dia': dia,
            'nombre': dias_nombres[dia],
            'disabled': True,
            'motivo': motivo
        })

    return JsonResponse({'dias': respuesta_dias})


# AJAX: Vista para calcular horarios disponibles
@login_required
def calcular_horarios_disponibles(request):
    """
    Soporta 2 modos:
    - Modo fecha puntual: pelicula + sala + fecha
    - Modo rango: pelicula + sala + fecha_inicio + fecha_fin + dias_semana[]

    En modo rango devuelve solo horarios comunes disponibles para todas las fechas seleccionadas.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    pelicula_id = request.GET.get('pelicula_id')
    sala_id = request.GET.get('sala_id')
    funcion_id = request.GET.get('funcion_id')
    fecha_str = request.GET.get('fecha')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    dias_semana_raw = request.GET.getlist('dias_semana')
    formato_experiencia_id = request.GET.get('formato_experiencia_id')

    if not pelicula_id or not sala_id:
        return JsonResponse({'error': 'Faltan parámetros'}, status=400)

    try:
        pelicula = Pelicula.objects.get(pk=pelicula_id)
        sala = Sala.objects.get(pk=sala_id)
    except (Pelicula.DoesNotExist, Sala.DoesNotExist):
        return JsonResponse({'error': 'Película o sala no encontrada'}, status=404)

    # Modo rango
    if fecha_inicio_str or fecha_fin_str:
        if not fecha_inicio_str or not fecha_fin_str:
            return JsonResponse({'error': 'Debes enviar fecha_inicio y fecha_fin.'}, status=400)

        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            dias_semana = _parse_dias_semana(dias_semana_raw)
        except ValueError:
            return JsonResponse({'error': 'Formato de fecha o dí­as inválido.'}, status=400)

        if fecha_fin < fecha_inicio:
            return JsonResponse({'error': 'La fecha_fin debe ser igual o posterior a fecha_inicio.'}, status=400)

        if not dias_semana:
            return JsonResponse({'error': 'Debes seleccionar al menos un dí­a de la semana.'}, status=400)

        fechas_objetivo = []
        fecha_cursor = fecha_inicio
        dias_set = set(dias_semana)
        while fecha_cursor <= fecha_fin:
            if fecha_cursor.weekday() in dias_set:
                fechas_objetivo.append(fecha_cursor)
            fecha_cursor += timedelta(days=1)

        duracion_total = pelicula.duracion
        if not fechas_objetivo:
            return JsonResponse({
                'horarios': [],
                'duracion_total': duracion_total,
                'mensaje': 'No hay fechas dentro del rango que coincidan con los dí­as seleccionados.',
                'cerrado': True
            })

        horarios_comunes = None
        solapados_comunes = None
        dias_sin_disponibilidad = []
        duracion_total = 0

        for fecha in fechas_objetivo:
            resultado_fecha = _calcular_horarios_para_fecha(
                pelicula=pelicula,
                sala=sala,
                fecha=fecha,
                funcion_id=funcion_id,
                formato_experiencia_id=formato_experiencia_id,
            )
            duracion_total = resultado_fecha.get('duracion_total', duracion_total)

            if resultado_fecha.get('error'):
                return JsonResponse({'error': resultado_fecha['mensaje']}, status=400)

            horarios_fecha = set(resultado_fecha.get('horarios', []))
            solapados_fecha = set(resultado_fecha.get('horarios_solapados', []))
            if horarios_comunes is None:
                horarios_comunes = horarios_fecha
            else:
                horarios_comunes &= horarios_fecha

            if solapados_comunes is None:
                solapados_comunes = solapados_fecha
            else:
                solapados_comunes &= solapados_fecha

            if not horarios_fecha:
                dias_sin_disponibilidad.append({
                    'fecha': fecha.strftime('%d/%m/%Y'),
                    'motivo': resultado_fecha.get('mensaje', 'Sin disponibilidad')
                })

        horarios_finales = sorted(horarios_comunes or [], key=_sort_hora_str)
        solapados_finales = sorted(
            (solapados_comunes or set()) & set(horarios_finales),
            key=_sort_hora_str,
        )

        if not horarios_finales:
            mensaje = (
                f'No hay horarios comunes disponibles para las {len(fechas_objetivo)} fechas seleccionadas.'
            )
            if dias_sin_disponibilidad:
                primeras = ', '.join(x['fecha'] for x in dias_sin_disponibilidad[:4])
                mensaje += f' Fechas sin disponibilidad: {primeras}.'

            return JsonResponse({
                'horarios': [],
                'duracion_total': duracion_total,
                'mensaje': mensaje,
                'cerrado': True,
                'dias_sin_disponibilidad': dias_sin_disponibilidad,
                'total_fechas': len(fechas_objetivo)
            })

        return JsonResponse({
            'horarios': horarios_finales,
            'duracion_total': duracion_total,
            'mensaje': f'Horarios comunes disponibles para {len(fechas_objetivo)} fecha(s) del rango.',
            'cerrado': False,
            'horarios_solapados': solapados_finales,
            'dias_sin_disponibilidad': dias_sin_disponibilidad,
            'total_fechas': len(fechas_objetivo)
        })

    # Modo fecha puntual (edicion / compatibilidad)
    if not fecha_str:
        return JsonResponse({'error': 'Falta el parámetro fecha.'}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido'}, status=400)

    resultado = _calcular_horarios_para_fecha(
        pelicula=pelicula,
        sala=sala,
        fecha=fecha,
        funcion_id=funcion_id,
        formato_experiencia_id=formato_experiencia_id,
    )

    if resultado.get('error'):
        return JsonResponse({'error': resultado['mensaje']}, status=400)

    return JsonResponse(resultado)


def verificar_horario_fecha(request):
    """
    Vista AJAX que verifica si hay excepciones de horario para una fecha especi­fica.
    
    Retorna:
    - cerrado: bool (True si el cine está cerrado)
    - motivo: str (descripción de la excepción)
    - horarios: list (rangos horarios disponibles)
    - es_excepcion: bool (True si hay un horario modificado)
    """
    if request.method == 'GET':
        fecha_str = request.GET.get('fecha')  # formato: YYYY-MM-DD
        
        if not fecha_str:
            return JsonResponse({'error': 'Falta el parámetro fecha'}, status=400)
        
        try:
            from cine.models import ConfiguracionCine, ExcepcionHorario
            from django.db.models import Q
            
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            configuracion = ConfiguracionCine.load()
            
            # Buscar excepcion que aplique a esta fecha (puede ser fecha exacta o dentro de un rango)
            excepciones = ExcepcionHorario.objects.filter(
                configuracion_cine=configuracion,
                fecha__lte=fecha  # fecha de inicio <= fecha buscada
            ).filter(
                Q(fecha_fin__isnull=True, fecha=fecha) |  # Excepcion de un solo di­a
                Q(fecha_fin__gte=fecha)  # O fecha dentro del rango
            )
            
            if excepciones.exists():
                excepcion = excepciones.first()
                
                # Caso 1: Cine cerrado
                if excepcion.cerrado:
                    return JsonResponse({
                        'cerrado': True,
                        'motivo': excepcion.descripcion or 'Cine cerrado',
                        'horarios': [],
                        'es_excepcion': True,
                        'tipo': 'cerrado'
                    })
                
                # Caso 2: Horario modificado
                else:
                    horarios = [{
                        'apertura': excepcion.hora_apertura.strftime('%H:%M'),
                        'cierre': excepcion.hora_cierre.strftime('%H:%M')
                    }]
                    
                    return JsonResponse({
                        'cerrado': False,
                        'motivo': excepcion.descripcion or 'Horario especial',
                        'horarios': horarios,
                        'es_excepcion': True,
                        'tipo': 'modificado',
                        'fecha_formateada': fecha.strftime('%d/%m/%Y')
                    })
            
            else:
                
                dia_semana = fecha.weekday()
                horarios_dia = configuracion.get_horarios_dia(dia_semana)
                
                if not horarios_dia.exists():
                    # El cine esta cerrado ese di­a de la semana (sin horarios configurados)
                    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                    return JsonResponse({
                        'cerrado': True,
                        'motivo': f'Cerrado los {dias_nombres[dia_semana]}s',
                        'horarios': [],
                        'es_excepcion': False,
                        'tipo': 'cerrado_regular'
                    })
                
                # Hay horarios normales
                horarios = [
                    {
                        'apertura': h.hora_apertura.strftime('%H:%M'),
                        'cierre': h.hora_cierre.strftime('%H:%M')
                    }
                    for h in horarios_dia
                ]
                
                return JsonResponse({
                    'cerrado': False,
                    'motivo': None,
                    'horarios': horarios,
                    'es_excepcion': False,
                    'tipo': 'normal'
                })
        
        except ValueError:
            return JsonResponse({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


