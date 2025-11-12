// JS extracted from templates/cine/pelicula_list.html
var selectedRows = [];
var btnModificar = null;
var btnEliminar = null;

function ordenarPor(columna) {
    const urlParams = new URLSearchParams(window.location.search);
    const ordenActual = urlParams.get('orden');
    let nuevoOrden = columna;
    if (ordenActual === columna) nuevoOrden = columna + '_desc';
    else if (ordenActual === columna + '_desc') nuevoOrden = columna;
    urlParams.set('orden', nuevoOrden);
    window.location.href = '?' + urlParams.toString();
}

function updateUI() {
    if (!btnModificar || !btnEliminar) return;
    btnModificar.disabled = selectedRows.length !== 1;
    btnEliminar.disabled = selectedRows.length === 0;
    if (selectedRows.length > 0) btnEliminar.textContent = `🗑️ Eliminar ${selectedRows.length > 1 ? `(${selectedRows.length})` : ''}`;
    else btnEliminar.textContent = '🗑️ Eliminar';
}

function attachRowListeners(container) {
    if (!container) return;
    const rows = container.querySelectorAll('.pelicula-row');
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

document.addEventListener('DOMContentLoaded', function() {
    btnModificar = document.getElementById('btn-modificar');
    btnEliminar = document.getElementById('btn-eliminar');
    if(btnModificar) btnModificar.addEventListener('click', function() {
        if (selectedRows.length === 1) {
            window.location.href = `/peliculas/${selectedRows[0]}/editar/`;
        }
    });
    if(btnEliminar) btnEliminar.addEventListener('click', function() {
        if (selectedRows.length === 0) return;
        if (selectedRows.length === 1) {
            window.location.href = `/peliculas/${selectedRows[0]}/eliminar/`;
        } else {
            if (confirm(`¿Estás seguro de que deseas eliminar ${selectedRows.length} películas seleccionadas?`)) {
                alert('Función de eliminación masiva en desarrollo');
            }
        }
    });
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => { document.getElementById('form-filtros').submit(); }, 500);
        });
    }
    attachRowListeners(document.getElementById('peliculaTableContainer'));
    updateUI();
});

// AJAX pagination handling
(function(){
    const container = document.getElementById('peliculaTableContainer');
    if (!container) return;
    container.addEventListener('click', function(e){
        const a = e.target.closest('a');
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || (!a.href.includes('page=') && !a.href.includes('orden=')) || !container.contains(a)) return;
        e.preventDefault();
        container.style.opacity = '0.6';
        fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => { if (!r.ok) throw new Error('Network response not ok'); return r.text(); })
            .then(html => {
                container.innerHTML = html;
                attachRowListeners(container);
                selectedRows = [];
                updateUI();
                history.pushState(null, '', href);
            })
            .catch(err => { console.error('AJAX error', err); })
            .finally(()=>{ container.style.opacity = ''; });
    });
    window.addEventListener('popstate', function(){
         fetch(window.location.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.text())
            .then(html => { container.innerHTML = html; attachRowListeners(container); selectedRows = []; updateUI(); });
    });
})();
