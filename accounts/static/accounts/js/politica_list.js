document.addEventListener('DOMContentLoaded', function() {
        const rows = document.querySelectorAll('.politica-row');
        const btnModificar = document.getElementById('btn-modificar');
        const btnEliminar = document.getElementById('btn-eliminar');
        
        let selectedRows = [];
        
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
        
        rows.forEach(row => {
            row.addEventListener('click', function(event) {
                if (!event.ctrlKey && !event.metaKey) {
                    rows.forEach(r => {
                        if (r !== this && r.classList.contains('selected')) {
                            r.classList.remove('selected');
                        }
                    });
                    selectedRows = [];
                }
                toggleRowSelection(this);
            });
        });
        
        // Adaptar URLs a las de políticas
        if(btnModificar) btnModificar.addEventListener('click', function() {
            if (selectedRows.length === 1) {
                window.location.href = `/accounts/politicas/${selectedRows[0]}/editar/`;
            }
        });
        
        if(btnEliminar) btnEliminar.addEventListener('click', function() {
            if (selectedRows.length === 0) return;
            
            if (selectedRows.length === 1) {
                window.location.href = `/accounts/politicas/${selectedRows[0]}/eliminar/`;
            } else {
                if (confirm(`¿Estás seguro de que deseas eliminar ${selectedRows.length} políticas seleccionadas?`)) {
                    alert('Función de eliminación masiva en desarrollo');
                }
            }
        });
        
        // Inicializar UI
        updateUI();
    });