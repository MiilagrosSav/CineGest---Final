# Generated manually on 2026-03-06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0045_migrate_data_to_clasificacion_fk'),
    ]

    operations = [
        # Paso 1: Eliminar el campo clasificacion viejo (CharField) de ambas tablas
        migrations.RemoveField(
            model_name='historicalpelicula',
            name='clasificacion',
        ),
        migrations.RemoveField(
            model_name='pelicula',
            name='clasificacion',
        ),
        
        # Paso 2: Renombrar clasificacion_fk a clasificacion
        migrations.RenameField(
            model_name='historicalpelicula',
            old_name='clasificacion_fk',
            new_name='clasificacion',
        ),
        migrations.RenameField(
            model_name='pelicula',
            old_name='clasificacion_fk',
            new_name='clasificacion',
        ),
    ]
