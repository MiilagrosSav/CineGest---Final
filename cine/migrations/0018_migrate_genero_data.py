from django.db import migrations


def forwards(apps, schema_editor):
    Pelicula = apps.get_model('cine', 'Pelicula')
    Genero = apps.get_model('cine', 'Genero')

    # Mapeo del antiguo código -> nombre legible
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

    # Crear géneros si no existen
    for code, nombre in mapping.items():
        Genero.objects.get_or_create(nombre=nombre)

    # Si la columna antigua 'genero' existe, asignar M2M
    for p in Pelicula.objects.all():
        old = getattr(p, 'genero', None)
        if not old:
            continue
        nombre = mapping.get(old)
        if not nombre:
            # si no hay mapeo, intentar usar el mismo valor como nombre
            nombre = old
        genero_obj = Genero.objects.filter(nombre=nombre).first()
        if genero_obj:
            p.generos.add(genero_obj)


def reverse(apps, schema_editor):
    # Reverso: limpiar relaciones creadas
    Pelicula = apps.get_model('cine', 'Pelicula')
    for p in Pelicula.objects.all():
        p.generos.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0017_add_genero_and_m2m'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
