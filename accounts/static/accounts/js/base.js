// Auto-ocultar mensajes (esto estaba bien)
        // Esperar a que el documento esté cargado
        document.addEventListener('DOMContentLoaded', function() {
            // Seleccionar todas las notificaciones (toasts)
            const notifications = document.querySelectorAll('.custom-toast');

            notifications.forEach(function(notification) {
                // 1. Definir el tiempo de espera (5000ms = 5 segundos)
                setTimeout(function() {
                    // 2. Aplicar una transición de salida (opacidad y movimiento)
                    notification.style.transition = "opacity 0.5s ease, transform 0.5s ease";
                    notification.style.opacity = "0";
                    notification.style.transform = "translateX(100px)";

                    // 3. Eliminar el elemento del DOM después de que termine la animación
                    setTimeout(function() {
                        notification.remove();
                    }, 500); 
                }, 5000); 
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

// ✅ NOTIFICACIONES - CAMPANA
document.addEventListener('DOMContentLoaded', function() {
    const notifBellBtn = document.getElementById('notifBellBtn');
    const notifDropdown = document.getElementById('notifDropdown');
    const notifList = document.getElementById('notifList');
    const markAllReadBtn = document.getElementById('markAllReadBtn');
    
    if (!notifBellBtn || !notifDropdown || !notifList) return;
    
    // Toggle dropdown
    notifBellBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        const isVisible = notifDropdown.classList.contains('show');
        
        if (!isVisible) {
            // Cargar notificaciones
            cargarNotificaciones();
            notifDropdown.classList.add('show');
        } else {
            notifDropdown.classList.remove('show');
        }
    });
    
    // Cerrar dropdown al hacer clic fuera
    document.addEventListener('click', function(e) {
        if (!notifBellBtn.contains(e.target) && !notifDropdown.contains(e.target)) {
            notifDropdown.classList.remove('show');
        }
    });
    
    // Marcar todas como leídas
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', function() {
            marcarTodasLeidas();
        });
    }
    
    // Función para cargar notificaciones
    async function cargarNotificaciones() {
        notifList.innerHTML = '<div class="notif-loading">Cargando...</div>';
        
        try {
            const response = await fetch('/valoraciones/notificaciones/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) throw new Error('Error al cargar notificaciones');
            
            const data = await response.json();
            
            if (data.success && data.notificaciones.length > 0) {
                mostrarNotificaciones(data.notificaciones);
            } else {
                notifList.innerHTML = '<div class="notif-empty">No tienes notificaciones</div>';
            }
        } catch (error) {
            console.error('Error:', error);
            notifList.innerHTML = '<div class="notif-empty">Error al cargar notificaciones</div>';
        }
    }
    
    // Función para mostrar notificaciones
    function mostrarNotificaciones(notificaciones) {
        notifList.innerHTML = '';
        
        notificaciones.forEach(notif => {
            const item = document.createElement('div');
            item.className = 'notif-item' + (notif.leido ? '' : ' no-leido');
            item.dataset.notifId = notif.id;
            item.dataset.funcionId = notif.funcion_id;
            
            item.innerHTML = `
                <div class="notif-item-title">
                    <span class="notif-item-icon">⭐</span>
                    <span>${notif.pelicula_titulo}</span>
                </div>
                <div class="notif-item-msg">${notif.mensaje}</div>
                <div class="notif-item-time">${notif.fecha}</div>
            `;
            
            item.addEventListener('click', function() {
                abrirModalValoracion(notif.id, notif.funcion_id);
            });
            
            notifList.appendChild(item);
        });
    }
    
    // Función para marcar todas como leídas
    async function marcarTodasLeidas() {
        try {
            const response = await fetch('/valoraciones/notificaciones/leer-todas/', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
            
            if (!response.ok) throw new Error('Error');
            
            const data = await response.json();
            if (data.success) {
                // Actualizar contador
                actualizarBadge(0);
                // Recargar notificaciones
                cargarNotificaciones();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
    
    // Función para abrir modal de valoración
    async function abrirModalValoracion(notifId, funcionId) {
        // Marcar como leída
        try {
            const response = await fetch(`/valoraciones/notificaciones/${notifId}/leer/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                actualizarBadge(data.count_no_leidas);
            }
        } catch (error) {
            console.error('Error:', error);
        }
        
        // Redirigir a la página de valoración
        window.location.href = `/valoraciones/modal/?funcion_id=${funcionId}`;
    }
    
    // Función para actualizar badge
    function actualizarBadge(count) {
        const badge = notifBellBtn.querySelector('.notif-badge');
        
        if (count > 0) {
            if (badge) {
                badge.textContent = count;
            } else {
                const newBadge = document.createElement('span');
                newBadge.className = 'notif-badge';
                newBadge.textContent = count;
                notifBellBtn.appendChild(newBadge);
            }
        } else {
            if (badge) badge.remove();
        }
    }
    
    // Función auxiliar para obtener CSRF token
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
});