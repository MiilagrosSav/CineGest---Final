sequenceDiagram
    actor Admin
    participant Views as funcion_create_view()
    participant Form as FuncionBatchForm
    participant Builder as _procesar_carga_masiva_funciones()
    participant Conf as ConfiguracionCine
    participant ModelFun as Funcion
    
    Admin->>Views: POST (pelicula, sala, fechas_objetivo, horarios[], formatos[])
    Views->>Form: is_valid()
    
    alt Formulario Inválido
        Form-->>Views: False (Error dict)
        Views-->>Admin: Renderiza Form Errors
    else Formulario Válido
        Views->>Builder: invocar con (pelicula, sala, fechas, horarios y formatos)
        Builder->>Conf: load() (Obtiene minutos_limpieza y configuración)
        Builder->>ModelFun: filter(...) (Obtener funciones existentes para generar agenda)
        ModelFun-->>Builder: QuerySet<funciones_existentes>
        
        loop Iteración: por cada fecha y por cada hora
            Builder->>Conf: validar_rango_horario(fecha_hora, fin_funcion)
            
            Builder->>Builder: _buscar_conflicto_intervalo(agenda, inicio, fin)
            alt Conflicto: inicio y fin pisado en distintos horarios
                Builder-->>Builder: Retorna Omision {tipo: 'sala_ocupada'}
            else Conflicto: Igual horario_inicio (Bisala)
                Builder->>ModelFun: permite_solape_bisala()
                alt Misma Película y 4D != Estándar
                    ModelFun-->>Builder: True (Autoriza ciclo)
                    Builder->>Builder: append a funciones_a_crear y actualiza agenda
                else Diferente Película o Mismos Formatos
                    ModelFun-->>Builder: False (Rechaza solape)
                    Builder-->>Builder: Retorna Omision {tipo: 'motivo_bisala'}
                end
            else Sin conflicto
                Builder->>Builder: append a funciones_a_crear y actualiza agenda
            end
        end
        
        Builder->>ModelFun: objects.bulk_create(funciones_a_crear)
        ModelFun-->>Builder: instancias funciones_creadas
        Builder-->>Views: Retorna (funciones_creadas, omisiones, omisiones_total)
        
        Views->>Views: FuncionFormato.objects.bulk_create(formatos_a_crear)
        Views-->>Admin: Redirección con messages.success y .warnings(omisiones)
    end