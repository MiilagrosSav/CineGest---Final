sequenceDiagram
    actor U as Sistema
    participant Ctrl as :VistaIntercambio
    participant IS as :IntercambioService
    participant PR as :PoliticaIntercamibio
    participant Ent as Entradas
    participant Btc as Butacas
    participant InterORM as Intercambio
    participant NS as :notificacion_service
    participant PS as :promociones.services
    participant PProm as PoliticaPromocion (Manager)
    participant Cupon as CuponGenerado (Manager)

    %% INICIO DE LA EJECUCIÓN
   U->>Ctrl: cinfirmarintercambio(venta, funcionDestino, butacas)
    activate Ctrl
    
    Ctrl->>IS: ejecutar_intercambio(venta, funcionDestino, butacas, request)
    activate IS
    
    IS->>PR: es_valido = validar_intercambio(venta, funcionDestino)
    activate PR
    PR-->>IS: retorna (True, '')
    deactivate PR

    %% BLOQUE TRANSACCIONAL ATÓMICO (RETRY LOGIC OMISO POR ABSTRACIÓN)
    Note over IS,Btc: Inicia Transacción (Con bloqueo de tabla - select_for_update)
    
    IS->>Btc: lock = select_for_update().filter(butacasSeleccionadas)
    Btc-->>IS: butacas_locked
    
    IS->>Ent: ocupadas = exists(funcion_destino, butacas_locked, ESTADOS_OCUPADOS)
    activate Ent
    alt Si ocupadas == True (Conflicto Asíncrono)
        Ent-->>IS: true
        IS-->>Ctrl: Lanza IntercambioDisponibilidadError
    else ocupadas == False
        Ent-->>IS: false
    end
    deactivate Ent

    %% 1. CANCELACIÓN Y EMISIÓN
    IS->>Ent: update(estado = 'CANCELADA') [ent. activas origen]
    
    loop Para cada butaca de butacas_locked
        IS->>Ent: delete() [Limpieza manual de expiradas/canceladas previas]
        IS->>Ent: create(id_venta, funcion, butaca, estado='VENDIDA')
        activate Ent
        Note right of Ent: La entrada nace aprobada sin pago extra
        Ent-->>IS: nuevaEntrada
        deactivate Ent
    end
    
    %% 2. AUDITORÍA DEL PASO
    IS->>InterORM: create(venta, funcion_origen, funcion_destino, 'COMPLETADO')
    activate InterORM
    InterORM-->>IS: inst_intercambio
    deactivate InterORM

    IS->>NS: enviar_confirmacion_intercambio(venta, inst_intercambio)
    activate NS
    Note right of NS: Email de finalización de trámite
    NS-->>IS: Ok
    deactivate NS

    %% =========================================================
    %% BLOQUE 3. YIELD MANAGEMENT (LIBERACIÓN Y MARKETING)
    %% =========================================================
    Note over IS,Cupon: Se delega control al módulo de Promociones a causa de la liberación
    
    IS->>PS: procesar_butaca_liberada(funcion_origen, cliente_excluido=Venta.cliente)
    activate PS

    PS->>PProm: politicas = filter(activa=True, horario_coincide, genero_coincide)
    activate PProm
    PProm-->>PS: list(PoliticaPromocion)
    deactivate PProm

    alt Si no existen politicas o promo no es válida
        PS-->>IS: retorna vacío (Proceso Yield Inactivo)
    else Si hay política candidata
        PS->>PS: politicaGanadora = sort(politicas_match, por_prioridad)[0]
        
        %% Búsqueda de la demanda
        PS->>PS: candidatos = filter(Cliente, acepta_marketing=True, perfil=genero/horario)
        
        loop Para cada cliente candidato (distinto al que canceló)
            Note over PS,Cupon: Nueva Transacción Atómica
            PS->>Cupon: create(cliente, politica_origen, expira_minutos)
            activate Cupon
            Note right of Cupon: Se forja Token UUID único en el objeto
            Cupon-->>PS: inst_cupon (con token)
            deactivate Cupon
            
            PS->>PS: link = "base_url/promociones/activar/" + inst_cupon.token
            
            PS->>NS: enviar_oferta_promocion(cliente, link_token)
            activate NS
            NS-->>PS: mailCrab(simulado) exitoso
            deactivate NS
        end
    end
    
    PS-->>IS: return respuestas (log final metadata)
    deactivate PS

    %% FINALIZACIÓN
    IS-->>Ctrl: retorna (True, '', inst_intercambio)
    deactivate IS