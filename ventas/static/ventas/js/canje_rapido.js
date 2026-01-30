document.addEventListener('DOMContentLoaded', function() {
    const codigoInput = document.getElementById('codigoInput');
    const resultsSection = document.getElementById('resultsSection');
    const loading = document.getElementById('loading');
    const ticketPrintArea = document.getElementById('ticket-print-area');
    const historyList = document.getElementById('historyList');
    
    let ventaActual = null;

    // Función para obtener el CSRF token de las cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // Focus siempre en el input para escanear seguido
    codigoInput.focus();
    document.addEventListener('click', (e) => {
        // Si no clicamos en un botón, devolver el foco al input
        if (!e.target.closest('button') && !e.target.closest('a')) {
            codigoInput.focus();
        }
    });

    // Detectar Enter
    codigoInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            buscarVenta();
        }
    });

    // Función principal
    async function buscarVenta() {
        const codigo = codigoInput.value.trim();
        if (!codigo) return;

        loading.classList.add('show');
        resultsSection.innerHTML = ''; // Limpiar anterior

        try {
            const response = await fetch(window.BUSCAR_VENTA_URL, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'X-CSRFToken': csrftoken 
                },
                body: JSON.stringify({ codigo: codigo })
            });
            const data = await response.json();
            
            loading.classList.remove('show');
            codigoInput.value = ''; // Limpiar input para el siguiente

            if (data.success) {
                // Si el servidor devuelve info de la venta, persistir en historial
                try {
                    if (data.venta_info) {
                        agregarHistorial(data.venta_info);
                    }
                } catch (e) {
                    console.warn('No se pudo agregar al historial antes de redirigir:', e);
                }

                // Redirigir directamente a la página del ticket
                window.location.href = data.redirect_url;
            } else {
                mostrarError(data.error, data.detalles);
                reproducirSonido('error');
            }
        } catch (error) {
            loading.classList.remove('show');
            mostrarError('Error de conexión', 'Intente nuevamente.');
            reproducirSonido('error');
        }
    }

    function mostrarExito(data) {
        const info = data.venta_info;
        const cantidadTickets = data.cantidad_tickets || 1;
        const html = `
            <div class="result-card success">
                <h2 class="success-title">✅ Acceso Permitido</h2>
                <p style="opacity: 0.8; margin-bottom: 0;">Venta validada. Se generarán ${cantidadTickets} ticket(s) individual(es).</p>
                
                <div class="info-grid">
                    <div class="info-item"><small>CLIENTE</small><strong>${info.cliente}</strong></div>
                    <div class="info-item"><small>PELÍCULA</small><strong>${info.pelicula}</strong></div>
                    <div class="info-item"><small>SALA</small><strong>${info.sala}</strong></div>
                    <div class="info-item"><small>ENTRADAS</small><strong>${cantidadTickets}</strong></div>
                </div>
                
                <div class="result-actions">
                    <button class="btn btn-success" onclick="imprimirTicket()">🖨️ Re-imprimir ${cantidadTickets} ticket(s)</button>
                    <button class="btn btn-danger" onclick="limpiarResultados()">Cerrar</button>
                </div>
            </div>
        `;
        resultsSection.innerHTML = html;
        ticketPrintArea.innerHTML = data.ticket_html; // Inyectar todos los tickets para imprimir
        
        agregarHistorial(info);
    }

    function mostrarError(titulo, mensaje) {
        const html = `
            <div class="result-card error">
                <h2 class="error-title">❌ Acceso Denegado</h2>
                <p style="font-size: 1.1rem; margin-top: 0.5rem;">${titulo}</p>
                ${mensaje ? `<p style="opacity: 0.7;">${mensaje}</p>` : ''}
                
                <div class="result-actions">
                    <button class="btn btn-danger" onclick="limpiarResultados()">Intentar de nuevo</button>
                </div>
            </div>
        `;
        resultsSection.innerHTML = html;
    }

    window.imprimirTicket = async function() {
        if (!ventaActual) return;
        
        // Imprimir
        window.print();
        
        // Marcar como impreso en el servidor
        try {
            const response = await fetch(window.IMPRIMIR_TICKET_URL.replace('0', ventaActual.venta_id), {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'X-CSRFToken': csrftoken 
                },
                body: JSON.stringify({ venta_id: ventaActual.venta_id })
            });
            
            const data = await response.json();
            if (data.success) {
                // Agregar al historial
                agregarHistorial(ventaActual.venta_info);
                // Limpiar después de un momento
                setTimeout(() => limpiarResultados(), 1500);
            }
        } catch (error) {
            console.error('Error al marcar como impreso:', error);
        }
    };

    window.limpiarResultados = function() {
        resultsSection.innerHTML = '';
        codigoInput.focus();
    };

    function reproducirSonido(id) {
        const audio = document.getElementById(id + 'Sound');
        if (audio) { audio.currentTime = 0; audio.play().catch(e => {}); }
    }

    function agregarHistorial(info) {
        const item = document.createElement('div');
        item.className = 'history-item';
        const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        item.innerHTML = `
            <div>
                <strong>#${info.codigo_compra}</strong> - ${info.cliente}
            </div>
            <span class="history-time">${time}</span>
        `;
        
        // Remover mensaje de vacío si existe
        const empty = historyList.querySelector('.empty-history');
        if (empty) empty.remove();
        
        historyList.prepend(item);
        
        // Mantener solo 10 en la vista DOM
        if (historyList.children.length > 10) historyList.lastElementChild.remove();

        // Persistir en localStorage (mantener un array de hasta 10 entradas)
        try {
            const raw = localStorage.getItem('canje_history') || '[]';
            const arr = JSON.parse(raw);
            // Insertar al inicio
            arr.unshift({ codigo_compra: info.codigo_compra, cliente: info.cliente, time: time });
            const trimmed = arr.slice(0, 10);
            localStorage.setItem('canje_history', JSON.stringify(trimmed));
        } catch (e) {
            console.warn('No se pudo actualizar localStorage del historial:', e);
        }
    }

    // Wiring del botón para limpiar historial
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', function() {
            if (confirm('¿Borrar historial de canjes en esta máquina?')) {
                clearHistory();
            }
        });
    }

    // Cargar historial previo (si existe)
    loadHistoryFromStorage();

    // Cargar historial desde localStorage al inicio
    function loadHistoryFromStorage() {
        try {
            const raw = localStorage.getItem('canje_history') || '[]';
            const arr = JSON.parse(raw);
            historyList.innerHTML = '';
            if (!arr || arr.length === 0) {
                historyList.innerHTML = '<div class="empty-history">Aún no has validado entradas hoy.</div>';
                return;
            }
            arr.forEach(item => {
                const div = document.createElement('div');
                div.className = 'history-item';
                div.innerHTML = `
                    <div>
                        <strong>#${item.codigo_compra}</strong> - ${item.cliente}
                    </div>
                    <span class="history-time">${item.time || ''}</span>
                `;
                historyList.appendChild(div);
            });
        } catch (e) {
            console.warn('Error al cargar historial desde localStorage:', e);
        }
    }

    // Limpiar historial (vista + localStorage)
    function clearHistory() {
        localStorage.removeItem('canje_history');
        historyList.innerHTML = '<div class="empty-history">Aún no has validado entradas hoy.</div>';
    }
});
