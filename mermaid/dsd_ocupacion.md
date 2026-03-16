sequenceDiagram
    actor CRON as Actor Temporizador (CRON)
    participant Cmd as Command_YieldManagement
    participant PolM as PoliticaPromociones
    participant FunM as Funciones
    participant ClipM as Clientes
    participant CupM as CuponGenerado
    participant NotS as :NotificacionService

    CRON->>Cmd: .handle(opciones)
    activate Cmd
    
    Cmd->>PolM: politicasActivas = filter(activa=True, activar_por_ocupacion=True)
    activate PolM
    PolM-->>Cmd: lista_politicas
    deactivate PolM
    
    loop Por cada politica en lista_politicas
        Cmd->>FunM: filter(rango fechas)
        activate FunM
        Cmd->>FunM: exclude(estado_promocion='OFERTA_ACTIVA')
        FunM-->>Cmd: funciones_candidatas (anotadas con entradas_vendidas)
        deactivate FunM

        Cmd->>Cmd: funcionesFiltradas = filtrarXDiaYHora(funciones_candidatas)
        
        loop Por cada funcion_objetivo en funcionesFiltradas
            Cmd->>Cmd: ocupacion_prc = (funcion.entradas_vendidas / sala.capacidad) * 100
            
            alt ocupacion_prc < politica.umbral_ocupacion
                %% Modificación Real sobre Instancia
                Cmd->>FunM: funcion.estado_promocion = 'OFERTA_ACTIVA'
                Cmd->>FunM: funcion.save(update_fields)
                
                Cmd->>ClipM: clientesCandidatos = filter(ultimaCompra=180d, generoAfín)
                activate ClipM
                ClipM-->>Cmd: lista_clientes_candidatos
                deactivate ClipM
                
                loop Por cada cliente en clientesCandidatos
                    Cmd->>CupM: nuevoCupon = create(cliente, funcion, expira_horas)
                    activate CupM
                    CupM-->>Cmd: token uuid generado (asociado al Cupon)
                    deactivate CupM
                    
                    Cmd->>NotS: instanciar()
                    Cmd->>NotS: enviar_email_promocional(cliente, token)
                    activate NotS
                    NotS-->>Cmd: retorno Exitoso
                    deactivate NotS
                end
            end
        end
    end
    
    %% Output Real como respuesta a quien hizo el Trigger
    Cmd-->>CRON: Generar reporte texto (sys.stdout) con log contadores
    deactivate Cmd