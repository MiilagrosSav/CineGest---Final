document.addEventListener('DOMContentLoaded', function() {
    console.log('politica_form.js loaded');
    
    // ===== Botón Cancelar =====
    var btn = document.getElementById('btn-cancelar');
    if (btn) {
        btn.addEventListener('click', function() {
            var href = this.getAttribute('data-href');
            if (href) window.location.href = href;
        });
    }

    // ===== Toggle de Ocupación Automática (Yield Management) =====
    // Buscar el checkbox de múltiples formas para mayor robustez
    var yieldCheckbox = document.getElementById('id_activar_por_ocupacion');
    console.log('Search 1 - By ID id_activar_por_ocupacion:', yieldCheckbox);
    
    // Si no lo encuentra por ID, intentar por name
    if (!yieldCheckbox) {
        yieldCheckbox = document.querySelector('input[name="activar_por_ocupacion"]');
        console.log('Search 2 - By name activar_por_ocupacion:', yieldCheckbox);
    }
    
    // Tercera búsqueda: mostrar todos los checkboxes
    if (!yieldCheckbox) {
        var allCheckboxes = document.querySelectorAll('input[type="checkbox"]');
        console.log('All checkboxes in page:', allCheckboxes.length);
        for (var i = 0; i < allCheckboxes.length; i++) {
            console.log('Checkbox', i, '- ID:', allCheckboxes[i].id, 'Name:', allCheckboxes[i].name);
        }
    }
    
    var yieldCampos = document.getElementById('yield-campos');
    console.log('Container found:', !!yieldCampos);
    
    if (yieldCheckbox) {
        console.log('✓ Checkbox element details:');
        console.log('  - ID:', yieldCheckbox.id);
        console.log('  - Name:', yieldCheckbox.name);
        console.log('  - Type:', yieldCheckbox.type);
        console.log('  - Value:', yieldCheckbox.value);
        console.log('  - Checked:', yieldCheckbox.checked);
        console.log('  - Parent:', yieldCheckbox.parentElement.className);
    }
    
    if (yieldCheckbox && yieldCampos) {
        // Inicializar estilos del contenedor
        yieldCampos.style.transition = 'opacity 0.3s ease-in-out, max-height 0.3s ease-in-out, visibility 0.3s ease-in-out';
        yieldCampos.style.overflow = 'hidden';
        
        function toggleYieldCampos() {
            console.log('Toggle called. Checkbox checked:', yieldCheckbox.checked);
            
            if (yieldCheckbox.checked) {
                // Mostrar
                yieldCampos.style.display = 'block';
                yieldCampos.style.visibility = 'visible';
                yieldCampos.style.opacity = '1';
                yieldCampos.style.maxHeight = '500px';
                console.log('Showing yield-campos');
            } else {
                // Ocultar
                yieldCampos.style.opacity = '0';
                yieldCampos.style.maxHeight = '0px';
                yieldCampos.style.visibility = 'hidden';
                
                // No necesitamos setTimeout, la transición se encarga
                setTimeout(function() {
                    if (!yieldCheckbox.checked) {
                        yieldCampos.style.display = 'none';
                    }
                }, 300);
                console.log('Hiding yield-campos');
            }
        }
        
        // Estado inicial: evaluar el estado actual del checkbox
        console.log('Initial checkbox state:', yieldCheckbox.checked);
        toggleYieldCampos();
        
        // Escuchar cambios del checkbox
        yieldCheckbox.addEventListener('change', function(e) {
            console.log('✓ [EVENT-CHANGE] Checkbox changed to:', e.target.checked);
            toggleYieldCampos();
        });
        
        // Escuchar también 'click' por si acaso
        yieldCheckbox.addEventListener('click', function(e) {
            console.log('✓ [EVENT-CLICK] Checkbox clicked, checked:', e.target.checked);
            toggleYieldCampos();
        });
        
        // Si el form tiene errores en umbral_ocupacion, mostrar el campo
        var umbralInput = document.querySelector('input.input-umbral');
        if (umbralInput) {
            var errorMsg = umbralInput.parentElement.querySelector('.form-error');
            if (errorMsg && errorMsg.textContent.trim()) {
                console.log('Umbral error found, forcing checkbox ON');
                yieldCheckbox.checked = true;
                toggleYieldCampos();
            }
        }
    } else {
        console.warn('Yield Management: checkbox or container not found');
    }
});
