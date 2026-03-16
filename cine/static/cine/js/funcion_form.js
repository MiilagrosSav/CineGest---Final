// Combobox funcionalidad para el campo pelicula
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('pelicula-search');
    const dropdown = document.getElementById('pelicula-dropdown');
    const realSelect = document.querySelector('select[name="pelicula"]');
    const form = searchInput ? searchInput.closest('form') : null;

    if (!searchInput || !dropdown || !realSelect || !form) return;

    const peliculas = Array.from(realSelect.options)
        .filter(opt => opt.value)
        .map(opt => ({
            value: opt.value,
            text: opt.text
        }));

    let selectedIndex = -1;
    let lastValidValue = '';

    function renderOptions(filteredPeliculas) {
        if (filteredPeliculas.length === 0) {
            dropdown.innerHTML = '<div class="combobox-empty">No se encontraron peliculas</div>';
            return;
        }

        dropdown.innerHTML = filteredPeliculas.map((pel, idx) =>
            `<div class="combobox-option" data-value="${pel.value}" data-index="${idx}">${pel.text}</div>`
        ).join('');

        dropdown.querySelectorAll('.combobox-option').forEach(opt => {
            opt.addEventListener('click', function() {
                selectOption(this.dataset.value, this.textContent);
            });
        });
    }

    function selectOption(value, text) {
        realSelect.value = value;
        searchInput.value = text;
        lastValidValue = text;
        dropdown.style.display = 'none';
        selectedIndex = -1;
        searchInput.classList.remove('invalid-input');
        realSelect.dispatchEvent(new Event('change'));
    }

    function validateInput() {
        const inputValue = searchInput.value.trim();

        if (!inputValue) {
            realSelect.value = '';
            searchInput.classList.remove('invalid-input');
            return false;
        }

        const match = peliculas.find(pel => pel.text === inputValue);

        if (match) {
            realSelect.value = match.value;
            lastValidValue = inputValue;
            searchInput.classList.remove('invalid-input');
            return true;
        }

        realSelect.value = '';
        searchInput.classList.add('invalid-input');
        return false;
    }

    function filterOptions(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        if (!term) return peliculas;

        return peliculas.filter(pel => pel.text.toLowerCase().includes(term));
    }

    searchInput.addEventListener('focus', function() {
        const searchTerm = this.value.trim();

        if (searchTerm.length < 3) {
            dropdown.innerHTML = '<div class="combobox-empty">Escribe al menos 3 letras para buscar...</div>';
            dropdown.style.display = 'block';
            return;
        }

        const filtered = filterOptions(searchTerm);
        renderOptions(filtered);
        dropdown.style.display = 'block';
    });

    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.trim();

        if (searchTerm.length < 3 && searchTerm.length > 0) {
            dropdown.innerHTML = '<div class="combobox-empty">Escribe al menos 3 letras para buscar...</div>';
            dropdown.style.display = 'block';
            return;
        }

        const filtered = filterOptions(searchTerm);
        renderOptions(filtered);
        dropdown.style.display = 'block';
        selectedIndex = -1;
        validateInput();
    });

    searchInput.addEventListener('blur', function() {
        setTimeout(() => {
            if (!dropdown.contains(document.activeElement)) {
                const isValid = validateInput();

                if (!isValid && searchInput.value.trim()) {
                    if (lastValidValue) {
                        searchInput.value = lastValidValue;
                        const match = peliculas.find(pel => pel.text === lastValidValue);
                        if (match) {
                            realSelect.value = match.value;
                        }
                    } else {
                        searchInput.value = '';
                        realSelect.value = '';
                    }
                    searchInput.classList.remove('invalid-input');
                }
            }
        }, 200);
    });

    searchInput.addEventListener('keydown', function(e) {
        const options = dropdown.querySelectorAll('.combobox-option');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (dropdown.style.display === 'none') {
                dropdown.style.display = 'block';
                const filtered = filterOptions(this.value);
                renderOptions(filtered);
            }
            selectedIndex = Math.min(selectedIndex + 1, options.length - 1);
            updateSelectedOption(options);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, 0);
            updateSelectedOption(options);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex >= 0 && options[selectedIndex]) {
                const opt = options[selectedIndex];
                selectOption(opt.dataset.value, opt.textContent);
            } else {
                validateInput();
            }
        } else if (e.key === 'Escape') {
            dropdown.style.display = 'none';
            selectedIndex = -1;
        }
    });

    function updateSelectedOption(options) {
        options.forEach((opt, idx) => {
            opt.classList.toggle('active', idx === selectedIndex);
        });

        if (options[selectedIndex]) {
            options[selectedIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.style.display = 'none';
            selectedIndex = -1;
        }
    });

    form.addEventListener('submit', function(e) {
        const isValid = validateInput();

        if (!realSelect.value || !isValid) {
            e.preventDefault();
            searchInput.classList.add('invalid-input');
            searchInput.focus();
            alert('Debe seleccionar una pelicula valida de la lista.');
            return false;
        }
        return true;
    });

    if (realSelect.value) {
        const selectedOption = Array.from(realSelect.options).find(opt => opt.value === realSelect.value);
        if (selectedOption) {
            searchInput.value = selectedOption.text;
            lastValidValue = selectedOption.text;
        }
    }

    renderOptions(peliculas);
});

// ==========================================
// LOGICA PARA CARGAR HORARIOS DISPONIBLES
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    const peliculaSelect = document.querySelector('select[name="pelicula"]');
    const salaSelect = document.querySelector('select[name="sala"]');
    const fechaInicioInput = document.querySelector('input[name="fecha_inicio"]');
    const fechaFinInput = document.querySelector('input[name="fecha_fin"]');
    const diasSemanaInputs = document.querySelectorAll('input[name="dias_semana"]');
    const formatosExperienciaInputs = document.querySelectorAll('input[name="formatos_experiencia"]');
    const diasSemanaSection = document.getElementById('dias-semana-section');
    const seleccionarTodosDiasBtn = document.getElementById('btn-seleccionar-todos-dias');
    const horariosContainer = document.getElementById('horarios-disponibles');
    const horariosInputHidden = document.querySelector('input[name="horarios"]');
    const submitButton = document.querySelector('button[type="submit"]');

    if (!peliculaSelect || !salaSelect || !fechaInicioInput || !horariosContainer) {
        return;
    }

    const djangoDataScript = document.getElementById('django-data');
    let esEdicion = false;
    let funcionActual = null;

    if (djangoDataScript) {
        try {
            const data = JSON.parse(djangoDataScript.textContent);
            esEdicion = data.esEdicion;
            funcionActual = data.funcionActual;
        } catch (error) {
            console.error('Error al parsear datos de Django:', error);
        }
    }

    let horariosSeleccionados = [];
    let duracionTotal = 0;
    let sinDisponibilidad = false;
    let ultimoPeliculaId = peliculaSelect ? peliculaSelect.value : '';

    function getDiasSeleccionados() {
        return Array.from(diasSemanaInputs)
            .filter(input => input.checked)
            .map(input => input.value);
    }

    function getFormatoExperienciaId() {
        const seleccionado = document.querySelector('input[name="formatos_experiencia"]:checked');
        return seleccionado ? seleccionado.value : '';
    }

    function esModoRango() {
        return !esEdicion && Boolean(fechaFinInput && fechaFinInput.value);
    }

    function actualizarVisibilidadDiasSemana() {
        const mostrarDias = esModoRango();
        if (diasSemanaSection) {
            diasSemanaSection.style.display = mostrarDias ? 'block' : 'none';
        }

        if (!mostrarDias) {
            diasSemanaInputs.forEach(input => {
                input.checked = false;
            });
            habilitarTodosDiasSemana();
        }
    }

    function obtenerLabelDia(input) {
        return document.querySelector(`label[for="${input.id}"]`);
    }

    function habilitarTodosDiasSemana() {
        diasSemanaInputs.forEach(input => {
            input.disabled = false;
            const label = obtenerLabelDia(input);
            if (label) {
                label.classList.remove('dia-semana-btn-disabled');
                label.title = '';
            }
        });
    }

    function aplicarEstadoDias(diasEstado) {
        const estadoMap = new Map();
        (diasEstado || []).forEach(item => {
            estadoMap.set(String(item.dia), item);
        });

        diasSemanaInputs.forEach(input => {
            const estado = estadoMap.get(input.value);
            const disabled = Boolean(estado && estado.disabled);
            input.disabled = disabled;
            if (disabled) {
                input.checked = false;
            }

            const label = obtenerLabelDia(input);
            if (label) {
                label.classList.toggle('dia-semana-btn-disabled', disabled);
                label.title = estado && estado.motivo ? estado.motivo : '';
            }
        });
    }

    async function prechequearDiasSemana() {
        if (esEdicion || !esModoRango()) {
            habilitarTodosDiasSemana();
            return true;
        }

        const peliculaId = peliculaSelect.value;
        const salaId = salaSelect.value;
        const fechaInicio = fechaInicioInput.value;
        const fechaFin = fechaFinInput ? fechaFinInput.value : fechaInicio;
        const formatoExperienciaId = getFormatoExperienciaId();

        if (!peliculaId || !salaId || !fechaInicio || !fechaFin) {
            habilitarTodosDiasSemana();
            return true;
        }

        if (!window.PRECHECK_DIAS_URL) {
            return true;
        }

        try {
            const url = new URL(window.PRECHECK_DIAS_URL, window.location.origin);
            url.searchParams.append('pelicula_id', peliculaId);
            url.searchParams.append('sala_id', salaId);
            url.searchParams.append('fecha_inicio', fechaInicio);
            url.searchParams.append('fecha_fin', fechaFin);
            if (formatoExperienciaId) {
                url.searchParams.append('formato_experiencia_id', formatoExperienciaId);
            }

            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok || data.error) {
                console.error('Error en precheck de dias:', data.error || response.statusText);
                habilitarTodosDiasSemana();
                return true;
            }

            aplicarEstadoDias(data.dias);
            const diasHabilitados = Array.from(diasSemanaInputs).filter(input => !input.disabled).length;
            return diasHabilitados > 0;
        } catch (error) {
            console.error('Error en precheck de dias:', error);
            habilitarTodosDiasSemana();
            return true;
        }
    }

    function actualizarSubmit(disabled, title = '') {
        if (!submitButton) return;

        submitButton.disabled = disabled;
        submitButton.style.opacity = disabled ? '0.5' : '1';
        submitButton.style.cursor = disabled ? 'not-allowed' : 'pointer';
        submitButton.title = title;
    }

    function limpiarSeleccionHorarios() {
        horariosSeleccionados = [];
        if (horariosInputHidden) {
            horariosInputHidden.value = '';
        }
    }

    function mostrarMensajeHorarios(texto, isError = false) {
        const color = isError ? '#ff6b6b' : 'inherit';
        horariosContainer.innerHTML = `<p class="text-secondary" style="text-align: center; font-size: 0.9rem; color: ${color};">${texto}</p>`;
    }

    function calcularSolapamiento(hora1, hora2, duracion) {
        const [h1, m1] = hora1.split(':').map(Number);
        const [h2, m2] = hora2.split(':').map(Number);
        const inicio1 = h1 * 60 + m1;
        const inicio2 = h2 * 60 + m2;
        const fin1 = inicio1 + duracion;
        const fin2 = inicio2 + duracion;
        return inicio1 < fin2 && inicio2 < fin1;
    }

    function actualizarVisibilidadBotones() {
        document.querySelectorAll('.horario-btn').forEach(btn => {
            const hora = btn.getAttribute('data-hora');
            let ocultar = false;

            for (const seleccionado of horariosSeleccionados) {
                if (hora !== seleccionado && calcularSolapamiento(hora, seleccionado, duracionTotal)) {
                    ocultar = true;
                    break;
                }
            }

            btn.style.display = ocultar ? 'none' : 'block';
        });
    }

    function marcarBotonSeleccion(btn, seleccionado) {
        if (seleccionado) {
            btn.style.background = 'var(--primary)';
            btn.style.borderColor = 'var(--primary)';
            btn.style.color = '#fff';
            return;
        }

        btn.style.background = 'rgba(26, 11, 46, 0.6)';
        btn.style.borderColor = 'rgba(186, 104, 200, 0.5)';
        btn.style.color = 'var(--text-light)';
    }

    function renderHorarios(data, peliculaCambiada = false) {
        duracionTotal = data.duracion_total || 0;
        const horariosDisponibles = data.horarios || [];
        const horariosSolapados = new Set(data.horarios_solapados || []);

        const seleccionadosPrevios = horariosSeleccionados.slice();
        horariosSeleccionados = horariosSeleccionados.filter(hora => horariosDisponibles.includes(hora));
        const removidos = seleccionadosPrevios.filter(hora => !horariosSeleccionados.includes(hora));
        if (peliculaCambiada && removidos.length > 0) {
            horariosSeleccionados = [];
            if (horariosInputHidden) {
                horariosInputHidden.value = '';
            }
            alert('El horario seleccionado no es compatible con esta película para esta sala.');
        }

        if (esEdicion && funcionActual && horariosSeleccionados.length === 0) {
            if (horariosDisponibles.includes(funcionActual.hora)) {
                horariosSeleccionados = [funcionActual.hora];
            }
        }

        const mensajeTexto = esEdicion
            ? `Selecciona el nuevo horario (${data.mensaje || ''}):`
            : `Selecciona uno o mas horarios (${data.mensaje || ''}):`;

        let html = `<p class="text-secondary" style="font-size: 0.85rem; margin-bottom: var(--space-sm);">${mensajeTexto}</p>`;
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: var(--space-sm);">';

        horariosDisponibles.forEach(hora => {
            const seleccionado = horariosSeleccionados.includes(hora);
            const estilo = seleccionado
                ? 'padding: 0.7rem 0.5rem; border: 2px solid var(--primary); background: var(--primary); color: #fff; border-radius: 8px; cursor: pointer; transition: all 0.2s ease; font-weight: 600; font-size: 1rem; text-align: center;'
                : 'padding: 0.7rem 0.5rem; border: 2px solid rgba(186, 104, 200, 0.5); background: rgba(26, 11, 46, 0.6); color: var(--text-light); border-radius: 8px; cursor: pointer; transition: all 0.2s ease; font-weight: 600; font-size: 1rem; text-align: center;';

            const badgeSolapado = horariosSolapados.has(hora)
                ? '<span style="display:block; font-size:0.55rem; font-weight:500; opacity:0.85; margin-top:0.2rem;">Solapamiento permitido</span>'
                : '';

            html += `<button type="button" class="horario-btn" data-hora="${hora}" style="${estilo}">${hora}${badgeSolapado}</button>`;
        });

        html += '</div>';
        horariosContainer.innerHTML = html;

        if (horariosInputHidden) {
            horariosInputHidden.value = horariosSeleccionados.join(', ');
        }

        document.querySelectorAll('.horario-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const hora = this.getAttribute('data-hora');
                const yaSeleccionado = horariosSeleccionados.includes(hora);

                if (yaSeleccionado) {
                    horariosSeleccionados = horariosSeleccionados.filter(h => h !== hora);
                } else {
                    horariosSeleccionados.push(hora);
                }

                marcarBotonSeleccion(this, !yaSeleccionado);

                if (horariosInputHidden) {
                    horariosInputHidden.value = horariosSeleccionados.join(', ');
                }

                actualizarVisibilidadBotones();
            });

            btn.addEventListener('mouseenter', function() {
                const hora = this.getAttribute('data-hora');
                if (!horariosSeleccionados.includes(hora)) {
                    this.style.background = 'rgba(139, 95, 191, 0.3)';
                    this.style.borderColor = 'var(--primary)';
                }
            });

            btn.addEventListener('mouseleave', function() {
                const hora = this.getAttribute('data-hora');
                if (!horariosSeleccionados.includes(hora)) {
                    marcarBotonSeleccion(this, false);
                }
            });
        });

        actualizarVisibilidadBotones();
    }

    async function cargarHorarios() {
        const peliculaId = peliculaSelect.value;
        const salaId = salaSelect.value;
        const fechaInicio = fechaInicioInput.value;
        const fechaFin = fechaFinInput ? fechaFinInput.value : fechaInicio;
        const formatoExperienciaId = getFormatoExperienciaId();
        const diasSeleccionados = getDiasSeleccionados();
        const diasHabilitados = Array.from(diasSemanaInputs).filter(input => !input.disabled).length;
        const modoRango = esModoRango();

        if (esEdicion) {
            if (!peliculaId || !salaId || !fechaInicio) {
                mostrarMensajeHorarios('Selecciona pelicula, sala y fecha para ver horarios disponibles');
                limpiarSeleccionHorarios();
                sinDisponibilidad = false;
                actualizarSubmit(false);
                return;
            }
        } else if (!modoRango) {
            if (!peliculaId || !salaId || !fechaInicio) {
                mostrarMensajeHorarios('Selecciona pelicula, sala y fecha para ver horarios disponibles');
                limpiarSeleccionHorarios();
                sinDisponibilidad = false;
                actualizarSubmit(false);
                return;
            }
        } else if (diasHabilitados === 0 && peliculaId && salaId && fechaInicio && fechaFin) {
            mostrarMensajeHorarios('No hay dias disponibles en el rango seleccionado (dias cerrados u ocupados).', true);
            limpiarSeleccionHorarios();
            sinDisponibilidad = true;
            actualizarSubmit(true, 'No hay dias habilitados en el rango');
            return;
        } else if (!peliculaId || !salaId || !fechaInicio || !fechaFin || diasSeleccionados.length === 0) {
            mostrarMensajeHorarios('Selecciona pelicula, sala, rango de fechas y al menos un dia para ver horarios');
            limpiarSeleccionHorarios();
            sinDisponibilidad = false;
            actualizarSubmit(false);
            return;
        }

        mostrarMensajeHorarios('Calculando horarios disponibles...');

        try {
            const url = new URL(window.CALCULAR_HORARIOS_URL, window.location.origin);
            url.searchParams.append('pelicula_id', peliculaId);
            url.searchParams.append('sala_id', salaId);

            if (esEdicion) {
                url.searchParams.append('fecha', fechaInicio);
                if (funcionActual) {
                    url.searchParams.append('funcion_id', funcionActual.id);
                }
            } else if (!modoRango) {
                url.searchParams.append('fecha', fechaInicio);
            } else {
                url.searchParams.append('fecha_inicio', fechaInicio);
                url.searchParams.append('fecha_fin', fechaFin);
                diasSeleccionados.forEach(dia => url.searchParams.append('dias_semana', dia));
            }

            if (formatoExperienciaId) {
                url.searchParams.append('formato_experiencia_id', formatoExperienciaId);
            }

            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok || data.error) {
                mostrarMensajeHorarios(`Error: ${data.error || 'No se pudieron calcular horarios'}`, true);
                limpiarSeleccionHorarios();
                sinDisponibilidad = true;
                actualizarSubmit(true, 'No hay horarios disponibles con la configuracion actual');
                return;
            }

            if (!data.horarios || data.horarios.length === 0 || data.cerrado) {
                mostrarMensajeHorarios(data.mensaje || 'No hay horarios disponibles', true);
                limpiarSeleccionHorarios();
                sinDisponibilidad = true;
                actualizarSubmit(true, 'No hay horarios disponibles con la configuracion actual');
                return;
            }

            sinDisponibilidad = false;
            actualizarSubmit(false);
            const peliculaCambiada = Boolean(ultimoPeliculaId) && peliculaId !== ultimoPeliculaId;
            renderHorarios(data, peliculaCambiada);
            ultimoPeliculaId = peliculaId;
        } catch (error) {
            console.error('Error al cargar horarios:', error);
            mostrarMensajeHorarios('Error al cargar horarios. Intenta de nuevo.', true);
            limpiarSeleccionHorarios();
            sinDisponibilidad = true;
            actualizarSubmit(true, 'No hay horarios disponibles con la configuracion actual');
        }
    }

    async function manejarCambioRango() {
        actualizarVisibilidadDiasSemana();
        if (esModoRango()) {
            await prechequearDiasSemana();
        } else {
            habilitarTodosDiasSemana();
        }
        await cargarHorarios();
    }

    if (peliculaSelect) peliculaSelect.addEventListener('change', manejarCambioRango);
    if (salaSelect) salaSelect.addEventListener('change', manejarCambioRango);
    if (fechaInicioInput) fechaInicioInput.addEventListener('change', manejarCambioRango);
    if (fechaFinInput) fechaFinInput.addEventListener('change', manejarCambioRango);

    diasSemanaInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (esModoRango()) {
                cargarHorarios();
            }
        });
    });

    formatosExperienciaInputs.forEach(input => {
        input.addEventListener('change', function() {
            manejarCambioRango();
        });
    });

    if (seleccionarTodosDiasBtn) {
        seleccionarTodosDiasBtn.addEventListener('click', function() {
            if (!esModoRango()) {
                return;
            }

            let algunDiaSeleccionable = false;
            diasSemanaInputs.forEach(input => {
                if (!input.disabled) {
                    input.checked = true;
                    algunDiaSeleccionable = true;
                }
            });

            if (algunDiaSeleccionable) {
                cargarHorarios();
            }
        });
    }

    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!esEdicion && esModoRango() && getDiasSeleccionados().length === 0) {
                e.preventDefault();
                alert('Debes seleccionar al menos un dia de la semana.');
                return false;
            }

            if (sinDisponibilidad) {
                e.preventDefault();
                alert('No hay horarios disponibles para la configuracion elegida.');
                return false;
            }

            if (horariosInputHidden && (!horariosInputHidden.value || horariosInputHidden.value.trim() === '')) {
                e.preventDefault();
                alert('Debes seleccionar al menos un horario.');
                return false;
            }

            return true;
        });
    }

    if (esEdicion && peliculaSelect.value && salaSelect.value && fechaInicioInput.value) {
        setTimeout(cargarHorarios, 100);
    } else {
        actualizarSubmit(false);
        actualizarVisibilidadDiasSemana();
        if (!esEdicion && peliculaSelect.value && salaSelect.value && fechaInicioInput.value) {
            manejarCambioRango();
        } else if (!esEdicion) {
            mostrarMensajeHorarios('Selecciona pelicula, sala y fecha de inicio. Fecha fin opcional para modo rango.');
        }
    }
});
