document.addEventListener('DOMContentLoaded', function() {
    const codigoInput = document.getElementById('codigoInput');
    const resultsSection = document.getElementById('resultsSection');
    const loading = document.getElementById('loading');
    const ticketPrintArea = document.getElementById('ticket-print-area');
    const historyList = document.getElementById('historyList');
    const startCameraBtn = document.getElementById('startCameraBtn');
    const stopCameraBtn = document.getElementById('stopCameraBtn');
    const cameraScanner = document.getElementById('cameraScanner');
    const qrVideo = document.getElementById('qrVideo');
    const cameraStatus = document.getElementById('cameraStatus');
    
    let ventaActual = null;
    let cameraStream = null;
    let scannerTimer = null;
    let scannerBusy = false;
    let barcodeDetector = null;
    let lastDetectedCode = null;
    let lastDetectedAt = 0;
    const scanCanvas = document.createElement('canvas');
    const scanContext = scanCanvas.getContext('2d', { willReadFrequently: true });

    if ('BarcodeDetector' in window) {
        try {
            barcodeDetector = new BarcodeDetector({ formats: ['qr_code'] });
        } catch (e) {
            barcodeDetector = null;
        }
    }

    const hasNativeDetector = !!barcodeDetector;
    const hasJsQrFallback = typeof window.jsQR === 'function';

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
    async function buscarVenta(codigoOverride) {
        const codigo = (codigoOverride || codigoInput.value).trim();
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
                stopCameraScanner();
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

    async function startCameraScanner() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            cameraStatus.textContent = 'Este navegador no soporta acceso a camara. Usa lector USB o ingreso manual.';
            cameraScanner.style.display = 'block';
            return;
        }

        if (!hasNativeDetector && !hasJsQrFallback) {
            cameraStatus.textContent = 'No hay motor QR disponible en este navegador. Usa lector USB o ingreso manual.';
            cameraScanner.style.display = 'block';
            return;
        }

        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: { ideal: 'environment' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: false
            });

            qrVideo.srcObject = cameraStream;
            cameraScanner.style.display = 'block';
            startCameraBtn.style.display = 'none';
            stopCameraBtn.style.display = 'inline-flex';
            if (hasNativeDetector) {
                cameraStatus.textContent = 'Camara activa. Enfoca el QR para leer automaticamente.';
            } else {
                cameraStatus.textContent = 'Camara activa con modo compatible de escritorio. Enfoca el QR.';
            }

            scannerTimer = setInterval(scanQrFrame, 250);
        } catch (error) {
            cameraStatus.textContent = 'No se pudo acceder a la camara. Revisa permisos del navegador.';
            cameraScanner.style.display = 'block';
        }
    }

    async function scanQrFrame() {
        if (!qrVideo || scannerBusy) return;
        if (qrVideo.readyState < 2) return;

        scannerBusy = true;
        try {
            let rawCode = null;

            if (hasNativeDetector && barcodeDetector) {
                const barcodes = await barcodeDetector.detect(qrVideo);
                if (barcodes && barcodes.length > 0) {
                    rawCode = (barcodes[0].rawValue || '').trim();
                }
            } else if (hasJsQrFallback && scanContext) {
                rawCode = decodeWithJsQr();
            }

            if (rawCode) {
                const now = Date.now();
                if (lastDetectedCode === rawCode && now - lastDetectedAt < 2000) {
                    return;
                }
                lastDetectedCode = rawCode;
                lastDetectedAt = now;
                cameraStatus.textContent = `QR detectado: ${rawCode}. Validando...`;
                codigoInput.value = rawCode;
                await buscarVenta(rawCode);
            }
        } catch (error) {
            // Ignorar errores transitorios del detector.
        } finally {
            scannerBusy = false;
        }
    }

    function decodeWithJsQr() {
        const width = qrVideo.videoWidth;
        const height = qrVideo.videoHeight;
        if (!width || !height || !scanContext) {
            return null;
        }

        if (scanCanvas.width !== width || scanCanvas.height !== height) {
            scanCanvas.width = width;
            scanCanvas.height = height;
        }

        scanContext.drawImage(qrVideo, 0, 0, width, height);
        const imageData = scanContext.getImageData(0, 0, width, height);
        const result = window.jsQR(imageData.data, width, height, {
            inversionAttempts: 'attemptBoth'
        });

        if (result && result.data) {
            return String(result.data).trim();
        }

        return null;
    }

    function stopCameraScanner() {
        if (scannerTimer) {
            clearInterval(scannerTimer);
            scannerTimer = null;
        }

        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }

        if (qrVideo) {
            qrVideo.srcObject = null;
        }

        lastDetectedCode = null;
        lastDetectedAt = 0;

        if (cameraScanner) {
            cameraScanner.style.display = 'none';
        }

        if (startCameraBtn) {
            startCameraBtn.style.display = 'inline-flex';
        }

        if (stopCameraBtn) {
            stopCameraBtn.style.display = 'none';
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

    if (startCameraBtn) {
        startCameraBtn.addEventListener('click', startCameraScanner);
    }

    if (stopCameraBtn) {
        stopCameraBtn.addEventListener('click', stopCameraScanner);
    }

    window.addEventListener('beforeunload', stopCameraScanner);

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
