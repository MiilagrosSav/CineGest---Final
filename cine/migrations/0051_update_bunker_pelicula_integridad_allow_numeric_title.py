from django.db import migrations


def _update_bunker_pelicula_integridad(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    sql_function = """
    CREATE OR REPLACE FUNCTION public.bunker_pelicula_integridad()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    BEGIN
        -- 1) Limpieza de titulo (sin tocar director: ahora es FK)
        NEW.titulo := TRIM(REGEXP_REPLACE(COALESCE(NEW.titulo, ''), '\\s+', ' ', 'g'));

        -- 2) Validacion: fecha historica (cine de 1888 en adelante)
        IF (NEW.fecha_estreno < DATE '1888-01-01') THEN
            RAISE EXCEPTION 'ERROR: La fecha de estreno (%) es anterior a la invencion del cine.', NEW.fecha_estreno;
        END IF;

        -- 3) Integridad FK: director debe estar informado
        IF (NEW.director_id IS NULL) THEN
            RAISE EXCEPTION 'ERROR: Debe especificar un director valido para la pelicula.';
        END IF;

        -- 4) Sincronizacion tecnica: forzar anio_estreno desde fecha_estreno
        NEW.anio_estreno := EXTRACT(YEAR FROM NEW.fecha_estreno);

        RETURN NEW;
    END;
    $function$;
    """

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql_function)


def _noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0050_alter_clasificacion_options_butaca_en_mantenimiento_and_more'),
    ]

    operations = [
        migrations.RunPython(_update_bunker_pelicula_integridad, _noop_reverse),
    ]
