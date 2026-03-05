"""
Migración para actualizar el trigger trg_bunker_venta_integridad
Agregar soporte para el estado 'EXPIRADA' en ventas
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0051_historicalventa_activo_venta_activo_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- ============================================================================
            -- Actualizar trigger trg_bunker_venta_integridad
            -- Agregar soporte para el estado 'EXPIRADA'
            -- ============================================================================
            
            -- DROP del trigger actual si existe
            DROP TRIGGER IF EXISTS trg_bunker_venta_integridad ON "Venta";
            
            -- DROP de la función si existe
            DROP FUNCTION IF EXISTS trg_bunker_venta_integridad();
            
            -- Recrear la función con el nuevo estado 'EXPIRADA'
            CREATE OR REPLACE FUNCTION trg_bunker_venta_integridad()
            RETURNS TRIGGER AS $$
            BEGIN
                -- ========================================
                -- VALIDACIÓN DE ESTADOS PERMITIDOS
                -- ========================================
                IF NEW.estado NOT IN ('PENDIENTE', 'PENDIENTE_PAGO', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA') THEN
                    RAISE EXCEPTION 'ERROR BÚNKER: El estado de venta % no es válido.', NEW.estado;
                END IF;
                
                -- ========================================
                -- VALIDACIÓN DE TRANSICIONES DE ESTADO
                -- ========================================
                IF TG_OP = 'UPDATE' THEN
                    -- PENDIENTE puede ir a: PENDIENTE_PAGO, CONFIRMADA, CANCELADA, EXPIRADA
                    IF OLD.estado = 'PENDIENTE' THEN
                        IF NEW.estado NOT IN ('PENDIENTE', 'PENDIENTE_PAGO', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA') THEN
                            RAISE EXCEPTION 'Transición de estado inválida: PENDIENTE → %', NEW.estado;
                        END IF;
                    END IF;
                    
                    -- PENDIENTE_PAGO puede ir a: CONFIRMADA, CANCELADA, EXPIRADA
                    IF OLD.estado = 'PENDIENTE_PAGO' THEN
                        IF NEW.estado NOT IN ('PENDIENTE_PAGO', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA') THEN
                            RAISE EXCEPTION 'Transición de estado inválida: PENDIENTE_PAGO → %', NEW.estado;
                        END IF;
                    END IF;
                    
                    -- CONFIRMADA es un estado terminal
                    IF OLD.estado = 'CONFIRMADA' THEN
                        IF NEW.estado != 'CONFIRMADA' THEN
                            RAISE EXCEPTION 'Una venta CONFIRMADA no puede cambiar de estado';
                        END IF;
                    END IF;
                    
                    -- CANCELADA es un estado terminal
                    IF OLD.estado = 'CANCELADA' THEN
                        IF NEW.estado != 'CANCELADA' THEN
                            RAISE EXCEPTION 'Una venta CANCELADA no puede cambiar de estado';
                        END IF;
                    END IF;
                    
                    -- EXPIRADA es un estado terminal
                    IF OLD.estado = 'EXPIRADA' THEN
                        IF NEW.estado != 'EXPIRADA' THEN
                            RAISE EXCEPTION 'Una venta EXPIRADA no puede cambiar de estado';
                        END IF;
                    END IF;
                END IF;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            
            -- Crear el trigger
            CREATE TRIGGER trg_bunker_venta_integridad
                BEFORE INSERT OR UPDATE ON "Venta"
                FOR EACH ROW
                EXECUTE FUNCTION trg_bunker_venta_integridad();
            """,
            reverse_sql="""
            -- Revertir al trigger anterior (sin EXPIRADA)
            DROP TRIGGER IF EXISTS trg_bunker_venta_integridad ON "Venta";
            DROP FUNCTION IF EXISTS trg_bunker_venta_integridad();
            
            CREATE OR REPLACE FUNCTION trg_bunker_venta_integridad()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.estado NOT IN ('PENDIENTE', 'PENDIENTE_PAGO', 'CONFIRMADA', 'CANCELADA') THEN
                    RAISE EXCEPTION 'ERROR BÚNKER: El estado de venta % no es válido.', NEW.estado;
                END IF;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            
            CREATE TRIGGER trg_bunker_venta_integridad
                BEFORE INSERT OR UPDATE ON "Venta"
                FOR EACH ROW
                EXECUTE FUNCTION trg_bunker_venta_integridad();
            """
        ),
    ]
