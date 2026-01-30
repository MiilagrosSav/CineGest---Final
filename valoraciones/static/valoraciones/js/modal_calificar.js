document.addEventListener('DOMContentLoaded', function(){
    // Inicializar cada formulario de valoración
    document.querySelectorAll('.valoracion-form').forEach(form => {
        const stars = Array.from(form.querySelectorAll('.star'));
        const estrellasInput = form.querySelector('[name="estrellas"]');
        let selected = parseInt(estrellasInput.value) || 5;

        // Pintar estrellas
        function paint(upTo){
            stars.forEach(s => {
                const v = parseInt(s.getAttribute('data-value'));
                if (v <= upTo) {
                    s.classList.add('selected');
                } else {
                    s.classList.remove('selected');
                }
            });
        }

        paint(selected);

        // Eventos de estrellas
        stars.forEach(s => {
            s.addEventListener('mouseenter', () => {
                paint(parseInt(s.getAttribute('data-value')));
            });
            s.addEventListener('mouseleave', () => {
                paint(selected);
            });
            s.addEventListener('click', () => {
                selected = parseInt(s.getAttribute('data-value'));
                estrellasInput.value = selected;
                paint(selected);
                // Animación click
                s.style.transform = "scale(1.4)";
                setTimeout(() => s.style.transform = "", 200);
            });
        });

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

        // Submit AJAX
        form.addEventListener('submit', async function(e){
            e.preventDefault();
            const action = form.getAttribute('action');
            const formData = new FormData(form);
            const csrftoken = getCookie('csrftoken');

            if (!csrftoken) {
                console.error('No se encontró el token CSRF');
                mostrarPopupError('Error de configuración: token CSRF no disponible.');
                return;
            }

            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = 'Enviando...';
            submitBtn.disabled = true;

            try {
                const resp = await fetch(action, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrftoken
                    },
                    credentials: 'same-origin',
                    body: formData
                });

                // Verificar tipo de contenido
                const contentType = resp.headers.get('content-type') || '';
                if (!contentType.includes('application/json')) {
                    throw new Error('El servidor no devolvió JSON.');
                }

                const data = await resp.json();

                if (data && data.success) {
                    // Éxito: cerrar modal si existe
                    const modalEl = form.closest('.modal');
                    if (modalEl) {
                        if (typeof $ !== 'undefined' && $.fn.modal) {
                            $(modalEl).modal('hide');
                        } else {
                            modalEl.classList.remove('show');
                            modalEl.style.display = 'none';
                            const backdrop = document.querySelector('.modal-backdrop');
                            if (backdrop) backdrop.remove();
                            document.body.classList.remove('modal-open');
                            document.body.style.overflow = '';
                        }
                    }
                    mostrarPopupExito(data.message || '¡Gracias por tu valoración!', selected);
                } else {
                    const msg = data && data.message ? data.message : 'Error al enviar la valoración.';
                    mostrarPopupError(msg);
                }
            } catch (err) {
                console.error('Error de red:', err);
                mostrarPopupError('Error de red al enviar la valoración: ' + err.message);
            } finally {
                if(submitBtn) {
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                }
            }
        });
    });

    // Funciones de Popup
    window.mostrarPopupExito = function(mensaje, estrellas) {
        const overlay = document.createElement('div');
        overlay.className = 'success-popup-overlay';
        const estrellasHTML = '★'.repeat(estrellas) + '☆'.repeat(5 - estrellas);
        
        overlay.innerHTML = `
            <div class="success-popup">
                <div class="success-popup-icon">🎉</div>
                <div class="success-popup-title">¡Valoración enviada!</div>
                <div class="success-popup-message">${mensaje}</div>
                <div style="color: #fbbf24; font-size: 1.5rem; margin-bottom: 1.5rem;">${estrellasHTML}</div>
                <button class="success-popup-btn" onclick="window.location.reload()">Aceptar</button>
            </div>
        `;
        document.body.appendChild(overlay);
    };

    window.mostrarPopupError = function(mensaje) {
        const overlay = document.createElement('div');
        overlay.className = 'success-popup-overlay';
        overlay.innerHTML = `
            <div class="success-popup" style="background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%);">
                <div class="success-popup-icon">⚠️</div>
                <div class="success-popup-title">Error</div>
                <div class="success-popup-message">${mensaje}</div>
                <button class="success-popup-btn" style="color: #ff6b6b;" onclick="this.closest('.success-popup-overlay').remove()">Cerrar</button>
            </div>
        `;
        document.body.appendChild(overlay);
    };
});
