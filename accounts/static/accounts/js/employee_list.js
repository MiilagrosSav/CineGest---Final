document.addEventListener('DOMContentLoaded', function() {
        // Apunta a las filas DENTRO del 'overflow-x' div
        const rows = document.querySelectorAll('.employee-row');
        const btnModificar = document.getElementById('btn-modificar');
        const btnEliminar = document.getElementById('btn-eliminar');
        
        // Variable para almacenar la selección actual
        let selectedRows = [];
        
        // Función para actualizar la interfaz según la selección
        function updateUI() {
            // Chequeo de seguridad por si los botones no existen
            if (!btnModificar || !btnEliminar) return;
            
            // Actualizar estado de botones
            btnModificar.disabled = selectedRows.length !== 1;
            btnEliminar.disabled = selectedRows.length === 0;
            
            // Actualizar texto del botón eliminar con contador
            if (selectedRows.length > 0) {
                btnEliminar.textContent = `🗑️ Eliminar ${selectedRows.length > 1 ? `(${selectedRows.length})` : ''}`;
            } else {
                btnEliminar.textContent = '🗑️ Eliminar';
            }
        }
        
        // Función para seleccionar/deseleccionar una fila
        function toggleRowSelection(row) {
            const rowId = row.dataset.id;
            
            if (row.classList.contains('selected')) {
                // Deseleccionar
                row.classList.remove('selected');
                selectedRows = selectedRows.filter(id => id !== rowId);
            } else {
                // Seleccionar
                row.classList.add('selected');
                selectedRows.push(rowId);
            }
            
            updateUI();
        }
        
        // Evento para el clic en fila
        rows.forEach(row => {
            row.addEventListener('click', function(event) { // 'event' añadido

                // Si se mantiene presionada la tecla Ctrl, permite selección múltiple
                if (!event.ctrlKey && !event.metaKey) {
                    // Si no se presiona Ctrl/Cmd, deseleccionar todas las demás
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
        
        // Evento para botón modificar
        if(btnModificar) btnModificar.addEventListener('click', function() {
            if (selectedRows.length === 1) {
                window.location.href = `/accounts/employees/${selectedRows[0]}/edit/`;
            }
        });
        
        // Evento para botón eliminar
        if(btnEliminar) btnEliminar.addEventListener('click', function() {
            if (selectedRows.length === 0) return;
            
            if (selectedRows.length === 1) {
                window.location.href = `/accounts/employees/${selectedRows[0]}/delete/`;
            } else {
                if (confirm(`¿Estás seguro de que deseas eliminar ${selectedRows.length} empleados seleccionados?`)) {
                    // Aquí implementaríamos la eliminación masiva
                    alert('Función de eliminación masiva en desarrollo');
                }
            }
        });
        
        // Inicializar UI (si los botones existen)
        if(btnModificar && btnEliminar) {
            updateUI();
        }
    });