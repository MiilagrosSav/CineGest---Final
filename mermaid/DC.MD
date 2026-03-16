classDiagram
    %% ==========================================
    %% ACCOUNTS (Cuentas y Usuarios)
    %% ==========================================
    class Usuario {
        +String username
        +String email
        +String password
        +Boolean is_active
        +Boolean is_staff
        +Boolean is_superuser
        +login()
        +logout()
    }
    
    class Cliente {
        +String telefono
        +Date fecha_nacimiento
        +Integer puntos_fidelidad
        +String rfc
    }
    
    class Empleado {
        +String legajo
        +String turno
        +Date fecha_contratacion
        +String area
    }
    
    class Administrador {
        +String nivel_acceso
        +String area_supervision
    }

    Usuario <|-- Cliente
    Usuario <|-- Empleado
    Usuario <|-- Administrador

    %% ==========================================
    %% CINE (Catálogo, Funciones y Salas)
    %% ==========================================
    class Pelicula {
        +String titulo
        +String titulo_original
        +String sinopsis
        +Integer duracion
        +Date fecha_estreno
        +Boolean soft_delete
        +String poster
    }

    class Director {
        +String nombre
        +Boolean soft_delete
    }

    class Genero {
        +String nombre
        +Boolean soft_delete
    }

    class Clasificacion {
        +String codigo
        +String descripcion
        +Integer edad_minima
        +Boolean soft_delete
    }

    class Sala {
        +String nombre
        +Integer capacidad
        +Boolean operativa
        +Boolean soft_delete
    }

    class Butaca {
        +String fila
        +Integer numero
        +String estado
    }

    class Funcion {
        +DateTime fecha_hora
        +Float precio_base
        +Boolean soft_delete
        +Integer duracion_estimada
        +tiene_entradas_vendidas() Boolean
    }

    class Formato {
        +String tipo
        +String descripcion
        +Float recargo
    }

    class FuncionFormato {
        +Float precio_especial
    }

    class ConfiguracionCine {
        +String nombre
        +Time horario_apertura
        +Time horario_cierre
        +Integer tiempo_limpieza
    }

    class ExcepcionHorario {
        +Date fecha
        +Time hora_apertura_especial
        +Time hora_cierre_especial
        +String motivo
    }

    class HorarioAtencion {
        +Integer dia_semana
        +Time apertura
        +Time cierre
    }

    %% Relaciones Cine
    Pelicula "1" *-- "1..*" Director : dirigido por
    Pelicula "1" *-- "1..*" Genero : pertenece a
    Pelicula "1" *-- "1" Clasificacion : clasificada como
    Sala "1" *-- "1..*" Butaca : contiene
    Funcion "1" *-- "1" Pelicula : proyecta
    Funcion "1" *-- "1" Sala : ocurre en
    Funcion "1" *-- "1..*" Formato : usa (a través de FuncionFormato)
    FuncionFormato "1" -- "1" Funcion
    FuncionFormato "1" -- "1" Formato
    ConfiguracionCine "1" *-- "0..*" ExcepcionHorario
    ConfiguracionCine "1" *-- "1..7" HorarioAtencion

    %% ==========================================
    %% VENTAS (Transacciones e Intercambios)
    %% ==========================================
    class Venta {
        +DateTime fecha_venta
        +Float monto_total
        +String estado
        +generar_comprobante()
    }

    class Entrada {
        +Float precio_final
        +String codigo_qr
        +String estado
    }

    class MetodoPago {
        +String nombre
        +Boolean activo
        +String proveedor
    }

    class Pago {
        +Float monto
        +DateTime fecha_pago
        +String estado_transaccion
        +String referencia_pasarela
    }

    class Intercambio {
        +DateTime fecha_solicitud
        +Float penalidad_aplicada
        +String estado
        +String motivo
        +procesar_liberacion()
    }

    class CajaSesion {
        +DateTime apertura
        +DateTime cierre
        +Float saldo_inicial
        +Float saldo_final
        +String estado
    }

    class PoliticaReembolso {
        +String nombre
        +Float porcentaje_devolucion
        +Integer horas_anticipacion
        +Boolean soft_delete
    }

    %% Relaciones Ventas
    Venta "1" *-- "1..*" Entrada : agrupa
    Venta "1" *-- "1" Cliente : pertenece a
    Venta "1" -- "1" CajaSesion : procesada en
    Entrada "1" *-- "1" Butaca : asignada a
    Entrada "1" *-- "1" Funcion : válida para
    Pago "1" *-- "1" Venta : cubre
    Pago "1" *-- "1" MetodoPago : utiliza
    Intercambio "1" *-- "1" Venta : modifica a
    Intercambio "1" *-- "1..*" Entrada : libera
    PoliticaReembolso "1" -- "0..*" Intercambio : determina regla

    %% ==========================================
    %% PROMOCIONES (Marketing y Yield)
    %% ==========================================
    class PoliticaPromocion {
        +String nombre
        +Float porcentaje_descuento
        +Date vigencia_desde
        +Date vigencia_hasta
        +Boolean soft_delete
        +esta_bloqueada() Boolean
    }

    class Promocion {
        +String codigo
        +String tipo
        +Boolean activa
        +Boolean soft_delete
        +String descripcion
    }

    class CuponGenerado {
        +String codigo_unico
        +DateTime fecha_emision
        +Boolean utilizado
        +Date fecha_vencimiento
    }

    class VinculoPromocional {
        +String target_type
        +Integer target_id
        +validar_reglas()
    }

    %% Relaciones Promociones
    PoliticaPromocion "1" *-- "0..*" Promocion : define
    Promocion "1" *-- "1..*" VinculoPromocional : se aplica a
    PoliticaPromocion "1" *-- "0..*" CuponGenerado : emite
    CuponGenerado "0..1" -- "1" Venta : consumido en
    CuponGenerado "0..1" -- "1" Cliente : asignado a

    %% ==========================================
    %% VALORACIONES (Opiniones de los Clientes)
    %% ==========================================
    class Valoracion {
        +Integer puntaje
        +DateTime fecha
        +Boolean destacada
    }

    class Resena {
        +String comentario
        +Boolean validada
        +DateTime fecha_moderacion
    }

    class NotificacionValoracion {
        +DateTime fecha_envio
        +Boolean leida
        +String mensaje
    }

    %% Relaciones Valoraciones
    Valoracion "1" *-- "1" Pelicula : evaluando a
    Valoracion "1" *-- "1" Entrada : originada por
    Resena "0..1" -- "1" Valoracion : detalla (1 a 1 opcional)
    NotificacionValoracion "1" -- "1" Cliente : dirigida a

    %% ==========================================
    %% AUDITORIA (Logs y Cumplimiento)
    %% ==========================================
    class AuditEntry {
        +String accion
        +String modelo_afectado
        +Integer registro_id
        +DateTime timestamp
        +String datos_previos
        +String datos_nuevos
        +String ip_address
    }

    class AuditConfig {
        +Boolean activar_auditoria
        +Integer retencion_dias
    }

    class RegistroAcceso {
        +DateTime fecha_ingreso
        +String ip
        +String browser
    }

    %% Relaciones Auditoria
    AuditEntry "1" -- "1" Usuario : accion accionada por
    RegistroAcceso "1" -- "1" Usuario : sesion iniciada por