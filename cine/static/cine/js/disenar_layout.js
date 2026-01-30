// --- SCRIPT PRINCIPAL ---
window.addEventListener('DOMContentLoaded', function() {

    let distribucionActual = [];

    // Leer URLs desde data attributes
    const designerPage = document.querySelector('.designer-page');
    const urlGuardar = designerPage.dataset.urlGuardar;
    const urlRedirect = designerPage.dataset.urlRedirect;

    // Selectores de DOM
    const areaAsientos = document.getElementById('areaAsientos');
    const btnGenerar = document.getElementById('btnGenerar');
    const btnLimpiar = document.getElementById('btnLimpiar');
    const btnGuardar = document.getElementById('btnGuardar');
    const inputFilas = document.getElementById('numFilas');
    const inputColumnas = document.getElementById('numColumnas');
    const selectTipo = document.getElementById('tipoAsiento');
    const contador = document.getElementById('contadorAsientos');

    // --- FUNCIONES ---

    function crearAsiento(fila, numero, tipo) {
        const b = document.createElement('div');
        b.className = 'asiento';
        // Para 4D no agregamos clase, usamos solo data-tipo
        if (tipo !== '4D' && tipo !== 'vacio') {
            b.className += ` ${tipo}`;
        }
        if (tipo === 'vacio') {
            b.className += ' vacio';
        }
        b.dataset.fila = fila;
        b.dataset.num = numero;
        b.dataset.tipo = tipo;
        b.textContent = numero;

        // Click: Cambiar tipo
        b.addEventListener('click', () => {
            const tipoSel = selectTipo.value;
            if (b.dataset.tipo !== 'vacio') {
                b.className = 'asiento';
                // Para 4D no agregamos clase, usamos solo data-tipo
                if (tipoSel !== '4D') {
                    b.className += ` ${tipoSel}`;
                }
                b.dataset.tipo = tipoSel;
                const idx = distribucionActual.findIndex(x => x.fila === fila && x.num === numero);
                if (idx !== -1) distribucionActual[idx].tipo = tipoSel;
            }
        });

        // Doble Click: Alternar vacío/asiento
        b.addEventListener('dblclick', () => {
            if (b.dataset.tipo !== 'vacio') {
                // Convertir asiento a pasillo (vacío)
                b.className = 'asiento vacio';
                b.dataset.tipo = 'vacio';
                b.textContent = '';
                
                // Actualizar en distribucionActual: marcar como pasillo en lugar de eliminar
                const idx = distribucionActual.findIndex(x => x.fila === fila && x.num === numero);
                if (idx !== -1) {
                    distribucionActual[idx].tipo = 'vacio';
                    distribucionActual[idx].es_pasillo = true;
                } else {
                    distribucionActual.push({ fila, num: numero, tipo: 'vacio', es_pasillo: true });
                }
                
                // Renumerar asientos de esta fila
                renumerarFila(fila);
            } else {
                // Convertir pasillo a asiento
                const tipoSel = selectTipo.value;
                b.className = 'asiento';
                // Para 4D no agregamos clase, usamos solo data-tipo
                if (tipoSel !== '4D') {
                    b.className += ` ${tipoSel}`;
                }
                b.dataset.tipo = tipoSel;
                b.textContent = numero;
                
                // Actualizar en distribucionActual
                const idx = distribucionActual.findIndex(x => x.fila === fila && x.num === numero);
                if (idx !== -1) {
                    distribucionActual[idx].tipo = tipoSel;
                    distribucionActual[idx].es_pasillo = false;
                } else {
                    distribucionActual.push({ fila, num: numero, tipo: tipoSel, es_pasillo: false });
                }
                
                // Renumerar asientos de esta fila
                renumerarFila(fila);
            }
            actualizarContador();
            actualizarDimensionesInputs();
        });

        return b;
    }

    /**
     * Renumera los asientos de una fila específica de forma consecutiva.
     * Los pasillos (vacíos) no tienen número, solo los asientos reales.
     */
    function renumerarFila(fila) {
        // Obtener todos los elementos de asiento de esta fila en el DOM
        const filaRow = Array.from(areaAsientos.children).find(row => {
            const label = row.querySelector('.label-fila');
            return label && label.textContent === fila;
        });

        if (!filaRow) return;

        // Obtener todos los divs de asientos de esta fila (excluyendo el label)
        const asientosEnFila = Array.from(filaRow.querySelectorAll('.asiento'));
        
        // Contar solo los asientos reales (no vacíos) para renumeración
        let contadorAsiento = 1;
        
        asientosEnFila.forEach((asientoDiv) => {
            const esVacio = asientoDiv.dataset.tipo === 'vacio';
            
            if (!esVacio) {
                // Es un asiento real: actualizar número
                const numeroAnterior = parseInt(asientoDiv.dataset.num);
                const numeroNuevo = contadorAsiento;
                
                // Actualizar el DOM
                asientoDiv.dataset.num = numeroNuevo;
                asientoDiv.textContent = numeroNuevo;
                
                // Actualizar en distribucionActual
                const idx = distribucionActual.findIndex(
                    x => x.fila === fila && x.num === numeroAnterior
                );
                if (idx !== -1) {
                    distribucionActual[idx].num = numeroNuevo;
                }
                
                contadorAsiento++;
            } else {
                // Es un pasillo: no tiene número visible
                asientoDiv.textContent = '';
            }
        });
    }

    /**
     * Recalcula las filas y columnas máximas basadas 
     * en la distribución actual y actualiza los inputs.
     */
    function actualizarDimensionesInputs() {
        if (distribucionActual.length === 0) {
            inputFilas.value = 0;
            inputColumnas.value = 0;
            return;
        }

        // 1. Encontrar la columna máxima
        const maxCol = Math.max(0, ...distribucionActual.map(b => b.num));
        inputColumnas.value = maxCol;

        // 2. Encontrar la fila máxima (letra)
        const filasCharCodes = distribucionActual.map(b => b.fila.charCodeAt(0));
        const maxCharCode = Math.max(64, ...filasCharCodes); // 64 para que si está vacío, dé 0
        
        // (65 - 65) + 1 = 1 (Fila A)
        // (64 - 65) + 1 = 0 (Sin filas)
        const numFilas = (maxCharCode - 65) + 1;
        inputFilas.value = numFilas > 0 ? numFilas : 0;
    }

    function generarDistribucionBase() {
        const nf = parseInt(inputFilas.value) || 10;
        const nc = parseInt(inputColumnas.value) || 12;

        if (nf < 1 || nf > 26) {
            mostrarMensaje('⚠️ El número de filas debe estar entre 1 y 26', 'error');
            return;
        }
        if (nc < 1 || nc > 40) {
            mostrarMensaje('⚠️ El número de asientos por fila debe estar entre 1 y 40', 'error');
            return;
        }

        if (distribucionActual.length > 0 && !confirm('¿Deseas reemplazar la distribución actual?')) {
            return;
        }

        areaAsientos.innerHTML = '';
        distribucionActual = [];

        for (let i = 0; i < nf; i++) {
            const letra = String.fromCharCode(65 + i); // 65 es 'A'
            const row = document.createElement('div');
            row.className = 'fila-asientos';

            const label = document.createElement('div');
            label.className = 'label-fila';
            label.textContent = letra;
            row.appendChild(label);

            for (let j = 1; j <= nc; j++) {
                const b = crearAsiento(letra, j, 'GENERAL');
                row.appendChild(b);
                distribucionActual.push({ fila: letra, num: j, tipo: 'GENERAL', es_pasillo: false });
            }
            areaAsientos.appendChild(row);
        }

        actualizarContador();
        mostrarMensaje(`✅ Distribución generada: ${nf} filas × ${nc} asientos = ${nf * nc} asientos`, 'success');
    }

    function limpiarDistribucion() {
        if (distribucionActual.length === 0) {
            mostrarMensaje('ℹ️ No hay nada que limpiar', 'error');
            return;
        }

        if (confirm(`¿Estás seguro de limpiar ${distribucionActual.length} asientos?\n\nEsta acción no se puede deshacer.`)) {
            areaAsientos.innerHTML = '<p class="placeholder-text">👆 Crea una grilla para empezar a diseñar</p>';
            distribucionActual = [];
            actualizarContador();
            actualizarDimensionesInputs();
            mostrarMensaje('🗑️ Distribución limpiada correctamente', 'success');
        }
    }

    async function guardarDistribucion() {
        if (distribucionActual.length === 0) {
            mostrarMensaje('❌ No hay asientos para guardar. Genera una distribución primero.', 'error');
            return;
        }

        const butacasReales = distribucionActual.filter(b => b.tipo !== 'vacio' && !b.es_pasillo);
        const pasillos = distribucionActual.filter(b => b.tipo === 'vacio' || b.es_pasillo);
        
        const tiposCount = {
            GENERAL: butacasReales.filter(b => b.tipo === 'GENERAL').length,
            CUATROD: butacasReales.filter(b => b.tipo === '4D').length,
            DISCAPACITADO: butacasReales.filter(b => b.tipo === 'DISCAPACITADO').length
        };

        const mensaje = `¿Guardar esta distribución?\n\n📊 Total: ${butacasReales.length} asientos\n🟦 General: ${tiposCount.GENERAL}\n🟩 4D: ${tiposCount.CUATROD}\n🟣 Discapacitado: ${tiposCount.DISCAPACITADO}\n🚶 Pasillos: ${pasillos.length}`;

        if (!confirm(mensaje)) return;

        btnGuardar.disabled = true;
        btnGuardar.textContent = '⏳ Guardando...';

        // Log para debugging
        console.log('📤 Enviando distribución:', {
            total: distribucionActual.length,
            butacas: butacasReales.length,
            pasillos: pasillos.length
        });
        console.log('Datos completos:', distribucionActual);

        try {
            const res = await fetch(urlGuardar, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(distribucionActual)
            });
            const data = await res.json();

            if (data.status === 'ok' || res.ok) {
                let mensaje = `✅ Distribución guardada exitosamente!\n\n📊 Capacidad: ${data.capacidad} asientos\n🚶 Pasillos: ${data.pasillos}\n📦 Total guardado: ${data.butacas_creadas} posiciones`;
                if (data.warning) {
                    mensaje += `\n⚠️ ${data.warning}`;
                }
                mostrarMensaje(mensaje, 'success');
                
                // Redirigir a la lista de salas después de 2 segundos
                setTimeout(() => {
                    window.location.href = urlRedirect;
                }, 2000);
            } else {
                let mensajeError = '❌ Error: ' + (data.message || 'Error desconocido');
                if (data.duplicados && data.duplicados.length > 0) {
                    mensajeError += `\n\nButacas duplicadas: ${data.duplicados.join(', ')}`;
                }
                mostrarMensaje(mensajeError, 'error');
            }
        } catch (e) {
            mostrarMensaje('❌ Error de conexión: ' + e.message, 'error');
        } finally {
            btnGuardar.disabled = false;
            btnGuardar.textContent = '💾 Guardar Distribución';
        }
    }

    function cargarDistribucionExistente() {
        const dataEl = document.getElementById('butacasData');
        if (!dataEl) return;

        try {
            const butacasExistentes = JSON.parse(dataEl.textContent);
            if (butacasExistentes && butacasExistentes.length > 0) {
                
                const filas = [...new Set(butacasExistentes.map(b => b.fila))].sort();
                const maxColVisual = Math.max(0, ...butacasExistentes.map(b => b.numero));
                
                areaAsientos.innerHTML = '';
                distribucionActual = [];

                filas.forEach(f => {
                    const row = document.createElement('div');
                    row.className = 'fila-asientos';
                    const label = document.createElement('div');
                    label.className = 'label-fila';
                    label.textContent = f;
                    row.appendChild(label);

                    for (let j = 1; j <= maxColVisual; j++) { 
                        const be = butacasExistentes.find(x => x.fila === f && x.numero === j);
                        let b;
                        if (be) {
                            // Existe en BD - agregar a distribucionActual
                            const esPasillo = be.es_pasillo || be.tipo === 'vacio';
                            const tipoFinal = esPasillo ? 'vacio' : be.tipo;
                            b = crearAsiento(f, j, tipoFinal);
                            if (esPasillo) {
                                b.textContent = '';
                            }
                            distribucionActual.push({ 
                                fila: f, 
                                num: j, 
                                tipo: tipoFinal,
                                es_pasillo: esPasillo
                            });
                        } else {
                            // NO existe en BD - solo renderizar visualmente como vacío
                            // NO agregar a distribucionActual hasta que el usuario lo convierta
                            b = crearAsiento(f, j, 'vacio');
                            b.textContent = '';
                            // NO agregamos a distribucionActual - solo es visual
                        }
                        row.appendChild(b);
                    }
                    areaAsientos.appendChild(row);
                });
                
                actualizarContador();
                actualizarDimensionesInputs();
            }
        } catch(e) {
            console.error("Error al cargar butacas existentes:", e);
            mostrarMensaje("❌ Error al procesar datos de la sala.", "error");
        }
    }

    function actualizarContador() {
        // Contar solo butacas reales (sin pasillos)
        const butacasReales = distribucionActual.filter(b => b.tipo !== 'vacio' && !b.es_pasillo).length;
        contador.textContent = butacasReales;
    }

    // --- INICIALIZACIÓN ---
    btnGenerar.addEventListener('click', generarDistribucionBase);
    btnLimpiar.addEventListener('click', limpiarDistribucion);
    btnGuardar.addEventListener('click', guardarDistribucion);

    cargarDistribucionExistente();
});


// --- FUNCIONES AUXILIARES (Fuera del DOMContentLoaded) ---

function mostrarMensaje(texto, tipo) {
    const msg = document.createElement('div');
    msg.textContent = texto;
    msg.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: var(--radius);
        font-weight: 500;
        z-index: 1000;
        animation: slideIn 0.3s ease;
        ${tipo === 'success' ?
            'background: rgba(126,211,33,0.15); border: 1px solid #7ED321; color: #7ED321;' :
            'background: rgba(239,68,68,0.15); border: 1px solid #ef4444; color: #ef4444;'}
    `;
    document.body.appendChild(msg);
    setTimeout(() => {
        msg.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => msg.remove(), 300);
    }, 3000);
}

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
