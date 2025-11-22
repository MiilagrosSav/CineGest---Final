from django.db import migrations, models


def forwards(apps, schema_editor):
    Politica = apps.get_model('promociones', 'PoliticaPromocion')
    Genero = apps.get_model('cine', 'Genero')

    # Mapping if policies stored codes
    mapping = {
        'ACCION': 'Acción',
        'AVENTURA': 'Aventura',
        'COMEDIA': 'Comedia',
        'DRAMA': 'Drama',
        'CIENCIA_FICCION': 'Ciencia Ficción',
        'TERROR': 'Terror',
        'FANTASIA': 'Fantasía',
        'MUSICAL': 'Musical',
        'ANIMACION': 'Animación',
    }

    # crear géneros si no existen (defensivo)
    for code, nombre in mapping.items():
        Genero.objects.get_or_create(nombre=nombre)

    # Para cada política, si tiene valor en genero_pelicula (char) migrar a FK temporal
    for pol in Politica.objects.all():
        # la columna antigua todavía puede aparecer como 'genero_pelicula'
        old = getattr(pol, 'genero_pelicula', None)
        if not old:
            continue
        nombre = mapping.get(old, old)
        g = Genero.objects.filter(nombre=nombre).first()
        if g:
            # asignar en el campo fk temporal si existe
            if hasattr(pol, 'genero_pelicula_fk'):
                setattr(pol, 'genero_pelicula_fk_id', g.id)
                pol.save()


def reverse(apps, schema_editor):
    Politica = apps.get_model('promociones', 'PoliticaPromocion')
    # limpiar fk temporal
    for pol in Politica.objects.all():
        if hasattr(pol, 'genero_pelicula_fk'):
            pol.genero_pelicula_fk = None
            pol.save()


class Migration(migrations.Migration):

    dependencies = [
        ('promociones', '0004_cupongenerado_expira_en_and_more'),
        ('cine', '0017_add_genero_and_m2m'),
    ]

    operations = [
        # 1) Añadir campo FK temporal a Genero
        migrations.AddField(
            model_name='politicapromocion',
            name='genero_pelicula_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='politicas_temp', to='cine.Genero'),
        ),
        # 2) Ejecutar data migration que copia valores desde antiguo campo char al FK temporal
        migrations.RunPython(forwards, reverse),
        # 3) Remover el campo antiguo (char) si existe
        migrations.RemoveField(
            model_name='politicapromocion',
            name='genero_pelicula',
        ),
        # 4) Renombrar el campo temporal al nombre final esperado por el modelo
        migrations.RenameField(
            model_name='politicapromocion',
            old_name='genero_pelicula_fk',
            new_name='genero_pelicula',
        ),
    ]
