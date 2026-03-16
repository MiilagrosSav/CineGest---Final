(function () {
    'use strict';

    const btnOpen = document.getElementById('btn-open-director-modal');
    const modal = document.getElementById('director-modal');
    const btnClose = document.getElementById('director-close');
    const btnCancel = document.getElementById('director-cancel');
    const btnSave = document.getElementById('director-save');

    const inputNombre = document.getElementById('manual-director-nombre');
    const inputApellido = document.getElementById('manual-director-apellido');
    const inputFecha = document.getElementById('manual-director-fecha-nacimiento');
    const inputBio = document.getElementById('manual-director-biografia');

    const selectDirector = document.getElementById('id_director');
    const directorSearchInput = document.getElementById('director-search');
    const directorDropdown = document.getElementById('director-dropdown');
    const form = selectDirector ? selectDirector.closest('form') : null;

    const summary = document.getElementById('director-manual-summary');

    const hiddenUsarManual = document.getElementById('id_director_usar_manual');
    const hiddenNombre = document.getElementById('id_director_nombre_manual');
    const hiddenApellido = document.getElementById('id_director_apellido_manual');
    const hiddenFecha = document.getElementById('id_director_fecha_nacimiento_manual');
    const hiddenBio = document.getElementById('id_director_biografia_manual');
    const hiddenTmdbId = document.getElementById('id_director_tmdb_id_manual');

    let directorOptions = [];
    let directorSelectedIndex = -1;
    let lastValidDirectorText = '';

    function normalizar(valor) {
        return (valor || '').trim().replace(/\s+/g, ' ');
    }

    function formatFecha(isoDate) {
        if (!isoDate || !isoDate.includes('-')) {
            return isoDate || '';
        }
        const [anio, mes, dia] = isoDate.split('-');
        return `${dia}/${mes}/${anio}`;
    }

    function buildDirectorOptions() {
        if (!selectDirector) {
            directorOptions = [];
            return;
        }

        directorOptions = Array.from(selectDirector.options)
            .filter((opt) => opt.value)
            .map((opt) => ({ value: String(opt.value), text: opt.text.trim() }));
    }

    function openModal() {
        if (!modal || !btnOpen || btnOpen.disabled) {
            return;
        }
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        if (!modal) {
            return;
        }
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }

    function limpiarManual() {
        if (hiddenUsarManual) hiddenUsarManual.value = '0';
        if (hiddenNombre) hiddenNombre.value = '';
        if (hiddenApellido) hiddenApellido.value = '';
        if (hiddenFecha) hiddenFecha.value = '';
        if (hiddenBio) hiddenBio.value = '';
        if (hiddenTmdbId) hiddenTmdbId.value = '';

        if (summary) {
            summary.textContent = '';
            summary.style.display = 'none';
        }
    }

    function clearDirectorComboboxSelection() {
        if (directorSearchInput) {
            directorSearchInput.value = '';
            directorSearchInput.classList.remove('invalid-input');
        }
        if (directorDropdown) {
            directorDropdown.style.display = 'none';
        }
        directorSelectedIndex = -1;
        lastValidDirectorText = '';
    }

    function getCSRFToken() {
        const row = document.cookie.split('; ').find((r) => r.startsWith('csrftoken='));
        return row ? row.split('=')[1] : '';
    }

    function aplicarManualDesdeModal() {
        const nombre = normalizar(inputNombre ? inputNombre.value : '');
        const apellido = normalizar(inputApellido ? inputApellido.value : '');
        const fechaNac = inputFecha ? inputFecha.value : '';
        const biografia = normalizar(inputBio ? inputBio.value : '');

        if (!nombre || !apellido) {
            alert('Debes completar nombre y apellido del director.');
            return;
        }

        const crearUrl = modal ? modal.getAttribute('data-crear-url') : null;
        if (!crearUrl) {
            alert('Error de configuración: no se encontró la URL para guardar el director.');
            return;
        }

        if (btnSave) {
            btnSave.disabled = true;
            btnSave.textContent = 'Guardando...';
        }

        const formData = new FormData();
        formData.append('nombre', nombre);
        formData.append('apellido', apellido);
        formData.append('fecha_nacimiento', fechaNac);
        formData.append('biografia', biografia);

        fetch(crearUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: formData,
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.ok) {
                    alert(data.error || 'Error al guardar el director.');
                    return;
                }

                // Agregar la opción al <select> si no existe ya
                if (selectDirector) {
                    let option = selectDirector.querySelector('option[value="' + data.id + '"]');
                    if (!option) {
                        option = document.createElement('option');
                        option.value = String(data.id);
                        option.textContent = data.nombre_completo;
                        selectDirector.appendChild(option);
                        buildDirectorOptions();
                    }
                    selectDirectorOption(String(data.id), data.nombre_completo, true);
                }

                limpiarManual();

                if (summary) {
                    summary.textContent = 'Director: ' + data.nombre_completo +
                        (data.ya_existia ? ' (ya existía en la base)' : ' (guardado)');
                    summary.style.display = 'block';
                }

                closeModal();
            })
            .catch(function (err) {
                console.error('Error al guardar director:', err);
                alert('Error de conexión al guardar el director. Intenta nuevamente.');
            })
            .finally(function () {
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.textContent = 'Guardar';
                }
            });
    }

    function cargarModalDesdeHidden() {
        if (!hiddenUsarManual || hiddenUsarManual.value !== '1') {
            return;
        }

        const nombre = normalizar(hiddenNombre ? hiddenNombre.value : '');
        const apellido = normalizar(hiddenApellido ? hiddenApellido.value : '');
        const fechaNac = hiddenFecha ? hiddenFecha.value : '';
        const biografia = hiddenBio ? hiddenBio.value : '';

        if (inputNombre) inputNombre.value = nombre;
        if (inputApellido) inputApellido.value = apellido;
        if (inputFecha) inputFecha.value = fechaNac;
        if (inputBio) inputBio.value = biografia;

        if (summary && nombre && apellido) {
            let detalle = `Director manual: ${nombre} ${apellido}`;
            if (fechaNac) {
                detalle += ` (Nac.: ${formatFecha(fechaNac)})`;
            }
            summary.textContent = detalle;
            summary.style.display = 'block';
        }
    }

    function renderDirectorHint(message) {
        if (!directorDropdown) {
            return;
        }
        directorDropdown.innerHTML = `<div class="combobox-empty">${message}</div>`;
        directorDropdown.style.display = 'block';
    }

    function renderDirectorOptions(options) {
        if (!directorDropdown) {
            return;
        }

        if (options.length === 0) {
            renderDirectorHint('No se encontraron directores');
            return;
        }

        directorDropdown.innerHTML = options
            .map((opt, idx) => `<div class="combobox-option" data-value="${opt.value}" data-index="${idx}">${opt.text}</div>`)
            .join('');

        directorDropdown.querySelectorAll('.combobox-option').forEach((node) => {
            node.addEventListener('click', function () {
                selectDirectorOption(this.dataset.value, this.textContent, true);
            });
        });

        directorDropdown.style.display = 'block';
    }

    function filterDirectorOptions(term) {
        const text = normalizar(term).toLowerCase();
        if (!text) {
            return directorOptions;
        }

        return directorOptions.filter((opt) => opt.text.toLowerCase().includes(text));
    }

    function selectDirectorOption(value, text, dispatchChange) {
        if (!selectDirector || !directorSearchInput) {
            return;
        }

        const normalizedValue = String(value || '');
        selectDirector.value = normalizedValue;
        directorSearchInput.value = text || '';
        directorSearchInput.classList.remove('invalid-input');

        lastValidDirectorText = text || '';
        directorSelectedIndex = -1;

        if (directorDropdown) {
            directorDropdown.style.display = 'none';
        }

        if (dispatchChange) {
            selectDirector.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function validateDirectorInput() {
        if (!selectDirector || !directorSearchInput) {
            return true;
        }

        if (hiddenUsarManual && hiddenUsarManual.value === '1') {
            directorSearchInput.classList.remove('invalid-input');
            return true;
        }

        const current = normalizar(directorSearchInput.value);
        if (!current) {
            selectDirector.value = '';
            directorSearchInput.classList.remove('invalid-input');
            return false;
        }

        const exact = directorOptions.find((opt) => opt.text.toLowerCase() === current.toLowerCase());
        if (exact) {
            selectDirector.value = exact.value;
            lastValidDirectorText = exact.text;
            directorSearchInput.value = exact.text;
            directorSearchInput.classList.remove('invalid-input');
            return true;
        }

        if (selectDirector.value) {
            const selected = directorOptions.find((opt) => opt.value === String(selectDirector.value));
            if (selected) {
                directorSearchInput.value = selected.text;
                lastValidDirectorText = selected.text;
                directorSearchInput.classList.remove('invalid-input');
                return true;
            }
        }

        selectDirector.value = '';
        directorSearchInput.classList.add('invalid-input');
        return false;
    }

    function syncDirectorInputFromSelect() {
        if (!selectDirector || !directorSearchInput) {
            return;
        }

        if (!selectDirector.value) {
            if (!hiddenUsarManual || hiddenUsarManual.value !== '1') {
                directorSearchInput.value = '';
                lastValidDirectorText = '';
            }
            return;
        }

        const selectedOption = Array.from(selectDirector.options).find((opt) => opt.value === String(selectDirector.value));
        if (selectedOption) {
            directorSearchInput.value = selectedOption.text.trim();
            lastValidDirectorText = directorSearchInput.value;
            directorSearchInput.classList.remove('invalid-input');
        }
    }

    function setupDirectorCombobox() {
        if (!directorSearchInput || !directorDropdown || !selectDirector) {
            return;
        }

        buildDirectorOptions();
        syncDirectorInputFromSelect();

        if (selectDirector.disabled) {
            directorSearchInput.disabled = true;
            if (btnOpen) {
                btnOpen.disabled = true;
            }
            return;
        }

        directorSearchInput.addEventListener('focus', function () {
            const term = normalizar(directorSearchInput.value);
            if (term.length < 3) {
                renderDirectorHint('Escribe al menos 3 letras para buscar...');
                return;
            }
            renderDirectorOptions(filterDirectorOptions(term));
        });

        directorSearchInput.addEventListener('input', function () {
            if (hiddenUsarManual && hiddenUsarManual.value === '1') {
                limpiarManual();
            }

            const term = normalizar(directorSearchInput.value);
            directorSelectedIndex = -1;

            if (!term) {
                selectDirector.value = '';
                directorSearchInput.classList.remove('invalid-input');
                if (directorDropdown) {
                    directorDropdown.style.display = 'none';
                }
                return;
            }

            if (term.length < 3) {
                selectDirector.value = '';
                renderDirectorHint('Escribe al menos 3 letras para buscar...');
                return;
            }

            renderDirectorOptions(filterDirectorOptions(term));
            validateDirectorInput();
        });

        directorSearchInput.addEventListener('blur', function () {
            setTimeout(function () {
                if (directorDropdown.contains(document.activeElement)) {
                    return;
                }

                const valid = validateDirectorInput();
                if (!valid && directorSearchInput.value.trim()) {
                    if (lastValidDirectorText) {
                        directorSearchInput.value = lastValidDirectorText;
                        const exact = directorOptions.find((opt) => opt.text === lastValidDirectorText);
                        selectDirector.value = exact ? exact.value : '';
                        directorSearchInput.classList.remove('invalid-input');
                    }
                }

                directorDropdown.style.display = 'none';
                directorSelectedIndex = -1;
            }, 150);
        });

        directorSearchInput.addEventListener('keydown', function (event) {
            const nodes = directorDropdown.querySelectorAll('.combobox-option');
            if (!nodes.length) {
                return;
            }

            if (event.key === 'ArrowDown') {
                event.preventDefault();
                directorSelectedIndex = Math.min(directorSelectedIndex + 1, nodes.length - 1);
                updateActiveDirectorNode(nodes);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                directorSelectedIndex = Math.max(directorSelectedIndex - 1, 0);
                updateActiveDirectorNode(nodes);
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (directorSelectedIndex >= 0 && nodes[directorSelectedIndex]) {
                    const node = nodes[directorSelectedIndex];
                    selectDirectorOption(node.dataset.value, node.textContent, true);
                }
            } else if (event.key === 'Escape') {
                directorDropdown.style.display = 'none';
                directorSelectedIndex = -1;
            }
        });

        selectDirector.addEventListener('change', function () {
            buildDirectorOptions();
            if (selectDirector.value) {
                syncDirectorInputFromSelect();
                limpiarManual();
            }
        });

        document.addEventListener('click', function (event) {
            if (!directorSearchInput.contains(event.target) && !directorDropdown.contains(event.target)) {
                directorDropdown.style.display = 'none';
                directorSelectedIndex = -1;
            }
        });

        if (form) {
            form.addEventListener('submit', function (event) {
                if (hiddenUsarManual && hiddenUsarManual.value === '1') {
                    return;
                }

                const valid = validateDirectorInput();
                if (!selectDirector.value || !valid) {
                    event.preventDefault();
                    directorSearchInput.classList.add('invalid-input');
                    directorSearchInput.focus();
                    alert('Debes seleccionar un director válido de la lista o crear uno nuevo.');
                }
            });
        }
    }

    function updateActiveDirectorNode(nodes) {
        nodes.forEach(function (node, idx) {
            node.classList.toggle('active', idx === directorSelectedIndex);
        });

        if (nodes[directorSelectedIndex]) {
            nodes[directorSelectedIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    function init() {
        if (!modal) {
            return;
        }

        const tituloInput = document.getElementById('id_titulo');
        if (tituloInput) {
            tituloInput.setAttribute('title', 'El titulo es obligatorio (1-200 caracteres). Puede ser numerico.');
        }

        cargarModalDesdeHidden();
        setupDirectorCombobox();

        if (btnOpen) {
            btnOpen.addEventListener('click', openModal);
        }

        if (btnClose) {
            btnClose.addEventListener('click', closeModal);
        }

        if (btnCancel) {
            btnCancel.addEventListener('click', closeModal);
        }

        if (btnSave) {
            btnSave.addEventListener('click', aplicarManualDesdeModal);
        }

        if (modal) {
            modal.addEventListener('click', function (event) {
                if (event.target === modal) {
                    closeModal();
                }
            });
        }

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });

        window.clearManualDirectorSelection = limpiarManual;
        window.syncDirectorSearchFromSelect = syncDirectorInputFromSelect;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
