document.addEventListener('DOMContentLoaded', function() {
    const tipoSelect = document.getElementById('id_tipo_descuento');
    const valorGroup = document.getElementById('valor-descuento-group');
    const valorInput = document.getElementById('id_valor_descuento');
    const helpText = document.getElementById('valor-help-text');
    
    // ============================================
    // VALIDACIÓN EN TIEMPO REAL (Feedback Visual)
    // ============================================
    
    // Referencias a campos del formulario
    const codigoInput = document.querySelector('input[name="codigo"]');
    const nombreInput = document.querySelector('input[name="nombre"]');
    const fechaInicioInput = document.querySelector('input[name="fecha_inicio"]');
    const fechaFinInput = document.querySelector('input[name="fecha_fin"]');
    const form = document.querySelector('form');
    
    // Función auxiliar para feedback visual
    function setFieldStatus(input, isValid, errorMsg = '') {
        if (!input) return;
        
        // Remover errores previos
        const existingError = input.parentElement.querySelector('.form-error-realtime');
        if (existingError) existingError.remove();
        
        if (isValid) {
            input.style.borderColor = '#4ecdc4';
            input.style.background = 'rgba(78, 205, 196, 0.1)';
            input.setCustomValidity('');
        } else {
            input.style.borderColor = '#ff6b6b';
            input.style.background = 'rgba(255, 107, 107, 0.1)';
            input.setCustomValidity(errorMsg);
            
            // Agregar mensaje de error visual
            if (errorMsg) {
                const errorSpan = document.createElement('span');
                errorSpan.className = 'form-error form-error-realtime';
                errorSpan.textContent = '⚠️ ' + errorMsg;
                errorSpan.style.marginTop = '0.4rem';
                input.parentElement.appendChild(errorSpan);
            }
        }
    }
    
    // Validación de código (no vacío, sin espacios)
    if (codigoInput && !codigoInput.hasAttribute('readonly')) {
        codigoInput.addEventListener('input', function() {
            const value = this.value.trim();
            
            if (!value) {
                setFieldStatus(this, false, 'El código es obligatorio');
            } else if (value.includes(' ')) {
                setFieldStatus(this, false, 'El código no puede contener espacios');
            } else if (value.length < 3) {
                setFieldStatus(this, false, 'El código debe tener al menos 3 caracteres');
            } else {
                setFieldStatus(this, true);
            }
        });
    }
    
    // Validación de nombre (no vacío, longitud máxima)
    if (nombreInput) {
        nombreInput.addEventListener('input', function() {
            const value = this.value.trim();
            
            if (!value) {
                setFieldStatus(this, false, 'El nombre es obligatorio');
            } else if (value.length > 200) {
                setFieldStatus(this, false, 'El nombre no puede exceder 200 caracteres');
            } else {
                setFieldStatus(this, true);
            }
        });
    }
    
    // Validación de fechas
    function validarFechas() {
        if (!fechaInicioInput || !fechaFinInput) return;
        
        const fechaInicio = fechaInicioInput.value ? new Date(fechaInicioInput.value) : null;
        const fechaFin = fechaFinInput.value ? new Date(fechaFinInput.value) : null;
        const hoy = new Date();
        hoy.setHours(0, 0, 0, 0);
        
        // Validar fecha inicio
        if (fechaInicio) {
            if (fechaInicio < hoy && !fechaInicioInput.hasAttribute('readonly')) {
                setFieldStatus(fechaInicioInput, false, 'La fecha de inicio no puede ser anterior a hoy');
            } else {
                setFieldStatus(fechaInicioInput, true);
            }
        }
        
        // Validar fecha fin
        if (fechaFin && fechaInicio) {
            if (fechaFin < fechaInicio) {
                setFieldStatus(fechaFinInput, false, 'La fecha de fin no puede ser anterior a la fecha de inicio');
            } else {
                setFieldStatus(fechaFinInput, true);
            }
        } else if (fechaFin) {
            setFieldStatus(fechaFinInput, true);
        }
    }
    
    if (fechaInicioInput) {
        fechaInicioInput.addEventListener('change', validarFechas);
    }
    
    if (fechaFinInput) {
        fechaFinInput.addEventListener('change', validarFechas);
    }
    
    // Validación de valor descuento
    if (valorInput) {
        valorInput.addEventListener('input', function() {
            const tipo = tipoSelect ? tipoSelect.value : '';
            const value = parseFloat(this.value);
            
            // ✅ FIX: No validar si es 2x1 (readonly)
            if (tipo === '2X1') {
                setFieldStatus(this, true);
                return;
            }
            
            if (!this.value || isNaN(value)) {
                setFieldStatus(this, false, 'Ingrese un valor numérico válido');
            } else if (tipo === 'PORCENTAJE' && (value < 0 || value > 100)) {
                setFieldStatus(this, false, 'El porcentaje debe estar entre 0 y 100');
            } else if (tipo === 'MONTO_FIJO' && value < 0) {
                setFieldStatus(this, false, 'El monto no puede ser negativo');
            } else {
                setFieldStatus(this, true);
            }
        });
    }
    
    // Validación al submit
    if (form) {
        form.addEventListener('submit', function(e) {
            let hasErrors = false;
            
            // Validar código
            if (codigoInput && !codigoInput.hasAttribute('readonly')) {
                const codigoValue = codigoInput.value.trim();
                if (!codigoValue || codigoValue.length < 3 || codigoValue.includes(' ')) {
                    hasErrors = true;
                    codigoInput.focus();
                }
            }
            
            // Validar nombre
            if (nombreInput && !nombreInput.value.trim()) {
                hasErrors = true;
                if (!hasErrors) nombreInput.focus();
            }
            
            // Validar fechas
            if (fechaInicioInput && fechaFinInput) {
                const fechaInicio = new Date(fechaInicioInput.value);
                const fechaFin = new Date(fechaFinInput.value);
                
                if (fechaFin < fechaInicio) {
                    hasErrors = true;
                    alert('❌ La fecha de fin no puede ser anterior a la fecha de inicio');
                    fechaFinInput.focus();
                    e.preventDefault();
                    return false;
                }
            }
            
            // Validar valor descuento
            const tipo = tipoSelect ? tipoSelect.value : '';
            if (tipo !== '2X1' && valorInput) {
                const value = parseFloat(valorInput.value);
                if (isNaN(value) || (tipo === 'PORCENTAJE' && (value < 0 || value > 100))) {
                    hasErrors = true;
                    alert('❌ Revise el valor del descuento');
                    valorInput.focus();
                    e.preventDefault();
                    return false;
                }
            }
            
            if (hasErrors) {
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Controlar visibilidad del campo valor_descuento según tipo
    function actualizarCampoValor() {
        if (!tipoSelect || !valorGroup || !valorInput) return;

        const tipo = tipoSelect.value;
        
        if (tipo === '2X1') {
            // ✅ FIX: Para 2x1, mostrar el campo pero con valor 50 y readonly
            valorGroup.style.display = 'block';
            valorInput.value = '50';
            valorInput.setAttribute('readonly', 'readonly');
            valorInput.removeAttribute('required'); // No es necesario marcar required porque siempre tiene valor
            valorInput.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
            valorInput.style.cursor = 'not-allowed';
            
            if (helpText) {
                helpText.textContent = '💡 2x1 equivale a 50% de descuento (se aplica automáticamente el segundo producto a mitad de precio)';
                helpText.style.color = '#4ecdc4';
            }
        } else {
            // Para otros tipos, habilitar el campo
            valorGroup.style.display = 'block';
            valorInput.removeAttribute('readonly');
            valorInput.setAttribute('required', 'required');
            valorInput.style.backgroundColor = '';
            valorInput.style.cursor = '';
            
            // Limpiar el valor solo si venimos de 2x1
            if (valorInput.value === '50') {
                valorInput.value = '';
            }
            
            if (helpText) {
                helpText.style.color = '';
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
