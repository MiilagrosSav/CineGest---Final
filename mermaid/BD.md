erDiagram
    %% ==========================================
    %% ACCOUNTS
    %% ==========================================
    accounts_usuario {
        int id PK
        varchar username
        varchar email
        varchar password
        bool is_active
        bool is_staff
    }
    
    accounts_cliente {
        int usuario_id PK, FK "Referencia a usuario.id"
        varchar telefono
        date fecha_nacimiento
        int puntos_fidelidad
        varchar rfc
    }

    accounts_empleado {
        int usuario_id PK, FK "Referencia a usuario.id"
        varchar legajo
        varchar turno
        date fecha_contratacion
    }

    %% ==========================================
    %% CINE
    %% ==========================================
    cine_clasificacion {
        int id PK
        varchar codigo
        varchar descripcion
        int edad_minima
        bool soft_delete
    }

    cine_director {
        int id PK
        varchar nombre
        bool soft_delete
    }

    cine_genero {
        int id PK
        varchar nombre
        bool soft_delete
    }

    cine_pelicula {
        int id PK
        varchar titulo
        int director_id FK
        int clasificacion_id FK
        varchar sinopsis
        int duracion
        date fecha_estreno
        bool soft_delete
    }
    
    %% Tabla intermedia por ManyToManyField(Genero)
    cine_pelicula_generos {
        int id PK
        int pelicula_id FK
        int genero_id FK
    }

    cine_sala {
        int id PK
        varchar nombre
        int capacidad
        bool operativa
        bool soft_delete
    }

    cine_butaca {
        int id PK
        int sala_id FK
        varchar fila
        int numero
        varchar estado
    }

    cine_formato {
        int id PK
        varchar tipo
        float recargo
    }

    cine_funcion {
        int id PK
        int pelicula_id FK
        int sala_id FK
        datetime fecha_hora
        float precio_base
        bool soft_delete
    }

    %% Tabla intermedia formato (si aplicara como muchos a muchos, o OneToOne)
    cine_funcionformato {
        int id PK
        int funcion_id FK
        int formato_id FK
        float precio_especial
    }

    %% ==========================================
    %% VENTAS
    %% ==========================================
    ventas_metodopago {
        int id PK
        varchar nombre
        bool activo
    }

    ventas_venta {
        int id PK
        int id_cliente_id FK
        int id_empleado_id FK "Nullable"
        int cupon_utilizado_id FK "Nullable"
        int id_metodo_pago_id FK
        datetime fecha_venta
        float monto_total
        varchar estado
    }

    ventas_entrada {
        int id PK
        int id_venta_id FK
        int id_funcion_id FK
        int id_sala_id FK
        int id_butaca_id FK
        int id_pelicula_id FK
        float precio_final
        varchar codigo_qr
        varchar estado
    }

    ventas_pago {
        int id PK
        int venta_id FK
        int metodo_pago_id FK
        float monto
        datetime fecha_pago
    }

    ventas_intercambio {
        int id PK
        int venta_id FK
        datetime fecha_solicitud
        float penalidad_aplicada
        varchar estado
    }
    
    ventas_cajasesion {
        int id PK
        int empleado_id FK
        datetime apertura
        datetime cierre
        float saldo_inicial
    }

    %% ==========================================
    %% PROMOCIONES
    %% ==========================================
    promociones_politicapromocion {
        int id PK
        varchar nombre
        float porcentaje_descuento
        date vigencia_desde
        date vigencia_hasta
        bool soft_delete
    }

    promociones_promocion {
        int id PK
        int politica_id FK
        varchar codigo
        varchar tipo
        bool activa
    }

    promociones_cupongenerado {
        int id PK
        int politica_id FK
        int cliente_id FK "Nullable"
        varchar codigo_unico
        bool utilizado
    }
    
    promociones_vinculopromocional {
        int id PK
        int promocion_id FK
        varchar target_type "Generic ForeignKey"
        int target_id
    }

    %% ==========================================
    %% VALORACIONES & AUDITORIA
    %% ==========================================
    valoraciones_valoracion {
        int id PK
        int pelicula_id FK
        int cliente_id FK
        int entrada_id FK
        int puntaje
        datetime fecha
    }

    valoraciones_resena {
        int id PK
        int valoracion_id FK "OneToOne"
        varchar comentario
        bool validada
    }

    auditoria_auditentry {
        int id PK
        int usuario_id FK "Nullable"
        varchar accion
        varchar modelo_afectado
        int registro_id
        datetime timestamp
        jsonb datos_previos
        jsonb datos_nuevos
    }

    %% ==========================================
    %% RELACIONES PK/FK EXACTAS (Líneas ERD)
    %% ==========================================
    
    %% Herencia de Usuarios (OneToOneField en Django => Relación 1..1)
    accounts_usuario ||--o| accounts_cliente : "1..1 hereda"
    accounts_usuario ||--o| accounts_empleado : "1..1 hereda"

    %% Peliculas
    cine_director ||--o{ cine_pelicula : "dirige"
    cine_clasificacion ||--o{ cine_pelicula : "tiene"
    cine_pelicula ||--o{ cine_pelicula_generos : "posee"
    cine_genero ||--o{ cine_pelicula_generos : "asigna a"

    %% Funciones, Salas y Butacas
    cine_sala ||--o{ cine_butaca : "contiene"
    cine_pelicula ||--o{ cine_funcion : "proyectada en"
    cine_sala ||--o{ cine_funcion : "alberga"
    cine_funcion ||--o{ cine_funcionformato : "configura"
    cine_formato ||--o{ cine_funcionformato : "aplica en"

    %% Ventas e Intercambios
    accounts_cliente ||--o{ ventas_venta : "realiza"
    ventas_metodopago ||--o{ ventas_venta : "paga con"
    promociones_cupongenerado |o--o{ ventas_venta : "redime (Nullable)"
    
    ventas_venta ||--|{ ventas_entrada : "ticket padre"
    cine_funcion ||--|{ ventas_entrada : "ticket funcion"
    cine_butaca ||--|{ ventas_entrada : "ticket asiento"
    cine_pelicula ||--|{ ventas_entrada : "ticket pelicula"
    cine_sala ||--|{ ventas_entrada : "ticket sala"

    ventas_venta ||--|| ventas_intercambio : "modifica por intercambio"
    ventas_venta ||--o{ ventas_pago : "pagada vía"
    
    accounts_empleado ||--o{ ventas_cajasesion : "opera caja"

    %% Promociones
    promociones_politicapromocion ||--o{ promociones_promocion : "define campaña"
    promociones_politicapromocion ||--o{ promociones_cupongenerado : "emite campaña"
    promociones_promocion ||--o{ promociones_vinculopromocional : "restringe mediante"
    
    %% Valoraciones
    cine_pelicula ||--o{ valoraciones_valoracion : "es calificada"
    accounts_cliente ||--o{ valoraciones_valoracion : "escribe"
    ventas_entrada ||--o| valoraciones_valoracion : "habilita validacion"
    valoraciones_valoracion ||--o| valoraciones_resena : "contiene texto"

    %% Auditoria
    accounts_usuario ||--o{ auditoria_auditentry : "log"