from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0043_auto_20260207_1300'), # Verificá que este número sea el anterior
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION proteger_bunker_ventas()
            RETURNS TRIGGER AS $$
            BEGIN
                -- 1. Cliente
                IF (OLD.id_cliente_id IS DISTINCT FROM NEW.id_cliente_id) THEN
                    RAISE EXCEPTION 'EL CLIENTE DE LA VENTA ES INALTERABLE';
                END IF;

                -- 2. Total
                IF (OLD.total IS DISTINCT FROM NEW.total) THEN
                    RAISE EXCEPTION 'EL TOTAL CALCULADO NO PUEDE SER MODIFICADO MANUALMENTE';
                END IF;

                -- 3. Código de Compra
                IF (OLD.codigo_compra IS DISTINCT FROM NEW.codigo_compra) THEN
                    RAISE EXCEPTION 'EL CODIGO DE COMPRA ES INMUTABLE';
                END IF;

                -- 4. Empleado
                IF (OLD.id_empleado_id IS DISTINCT FROM NEW.id_empleado_id) THEN
                    RAISE EXCEPTION 'EL EMPLEADO DE LA VENTA NO PUEDE SER ALTERADO';
                END IF;

                -- 5. Fecha
                IF (OLD.fecha_compra IS DISTINCT FROM NEW.fecha_compra) THEN
                    RAISE EXCEPTION 'LA FECHA DE COMPRA NO PUEDE SER MODIFICADA';
                END IF;

                -- 6. Tipo de Venta
                IF (OLD.tipo_venta IS DISTINCT FROM NEW.tipo_venta) THEN
                    RAISE EXCEPTION 'EL TIPO DE VENTA ES INALTERABLE';
                END IF;

                -- 7. Cupón
                IF (OLD.cupon_utilizado_id IS DISTINCT FROM NEW.cupon_utilizado_id) THEN
                    RAISE EXCEPTION 'EL CUPON VINCULADO NO PUEDE SER CAMBIADO';
                END IF;

                -- 8. Método de Pago (NUEVO - El que faltaba)
                IF (OLD.id_metodo_pago_id IS DISTINCT FROM NEW.id_metodo_pago_id) THEN
                    RAISE EXCEPTION 'EL METODO DE PAGO NO PUEDE SER ALTERADO UNA VEZ REGISTRADO';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trigger_bunker_ventas ON "Venta";
            
            CREATE TRIGGER trigger_bunker_ventas
            BEFORE UPDATE ON "Venta"
            FOR EACH ROW
            EXECUTE FUNCTION proteger_bunker_ventas();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS trigger_bunker_ventas ON \"Venta\";"
        ),
    ]