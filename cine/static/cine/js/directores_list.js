var selectedRows = [];
var btnModificar = null;
var btnEliminar = null;
var activeDeleteOverlay = null;

function ordenarPor(columna) {
    const urlParams = new URLSearchParams(window.location.search);
    const ordenActual = urlParams.get('orden');
    let nuevoOrden = columna;
    if (ordenActual === columna) nuevoOrden = columna + '_desc';
    else if (ordenActual === columna + '_desc') nuevoOrden = columna;
    urlParams.set('orden', nuevoOrden);
    window.location.href = '?' + urlParams.toString();
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }
    return '';
}

function updateUI() {
    if (btnModificar) btnModificar.disabled = selectedRows.length !== 1;
    if (btnEliminar) btnEliminar.disabled = selectedRows.length !== 1;
}

function attachRowListeners(container) {
    if (!container) return;
    const rows = container.querySelectorAll('.director-row');
    rows.forEach(function (row) {
        row.addEventListener('click', function (event) {
            if (!event.ctrlKey && !event.metaKey) {
                rows.forEach(function (r) {
                    if (r !== row && r.classList.contains('selected')) {
                        r.classList.remove('selected');
                    }
                });
                if (!row.classList.contains('selected')) selectedRows = [];
            }

            const rowId = row.dataset.id;
            if (row.classList.contains('selected')) {
                row.classList.remove('selected');
                selectedRows = selectedRows.filter(function (id) { return id !== rowId; });
            } else {
                row.classList.add('selected');
                if (!selectedRows.includes(rowId)) selectedRows.push(rowId);
            }
            updateUI();
        });
    });
}

function urlFromTemplate(template, rowId) {
    return (template || '').replace('/0/', '/' + rowId + '/');
}

function closeDeleteModal() {
    if (activeDeleteOverlay) {
        activeDeleteOverlay.remove();
        activeDeleteOverlay = null;
    }
    document.removeEventListener('keydown', handleDeleteModalEsc);
}

function handleDeleteModalEsc(event) {
    if (event.key === 'Escape') {
        closeDeleteModal();
    }
}

function parseModalOverlay(html) {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.querySelector('#deleteModalOverlay') || tmp.firstElementChild;
}

function showModalError(message) {
    if (!activeDeleteOverlay) return;
    const card = activeDeleteOverlay.querySelector('.delete-modal-card');
    if (!card) return;

    let errorBox = card.querySelector('[data-delete-modal-error]');
    if (!errorBox) {
        errorBox = document.createElement('div');
        errorBox.setAttribute('data-delete-modal-error', '1');
        errorBox.className = 'message message-error';
        errorBox.style.marginTop = 'var(--space-md)';
        card.appendChild(errorBox);
    }
    errorBox.textContent = message;
}

function bindDeleteModalEvents(overlay) {
    activeDeleteOverlay = overlay;
    document.body.appendChild(overlay);
    document.addEventListener('keydown', handleDeleteModalEsc);

    overlay.addEventListener('click', function (event) {
        if (event.target === overlay || event.target.closest('[data-modal-close]')) {
            closeDeleteModal();
        }
    });

    const form = overlay.querySelector('[data-director-delete-form]');
    if (!form) return;

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        const submitButton = form.querySelector('[data-modal-submit]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.dataset.originalText = submitButton.textContent;
            submitButton.textContent = 'Eliminando...';
        }

        fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new FormData(form),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                const data = result.data || {};
                if (data.ok) {
                    window.location.href = data.redirect_url || window.location.href;
                    return;
                }

                if (data.html) {
                    closeDeleteModal();
                    const nextOverlay = parseModalOverlay(data.html);
                    if (nextOverlay) {
                        bindDeleteModalEvents(nextOverlay);
                        return;
                    }
                }

                showModalError(data.error || 'No se pudo eliminar el director.');
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = submitButton.dataset.originalText || 'Sí, Eliminar';
                }
            })
            .catch(function (error) {
                console.error('Error al eliminar director:', error);
                showModalError('Ocurrió un error inesperado al intentar eliminar el director.');
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = submitButton.dataset.originalText || 'Sí, Eliminar';
                }
            });
    });
}

function openDeleteModal(url) {
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
        .then(function (response) {
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                return response.json().then(function (data) {
                    if (data && data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        showModalError((data && data.error) || 'No se pudo abrir el modal de eliminación.');
                    }
                    return null;
                });
            }
            return response.text();
        })
        .then(function (html) {
            if (!html) return;
            closeDeleteModal();
            const overlay = parseModalOverlay(html);
            if (!overlay) {
                console.error('No modal fragment returned');
                window.location.href = url;
                return;
            }
            bindDeleteModalEvents(overlay);
        })
        .catch(function (error) {
            console.error('Error al abrir modal de eliminación:', error);
            window.location.href = url;
        });
}

function eliminarDirectorSeleccionado() {
    const tableContainer = document.getElementById('directorTableContainer');
    if (!tableContainer || selectedRows.length !== 1) return;

    const template = tableContainer.getAttribute('data-delete-url-template') || '';
    if (!template) return;
    const deleteUrl = urlFromTemplate(template, selectedRows[0]);
    openDeleteModal(deleteUrl);
}

document.addEventListener('DOMContentLoaded', function () {
    btnModificar = document.getElementById('btn-modificar');
    btnEliminar = document.getElementById('btn-eliminar');
    const tableContainer = document.getElementById('directorTableContainer');

    if (btnModificar && tableContainer) {
        btnModificar.addEventListener('click', function () {
            if (selectedRows.length !== 1) return;
            const template = tableContainer.getAttribute('data-edit-url-template');
            if (!template) return;
            window.location.href = urlFromTemplate(template, selectedRows[0]);
        });
    }

    if (btnEliminar) {
        btnEliminar.addEventListener('click', eliminarDirectorSeleccionado);
    }

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(function () {
                const form = document.getElementById('form-filtros');
                if (form) form.submit();
            }, 500);
        });
    }

    attachRowListeners(tableContainer);
    updateUI();
});

(function () {
    const container = document.getElementById('directorTableContainer');
    if (!container) return;

    container.addEventListener('click', function (e) {
        const a = e.target.closest('a');
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || (!a.href.includes('page=') && !a.href.includes('orden=')) || !container.contains(a)) return;

        e.preventDefault();
        container.style.opacity = '0.6';

        fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) {
                if (!r.ok) throw new Error('Network response not ok');
                return r.text();
            })
            .then(function (html) {
                container.innerHTML = html;
                attachRowListeners(container);
                selectedRows = [];
                updateUI();
                history.pushState(null, '', href);
            })
            .catch(function (err) { console.error('AJAX error', err); })
            .finally(function () { container.style.opacity = ''; });
    });

    window.addEventListener('popstate', function () {
        fetch(window.location.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                container.innerHTML = html;
                attachRowListeners(container);
                selectedRows = [];
                updateUI();
            });
    });
})();
