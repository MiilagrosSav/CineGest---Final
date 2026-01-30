document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    
    // Validación de fecha de estreno
    const fechaEstrenoInput = document.querySelector('input[name="fecha_estreno"]');
    if (fechaEstrenoInput) {
        // Setear mínimo al día de hoy si es nueva
        if (!fechaEstrenoInput.value) {
            const today = new Date().toISOString().split('T')[0];
            fechaEstrenoInput.min = today;
        }
        
        fechaEstrenoInput.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            const todayDate = new Date();
            todayDate.setHours(0, 0, 0, 0); 
            
            if (selectedDate < todayDate) {
                this.setCustomValidity('La fecha de estreno no puede ser anterior a la fecha actual.');
                this.style.borderColor = '#ff6b6b';
            } else {
                this.setCustomValidity('');
                this.style.borderColor = '#4ecdc4'; // O el color de borde por defecto
            }
        });
    }
    
    // Validación al enviar
    form.addEventListener('submit', function(e) {
        const fechaEstreno = document.querySelector('input[name="fecha_estreno"]');
        if (fechaEstreno && fechaEstreno.value) {
            const selectedDate = new Date(fechaEstreno.value);
            const todayDate = new Date();
            todayDate.setHours(0, 0, 0, 0);
            
            if (selectedDate < todayDate) {
                e.preventDefault();
                alert('❌ La fecha de estreno no puede ser anterior a la fecha actual.');
                fechaEstreno.focus();
                return false;
            }
        }
    });
});
