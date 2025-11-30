# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0013_add_cupon_to_historicalventa'),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='medio_pago',
            field=models.CharField(
                blank=True,
                choices=[('EFECTIVO', 'Efectivo'), ('MERCADOPAGO', 'Mercado Pago'), ('TARJETA', 'Tarjeta')],
                help_text='Medio de pago utilizado para la venta',
                max_length=20,
                null=True,
                verbose_name='Medio de Pago'
            ),
        ),
    ]
