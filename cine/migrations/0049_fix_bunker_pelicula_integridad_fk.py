from django.db import migrations


def _fix_bunker_pelicula_integridad(apps, schema_editor):
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

        -- 2) Validacion: titulo no puede ser puramente numerico
        IF (NEW.titulo ~ '^-?[0-9.]+$') THEN
            RAISE EXCEPTION 'ERROR: El titulo "%" no puede ser puramente numerico.', NEW.titulo;
        END IF;

        -- 3) Validacion: fecha historica (cine de 1888 en adelante)
        IF (NEW.fecha_estreno < DATE '1888-01-01') THEN
            RAISE EXCEPTION 'ERROR: La fecha de estreno (%) es anterior a la invencion del cine.', NEW.fecha_estreno;
        END IF;

        -- 4) Integridad FK: director debe estar informado
        IF (NEW.director_id IS NULL) THEN
            RAISE EXCEPTION 'ERROR: Debe especificar un director valido para la pelicula.';
        END IF;

        -- 5) Sincronizacion tecnica: forzar anio_estreno desde fecha_estreno
        NEW.anio_estreno := EXTRACT(YEAR FROM NEW.fecha_estreno);

        RETURN NEW;
    END;
    $function$;
    """

    sql_trigger = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE t.tgname = 'trg_bunker_pelicula'
              AND c.relname = 'peliculas'
              AND NOT t.tgisinternal
        ) THEN
            CREATE TRIGGER trg_bunker_pelicula
            BEFORE INSERT OR UPDATE ON peliculas
            FOR EACH ROW
            EXECUTE FUNCTION bunker_pelicula_integridad();
        END IF;
    END
    $$;
    """

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql_function)
        cursor.execute(sql_trigger)


def _noop_reverse(apps, schema_editor):
    # No restauramos la funcion vieja porque referenciaba NEW.director
    # y es incompatible con el esquema actual.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0048_director_model_and_fk'),
    ]

    operations = [
        migrations.RunPython(_fix_bunker_pelicula_integridad, _noop_reverse),
    ]
