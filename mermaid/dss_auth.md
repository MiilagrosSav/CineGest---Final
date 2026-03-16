sequenceDiagram
    actor Cliente
    participant Sistema as :Sistema
    participant Google as API_Google (OAuth)

    %% 1. Peticion Inicial General
    Cliente->>Sistema: solicitar_acceso_formulario(tipoAuth="login_o_registro")
    Sistema-->>Cliente: render_interface(Opciones_Normales_y_Sociales)

    %% Bifurcación en DSS: El usuario elige su destino
    alt Inicio Local (Normal)
        Cliente->>Sistema: procesar_credenciales_propias(usuario,nombre,apellido,email,pwd, acepta_notificaciones)
        
        alt Datos incorrectos o en uso (Ya existe)
            Sistema-->>Cliente: mostrar_formulario_con_errores(mensaje_validacion)
        else Datos Válidos
            Sistema-->>Cliente: iniciarSesion_y_redirigir(dashboard_url)
        end
        
    else Inicio vía Red Social (Google)
        Cliente->>Sistema: solicitar_auth_redSocial(provider="Google")
        %% Se cruza fronteras del sistema
        Sistema->>Google: redirectAuth()
        Google-->>Cliente: solicitarOauth(Google_UI)
        Cliente->>Google: otorgar_permisos_y_credenciales_externas()
        
        %% Retorno al sistema
        Google->>Sistema: callbackSocialPipeline(token_OAuth, payload:{email, nombre})
        
        %% Evaluación final tras el PIPELINE
        alt Faltan datos críticos en B.D (Debe completar DNI)
            Sistema-->>Cliente: redirect(completar_perfil_google)
            Cliente->>Sistema: confirmar_campos_faltantes(dni)
        end
        
        Sistema-->>Cliente: iniciarSesion_y_redirigir(dashboard_url)
    end