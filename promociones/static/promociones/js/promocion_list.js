document.addEventListener('DOMContentLoaded', function() {
    const btnModificar = document.getElementById('btn-modificar');
    const btnEliminar = document.getElementById('btn-eliminar');
    let selectedRows = [];

    // Función para adjuntar listeners a las filas
    function attachRowListeners(container) {
        if (!container) container = document;
        const rows = container.querySelectorAll('.promocion-row');
        rows.forEach(row => {
            row.addEventListener('click', function(event) {
                if (!event.ctrlKey && !event.metaKey) {
                    document.querySelectorAll('.promocion-row.selected').forEach(r => {
                        if (r !== this) r.classList.remove('selected');
                    });
                    selectedRows = [];
                }
                toggleRowSelection(this);
            });
        });
    }

    function updateUI() {
        if (!btnModificar || !btnEliminar) return;
        btnModificar.disabled = selectedRows.length !== 1;
        btnEliminar.disabled = selectedRows.length === 0;
        
        if (selectedRows.length > 0) {
            btnEliminar.textContent = `⛔ Desactivar ${selectedRows.length > 1 ? `(${selectedRows.length})` : ''}`;
        } else {
            btnEliminar.textContent = '⛔ Desactivar';
        }
    }
    
    function toggleRowSelection(row) {
        const rowId = row.dataset.id;
        if (row.classList.contains('selected')) {
            row.classList.remove('selected');
            selectedRows = selectedRows.filter(id => id !== rowId);
        } else {
            row.classList.add('selected');
            selectedRows.push(rowId);
        }
        updateUI();
    }

    // Inicializar listeners en la carga inicial
    attachRowListeners();

    // --- FILTROS CON AJAX ---
    const searchInput = document.getElementById('search-input');
    const btnFilter = document.getElementById('btn-filter');
    const formFiltros = document.getElementById('form-filtros');

    function serializeForm() {
        const form = document.getElementById('form-filtros');
        const params = new URLSearchParams(new FormData(form));
        return params.toString();
    }

    let searchTimeout = null;
    function fetchTable(push=true) {
        const qs = serializeForm();
        const url = window.location.pathname + (qs ? ('?' + qs) : '');
        const container = document.getElementById('promocionTableContainer');
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

    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            fetchTableDebounced();
        });
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(searchTimeout);
                fetchTable(true);
            }
        });
    }

    if (btnFilter) {
        btnFilter.addEventListener('click', function() { 
            clearTimeout(searchTimeout); 
            fetchTable(true); 
        });
    }

    const allSelects = document.querySelectorAll('#form-filtros select');
    allSelects.forEach(select => {
        select.addEventListener('change', function() {
            clearTimeout(searchTimeout);
            fetchTable(true);
        });
    });

    // Manejar botón atrás del navegador
    window.addEventListener('popstate', function() {
        fetchTable(false);
    });

    // --- BOTONES DE ACCIÓN ---
    if(btnModificar) btnModificar.addEventListener('click', function() {
        if (selectedRows.length === 1) {
            const row = document.querySelector(`.promocion-row[data-id="${selectedRows[0]}"]`);
            if (row) {
                const url = row.getAttribute('data-edit-url');
                if (url) window.location.href = url;
            }
        }
    });
    
    if(btnEliminar) btnEliminar.addEventListener('click', function() {
        if (selectedRows.length === 0) return;
        
        if (selectedRows.length === 1) {
            const row = document.querySelector(`.promocion-row[data-id="${selectedRows[0]}"]`);
            if (row) {
                const url = row.getAttribute('data-delete-url');
                if (url) window.location.href = url;
            }
        } else {
            if (confirm(`¿Estás seguro de que deseas desactivar ${selectedRows.length} promociones seleccionadas?`)) {
                alert('Función de desactivación masiva en desarrollo');
            }
        }
    });
    
    updateUI();
});
