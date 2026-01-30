// Butacas selection logic
const precioUnitario = parseFloat(document.getElementById('precio-data').getAttribute('data-precio'));
const cantidadNecesariaEl = document.getElementById('cantidad-data');
const cantidadNecesaria = cantidadNecesariaEl ? parseInt(cantidadNecesariaEl.getAttribute('data-cantidad')) : null;
const promo2x1El = document.getElementById('promo-2x1-data');
const promo2x1 = promo2x1El ? (promo2x1El.getAttribute('data-promo-2x1') === 'true') : false;

const infoDescuentoEl = document.getElementById('info-descuento-data');
const tipoDescuento = infoDescuentoEl ? infoDescuentoEl.getAttribute('data-tipo') : null;
const precioConDescuento = infoDescuentoEl ? parseFloat(infoDescuentoEl.getAttribute('data-precio-con-descuento')) : null;

const requiere4DEl = document.getElementById('requiere-4d-data');
const requiere4D = requiere4DEl ? (requiere4DEl.getAttribute('data-requiere-4d') === 'true') : false;

let butacasSeleccionadas = [];

console.log('Script cargado. Precio unitario:', precioUnitario, 'Tipo descuento:', tipoDescuento, 'Requiere 4D:', requiere4D);

function toggleButaca(elemento) {
    if (elemento.classList.contains('deshabilitada') || elemento.classList.contains('pasillo') || elemento.classList.contains('ocupada')) {
        console.log('Intento de seleccionar butaca no permitida');
        return;
    }
    
    console.log('Toggle butaca clickeada:', elemento);
    const butacaId = elemento.getAttribute('data-butaca-id');
    const fila = elemento.getAttribute('data-fila');
    const numero = elemento.getAttribute('data-numero');
    const tipoButaca = elemento.getAttribute('data-tipo-butaca');
    
    console.log('Butaca ID:', butacaId, 'Fila:', fila, 'Numero:', numero, 'Tipo:', tipoButaca);
    
    if (elemento.classList.contains('seleccionada')) {
        console.log('Deseleccionando butaca');
        elemento.classList.remove('seleccionada');
        butacasSeleccionadas = butacasSeleccionadas.filter(b => b.id !== butacaId);
        const input = document.querySelector(`input[value="${butacaId}"]`);
        if (input) input.remove();
    } else {
        if (cantidadNecesaria && butacasSeleccionadas.length >= cantidadNecesaria) {
            console.log('Ya seleccionaste la cantidad necesaria:', cantidadNecesaria);
            return;
        }
        console.log('Seleccionando butaca');
        elemento.classList.add('seleccionada');
        butacasSeleccionadas.push({ id: butacaId, fila: fila, numero: numero });
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'butacas[]';
        input.value = butacaId;
        document.getElementById('formButacas').appendChild(input);
    }
    console.log('Butacas seleccionadas:', butacasSeleccionadas);
    actualizarResumen();
}

function actualizarResumen() {
    const cantidad = butacasSeleccionadas.length;
    
    let total = cantidad * precioUnitario;
    
    if (tipoDescuento === '2X1' && cantidad === 2) {
        total = precioUnitario;
    } else if (tipoDescuento === 'PORCENTAJE' || tipoDescuento === 'MONTO_FIJO') {
        total = cantidad * precioUnitario;
    }
    
    console.log('Actualizando resumen. Cantidad:', cantidad, 'Total:', total, 'Tipo:', tipoDescuento);
    
    document.getElementById('cantidadButacas').textContent = cantidad;
    document.getElementById('totalCompra').textContent = `$${total.toFixed(2)}`;
    
    const contenedor = document.getElementById('butacasSeleccionadas');
    if (cantidad === 0) {
        contenedor.innerHTML = '<p style="opacity: 0.7; text-align: center; padding: var(--space-lg) 0;">Selecciona tus butacas en el mapa</p>';
        document.getElementById('btnConfirmar').disabled = true;
        console.log('Sin butacas seleccionadas, botón deshabilitado');
    } else {
        let html = '<div style="display: flex; flex-direction: column; gap: 0.5rem;">';
        butacasSeleccionadas.forEach((butaca, idx) => {
            const precio = (tipoDescuento === '2X1' && cantidad === 2 && idx === 1) ? 0 : precioUnitario;
            const precioTexto = precio === 0 ? 'GRATIS 🎉' : `$${precio.toFixed(2)}`;
            html += `<div style="background: rgba(0,0,0,0.3); padding: 0.5rem; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                <span>💺 Butaca ${butaca.fila}${butaca.numero}</span>
                <span style="color: ${precio === 0 ? 'var(--accent)' : 'var(--primary)'};">${precioTexto}</span>
            </div>`;
        });
        html += '</div>';
        contenedor.innerHTML = html;
        if (cantidadNecesaria) {
            document.getElementById('btnConfirmar').disabled = cantidad !== cantidadNecesaria;
        } else {
            document.getElementById('btnConfirmar').disabled = false;
        }
        console.log('Butacas seleccionadas, botón habilitado');
    }
}

// Timer logic
(function(){
    const timerRoot = document.getElementById('reserva-timer');
    if (!timerRoot) return;
    const expirationIso = timerRoot.getAttribute('data-expiration');
    const expirationDate = expirationIso ? new Date(expirationIso) : new Date(Date.now() + 10*60*1000);
    const textEl = document.getElementById('reserva-timer-text');
    const mapa = document.querySelector('.mapa-butacas');
    const btnConfirmar = document.getElementById('btnConfirmar');

    function formatTime(sec){
        const m = Math.floor(sec/60).toString().padStart(2,'0');
        const s = Math.floor(sec%60).toString().padStart(2,'0');
        return `${m}:${s}`;
    }

    function tick(){
        const now = new Date();
        let restante_ms = expirationDate.getTime() - now.getTime();
        let restante = Math.floor(restante_ms / 1000);
        if (restante <= 0){
            textEl.textContent = '00:00';
            handleExpiry();
            return;
        }
        textEl.textContent = formatTime(restante);
        if (restante <= 60){
            timerRoot.style.background = 'linear-gradient(90deg,#36213a,#5c0fa8)';
            textEl.style.color = '#ffb3b3';
        }
    }

    function handleExpiry(){
        try{
            if (mapa) mapa.style.pointerEvents = 'none';
            if (btnConfirmar) btnConfirmar.disabled = true;

            if (window.Swal){
                Swal.fire({
                    title: '¡Tiempo Agotado!',
                    text: 'Tus reservas han sido liberadas por inactividad',
                    icon: 'warning',
                    confirmButtonText: 'Aceptar',
                    allowOutsideClick: false,
                    allowEscapeKey: true
                }).then(() => {
                    window.location.href = window.CARTELERA_URL || '/';
                });
            } else {
                alert('El tiempo de reserva ha expirado. Serás redirigido.');
                window.location.href = window.CARTELERA_URL || '/';
            }
        }catch(e){
            console.error('Error handling expiry', e);
            window.location.href = window.CARTELERA_URL || '/';
        }
    }

    tick();
    const interval = setInterval(tick, 1000);
})();

// Real-time synchronization
(function() {
    const funcionId = window.FUNCION_ID;
    if (!funcionId) return;
    
    const urlVerificarButacas = '/ventas/api/verificar-butacas/' + funcionId + '/';
    
    function sincronizarButacas() {
        fetch(urlVerificarButacas)
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success) {
                    const butacasOcupadasServidor = new Set(data.butacas_ocupadas);
                    
                    const todosLosElementos = document.querySelectorAll('.butaca[data-butaca-id]');
                    todosLosElementos.forEach(function(butacaEl) {
                        const butacaId = parseInt(butacaEl.getAttribute('data-butaca-id'));
                        const estaOcupadaServidor = butacasOcupadasServidor.has(butacaId);
                        const estaOcupadaLocal = butacaEl.classList.contains('ocupada');
                        
                        if (estaOcupadaServidor && !estaOcupadaLocal) {
                            butacaEl.classList.add('ocupada');
                            
                            if (butacaEl.classList.contains('seleccionada')) {
                                butacaEl.classList.remove('seleccionada');
                                const fila = butacaEl.getAttribute('data-fila');
                                const numero = butacaEl.getAttribute('data-numero');
                                
                                butacasSeleccionadas = butacasSeleccionadas.filter(function(b) {
                                    return !(b.fila === fila && b.numero === numero);
                                });
                                
                                const input = document.querySelector('input[value="' + butacaId + '"]');
                                if (input) input.remove();
                                
                                butacaEl.style.transform = 'scale(1.1)';
                                setTimeout(function() {
                                    butacaEl.style.transform = '';
                                }, 300);
                                
                                actualizarResumen();
                            }
                        }
                        else if (!estaOcupadaServidor && estaOcupadaLocal) {
                            butacaEl.classList.remove('ocupada');
                        }
                    });
                }
            })
            .catch(function(error) {
                console.warn('Error al sincronizar butacas:', error);
            });
    }
    
    setInterval(sincronizarButacas, 3000);
    sincronizarButacas();
    
    const formButacas = document.getElementById('formButacas');
    if (formButacas) {
        formButacas.addEventListener('submit', function(e) {
            e.preventDefault();
            
            fetch(urlVerificarButacas)
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data.success) {
                        const butacasOcupadasServidor = new Set(data.butacas_ocupadas);
                        const inputsButacas = document.querySelectorAll('input[name="butacas[]"]');
                        const butacasSeleccionadasIds = [];
                        inputsButacas.forEach(function(input) {
                            butacasSeleccionadasIds.push(parseInt(input.value));
                        });
                        
                        let conflicto = false;
                        for (let i = 0; i < butacasSeleccionadasIds.length; i++) {
                            if (butacasOcupadasServidor.has(butacasSeleccionadasIds[i])) {
                                conflicto = true;
                                break;
                            }
                        }
                        
                        if (conflicto) {
                            if (window.Swal) {
                                Swal.fire({
                                    title: '⚠️ Butacas No Disponibles',
                                    text: 'Algunas butacas fueron ocupadas por otro usuario. Por favor selecciona otras.',
                                    icon: 'warning',
                                    confirmButtonText: 'Entendido'
                                });
                            } else {
                                alert('⚠️ Algunas butacas fueron ocupadas. Por favor selecciona otras.');
                            }
                            sincronizarButacas();
                        } else {
                            formButacas.submit();
                        }
                    } else {
                        formButacas.submit();
                    }
                })
                .catch(function(error) {
                    console.error('Error en validación final:', error);
                    formButacas.submit();
                });
        });
    }
})();
