// JS extracted from templates/cine/funcion_form.html
const CALCULAR_HORARIOS_URL = window.CALCULAR_HORARIOS_URL || null;
// Diagnostic logs to help debug submit/save issues
console.info('funcion_form.js: cargado', { CALCULAR_HORARIOS_URL });
const djangoData = (function(){
    const el = document.getElementById('django-data');
    return el ? JSON.parse(el.textContent) : { esEdicion: false, funcionActual: null };
})();
const ES_EDICION = djangoData.esEdicion;
const FUNCION_ACTUAL = djangoData.funcionActual;

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('funcion-form');
    console.debug('funcion_form.js: buscando #funcion-form ->', !!form);
    
    // Fecha/hora validation
    const fechaHoraInput = document.querySelector('input[name="fecha_hora"]');
    if (fechaHoraInput) {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const minDateTime = `${year}-${month}-${day}T${hours}:${minutes}`;
        if (!fechaHoraInput.value) { fechaHoraInput.min = minDateTime; }
        fechaHoraInput.addEventListener('change', function() {
            const selectedDateTime = new Date(this.value);
            const nowDateTime = new Date();
            if (selectedDateTime < nowDateTime) {
                this.setCustomValidity('La fecha y hora no pueden ser en el pasado.');
                this.style.borderColor = '#ff6b6b';
            } else {
                this.setCustomValidity('');
                this.style.borderColor = '#4ecdc4';
            }
        });
    }

    // Fecha validation
    const fechaInput = document.querySelector('input[name="fecha"]');
    if (fechaInput) {
         const now = new Date();
         const year = now.getFullYear();
         const month = String(now.getMonth() + 1).padStart(2, '0');
         const day = String(now.getDate()).padStart(2, '0');
         const minDate = `${year}-${month}-${day}`;
         if (!fechaInput.value) { fechaInput.min = minDate; }
         fechaInput.addEventListener('change', function() {
             const selectedDate = new Date(this.value + 'T00:00:00'); 
             const today = new Date();
             today.setHours(0, 0, 0, 0);
             if (selectedDate < today) {
                 this.setCustomValidity('La fecha no puede ser en el pasado.');
                 this.style.borderColor = '#ff6b6b';
             } else {
                 this.setCustomValidity('');
                 this.style.borderColor = '#4ecdc4';
             }
         });
    }

    // Horarios input validation
    const horariosInputValidation = document.querySelector('input[name="horarios"]');
    if (horariosInputValidation) {
        horariosInputValidation.addEventListener('input', function() {
            const regex = /^\s*([0-2]\d:[0-5]\d)(\s*,\s*[0-2]\d:[0-5]\d)*\s*$/;
            if (!this.value.match(regex) && this.value.length > 0) {
                this.setCustomValidity('Formato incorrecto. Debe ser HH:MM, ej: 18:00, 20:15');
                this.style.borderColor = '#ff6b6b';
            } else {
                this.setCustomValidity('');
                this.style.borderColor = '#4ecdc4';
            }
        });
    }

    // Precio validation
    const precioInput = document.querySelector('input[name="precio_base"]');
    if (precioInput) {
        precioInput.addEventListener('input', function() {
            const value = parseFloat(this.value);
            if (value <= 0) {
                this.setCustomValidity('El precio debe ser mayor a 0');
                this.style.borderColor = '#ff6b6b';
            } else if (value > 99999.99) {
                this.setCustomValidity('El precio es demasiado alto');
                this.style.borderColor = '#ff6b6b';
            } else {
                this.setCustomValidity('');
                this.style.borderColor = '#4ecdc4';
            }
        });
    }

    if (form) {
        form.addEventListener('submit', function(e) {
            console.debug('funcion_form.js: submit handler invoked');
        const fechaHora = document.querySelector('input[name="fecha_hora"]');
        if (fechaHora && fechaHora.value) {
            const selectedDateTime = new Date(fechaHora.value);
            const nowDateTime = new Date();
            if (selectedDateTime < nowDateTime) {
                e.preventDefault();
                alert('❌ La fecha y hora no pueden ser en el pasado.');
                fechaHora.focus();
                return false;
            }
        }
        const fecha = document.querySelector('input[name="fecha"]');
        if (fecha && fecha.value) {
            const selectedDate = new Date(fecha.value + 'T00:00:00');
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            if (selectedDate < today) {
                e.preventDefault();
                alert('❌ La fecha no puede ser en el pasado.');
                fecha.focus();
                return false;
            }
        }
        const precio = document.querySelector('input[name="precio_base"]');
        if (precio && precio.value) {
            const precioValue = parseFloat(precio.value);
            if (precioValue <= 0) {
                e.preventDefault();
                alert('❌ El precio debe ser mayor a 0.');
                precio.focus();
                return false;
            }
        }
        });
    } else {
        // If the specific form isn't present, do not attach submit handler to avoid
        // interfering with other forms on the page. Other behaviors (horarios loader, radios formatting)
        // continue to work even if this form is not found.
        console.warn('funcion_form.js: #funcion-form no encontrado — no se adjuntó el manejador de submit.');
    }

    // Horarios AJAX loader
    const peliculaSelect = document.querySelector('select[name="pelicula"]');
    const salaSelect = document.querySelector('select[name="sala"]');
    const fechaInputAuto = document.querySelector('input[name="fecha"]');
    const horariosContainer = document.getElementById('horarios-disponibles');
    const horariosInput = document.querySelector('input[name="horarios"]');
    const esEdicion = ES_EDICION;
    const funcionActual = FUNCION_ACTUAL;
    let horariosSeleccionados = [];

    function cargarHorariosDisponibles() {
        if (!peliculaSelect || !salaSelect || !fechaInputAuto) return;
        const peliculaId = peliculaSelect.value;
        const salaId = salaSelect.value;
        const fecha = fechaInputAuto.value;
        if (!peliculaId || !salaId || !fecha) {
            horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem;">👆 Selecciona película, sala y fecha para ver los horarios disponibles</p>';
            return;
        }
        horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem;">⏳ Calculando horarios disponibles...</p>';
        let url = CALCULAR_HORARIOS_URL ? `${CALCULAR_HORARIOS_URL}?pelicula_id=${peliculaId}&sala_id=${salaId}&fecha=${fecha}` : null;
        if (!url) {
            console.error('CALCULAR_HORARIOS_URL no está definido');
            horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem; color: #ff6b6b;">❌ Error de configuración.</p>';
            return;
        }
        if (esEdicion && funcionActual && funcionActual.id) {
            url += `&funcion_id=${funcionActual.id}`;
        }
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    horariosContainer.innerHTML = `<p class="text-secondary" style="text-align: center; font-size: 0.9rem; color: #ff6b6b;">❌ ${data.error}</p>`;
                    return;
                }
                if (data.horarios.length === 0) {
                    horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem;">😔 No hay horarios disponibles para este día. Intenta con otra fecha.</p>';
                    return;
                }
                let mensajeTexto = esEdicion ? '🕐 Selecciona el nuevo horario para esta función (' + data.mensaje + '):' : '✨ Selecciona uno o varios horarios (' + data.mensaje + '):';
                let html = '<p class="text-secondary" style="font-size: 0.85rem; margin-bottom: var(--space-sm);">' + mensajeTexto + '</p>';
                html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: var(--space-sm);">';
                let horarioActual = null;
                if (esEdicion && funcionActual) { horarioActual = funcionActual.hora; }
                data.horarios.forEach(hora => {
                    let esHorarioActual = (esEdicion && hora === horarioActual);
                    let estiloInicial = esHorarioActual 
                        ? 'padding: 0.7rem 0.5rem; border: 2px solid var(--primary); background: var(--primary); color: #fff; border-radius: 8px; cursor: pointer; transition: all 0.2s ease; font-weight: 600; font-size: 1rem; text-align: center;'
                        : 'padding: 0.7rem 0.5rem; border: 2px solid rgba(186, 104, 200, 0.5); background: rgba(26, 11, 46, 0.6); color: var(--text-light); border-radius: 8px; cursor: pointer; transition: all 0.2s ease; font-weight: 600; font-size: 1rem; text-align: center;';
                    html += `<button type="button" class="horario-btn" data-hora="${hora}" style="${estiloInicial}">${hora}</button>`;
                    if (esHorarioActual) { horariosSeleccionados = [hora]; }
                });
                html += '</div>';
                horariosContainer.innerHTML = html;
                if (horariosInput && horariosSeleccionados.length > 0) {
                    horariosInput.value = horariosSeleccionados.join(', ');
                }
                function calcularSolapamiento(hora1, hora2, duracionTotal) {
                    const [h1, m1] = hora1.split(':').map(Number);
                    const [h2, m2] = hora2.split(':').map(Number);
                    const minutos1 = h1 * 60 + m1;
                    const minutos2 = h2 * 60 + m2;
                    const fin1 = minutos1 + duracionTotal;
                    const fin2 = minutos2 + duracionTotal;
                    return (minutos1 < fin2 && minutos2 < fin1);
                }
                function actualizarVisibilidadBotones() {
                    document.querySelectorAll('.horario-btn').forEach(btn => {
                        const hora = btn.getAttribute('data-hora');
                        let debeOcultar = false;
                        if (!horariosSeleccionados.includes(hora)) {
                            for (let horaSeleccionada of horariosSeleccionados) {
                                if (calcularSolapamiento(hora, horaSeleccionada, data.duracion_total)) {
                                    debeOcultar = true; break;
                                }
                            }
                        }
                        if (debeOcultar) { btn.style.display = 'none'; } else { btn.style.display = 'block'; }
                    });
                }
                document.querySelectorAll('.horario-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const hora = this.getAttribute('data-hora');
                        if (horariosSeleccionados.includes(hora)) {
                            horariosSeleccionados = horariosSeleccionados.filter(h => h !== hora);
                            this.style.background = 'rgba(26, 11, 46, 0.6)';
                            this.style.borderColor = 'rgba(186, 104, 200, 0.5)';
                            this.style.color = 'var(--text-light)';
                        } else {
                            horariosSeleccionados.push(hora);
                            this.style.background = 'var(--primary)';
                            this.style.borderColor = 'var(--primary)';
                            this.style.color = '#fff';
                        }
                        if (!esEdicion) { actualizarVisibilidadBotones(); }
                        if (horariosInput) { horariosInput.value = horariosSeleccionados.join(', '); }
                    });
                    btn.addEventListener('mouseenter', function() {
                        if (!horariosSeleccionados.includes(this.getAttribute('data-hora'))) { this.style.borderColor = 'var(--primary)'; }
                    });
                    btn.addEventListener('mouseleave', function() {
                        if (!horariosSeleccionados.includes(this.getAttribute('data-hora'))) { this.style.borderColor = 'rgba(186, 104, 200, 0.5)'; }
                    });
                });
            })
            .catch(error => {
                console.error('Error:', error);
                horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem; color: #ff6b6b;">❌ Error al cargar horarios. Intenta de nuevo.</p>';
            });
    }
    if (peliculaSelect) peliculaSelect.addEventListener('change', cargarHorariosDisponibles);
    if (salaSelect) salaSelect.addEventListener('change', cargarHorariosDisponibles);
    if (fechaInputAuto) fechaInputAuto.addEventListener('change', cargarHorariosDisponibles);
    if (esEdicion && peliculaSelect && salaSelect && fechaInputAuto && funcionActual) {
        if (peliculaSelect.value && salaSelect.value && fechaInputAuto.value) {
            setTimeout(function() { cargarHorariosDisponibles(); }, 100);
        }
    }
    // radios formatting logic
    const allFormatoRadios = document.querySelectorAll('input[type="radio"][name^="formatos_"], input[type="radio"][name="idioma"]');
    allFormatoRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const groupName = this.name;
            const groupRadios = document.querySelectorAll(`input[name="${groupName}"]`);
            groupRadios.forEach(r => {
                const label = r.parentElement; const span = label.querySelector('span');
                if (r.checked) { label.style.background = 'var(--primary)'; label.style.borderColor = 'var(--primary)'; if (span) span.style.color = '#FFFFFF'; }
                else { label.style.background = 'transparent'; label.style.borderColor = 'rgba(139, 95, 191, 0.4)'; if (span) span.style.color = 'var(--text-light)'; }
            });
        });
        if (radio.checked) { const label = radio.parentElement; const span = label.querySelector('span'); label.style.background = 'var(--primary)'; label.style.borderColor = 'var(--primary)'; if (span) span.style.color = '#FFFFFF'; }
    });
});
