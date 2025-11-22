from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0018_migrate_genero_data'),
    ]

    operations = [
        # Eliminar la columna antigua 'genero' (si existe)
        migrations.RemoveField(
            model_name='pelicula',
            name='genero',
        ),
    ]
