/**
 * ✅ VÍNCULOS MANAGER - Gestión de vínculos con Combobox
 * 
 * Características:
 * - Combobox para búsqueda en películas y funciones (igual que funcion_form.js)
 * - Filtrado excluyente: películas/funciones ya seleccionadas no aparecen en otros
 * - Validación de duplicados con mensaje de error
 * - Nuevos vínculos aparecen completamente vacíos
 */

document.addEventListener('DOMContentLoaded', function() {
    const vinculosContainer = document.getElementById('vinculos-container');
    if (!vinculosContainer) {
        console.warn('❌ No se encontró #vinculos-container');
        return;
    }
    
    console.log('🚀 Inicializando Vínculos Manager con Combobox...');
    
    // ========== CONFIGURACIÓN GLOBAL ==========
    
    // Almacenar opciones originales (se cargan una sola vez)
    let peliculasOriginales = [];
    let funcionesOriginales = [];
    
    // Cargar opciones del primer select (si existe)
    const primeraFilaPelicula = document.querySelector('select[name$="-pelicula"]');
    const primeraFilaFuncion = document.querySelector('select[name$="-funcion"]');
    
    if (primeraFilaPelicula) {
        peliculasOriginales = Array.from(primeraFilaPelicula.options)
            .filter(opt => opt.value)
            .map(opt => ({ value: opt.value, text: opt.textContent.trim() }));
    }
    
    if (primeraFilaFuncion) {
        funcionesOriginales = Array.from(primeraFilaFuncion.options)
            .filter(opt => opt.value)
            .map(opt => ({ value: opt.value, text: opt.textContent.trim() }));
    }
    
    console.log(`📦 Cargadas ${peliculasOriginales.length} películas y ${funcionesOriginales.length} funciones`);
    
    // ========== FUNCIONES DE COMBOBOX ==========
    
    /**
     * Inicializa un combobox para un campo específico
     */
    function initCombobox(searchInput, dropdown, realSelect, tipo) {
        if (!searchInput || !dropdown || !realSelect) return;
        
        const vinculoIndex = searchInput.dataset.vinculoIndex;
        const opciones = tipo === 'pelicula' ? peliculasOriginales : funcionesOriginales;
        
        let selectedIndex = -1;
        let lastValidValue = '';
        
        // Obtener opciones disponibles (excluyendo las ya seleccionadas en otros vínculos)
        function getOpcionesDisponibles() {
            const seleccionadas = getSeleccionadas(tipo);
            const currentValue = realSelect.value;
            
            return opciones.filter(opt => 
                opt.value === currentValue || !seleccionadas.has(opt.value)
            );
        }
        
        // Renderizar opciones en dropdown
        function renderOptions(filteredOpciones) {
            if (filteredOpciones.length === 0) {
                dropdown.innerHTML = `<div class="combobox-empty">No hay ${tipo === 'pelicula' ? 'películas' : 'funciones'} disponibles</div>`;
                return;
            }
            
            dropdown.innerHTML = filteredOpciones.map((opt, idx) => 
                `<div class="combobox-option" data-value="${opt.value}" data-index="${idx}">${opt.text}</div>`
            ).join('');
            
            dropdown.querySelectorAll('.combobox-option').forEach(opt => {
                opt.addEventListener('click', function() {
                    selectOption(this.dataset.value, this.textContent);
                });
            });
        }
        
        // Seleccionar opción
        function selectOption(value, text) {
            // Validar duplicado ANTES de seleccionar
            if (isDuplicado(tipo, value, vinculoIndex)) {
                alert(`⚠️ La ${tipo === 'pelicula' ? 'película' : 'función'} "${text}" ya está seleccionada en otro vínculo.\n\nPor favor, selecciona una ${tipo === 'pelicula' ? 'película' : 'función'} diferente.`);
                searchInput.value = '';
                realSelect.value = '';
                dropdown.style.display = 'none';
                return;
            }
            
            realSelect.value = value;
            searchInput.value = text;
            lastValidValue = text;
            dropdown.style.display = 'none';
            selectedIndex = -1;
            searchInput.classList.remove('invalid-input');
            
            // Limpiar el campo opuesto (película vs función)
            const row = searchInput.closest('.vinculo-form-row');
            if (tipo === 'pelicula') {
                const funcionSelect = row.querySelector('select[name$="-funcion"]');
                const funcionSearch = row.querySelector('.vinculo-funcion-search');
                if (funcionSelect) funcionSelect.value = '';
                if (funcionSearch) funcionSearch.value = '';
            } else {
                const peliculaSelect = row.querySelector('select[name$="-pelicula"]');
                const peliculaSearch = row.querySelector('.vinculo-pelicula-search');
                if (peliculaSelect) peliculaSelect.value = '';
                if (peliculaSearch) peliculaSearch.value = '';
            }
            
            // Actualizar todos los comboboxes
            updateAllComboboxes();
        }
        
        // Validar input
        function validateInput() {
            const inputValue = searchInput.value.trim();
            
            if (!inputValue) {
                realSelect.value = '';
                searchInput.classList.remove('invalid-input');
                return false;
            }
            
            const match = opciones.find(opt => opt.text === inputValue);
            
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
        
        // Filtrar opciones
        function filterOptions(searchTerm) {
            const term = searchTerm.toLowerCase().trim();
            const disponibles = getOpcionesDisponibles();

            if (term.length < 3) return [];

            return disponibles.filter(opt =>
                opt.text.toLowerCase().includes(term)
            );
        }

        function renderMinCharsMessage() {
            dropdown.innerHTML = '<div class="combobox-empty">Escribe al menos 3 letras para buscar...</div>';
            dropdown.style.display = 'block';
        }
        
        // Event listeners
        searchInput.addEventListener('focus', function() {
            const searchTerm = this.value.trim();

            if (searchTerm.length < 3) {
                renderMinCharsMessage();
                return;
            }

            const filtered = filterOptions(searchTerm);
            renderOptions(filtered);
            dropdown.style.display = 'block';
        });
        
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.trim();

            if (searchTerm.length < 3) {
                renderMinCharsMessage();
                return;
            }

            const filtered = filterOptions(searchTerm);
            renderOptions(filtered);
            dropdown.style.display = 'block';
            selectedIndex = -1;
        });
        
        searchInput.addEventListener('blur', function(e) {
            setTimeout(() => {
                if (!dropdown.contains(document.activeElement)) {
                    validateInput();
                    dropdown.style.display = 'none';
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
        
        // Inicializar valor si existe
        if (realSelect.value) {
            const selectedOption = opciones.find(opt => opt.value === realSelect.value);
            if (selectedOption) {
                searchInput.value = selectedOption.text;
                lastValidValue = selectedOption.text;
            }
        }
    }
    
    // ========== GESTIÓN DE SELECCIONES ==========
    
    /**
     * Obtiene IDs ya seleccionados de películas o funciones
     */
    function getSeleccionadas(tipo) {
        const seleccionadas = new Set();
        
        document.querySelectorAll('.vinculo-form-row').forEach(row => {
            const deleteCheckbox = row.querySelector('input[id$="-DELETE"]');
            if (deleteCheckbox?.checked) return; // Ignorar eliminados
            
            const select = row.querySelector(`select[name$="-${tipo}"]`);
            if (select && select.value) {
                seleccionadas.add(select.value);
            }
        });
        
        return seleccionadas;
    }
    
    /**
     * Verifica si un valor ya está seleccionado en otro vínculo
     */
    function isDuplicado(tipo, valor, indexActual) {
        if (!valor) return false;
        
        let contador = 0;
        document.querySelectorAll('.vinculo-form-row').forEach((row, index) => {
            const deleteCheckbox = row.querySelector('input[id$="-DELETE"]');
            if (deleteCheckbox?.checked) return;
            
            const select = row.querySelector(`select[name$="-${tipo}"]`);
            if (select && select.value === valor) {
                contador++;
            }
        });
        
        return contador > 0; // Si ya hay al menos 1, es duplicado
    }
    
    /**
     * Actualiza todos los comboboxes (re-renderiza opciones disponibles)
     */
    function updateAllComboboxes() {
        document.querySelectorAll('.vinculo-pelicula-search').forEach(input => {
            const dropdown = document.getElementById(input.id.replace('search', 'dropdown'));
            if (dropdown && dropdown.style.display === 'block') {
                const realSelect = input.closest('.combobox-wrapper').querySelector('select');
                const opciones = peliculasOriginales.filter(opt => {
                    const seleccionadas = getSeleccionadas('pelicula');
                    return opt.value === realSelect.value || !seleccionadas.has(opt.value);
                });
                
                if (opciones.length === 0) {
                    dropdown.innerHTML = '<div class="combobox-empty">No hay películas disponibles</div>';
                } else {
                    dropdown.innerHTML = opciones.map((opt, idx) => 
                        `<div class="combobox-option" data-value="${opt.value}" data-index="${idx}">${opt.text}</div>`
                    ).join('');
                }
            }
        });
        
        document.querySelectorAll('.vinculo-funcion-search').forEach(input => {
            const dropdown = document.getElementById(input.id.replace('search', 'dropdown'));
            if (dropdown && dropdown.style.display === 'block') {
                const realSelect = input.closest('.combobox-wrapper').querySelector('select');
                const opciones = funcionesOriginales.filter(opt => {
                    const seleccionadas = getSeleccionadas('funcion');
                    return opt.value === realSelect.value || !seleccionadas.has(opt.value);
                });
                
                if (opciones.length === 0) {
                    dropdown.innerHTML = '<div class="combobox-empty">No hay funciones disponibles</div>';
                } else {
                    dropdown.innerHTML = opciones.map((opt, idx) => 
                        `<div class="combobox-option" data-value="${opt.value}" data-index="${idx}">${opt.text}</div>`
                    ).join('');
                }
            }
        });
    }
    
    // ========== INICIALIZACIÓN DE COMBOBOXES ==========
    
    function initAllComboboxes() {
        // Películas
        document.querySelectorAll('.vinculo-pelicula-search').forEach(searchInput => {
            const vinculoIndex = searchInput.dataset.vinculoIndex;
            const dropdown = document.getElementById(`pelicula-dropdown-${vinculoIndex}`);
            const realSelect = searchInput.closest('.combobox-wrapper').querySelector('select[name$="-pelicula"]');
            
            if (dropdown && realSelect) {
                initCombobox(searchInput, dropdown, realSelect, 'pelicula');
            }
        });
        
        // Funciones
        document.querySelectorAll('.vinculo-funcion-search').forEach(searchInput => {
            const vinculoIndex = searchInput.dataset.vinculoIndex;
            const dropdown = document.getElementById(`funcion-dropdown-${vinculoIndex}`);
            const realSelect = searchInput.closest('.combobox-wrapper').querySelector('select[name$="-funcion"]');
            
            if (dropdown && realSelect) {
                initCombobox(searchInput, dropdown, realSelect, 'funcion');
            }
        });
    }
    
    // ========== MANEJO DE ELIMINACIÓN ==========
    
    function attachDeleteListeners() {
        document.querySelectorAll('.btn-remove-vinculo').forEach(button => {
            if (button.hasAttribute('data-listener-attached')) return;
            
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const row = this.closest('.vinculo-form-row');
                if (!row) return;
                
                const deleteCheckbox = row.querySelector('input[id$="-DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                    row.style.display = 'none';
                    updateAllComboboxes();
                }
            });
            
            button.setAttribute('data-listener-attached', 'true');
        });
    }
    
    // ========== CERRAR DROPDOWNS AL HACER CLIC FUERA ==========
    
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.combobox-wrapper')) {
            document.querySelectorAll('.combobox-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });
        }
    });
    
    // ========== OBSERVADOR PARA NUEVOS VÍNCULOS ==========
    
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1 && node.classList && node.classList.contains('vinculo-form-row')) {
                    console.log('➕ Nuevo vínculo detectado');
                    
                    // Inicializar comboboxes en el nuevo vínculo
                    const peliculaSearch = node.querySelector('.vinculo-pelicula-search');
                    const funcionSearch = node.querySelector('.vinculo-funcion-search');
                    
                    if (peliculaSearch) {
                        const vinculoIndex = peliculaSearch.dataset.vinculoIndex;
                        const dropdown = document.getElementById(`pelicula-dropdown-${vinculoIndex}`);
                        const realSelect = node.querySelector('select[name$="-pelicula"]');
                        if (dropdown && realSelect) {
                            initCombobox(peliculaSearch, dropdown, realSelect, 'pelicula');
                        }
                    }
                    
                    if (funcionSearch) {
                        const vinculoIndex = funcionSearch.dataset.vinculoIndex;
                        const dropdown = document.getElementById(`funcion-dropdown-${vinculoIndex}`);
                        const realSelect = node.querySelector('select[name$="-funcion"]');
                        if (dropdown && realSelect) {
                            initCombobox(funcionSearch, dropdown, realSelect, 'funcion');
                        }
                    }
                    
                    attachDeleteListeners();
                }
            });
        });
    });
    
    observer.observe(vinculosContainer, { childList: true, subtree: true });
    
    // ========== INICIALIZACIÓN ==========
    
    initAllComboboxes();
    attachDeleteListeners();
    
    console.log('✅ Vínculos Manager con Combobox inicializado correctamente');
});
