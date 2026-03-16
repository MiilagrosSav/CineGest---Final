sequenceDiagram
    actor Reloj as Reloj Sistema (Cron)
    participant Sistema as :Sistema
    participant Logica as :Sistema

    Reloj->>Sistema: ejecutar_gestion_ocupacion()
    activate Sistema

    Sistema->>Logica: buscar_funciones_riesgo_vacio()
    Logica-->>Sistema: funcionesConRiesgo

    alt Hay funciones con riesgo identificadas (Ocupación baja)
        Sistema->>Logica: enviar_cupones_promocionales(funcionesConRiesgo)
        Logica-->>Sistema: 
    end

    opt En ejecución de Pruebas (Modo Testing/QA)
        Sistema->>Logica: verificar_integridad_envios()
        Logica-->>Sistema: 
        Sistema->>Logica: mostrar_detalles_pruebas()
        Logica-->>Sistema: 
    end

    deactivate Sistema