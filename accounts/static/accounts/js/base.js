// Auto-ocultar mensajes (esto estaba bien)
        document.addEventListener('DOMContentLoaded', function() {
            const messages = document.querySelectorAll('.message');
            messages.forEach(message => {
                setTimeout(() => message.remove(), 5000);
            });
        });

        // (esto estaba bien)
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input[required], select[required], textarea[required]');
            
            inputs.forEach(input => {
                input.addEventListener('blur', function() {
                    if (this.validity.valid) {
                        this.classList.add('valid');
                        this.classList.remove('invalid');
                    } else {
                        this.classList.add('invalid');
                        this.classList.remove('valid');
                    }
                });
                
                input.addEventListener('input', function() {
                    if (this.classList.contains('invalid')) {
                        if (this.validity.valid) {
                            this.classList.add('valid');
                            this.classList.remove('invalid');
                        }
                    }
                });
            });
        });

        // ✅ MENÚ DESPLEGABLE DE USUARIO
        document.addEventListener('DOMContentLoaded', function() {
            const userMenuButton = document.getElementById('userMenuButton');
            const userMenuDropdown = document.getElementById('userMenuDropdown');
            
            if (userMenuButton && userMenuDropdown) {
                // Toggle del menú al hacer clic en el botón
                userMenuButton.addEventListener('click', function(e) {
                    e.stopPropagation();
                    userMenuDropdown.classList.toggle('show');
                });
                
                // Cerrar el menú al hacer clic fuera de él
                document.addEventListener('click', function(e) {
                    if (!userMenuButton.contains(e.target) && !userMenuDropdown.contains(e.target)) {
                        userMenuDropdown.classList.remove('show');
                    }
                });
            }
        });

        // ✅ MENÚ DESPLEGABLE DE REPORTES
        document.addEventListener('DOMContentLoaded', function() {
            const reportsMenuButton = document.getElementById('reportsMenuButton');
            const reportsMenuDropdown = document.getElementById('reportsMenuDropdown');
            if (reportsMenuButton && reportsMenuDropdown) {
                reportsMenuButton.addEventListener('click', function(e) {
                    e.stopPropagation();
                    reportsMenuDropdown.classList.toggle('show');
                });
                document.addEventListener('click', function(e) {
                    if (!reportsMenuButton.contains(e.target) && !reportsMenuDropdown.contains(e.target)) {
                        reportsMenuDropdown.classList.remove('show');
                    }
                });
            }
        });