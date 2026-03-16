sequenceDiagram
    actor Admin
    participant Sistema as :Sistema

    %% 1. Búsqueda y selección de catálogos base
    Admin->>Sistema: peliculas = buscarPeliculas()
    Admin->>Sistema: unaPelicula = buscarPelicula(peliculas, id_pelicula)

    Admin->>Sistema: salas = buscarSalas()
    Admin->>Sistema: unaSala = buscarSala(salas, id_sala)

    Admin->>Sistema: formatos = buscarFormatos()
    Admin->>Sistema: unFormato = buscarFormato(formatos, id_formato)

    %% 2. Búsqueda y validación de disponibilidad
    loop Mientras configura fechas y horarios
        Admin->>Sistema: horariosDisponibles = calcular_horarios_disponibles(unaSala)
    end
    
    %% 3. Ejecución de la operación principal
    Admin->>Sistema: funcion_create_view(unaPelicula, unaSala, horariosDisponibles, unFormato, precioBase)

    %% 4. Respuesta del sistema según validaciones internas
    alt Hay solapamientos (limpieza, pisadas) no sorteados por Bisala
        Sistema-->>Admin: redirect() [con messages.warning(omisiones)]
    else Todo el lote es perfecto o entra en regla Bisala
        Sistema-->>Admin: redirect() [con messages.success(total_funciones_creadas)]
    end