# Generated manually on 2026-03-04
# Adds fecha_activacion field to Funcion model for automatic PREVENTA->ACTIVA transition

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0039_configuracioncine_logo_local_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcion',
            name='fecha_activacion',
            field=models.DateTimeField(blank=True, help_text='Fecha y hora en que la función pasará automáticamente de PREVENTA a ACTIVA', null=True),
        ),
        migrations.AddField(
            model_name='historicalfuncion',
            name='fecha_activacion',
            field=models.DateTimeField(blank=True, help_text='Fecha y hora en que la función pasará automáticamente de PREVENTA a ACTIVA', null=True),
        ),
    ]
