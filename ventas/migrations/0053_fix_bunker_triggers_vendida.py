# Generated migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0052_update_trigger_agregar_estado_expirada'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- 1. ELIMINAR el trigger y función VIEJA que no permite VENDIDA
            DROP TRIGGER IF EXISTS bunker_entrada_seguridad ON "Entrada";
            DROP FUNCTION IF EXISTS trg_bunker_entrada_integridad();
            
            -- 2. El trigger consolidado ya existe y permite VENDIDA correctamente,
            --    pero vamos a recrearlo para asegurar que incluye todos los estados
            DROP TRIGGER IF EXISTS trigger_bunker_entrada_consolidado ON "Entrada";
            DROP FUNCTION IF EXISTS trg_bunker_entrada_consolidado();
            
            -- 3. RECREAR la función bunker consolidada con TODOS los estados válidos
            CREATE OR REPLACE FUNCTION trg_bunker_entrada_consolidado()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Validar que el estado sea uno de los permitidos en el sistema
                IF NEW.estado NOT IN ('PENDIENTE', 'RESERVADA', 'VENDIDA', 'ENTREGADA', 'USADA', 'CANCELADA', 'EXPIRADA') THEN
                    RAISE EXCEPTION 'ERROR BUNKER: El estado % no es valido para el dominio del sistema.', NEW.estado;
                END IF;
            
                -- Proteger campos inmutables en actualizaciones
                IF (TG_OP = 'UPDATE') THEN
                    -- No permitir cambios en entradas ya procesadas (VENDIDA, ENTREGADA, USADA)
                    IF (OLD.estado IN ('VENDIDA', 'ENTREGADA', 'USADA')) THEN
                        IF (OLD.id_funcion_id IS DISTINCT FROM NEW.id_funcion_id) THEN
                            RAISE EXCEPTION 'ERROR BUNKER: No se puede cambiar la funcion de una entrada ya procesada.';
                        END IF;
            
                        IF (OLD.id_butaca_id IS DISTINCT FROM NEW.id_butaca_id) THEN
                            RAISE EXCEPTION 'ERROR BUNKER: No se puede cambiar la butaca de una entrada ya procesada.';
                        END IF;
            
                        IF (OLD.precio_unitario IS DISTINCT FROM NEW.precio_unitario) THEN
                            RAISE EXCEPTION 'ERROR BUNKER: El precio unitario ya facturado no se puede modificar.';
                        END IF;
                    END IF;
            
                    -- Campos de auditoría siempre inmutables
                    IF (NEW.id_entrada <> OLD.id_entrada OR
                        NEW.id_venta_id <> OLD.id_venta_id OR
                        NEW.fecha_creacion <> OLD.fecha_creacion) THEN
                        RAISE EXCEPTION 'ERROR BUNKER: Intento de manipular campos de auditoria inmutables.';
                    END IF;
                END IF;
            
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            
            -- 4. RECREAR el trigger consolidado
            CREATE TRIGGER trigger_bunker_entrada_consolidado
            BEFORE INSERT OR UPDATE ON "Entrada"
            FOR EACH ROW
            EXECUTE FUNCTION trg_bunker_entrada_consolidado();
            
            -- 5. ELIMINAR trigger bunker_entrada_total duplicado si existe
            DROP TRIGGER IF EXISTS bunker_entrada_total ON "Entrada";
            DROP FUNCTION IF EXISTS bunker_entrada_total();
            """,
            reverse_sql="""
            -- No revertir - los triggers viejos causaban problemas
            """,
        ),
    ]
