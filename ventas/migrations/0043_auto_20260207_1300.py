from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0042_auto_20260207_1233'), # Depende de la que ya tenés
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Actualizamos la función con TODOS los candados
            CREATE OR REPLACE FUNCTION proteger_campos_sagrados()
            RETURNS TRIGGER AS $$
            BEGIN
                -- 1. Bloqueo de código_compra
                IF (OLD.codigo_compra IS DISTINCT FROM NEW.codigo_compra) THEN
                    RAISE EXCEPTION 'EL CODIGO DE COMPRA ES INMUTABLE';
                END IF;

                -- 2. Bloqueo de empleado
                IF (OLD.id_empleado_id IS DISTINCT FROM NEW.id_empleado_id) THEN
                    RAISE EXCEPTION 'EL EMPLEADO DE LA VENTA NO PUEDE SER ALTERADO';
                END IF;

                -- 3. Bloqueo de fecha_compra
                IF (OLD.fecha_compra IS DISTINCT FROM NEW.fecha_compra) THEN
                    RAISE EXCEPTION 'LA FECHA DE COMPRA NO PUEDE SER MODIFICADA';
                END IF;

                -- 4. Bloqueo de tipo_venta
                IF (OLD.tipo_venta IS DISTINCT FROM NEW.tipo_venta) THEN
                    RAISE EXCEPTION 'EL TIPO DE VENTA ES INALTERABLE';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,
            reverse_sql="""
            -- En caso de volver atrás, al menos dejamos la función existiendo
            -- o podrías dejarla vacía con 'RETURN NEW;'
            """
        ),
    ]