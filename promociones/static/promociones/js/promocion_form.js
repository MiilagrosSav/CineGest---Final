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
            }
        }
    }

    if (checkboxAutomatica) {
        checkboxAutomatica.addEventListener('change', toggleSeccionAutomatica);
        // Ejecutar al cargar para mostrar/ocultar según el estado inicial
        toggleSeccionAutomatica();
    }
});
