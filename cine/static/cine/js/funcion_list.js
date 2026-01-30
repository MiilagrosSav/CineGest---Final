var selectedRows = [];
var btnModificar = null;
var btnEliminar = null;

/**
 * Función para ordenar por columna
 */
function ordenarPor(columna) {
    const urlParams = new URLSearchParams(window.location.search);
    const ordenActual = urlParams.get('orden');
    let nuevoOrden = columna;
    if (ordenActual === columna) nuevoOrden = columna + '_desc';
    else if (ordenActual === columna + '_desc') nuevoOrden = columna;
    urlParams.set('orden', nuevoOrden);
    window.location.href = '?' + urlParams.toString();
}

/**
 * Actualiza la UI de los botones (habilitado/deshabilitado y texto)
 */
function updateUI() {
    if (!btnModificar || !btnEliminar) return;
    btnModificar.disabled = selectedRows.length !== 1;
    btnEliminar.disabled = selectedRows.length === 0;
    if (selectedRows.length > 0) btnEliminar.textContent = `🗑️ Eliminar ${selectedRows.length > 1 ? `(${selectedRows.length})` : ''}`;
    else btnEliminar.textContent = '🗑️ Eliminar';
}

/**
 * Adjunta los listeners de click a las filas de la tabla.
 * Esta función DEBE llamarse cada vez que la tabla se recarga (inicial y AJAX).
 */
function attachRowListeners(container) {
    if (!container) return;
    const rows = container.querySelectorAll('.funcion-row');
    rows.forEach(row => {
        row.addEventListener('click', function(event) {
            if (!event.ctrlKey && !event.metaKey) {
                rows.forEach(r => { if (r !== row && r.classList.contains('selected')) r.classList.remove('selected'); });
                if (!row.classList.contains('selected')) selectedRows = [];
            }
            const rowId = row.dataset.id;
            if (row.classList.contains('selected')) {
                row.classList.remove('selected');
                selectedRows = selectedRows.filter(id => id !== rowId);
            } else {
                row.classList.add('selected');
                if (!selectedRows.includes(rowId)) selectedRows.push(rowId);
            }
            updateUI();
        });
    });
}

/**
 * Lógica de Carga Inicial (se ejecuta 1 vez)
 */
document.addEventListener('DOMContentLoaded', function() {
    // 1. Encontrar los botones (son estáticos)
    btnModificar = document.getElementById('btn-modificar');
    btnEliminar = document.getElementById('btn-eliminar');
    
    // 2. Adjuntar listeners a los botones
    if(btnModificar) btnModificar.addEventListener('click', function() {
        if (selectedRows.length === 1) window.location.href = `/funciones/${selectedRows[0]}/editar/`;
    });
    if(btnEliminar) btnEliminar.addEventListener('click', function() {
        if (selectedRows.length === 0) return;
        
        if (selectedRows.length === 1) {
            const url = `/funciones/${selectedRows[0]}/eliminar/`;
            // Simplemente redirigimos a la página de confirmación
            window.location.href = url; 
        
        } else if (confirm(`¿Estás seguro de que deseas eliminar ${selectedRows.length} funciones seleccionadas?`)) {
            alert('Función de eliminación masiva en desarrollo');
        }
    });

    // 3. Adjuntar listeners a los filtros (son estáticos) y activar búsqueda AJAX con debounce
    const searchInput = document.getElementById('search-input');
    const btnFilter = document.getElementById('btn-filter');

    function serializeForm() {
        const form = document.getElementById('form-filtros');
        const params = new URLSearchParams(new FormData(form));
        return params.toString();
    }

    let searchTimeout = null;
    function fetchTable(push=true) {
        const qs = serializeForm();
        // Removed debug output to keep UI clean for end users
        const url = window.location.pathname + (qs ? ('?' + qs) : '');
        const container = document.getElementById('funcionTableContainer');
        if (!container) return;
        container.style.opacity = '0.6';
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => { if (!r.ok) throw new Error('Network response not ok'); return r.text(); })
            .then(html => {
                container.innerHTML = html;
                attachRowListeners(container);
                selectedRows = [];
                updateUI();
                if (push) history.pushState(null, '', url);
            })
            .catch(err => { console.error('AJAX error', err); })
            .finally(()=>{ container.style.opacity = ''; });
    }

    function fetchTableDebounced() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => fetchTable(true), 500);
    }

    // Adjuntar listeners a todos los selects y inputs de filtro
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            // debounce while typing
            fetchTableDebounced();
        });
        // Enter key triggers immediate search
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(searchTimeout);
                fetchTable(true);
            }
        });
    }

    if (btnFilter) {
        btnFilter.addEventListener('click', function() { clearTimeout(searchTimeout); fetchTable(true); });
    }

    // Adjuntar listener a TODOS los selects (estado, pelicula, sala, formato)
    const allSelects = document.querySelectorAll('#form-filtros select');
    allSelects.forEach(select => {
        select.addEventListener('change', function() {
            clearTimeout(searchTimeout);
            fetchTable(true);
        });
    });
    
    const fechaInicioInput = document.getElementById('fecha-inicio');
    const fechaInicioDisplay = document.getElementById('fecha-inicio-display');
    const fechaFinInput = document.getElementById('fecha-fin');
    const fechaFinDisplay = document.getElementById('fecha-fin-display');

    function setupDatePair(input, display) {
        if (!input || !display) return;
        if (input.value) {
            const [year, month, day] = input.value.split('-');
            display.value = `${day}-${month}-${year}`;
        }
        display.addEventListener('click', function() { try { input.showPicker(); } catch(e) { input.click(); } });
        input.addEventListener('change', function() {
            if (this.value) {
                const [year, month, day] = this.value.split('-');
                display.value = `${day}-${month}-${year}`;
            } else {
                display.value = '';
            }
            // trigger immediate fetch for date changes
            clearTimeout(searchTimeout);
            fetchTable(true);
        });
        display.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' || e.key === 'Delete') {
                e.preventDefault();
                this.value = '';
                input.value = '';
                clearTimeout(searchTimeout);
                fetchTable(true);
            }
        });
    }

    setupDatePair(fechaInicioInput, fechaInicioDisplay);
    setupDatePair(fechaFinInput, fechaFinDisplay);

    // 4. Adjuntar listeners a las filas de la tabla cargada inicialmente
    attachRowListeners(document.getElementById('funcionTableContainer'));
    
    // 5. Inicializar estado de botones
    updateUI();
});

/**
 * Lógica de Paginación AJAX (se ejecuta 1 vez)
 */
(function(){
    const container = document.getElementById('funcionTableContainer');
    if (!container) return;

    // Listener para paginación y ordenamiento
    container.addEventListener('click', function(e){
        const a = e.target.closest('a');
        if (!a || (!a.href.includes('page=') && !a.href.includes('orden=')) || !container.contains(a)) return;
        
        e.preventDefault();
        const href = a.getAttribute('href');
        container.style.opacity = '0.6';

        fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => { if (!r.ok) throw new Error('Network response not ok'); return r.text(); })
            .then(html => {
                container.innerHTML = html;
                attachRowListeners(container); // Re-adjuntar listeners a las nuevas filas
                selectedRows = [];             // Resetear selección
                updateUI();                    // Actualizar botones (se deshabilitarán)
                history.pushState(null, '', href);
            })
            .catch(err => { console.error('AJAX error', err); })
            .finally(()=>{ container.style.opacity = ''; });
    });

    // Delegación: abrir modal (si existe en el partial)
    container.addEventListener('click', function(e){
        const btn = e.target.closest('.row-delete');
        if (!btn) return;
        e.stopPropagation();
        e.preventDefault();
        const url = btn.getAttribute('data-url');
        if (url && window.openDeleteModal) openDeleteModal(url);
    });

    // Listener para botones de historial del navegador
    window.addEventListener('popstate', function(){
         fetch(window.location.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.text())
            .then(html => { 
                container.innerHTML = html; 
                attachRowListeners(container);
                selectedRows = [];
                updateUI();
            });
    });
})();

/*
 * Helpers to open delete modal
 */
function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? decodeURIComponent(v.pop()) : '';
}

function openDeleteModal(url) {
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => { if (!r.ok) throw new Error('Network response not ok'); return r.text(); })
        .then(html => {
            const tmp = document.createElement('div'); tmp.innerHTML = html;
            const overlay = tmp.querySelector('#deleteModalOverlay') || tmp.firstElementChild;
            if (!overlay) { console.error('No modal fragment returned'); window.location.href = url; return; }
            document.body.appendChild(overlay);
            if (window.initDeleteModal) window.initDeleteModal();
        })
        .catch(err => { console.error('Error loading delete modal', err); window.location.href = url; });
}
