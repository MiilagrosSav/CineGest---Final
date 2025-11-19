"""
Migración manual para eliminar tabla de Reembolso (si existe)

Esta migración elimina la tabla ventas_reembolso que ya no se usa.
El sistema ahora usa el modelo Intercambio para auditoría.

IMPORTANTE: Si la tabla no existe, esta migración no fallará.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0004_politicareembolso_is_active_politicareembolso_nombre'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS ventas_reembolso;
            """,
            reverse_sql="""
                -- No hay reverse - la tabla Reembolso fue deprecada
                -- El modelo Intercambio la reemplaza completamente
            """,
        ),
    ]
