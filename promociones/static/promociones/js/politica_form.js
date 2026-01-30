document.addEventListener('DOMContentLoaded', function() {
    var btn = document.getElementById('btn-cancelar');
    if (btn) {
        btn.addEventListener('click', function() {
            var href = this.getAttribute('data-href');
            if (href) window.location.href = href;
        });
    }

    // Toggle de Yield Management
    var yieldCheckbox = document.getElementById('{{ form.activar_por_ocupacion.id_for_label }}');
    var yieldCampos = document.getElementById('yield-campos');
    
    function toggleYieldCampos() {
        if (yieldCheckbox && yieldCampos) {
            if (yieldCheckbox.checked) {
                yieldCampos.style.display = 'block';
            } else {
                yieldCampos.style.display = 'none';
            }
        }
    }
    
    // Estado inicial
    toggleYieldCampos();
    
    // Listener para cambios
    if (yieldCheckbox) {
        yieldCheckbox.addEventListener('change', toggleYieldCampos);
    }
});
