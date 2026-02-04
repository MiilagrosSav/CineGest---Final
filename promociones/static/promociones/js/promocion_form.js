document.addEventListener('DOMContentLoaded', function() {
    const tipoSelect = document.getElementById('id_tipo_descuento');
    const valorGroup = document.getElementById('valor-descuento-group');
    const valorInput = document.getElementById('id_valor_descuento');
    const helpText = document.getElementById('valor-help-text');
    
    // Controlar visibilidad del campo valor_descuento según tipo
    function actualizarCampoValor() {
        if (!tipoSelect || !valorGroup || !valorInput) return;

        const tipo = tipoSelect.value;
        
        if (tipo === '2X1') {
            valorGroup.style.display = 'none';
            valorInput.value = '';
            valorInput.removeAttribute('required');
        } else {
            valorGroup.style.display = 'block';
            valorInput.setAttribute('required', 'required');
            
            if (helpText) {
                if (tipo === 'PORCENTAJE') {
                    helpText.textContent = '💡 Ingrese un porcentaje entre 0 y 100 (ej: 20 para 20% de descuento)';
                    valorInput.setAttribute('max', '100');
                    valorInput.setAttribute('min', '0');
                } else if (tipo === 'MONTO_FIJO') {
                    helpText.textContent = '💡 Ingrese el monto fijo de descuento en pesos (ej: 500)';
                    valorInput.removeAttribute('max');
                    valorInput.setAttribute('min', '0');
                }
            }
        }
    }
    
    if (tipoSelect) {
        tipoSelect.addEventListener('change', actualizarCampoValor);
        actualizarCampoValor();
    }

    // Controlar visibilidad de la sección automática según es_automatica
    const checkboxAutomatica = document.getElementById('id_es_automatica');
    const seccionAutomatica = document.getElementById('config-automatica');

    function toggleSeccionAutomatica() {
        if (checkboxAutomatica && seccionAutomatica) {
            if (checkboxAutomatica.checked) {
                seccionAutomatica.style.display = 'block';
            } else {
                seccionAutomatica.style.display = 'none';
                // Si se desactiva automática, también desactivar vínculos
                const toggleVinculos = document.getElementById('toggle-vinculos-especificos');
                if (toggleVinculos && toggleVinculos.checked) {
                    toggleVinculos.checked = false;
                    toggleVinculosEspecificos();
                }
            }
        }
    }

    // Controlar expansión de la sección de vínculos específicos con animación suave
    const toggleVinculos = document.getElementById('toggle-vinculos-especificos');
    const seccionVinculos = document.getElementById('vinculos-section');

    function toggleVinculosEspecificos() {
        if (!toggleVinculos || !seccionVinculos) return;

        if (toggleVinculos.checked) {
            // Expandir con animación
            seccionVinculos.style.display = 'block';
            // Forzar reflow para que la transición funcione
            seccionVinculos.offsetHeight;
            seccionVinculos.style.maxHeight = '2000px';  // Altura suficiente para el contenido
            seccionVinculos.style.opacity = '1';
        } else {
            // Colapsar con animación
            seccionVinculos.style.maxHeight = '0';
            seccionVinculos.style.opacity = '0';
            // Esperar que termine la animación antes de ocultar
            setTimeout(() => {
                if (!toggleVinculos.checked) {
                    seccionVinculos.style.display = 'none';
                }
            }, 400);  // Mismo tiempo que la transición CSS
        }
    }

    if (checkboxAutomatica) {
        checkboxAutomatica.addEventListener('change', toggleSeccionAutomatica);
        // Ejecutar al cargar para mostrar/ocultar según el estado inicial
        toggleSeccionAutomatica();
    }

    if (toggleVinculos) {
        toggleVinculos.addEventListener('change', toggleVinculosEspecificos);
        // Ejecutar al cargar
        toggleVinculosEspecificos();
    }

    // ============================================
    // GESTIÓN DE FORMSET DE VÍNCULOS
    // ============================================

    const vinculosContainer = document.getElementById('vinculos-container');
    const addVinculoBtn = document.getElementById('add-vinculo');
    const totalFormsInput = document.querySelector('#id_vinculos-TOTAL_FORMS');

    // Contador de formularios (empezar desde el número actual)
    let formIdx = vinculosContainer ? vinculosContainer.querySelectorAll('.vinculo-form-row').length : 0;

    // Función para agregar nuevo formulario de vínculo
    function addVinculoForm() {
        if (!vinculosContainer || !totalFormsInput) return;

        // Obtener el último formulario como template
        const lastForm = vinculosContainer.querySelector('.vinculo-form-row:last-child');
        if (!lastForm) return;

        // Clonar el formulario
        const newForm = lastForm.cloneNode(true);

        // Actualizar índices en el nuevo formulario
        const regex = /vinculos-(\d+)-/g;
        newForm.innerHTML = newForm.innerHTML.replace(regex, `vinculos-${formIdx}-`);

        // Limpiar valores de los campos
        const selects = newForm.querySelectorAll('select');
        selects.forEach(select => {
            select.selectedIndex = 0; // Resetear a opción vacía
        });

        // Limpiar errores
        const errorSpans = newForm.querySelectorAll('.form-error, .message-error');
        errorSpans.forEach(span => span.remove());

        // Remover el botón eliminar (solo para formularios nuevos)
        const deleteBtn = newForm.querySelector('.btn-remove-vinculo');
        if (deleteBtn) deleteBtn.remove();

        // Ocultar campo DELETE
        const deleteField = newForm.querySelector('input[name*="-DELETE"]');
        if (deleteField) {
            deleteField.checked = false;
            deleteField.parentElement.style.display = 'none';
        }

        // Actualizar data-form-index
        newForm.setAttribute('data-form-index', formIdx);

        // Agregar el nuevo formulario al contenedor
        vinculosContainer.appendChild(newForm);

        // Incrementar contador y actualizar TOTAL_FORMS
        formIdx++;
        totalFormsInput.value = formIdx;

        // Agregar listeners a los selectores del nuevo formulario
        attachVinculoListeners(newForm);
    }

    // Función para eliminar vínculo (marcar DELETE)
    function removeVinculoForm(btn) {
        const formRow = btn.closest('.vinculo-form-row');
        if (!formRow) return;

        const deleteField = formRow.querySelector('input[name*="-DELETE"]');
        
        if (deleteField) {
            // Marcar como eliminado
            deleteField.checked = true;
            // Ocultar visualmente
            formRow.style.display = 'none';
        } else {
            // Si no tiene campo DELETE, es un formulario nuevo que no se ha guardado
            // Simplemente removerlo del DOM
            formRow.remove();
            // Actualizar TOTAL_FORMS
            formIdx--;
            if (totalFormsInput) {
                totalFormsInput.value = formIdx;
            }
        }
    }

    // Función para validar que solo un campo esté seleccionado (película O función)
    function attachVinculoListeners(formRow) {
        const peliculaSelect = formRow.querySelector('select[name*="-pelicula"]');
        const funcionSelect = formRow.querySelector('select[name*="-funcion"]');

        if (peliculaSelect && funcionSelect) {
            peliculaSelect.addEventListener('change', function() {
                if (this.value && funcionSelect.value) {
                    // Si se selecciona película, limpiar función
                    funcionSelect.selectedIndex = 0;
                }
            });

            funcionSelect.addEventListener('change', function() {
                if (this.value && peliculaSelect.value) {
                    // Si se selecciona función, limpiar película
                    peliculaSelect.selectedIndex = 0;
                }
            });
        }
    }

    // Listener para botón "Agregar Otro Vínculo"
    if (addVinculoBtn) {
        addVinculoBtn.addEventListener('click', addVinculoForm);
    }

    // Listeners para botones eliminar existentes
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-remove-vinculo') || e.target.closest('.btn-remove-vinculo')) {
            e.preventDefault();
            const btn = e.target.classList.contains('btn-remove-vinculo') ? e.target : e.target.closest('.btn-remove-vinculo');
            removeVinculoForm(btn);
        }
    });

    // Agregar listeners a formularios existentes al cargar
    if (vinculosContainer) {
        const existingForms = vinculosContainer.querySelectorAll('.vinculo-form-row');
        existingForms.forEach(form => attachVinculoListeners(form));
    }
});
