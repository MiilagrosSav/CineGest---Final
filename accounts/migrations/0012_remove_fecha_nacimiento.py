
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_update_fecha_registro_null'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cliente',
            name='fecha_nacimiento',
        ),
        migrations.AlterField(
            model_name='usuario',
            name='username',
            field=models.CharField(
                error_messages={'unique': 'Ya existe un usuario con ese nombre de usuario.'},
                help_text='150 caracteres o menos. Solo letras y números.',
                max_length=150,
                unique=True,
                validators=[django.core.validators.RegexValidator(
                    code='username_invalido',
                    message='El nombre de usuario solo puede contener letras y números, sin espacios ni caracteres especiales.',
                    regex='^[a-zA-Z0-9]+$',
                )],
                verbose_name='nombre de usuario',
            ),
        ),
        migrations.AlterField(
            model_name='historicalusuario',
            name='username',
            field=models.CharField(
                db_index=True,
                error_messages={'unique': 'Ya existe un usuario con ese nombre de usuario.'},
                help_text='150 caracteres o menos. Solo letras y números.',
                max_length=150,
                validators=[django.core.validators.RegexValidator(
                    code='username_invalido',
                    message='El nombre de usuario solo puede contener letras y números, sin espacios ni caracteres especiales.',
                    regex='^[a-zA-Z0-9]+$',
                )],
                verbose_name='nombre de usuario',
            ),
        ),
    ]
