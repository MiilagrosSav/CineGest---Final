# Generated manually to add funcion_origen to CuponGenerado
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('promociones', '0011_promocion_dias_semana'),
    ]

    operations = [
        migrations.AddField(
            model_name='cupongenerado',
            name='funcion_origen',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='cine.funcion'),
        ),
    ]
