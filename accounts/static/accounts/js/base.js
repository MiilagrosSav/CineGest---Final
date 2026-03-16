document.addEventListener('DOMContentLoaded', function() {
    
    // --- 1. AUTO-OCULTAR MENSAJES (TOASTS) ---
    const notifications = document.querySelectorAll('.custom-toast');
    notifications.forEach(function(notification) {
        setTimeout(function() {
            notification.style.transition = "opacity 0.5s ease, transform 0.5s ease";
            notification.style.opacity = "0";
            notification.style.transform = "translateX(100px)";
            setTimeout(function() { notification.remove(); }, 500); 
        }, 10000); 
    });

    // --- 2. VALIDACIÓN DE INPUTS ---
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
            if (this.classList.contains('invalid') && this.validity.valid) {
                this.classList.add('valid');
                this.classList.remove('invalid');
            }
        });
    });

    // --- 3. LÓGICA DE MENÚS DESPLEGABLES (Usuario y Reportes) ---
    // Esta lógica ahora es compatible con el modo móvil
    function setupDropdown(buttonId, dropdownId) {
        const btn = document.getElementById(buttonId);
        const dropdown = document.getElementById(dropdownId);
        if (btn && dropdown) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                // Cerramos otros dropdowns abiertos
                document.querySelectorAll('.user-menu-dropdown').forEach(d => {
                    if (d !== dropdown) d.classList.remove('show');
                });
                dropdown.classList.toggle('show');
            });
        }
    }

    setupDropdown('userMenuButton', 'userMenuDropdown');
    setupDropdown('reportsMenuButton', 'reportsMenuDropdown');

    // Cerrar todos los dropdowns al hacer clic fuera
    document.addEventListener('click', function(e) {
        document.querySelectorAll('.user-menu-dropdown, .notif-dropdown').forEach(dropdown => {
            const btn = dropdown.parentElement.querySelector('button');
            if (!dropdown.contains(e.target) && !btn.contains(e.target)) {
                dropdown.classList.remove('show');
            }
        });
    });

    // --- 4. MENÚ MÓVIL (HAMBURGUESA) ---
    const mobileToggle = document.getElementById('mobileMenuToggle');
    const navContainer = document.getElementById('navContainer');
    
    if (mobileToggle && navContainer) {
        mobileToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            navContainer.classList.toggle('active');
            this.classList.toggle('open');
            
            if (navContainer.classList.contains('active')) {
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = 'auto';
            }
        });
    }

    // --- 5. NOTIFICACIONES (CAMPANA) ---
    const notifBellBtn = document.getElementById('notifBellBtn');
    const notifDropdown = document.getElementById('notifDropdown');
    const notifList = document.getElementById('notifList');
    const markAllReadBtn = document.getElementById('markAllReadBtn');
    
    if (notifBellBtn && notifDropdown && notifList) {
        notifBellBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (!notifDropdown.classList.contains('show')) {
                cargarNotificaciones();
                notifDropdown.classList.add('show');
            } else {
                notifDropdown.classList.remove('show');
            }
        });

        if (markAllReadBtn) {
            markAllReadBtn.addEventListener('click', marcarTodasLeidas);
        }

        async function cargarNotificaciones() {
            notifList.innerHTML = '<div class="notif-loading">Cargando...</div>';
            try {
                const response = await fetch('/valoraciones/notificaciones/', {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await response.json();
                if (data.success && data.notificaciones.length > 0) {
                    mostrarNotificaciones(data.notificaciones);
                } else {
                    notifList.innerHTML = '<div class="notif-empty">No tienes notificaciones</div>';
                }
            } catch (error) {
                notifList.innerHTML = '<div class="notif-empty">Error al cargar</div>';
            }
        }

        function mostrarNotificaciones(notificaciones) {
            notifList.innerHTML = '';
            notificaciones.forEach(notif => {
                const item = document.createElement('div');
                item.className = 'notif-item' + (notif.leido ? '' : ' no-leido');
                item.innerHTML = `
                    <div class="notif-item-title"><span>⭐</span><span>${notif.pelicula_titulo}</span></div>
                    <div class="notif-item-msg">${notif.mensaje}</div>
                    <div class="notif-item-time">${notif.fecha}</div>
                `;
                item.addEventListener('click', () => abrirModalValoracion(notif.id, notif.funcion_id));
                notifList.appendChild(item);
            });
        }

        async function marcarTodasLeidas() {
            const response = await fetch('/valoraciones/notificaciones/leer-todas/', {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') }
            });
            const data = await response.json();
            if (data.success) { actualizarBadge(0); cargarNotificaciones(); }
        }

        async function abrirModalValoracion(notifId, funcionId) {
            const response = await fetch(`/valoraciones/notificaciones/${notifId}/leer/`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') }
            });
            if (response.ok) {
                const data = await response.json();
                actualizarBadge(data.count_no_leidas);
            }
            window.location.href = `/valoraciones/modal/?funcion_id=${funcionId}`;
        }

        function actualizarBadge(count) {
            const badge = notifBellBtn.querySelector('.notif-badge');
            if (count > 0) {
                if (badge) badge.textContent = count;
                else {
                    const b = document.createElement('span');
                    b.className = 'notif-badge'; b.textContent = count;
                    notifBellBtn.appendChild(b);
                }
            } else if (badge) badge.remove();
        }

        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
    }
});