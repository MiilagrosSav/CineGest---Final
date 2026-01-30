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
 * Actualiza la UI de los botones
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
 */
function attachRowListeners(container) {
    if (!container) return;
    const rows = container.querySelectorAll('.sala-row'); // <- Apunta a .sala-row
    
    rows.forEach(row => {
        row.addEventListener('click', function(event) {
            // Tu script original tenía esta lógica 'selectable-cell', la restauro
            if (event.target.classList.contains('btn-layout')) {
                // Si se hizo clic en el botón de layout, no seleccionar la fila
                return; 
            }
            
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
    
    // 2. Adjuntar listeners a los botones (apuntando a URLs de SALAS)
    if(btnModificar) btnModificar.addEventListener('click', function() {
        if (selectedRows.length === 1) {
            window.location.href = `/salas/${selectedRows[0]}/editar/`; // <- URL de Sala
        }
    });
    if(btnEliminar) btnEliminar.addEventListener('click', function() {
        if (selectedRows.length === 0) return;
        if (selectedRows.length === 1) {
            window.location.href = `/salas/${selectedRows[0]}/eliminar/`; // <- URL de Sala
        } else {
            if (confirm(`¿Estás seguro de que deseas eliminar ${selectedRows.length} salas seleccionadas?`)) {
                alert('Función de eliminación masiva en desarrollo');
            }
        }
    });

    // 3. Adjuntar listeners a los filtros (son estáticos)
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => { document.getElementById('form-filtros').submit(); }, 500);
        });
    }

    // 4. Adjuntar listeners a las filas de la tabla cargada inicialmente
    attachRowListeners(document.getElementById('salaTableContainer'));
    
    // 5. Inicializar estado de botones
    updateUI();
});

/**
 * Lógica de Paginación AJAX (se ejecuta 1 vez)
 */
(function(){
    const container = document.getElementById('salaTableContainer');
    if (!container) return;

    // Listener para paginación y ordenamiento
    container.addEventListener('click', function(e){
        const a = e.target.closest('a');
        if (!a) return;
        const href = a.getAttribute('href');
        // Asegurarse que el link sea de paginación u orden
        if (!href || (!a.href.includes('page=') && !a.href.includes('orden=')) || !container.contains(a)) return;
        
        e.preventDefault();
        container.style.opacity = '0.6';

        fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => { if (!r.ok) throw new Error('Network response not ok'); return r.text(); })
            .then(html => {
                container.innerHTML = html;
                attachRowListeners(container); // Re-adjuntar listeners a las nuevas filas
                selectedRows = [];             // Resetear selección
                updateUI();                    // Actualizar botones
                history.pushState(null, '', href);
            })
            .catch(err => { console.error('AJAX error', err); })
            .finally(()=>{ container.style.opacity = ''; });
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

/* (Funciones de Modal - copiadas de Funciones) */
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
