document.addEventListener('DOMContentLoaded', function() {
    
    // --- SCRIPT DE CUIL/CUIT MEJORADO ---
    // Selecciona el input renderizado por Django
    const cuilInput = document.querySelector('input[name="cuil_cuit"]');
    if (cuilInput) {
        // Le pone un maxlength por JS por si no lo tiene en el form de Django
        cuilInput.setAttribute('maxlength', '13'); 
        
        cuilInput.addEventListener('input', function(e) {
            // Limpia todo menos los números
            let value = e.target.value.replace(/[^\d]/g, ''); 
            let output = '';
            
            // Re-construye el formato XX-XXXXXXXX-X
            if (value.length > 2) {
                output = value.substring(0, 2) + '-';
                if (value.length > 10) {
                    output += value.substring(2, 10) + '-' + value.substring(10, 11);
                } else if (value.length > 2) {
                    output += value.substring(2, 10);
                }
            } else {
                output = value;
            }
            e.target.value = output;
        });
    }
    
    // Validación de horarios
    const horaApertura = document.querySelector('input[name="horario_apertura"]');
    const horaCierre = document.querySelector('input[name="horario_cierre"]');
    
    if (horaApertura && horaCierre) {
        function validateHorarios() {
            if (horaApertura.value && horaCierre.value && horaCierre.value <= horaApertura.value) {
                horaCierre.setCustomValidity('El horario de cierre debe ser posterior al de apertura');
            } else {
                horaCierre.setCustomValidity('');
            }
        }
        horaApertura.addEventListener('change', validateHorarios);
        horaCierre.addEventListener('change', validateHorarios);
    }
    
    // Preview de logo
    const logoInput = document.querySelector('input[name="logo"]');
    if (logoInput) {
        logoInput.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    let preview = document.querySelector('.logo-mini');
                    if (!preview) { 
                        preview = document.createElement('div');
                        preview.className = 'logo-mini';
                        logoInput.parentElement.insertBefore(preview, logoInput); 
                    }
                    preview.innerHTML = `<img src="${event.target.result}" alt="Preview">`;
                };
                reader.readAsDataURL(e.target.files[0]);
            }
        });
    }
});
