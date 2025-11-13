from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.urls import reverse
from django.apps import apps
from django.http import HttpResponse
import json
import csv

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = (
        'history_date_formatted',
        'history_type_badge',
        'model_name',
        'object_repr_truncated',
        'history_user',
        'snapshot_preview',
        'original_object_link'
    )
    list_filter = (
        'history_type',
        'model_name',
        'history_user',
        ('history_date', admin.DateFieldListFilter),
    )
    search_fields = ('model_name', 'object_repr', 'object_id', 'history_change_reason')
    readonly_fields = (
        'model_name',
        'object_id',
        'object_repr',
        'history_type',
        'history_date',
        'history_user',
        'history_change_reason',
        'snapshot_pretty',
        'original_object_link',
        'created_at'
    )
    date_hierarchy = 'history_date'
    list_per_page = 50
    actions = ['export_as_csv']
    
    fieldsets = (
        ('Información del Objeto', {
            'fields': ('model_name', 'object_id', 'object_repr', 'original_object_link')
        }),
        ('Información del Cambio', {
            'fields': ('history_type', 'history_date', 'history_user', 'history_change_reason')
        }),
        ('Datos Completos', {
            'fields': ('snapshot_pretty',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        """No permitir creación manual de entradas de auditoría."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar entradas de auditoría."""
        return request.user.is_superuser

    def history_date_formatted(self, obj):
        """Fecha formateada de forma legible."""
        return obj.history_date.strftime('%d/%m/%Y %H:%M:%S')
    history_date_formatted.short_description = 'Fecha'
    history_date_formatted.admin_order_field = 'history_date'

    def history_type_badge(self, obj):
        """Muestra el tipo de cambio con un badge de color."""
        colors = {
            '+': '#28a745',  # verde
            '~': '#ffc107',  # amarillo
            '-': '#dc3545',  # rojo
        }
        color = colors.get(obj.history_type, '#6c757d')
        return mark_safe(
            f'<span style="background-color:{color};color:white;padding:3px 8px;'
            f'border-radius:3px;font-weight:bold;font-size:11px;">'
            f'{escape(obj.get_history_type_display())}</span>'
        )
    history_type_badge.short_description = 'Tipo'
    history_type_badge.admin_order_field = 'history_type'

    def object_repr_truncated(self, obj):
        """Representación del objeto truncada."""
        if not obj.object_repr:
            return '-'
        if len(obj.object_repr) > 50:
            return obj.object_repr[:50] + '...'
        return obj.object_repr
    object_repr_truncated.short_description = 'Objeto'

    def snapshot_preview(self, obj):
        """Preview corto del snapshot."""
        try:
            text = json.dumps(obj.snapshot, ensure_ascii=False)
        except Exception:
            text = str(obj.snapshot)
        if len(text) > 100:
            return text[:100] + '...'
        return text
    snapshot_preview.short_description = 'Snapshot (preview)'

    def snapshot_pretty(self, obj):
        """Snapshot completo formateado."""
        try:
            pretty = json.dumps(obj.snapshot, indent=2, ensure_ascii=False, sort_keys=True)
            return mark_safe(f'<pre style="white-space:pre-wrap;background:#f5f5f5;padding:10px;border-radius:5px;">{escape(pretty)}</pre>')
        except Exception as e:
            return mark_safe(f'<p style="color:red;">Error al formatear: {escape(str(e))}</p><pre>{escape(str(obj.snapshot))}</pre>')
    snapshot_pretty.short_description = 'Snapshot Completo'

    def original_object_link(self, obj):
        """Link al objeto original en el admin."""
        try:
            # Buscar el modelo por db_table
            model = next(m for m in apps.get_models() if m._meta.db_table == obj.model_name)
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            
            # Generar URL del admin
            url = reverse(f"admin:{app_label}_{model_name}_change", args=(obj.object_id,))
            return mark_safe(f'<a href="{url}" target="_blank" style="color:#007bff;">🔗 Ver Objeto</a>')
        except StopIteration:
            return mark_safe('<span style="color:#999;">Modelo no encontrado</span>')
        except Exception as e:
            return mark_safe(f'<span style="color:#999;" title="{escape(str(e))}">No disponible</span>')
    original_object_link.short_description = 'Objeto Original'
    
    def export_as_csv(self, request, queryset):
        """Acción para exportar entradas seleccionadas como CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="auditoria.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Fecha', 'Tipo', 'Modelo', 'Objeto ID', 'Objeto', 'Usuario', 'Razón'])
        
        for obj in queryset:
            writer.writerow([
                obj.history_date.strftime('%Y-%m-%d %H:%M:%S'),
                obj.get_history_type_display(),
                obj.model_name,
                obj.object_id,
                obj.object_repr,
                obj.history_user.username if obj.history_user else 'Sistema',
                obj.history_change_reason or ''
            ])
        
        return response
    export_as_csv.short_description = 'Exportar como CSV'
