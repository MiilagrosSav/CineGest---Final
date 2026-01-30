document.addEventListener('DOMContentLoaded', function() {
    const btnModificar = document.getElementById('btn-modificar');
    const btnEliminar = document.getElementById('btn-eliminar');
    let selectedRows = [];

    // 1. Selección de filas
    function attachRowListeners(container) {
        if (!container) container = document;
        const rows = container.querySelectorAll('.politica-row');
        rows.forEach(row => {
            row.addEventListener('click', function(event) {
                if (!event.ctrlKey && !event.metaKey) {
                    document.querySelectorAll('.politica-row.selected').forEach(r => {
                        if (r !== this) r.classList.remove('selected');
                    });
                    selectedRows = [];
                }
                toggleRowSelection(this);
            });
        });
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

    function updateUI() {
        if (!btnModificar || !btnEliminar) return;
        btnModificar.disabled = selectedRows.length !== 1;
        btnEliminar.disabled = selectedRows.length === 0;
        
        if (selectedRows.length > 0) {
            btnEliminar.textContent = `🗑️ Eliminar ${selectedRows.length > 1 ? `(${selectedRows.length})` : ''}`;
        } else {
            btnEliminar.textContent = '🗑️ Eliminar';
        }
    }

    // 2. Acciones de Botones (Usando data-url)
    if(btnModificar) btnModificar.addEventListener('click', function() {
        if (selectedRows.length === 1) {
            const row = document.querySelector(`.politica-row[data-id="${selectedRows[0]}"]`);
            if (row && row.dataset.editUrl) {
                window.location.href = row.dataset.editUrl;
            }
        }
    });
    
    if(btnEliminar) btnEliminar.addEventListener('click', function() {
        if (selectedRows.length === 0) return;
        
        if (selectedRows.length === 1) {
            const row = document.querySelector(`.politica-row[data-id="${selectedRows[0]}"]`);
            if (row && row.dataset.deleteUrl) {
                window.location.href = row.dataset.deleteUrl;
            }
        } else {
            if (confirm(`¿Estás seguro de que deseas eliminar ${selectedRows.length} políticas seleccionadas?`)) {
                alert('Función de eliminación masiva en desarrollo');
            }
        }
    });

    // 3. Búsqueda en vivo (Opcional)
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let timeout = null;
        searchInput.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                document.getElementById('form-filtros').submit();
            }, 500);
        });
    }

    // Inicializar
    attachRowListeners();
    updateUI();
});
