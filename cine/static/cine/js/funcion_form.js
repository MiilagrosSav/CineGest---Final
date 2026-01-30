// Combobox funcionalidad para el campo película
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('pelicula-search');
    const dropdown = document.getElementById('pelicula-dropdown');
    const realSelect = document.querySelector('select[name="pelicula"]');
    const form = searchInput ? searchInput.closest('form') : null;
    
    if (!searchInput || !dropdown || !realSelect || !form) return;
    
    // Extraer todas las opciones del select original
    const peliculas = Array.from(realSelect.options)
        .filter(opt => opt.value)
        .map(opt => ({
            value: opt.value,
            text: opt.text
        }));
    
    let selectedIndex = -1;
    let lastValidValue = '';
    
    // Renderizar opciones en el dropdown
    function renderOptions(filteredPeliculas) {
        if (filteredPeliculas.length === 0) {
            dropdown.innerHTML = '<div class="combobox-empty">No se encontraron películas</div>';
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
    
    // Seleccionar una opción
    function selectOption(value, text) {
        realSelect.value = value;
        searchInput.value = text;
        lastValidValue = text;
        dropdown.style.display = 'none';
        selectedIndex = -1;
        searchInput.classList.remove('invalid-input');
        
        realSelect.dispatchEvent(new Event('change'));
    }
    
    // Validar que el texto ingresado corresponde a una película existente
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
        } else {
            realSelect.value = '';
            searchInput.classList.add('invalid-input');
            return false;
        }
    }
    
    // Filtrar opciones según lo que se escribe
    function filterOptions(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        if (!term) return peliculas;
        
        return peliculas.filter(pel => 
            pel.text.toLowerCase().includes(term)
        );
    }
    
    searchInput.addEventListener('focus', function() {
        const filtered = filterOptions(this.value);
        renderOptions(filtered);
        dropdown.style.display = 'block';
    });
    
    searchInput.addEventListener('input', function() {
        const filtered = filterOptions(this.value);
        renderOptions(filtered);
        dropdown.style.display = 'block';
        selectedIndex = -1;
        validateInput();
    });
    
    searchInput.addEventListener('blur', function(e) {
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
            alert('⚠️ Debe seleccionar una película válida de la lista.');
            return false;
        }
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
// LÓGICA PARA CARGAR HORARIOS DISPONIBLES
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    const peliculaSelect = document.querySelector('select[name="pelicula"]');
    const salaSelect = document.querySelector('select[name="sala"]');
    const fechaInput = document.querySelector('input[name="fecha"]');
    const horariosContainer = document.getElementById('horarios-disponibles');
    const horariosInputHidden = document.querySelector('input[name="horarios"]');
    
    if (!peliculaSelect || !salaSelect || !fechaInput || !horariosContainer) {
        return;
    }

    // Obtener datos de Django si estamos en edición
    const djangoDataScript = document.getElementById('django-data');
    let esEdicion = false;
    let funcionActual = null;

    if (djangoDataScript) {
        try {
            const data = JSON.parse(djangoDataScript.textContent);
            esEdicion = data.esEdicion;
            funcionActual = data.funcionActual;
        } catch (e) {
            console.error('Error al parsear datos de Django:', e);
        }
    }

    let horariosSeleccionados = [];
    let duracionTotal = 0;
    let todosLosHorarios = [];

    // Función para cargar horarios disponibles
    async function cargarHorarios() {
        const peliculaId = peliculaSelect.value;
        const salaId = salaSelect.value;
        const fecha = fechaInput.value;

        if (!peliculaId || !salaId || !fecha) {
            horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem;">👆 Selecciona película, sala y fecha para ver los horarios disponibles</p>';
            return;
        }

        horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem;">⏳ Calculando horarios disponibles...</p>';

        try {
            const url = new URL(window.CALCULAR_HORARIOS_URL, window.location.origin);
            url.searchParams.append('pelicula_id', peliculaId);
            url.searchParams.append('sala_id', salaId);
            url.searchParams.append('fecha', fecha);

            if (esEdicion && funcionActual) {
                url.searchParams.append('funcion_id', funcionActual.id);
            }

            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.error) {
                horariosContainer.innerHTML = `<p class="text-secondary" style="text-align: center; font-size: 0.9rem; color: #ff6b6b;">❌ ${data.error}</p>`;
                return;
            }

            if (!data.horarios || data.horarios.length === 0) {
                horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem;">😔 No hay horarios disponibles para este día. Intenta con otra fecha.</p>';
                return;
            }

            duracionTotal = data.duracion_total || 0;
            todosLosHorarios = data.horarios;

            let mensajeTexto = esEdicion 
                ? '🕐 Selecciona el nuevo horario para esta función (' + data.mensaje + '):'
                : '✨ Selecciona uno o varios horarios (' + data.mensaje + '):';
            
            let html = '<p class="text-secondary" style="font-size: 0.85rem; margin-bottom: var(--space-sm);">' + mensajeTexto + '</p>';
            html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: var(--space-sm);">';
            
            let horarioActual = null;
            if (esEdicion && funcionActual) {
                horarioActual = funcionActual.hora;
            }

            data.horarios.forEach(hora => {
                let esHorarioActual = (esEdicion && hora === horarioActual);
                let estiloInicial = esHorarioActual 
                    ? 'padding: 0.7rem 0.5rem; border: 2px solid var(--primary); background: var(--primary); color: #fff; border-radius: 8px; cursor: pointer; transition: all 0.2s ease; font-weight: 600; font-size: 1rem; text-align: center;'
                    : 'padding: 0.7rem 0.5rem; border: 2px solid rgba(186, 104, 200, 0.5); background: rgba(26, 11, 46, 0.6); color: var(--text-light); border-radius: 8px; cursor: pointer; transition: all 0.2s ease; font-weight: 600; font-size: 1rem; text-align: center;';
                html += `<button type="button" class="horario-btn" data-hora="${hora}" style="${estiloInicial}">${hora}</button>`;
                if (esHorarioActual) {
                    horariosSeleccionados = [hora];
                }
            });
            html += '</div>';
            horariosContainer.innerHTML = html;

            if (horariosInputHidden && horariosSeleccionados.length > 0) {
                horariosInputHidden.value = horariosSeleccionados.join(', ');
            }

            // Función para calcular solapamiento entre dos horarios
            function calcularSolapamiento(hora1, hora2, duracionTotal) {
                const [h1, m1] = hora1.split(':').map(Number);
                const [h2, m2] = hora2.split(':').map(Number);
                const minutos1 = h1 * 60 + m1;
                const minutos2 = h2 * 60 + m2;
                const fin1 = minutos1 + duracionTotal;
                const fin2 = minutos2 + duracionTotal;
                return (minutos1 < fin2 && minutos2 < fin1);
            }

            // Función para actualizar visibilidad de botones según horarios seleccionados
            function actualizarVisibilidadBotones() {
                document.querySelectorAll('.horario-btn').forEach(btn => {
                    const hora = btn.getAttribute('data-hora');
                    let debeOcultar = false;

                    // Verificar si se solapa con algún horario seleccionado
                    for (const horarioSeleccionado of horariosSeleccionados) {
                        if (hora !== horarioSeleccionado && calcularSolapamiento(hora, horarioSeleccionado, duracionTotal)) {
                            debeOcultar = true;
                            break;
                        }
                    }

                    if (debeOcultar) {
                        btn.style.display = 'none';
                    } else {
                        btn.style.display = 'block';
                    }
                });
            }

            // Agregar event listeners a los botones de horario
            document.querySelectorAll('.horario-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const hora = this.getAttribute('data-hora');
                    const yaSeleccionado = horariosSeleccionados.includes(hora);

                    if (yaSeleccionado) {
                        // Deseleccionar
                        horariosSeleccionados = horariosSeleccionados.filter(h => h !== hora);
                        this.style.background = 'rgba(26, 11, 46, 0.6)';
                        this.style.borderColor = 'rgba(186, 104, 200, 0.5)';
                        this.style.color = 'var(--text-light)';
                    } else {
                        // Seleccionar
                        horariosSeleccionados.push(hora);
                        this.style.background = 'var(--primary)';
                        this.style.borderColor = 'var(--primary)';
                        this.style.color = '#fff';
                    }

                    // Actualizar el input hidden
                    if (horariosInputHidden) {
                        horariosInputHidden.value = horariosSeleccionados.join(', ');
                    }

                    // Actualizar visibilidad de otros botones
                    actualizarVisibilidadBotones();
                });

                // Efecto hover
                btn.addEventListener('mouseenter', function() {
                    if (!horariosSeleccionados.includes(this.getAttribute('data-hora'))) {
                        this.style.background = 'rgba(139, 95, 191, 0.3)';
                        this.style.borderColor = 'var(--primary)';
                    }
                });
                btn.addEventListener('mouseleave', function() {
                    if (!horariosSeleccionados.includes(this.getAttribute('data-hora'))) {
                        this.style.background = 'rgba(26, 11, 46, 0.6)';
                        this.style.borderColor = 'rgba(186, 104, 200, 0.5)';
                    }
                });
            });

        } catch (error) {
            console.error('Error:', error);
            horariosContainer.innerHTML = '<p class="text-secondary" style="text-align: center; font-size: 0.9rem; color: #ff6b6b;">❌ Error al cargar horarios. Intenta de nuevo.</p>';
        }
    }

    // Event listeners para recargar horarios cuando cambien los campos
    if (peliculaSelect) peliculaSelect.addEventListener('change', cargarHorarios);
    if (salaSelect) salaSelect.addEventListener('change', cargarHorarios);
    if (fechaInput) fechaInput.addEventListener('change', cargarHorarios);

    // Si estamos en edición, cargar horarios al inicio
    if (esEdicion && peliculaSelect && salaSelect && fechaInput && funcionActual) {
        if (peliculaSelect.value && salaSelect.value && fechaInput.value) {
            setTimeout(function() {
                cargarHorarios();
            }, 100);
        }
    }
});