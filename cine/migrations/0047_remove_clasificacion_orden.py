# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0046_finalize_clasificacion_migration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clasificacion',
            name='orden',
        ),
    ]
