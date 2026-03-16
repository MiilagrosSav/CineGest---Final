sequenceDiagram
    actor Cliente
    participant Ctrl as :AuthViews
    participant Auth as DjangoAuth_Backend
    participant Google as API_Google (OAuth2)
    participant Pipeline as :accounts.pipeline
    participant UserMNG as CustomUser
    participant SocDB as UserSocialAuth

    %% INICIO Y TOMA DE DECISIÓN
    Cliente->>Ctrl: iniciarSesion(tipoAuth, credenciales_locales)
    activate Ctrl

    alt Flujo Tradicional (Local Backend)
        Ctrl->>Auth: user = authenticate(username, password)
        activate Auth
        
        Auth->>UserMNG: inst_user = filter(username=username)
        activate UserMNG
        UserMNG-->>Auth: inst_user
        deactivate UserMNG

        Auth->>Auth: esValido = check_password(password)

        alt esValido == True
            Auth-->>Ctrl: inst_user
            Ctrl->>Auth: login(request, inst_user)
        else esValido == False o inst_user == None
            Auth-->>Ctrl: None
        end
        deactivate Auth

    else Flujo API Google (OAuth Backend)
        %% --- Interacción de Diseño con API Externa ---
        Ctrl->>Google: GET Auth_Request(client_id, scopes)
        activate Google
        Note right of Google: Google muestra pantalla al usuario en su propio servidor,<br>valida su cuenta y emite el Callback
        Google-->>Ctrl: HTTP Callback(payload_response, uid, email)
        deactivate Google
        
        %% --- Regreso al sistema propio (El Pipeline) ---
        Ctrl->>Pipeline: dict_resultado = custom_social_user(uid, email)
        activate Pipeline

        %% Búsqueda de asociación de usuario previa
        Pipeline->>UserMNG: inst_user = get(email=email)
        activate UserMNG
        UserMNG-->>Pipeline: inst_user
        deactivate UserMNG

        alt inst_user Encontrado (Unir Cuenta Google-Local)
            Pipeline->>SocDB: create_social_auth(inst_user, uid)
            activate SocDB
            SocDB-->>Pipeline: inst_social
            deactivate SocDB
        else inst_user No Encontrado (Registro 100% Nuevo)
            %% Forjado del Perfil desde datos dados por la API
            Pipeline->>Pipeline: inst_user = associate_by_email()
            Pipeline->>Pipeline: inst_user = setup_user_profile(user, is_new=True, payload_response)
            
            Note right of Pipeline: Se aplican campos: rol='cliente',<br>generar username seguro,<br>first_y_last_name de API.
            
            Pipeline->>UserMNG: save(inst_user)
            activate UserMNG
            UserMNG-->>Pipeline: inst_guardada
            deactivate UserMNG
        end
        
        Pipeline-->>Ctrl: return {'user': inst_user, is_new: boolean}
        deactivate Pipeline

        Ctrl->>Auth: login(request, inst_user)
    end

    %% RESPUESTA AL ACTOR
    alt user==None (Fallo Local)
        Ctrl-->>Cliente: HttpResponse(PantallaErrorLogin)
    else user.is_new==True (Y falta DNI en BD por venir de Google)
        Ctrl-->>Cliente: HttpResponseRedirect(/completar-perfil)
    else Autenticación Aprobada / Login Completo
        Ctrl-->>Cliente: HttpResponseRedirect(/dashboard)
    end
    deactivate Ctrl