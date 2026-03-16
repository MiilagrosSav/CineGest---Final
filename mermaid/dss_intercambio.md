sequenceDiagram
    actor Cliente
    participant Sistema as :Sistema

    %% 1. Identificación y Búsqueda de Compra
    Cliente->>Sistema: ventas = buscarVentas()
    Cliente->>Sistema: unaVenta = seleccionarVenta(ventas, id_venta)

    %% 2. Búsqueda de Destino
    Cliente->>Sistema: funciones = buscarFuncionesCartelera()
    Cliente->>Sistema: unaFuncion = seleccionarFuncion(funciones, id_funcion)
    
 

    %% 3. Validación de Política (Caja Negra)
    Cliente->>Sistema: esValido = validar_intercambio(unaVenta, unaFuncion)

    alt esValido == False
        Sistema-->>Cliente: mostrarError(mensaje_politica)
    else esValido == True
        %% 4. Selección de Butacas
        Cliente->>Sistema: disponibilidad = buscarButacasLibres(unaFuncion)
        Cliente->>Sistema: nuevasButacas = seleccionarButacas(disponibilidad, cantidad)

        %% 5. Ejecución
        Cliente->>Sistema: confirmarIntercambio(unaVenta, unaFuncion, nuevasButacas)
        
       
        
        Sistema-->>Cliente: informarExito(nuevos_tickets)
    end