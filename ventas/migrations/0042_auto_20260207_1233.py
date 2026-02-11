from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0041_alter_historicalpago_monto_and_more'), # Asegurate que sea la última que hiciste
    ]

    operations = [
        migrations.RunSQL(
        sql="""
        CREATE OR REPLACE FUNCTION proteger_campos_sagrados()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Bloqueo de código_compra
            IF (OLD.codigo_compra IS DISTINCT FROM NEW.codigo_compra) THEN
                RAISE EXCEPTION 'EL CODIGO DE COMPRA ES INMUTABLE';
            END IF;

            -- Bloqueo de empleado
            IF (OLD.id_empleado_id IS DISTINCT FROM NEW.id_empleado_id) THEN
                RAISE EXCEPTION 'EL EMPLEADO DE LA VENTA NO PUEDE SER ALTERADO';
            END IF;

            -- Bloqueo de FECHA (NUEVO)
            IF (OLD.fecha_compra IS DISTINCT FROM NEW.fecha_compra) THEN
                RAISE EXCEPTION 'LA FECHA DE COMPRA NO PUEDE SER MODIFICADA';
            END IF;

            -- Bloqueo de TIPO DE VENTA (NUEVO)
            IF (OLD.tipo_venta IS DISTINCT FROM NEW.tipo_venta) THEN
                RAISE EXCEPTION 'EL TIPO DE VENTA ES INALTERABLE';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
        reverse_sql="..." # Opcional: el DROP que ya tenías
    )
    ]