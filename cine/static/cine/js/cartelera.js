let funcionIdSeleccionada = null;
let intercambioVentaId = '';
let peliculasData = {};
let offsetDias = 0; // Para controlar la navegación del carrusel

// Función de inicialización
function inicializarCartelera() {
    // Cargar intercambioVentaId desde el script inline
    const intercambioScript = document.getElementById('intercambioVentaIdScript');
    if (intercambioScript) {
        intercambioVentaId = intercambioScript.textContent.trim();
    }
    
    // Cargar datos de películas desde el JSON embebido
    const peliculasDataElement = document.getElementById('peliculasDataJson');
    peliculasData = peliculasDataElement ? JSON.parse(peliculasDataElement.textContent) : {};
    
    // Inicializar event listeners
    inicializarEventListeners();
    inicializarBusquedaExpandible();
}

// Ejecutar al cargar la página
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarCartelera);
} else {
    // El DOM ya está listo, ejecutar inmediatamente
    inicializarCartelera();
}

function navegarDias(dias) {
    offsetDias += dias;
    
    // Normalizar la fecha de hoy a medianoche
    const hoy = new Date();
    hoy.setHours(0, 0, 0, 0);
    
    // Obtener la fecha actual o la fecha seleccionada
    const params = new URLSearchParams(window.location.search);
    let fechaActual = params.get('dia');
    
    if (!fechaActual) {
        // Si no hay día seleccionado, usar hoy
        fechaActual = hoy.toISOString().split('T')[0];
    }
    
    // Calcular la nueva fecha
    const fecha = new Date(fechaActual + 'T00:00:00');
    fecha.setDate(fecha.getDate() + dias);
    
    const nuevaFecha = fecha.toISOString().split('T')[0];
    const fechaNavegada = new Date(nuevaFecha + 'T00:00:00');
    
    // 🛡️ PROTECCIÓN: No permitir navegar a fechas anteriores a HOY
    if (fechaNavegada < hoy) {
        console.log('⚠️ No se puede navegar a fechas pasadas (antes de hoy)');
        return; // Bloquear navegación hacia atrás
    }
    
    // Actualizar el parámetro 'dia' en la URL
    params.set('dia', nuevaFecha);
    
    // Redirigir con la nueva fecha
    window.location.search = params.toString();
}

function mostrarPopupCompra(pelicula, formato, fecha, hora, funcionId, clasificacion) {
    // Solo mostrar película, fecha y hora
    document.getElementById('popupPelicula').textContent = pelicula;
    document.getElementById('popupFecha').textContent = fecha;
    document.getElementById('popupHora').textContent = hora;
    funcionIdSeleccionada = funcionId;
    
    const popup = document.getElementById('popupCompra');
    popup.style.display = 'flex';
}

function cerrarPopupCompra() {
    document.getElementById('popupCompra').style.display = 'none';
    funcionIdSeleccionada = null;
}

function comprarEntrada() {
    if (funcionIdSeleccionada) {
        console.log('🎬 COMPRAR ENTRADA');
        console.log('   Función ID:', funcionIdSeleccionada);
        console.log('   Modo intercambio:', intercambioVentaId);
        console.log('   Intercambio venta ID:', intercambioVentaId);
        
        // Si estamos en modo intercambio (se pasó intercambio_for), redirigir al selector en modo intercambio
        if (intercambioVentaId && intercambioVentaId.length > 0) {
            const urlIntercambio = `/ventas/seleccionar-butacas/intercambio/${intercambioVentaId}/${funcionIdSeleccionada}/`;
            console.log('✅ Redirigiendo a INTERCAMBIO:', urlIntercambio);
            window.location.href = urlIntercambio;
            return;
        }
        // Redirigir a la página de selección de butacas (compra normal)
        const urlNormal = `/ventas/seleccionar-butacas/${funcionIdSeleccionada}/`;
        console.log('📝 Redirigiendo a COMPRA NORMAL:', urlNormal);
        window.location.href = urlNormal;
    }
}

function mostrarDetallesPelicula(peliculaId) {
    const pelicula = peliculasData[peliculaId];
    if (!pelicula) return;
    
    // Contenido inicial (sin comentarios aún)
    const contenidoBase = `
        <div style="display: grid; grid-template-columns: 140px 1fr; gap: 1rem; margin-bottom: 1rem;">
            ${pelicula.imagen ? 
                `<img src="${pelicula.imagen}" alt="${pelicula.titulo}" style="width: 100%; border-radius: 6px;">` :
                `<div style="width: 140px; height: 210px; background: linear-gradient(135deg, rgba(74, 144, 226, 0.2), rgba(155, 89, 182, 0.2)); border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 2.5rem;">🎬</span>
                </div>`
            }
            
            <div>
                <h3 style="color: var(--primary); margin-top: 0; margin-bottom: 0.7rem; font-size: 1.2rem;">${pelicula.titulo}</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.85rem;">
                    <div>
                        <span style="color: var(--text-secondary);">Género:</span>
                        <span style="color: var(--text-light);">${pelicula.genero}</span>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Duración:</span>
                        <span style="color: var(--text-light);">${pelicula.duracion} min</span>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Clasificación:</span>
                        <span style="color: var(--text-light);">${pelicula.clasificacion}</span>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Formato:</span>
                        <span style="color: var(--text-light);">${pelicula.formato}</span>
                    </div>
                </div>
                
                ${pelicula.director ? `
                <div style="margin-top: 0.5rem; font-size: 0.85rem;">
                    <span style="color: var(--text-secondary);">Director:</span>
                    <span style="color: var(--text-light);">${pelicula.director}</span>
                </div>` : ''}
                
                ${pelicula.fecha_estreno ? `
                <div style="margin-top: 0.5rem; font-size: 0.85rem;">
                    <span style="color: var(--text-secondary);">Estreno:</span>
                    <span style="color: var(--text-light);">${pelicula.fecha_estreno}</span>
                </div>` : ''}
            </div>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <div style="color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 0.3rem; text-transform: uppercase; letter-spacing: 0.5px;">Sinopsis</div>
            <p style="line-height: 1.5; color: var(--text-light); font-size: 0.9rem; margin: 0;">${pelicula.sinopsis || 'No disponible'}</p>
        </div>
        
        <div id="valoracionesContainer" style="margin-bottom: 1rem;">
            <div style="text-align: center; padding: 1rem;">
                <div style="display: inline-block; width: 20px; height: 20px; border: 2px solid var(--primary); border-top: 2px solid transparent; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <p style="color: var(--text-secondary); margin-top: 0.5rem; font-size: 0.85rem;">Cargando valoraciones...</p>
            </div>
        </div>
        
        <div style="background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 6px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">
            <span style="font-size: 1.5rem; display: block; margin-bottom: 0.3rem;">🎥</span>
            <span>Tráiler no disponible</span>
        </div>
    `;
    
    // Establecer contenido inicial
    document.getElementById('detallesContenido').innerHTML = contenidoBase;
    document.getElementById('popupDetalles').style.display = 'flex';
    
    // Cargar valoraciones via AJAX
    cargarValoraciones(peliculaId, 1);
}

function cargarValoraciones(peliculaId, page = 1) {
    fetch(`/valoraciones/pelicula/${peliculaId}/valoraciones/ajax/?page=${page}&page_size=5`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderizarValoraciones(data, peliculaId);
            } else {
                mostrarErrorValoraciones();
            }
        })
        .catch(error => {
            console.error('Error al cargar valoraciones:', error);
            mostrarErrorValoraciones();
        });
}

function renderizarValoraciones(data, peliculaId) {
    const container = document.getElementById('valoracionesContainer');
    if (!container) return;
    
    let html = `
        <div style="color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 0.5rem;">
            <span>⭐</span>
            <span>Reseñas de Espectadores</span>
            ${data.stats.total > 0 ? `<span style="color: var(--primary);">(${data.stats.promedio}/5 - ${data.stats.total} valoraciones)</span>` : ''}
        </div>
    `;
    
    if (data.valoraciones && data.valoraciones.length > 0) {
        html += `
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                ${data.valoraciones.map(val => `
                    <div style="
                        background: linear-gradient(135deg, rgba(139, 95, 191, 0.08), rgba(233, 69, 96, 0.05));
                        backdrop-filter: blur(10px);
                        -webkit-backdrop-filter: blur(10px);
                        padding: 0.8rem;
                        border-radius: 10px;
                        border-left: 3px solid var(--primary);
                        box-shadow: 0 4px 12px rgba(139, 95, 191, 0.1);
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <div style="
                                    width: 28px;
                                    height: 28px;
                                    border-radius: 50%;
                                    background: linear-gradient(135deg, var(--primary), rgba(233, 69, 96, 0.8));
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    color: white;
                                    font-weight: 600;
                                    font-size: 0.75rem;
                                ">${val.cliente.charAt(0).toUpperCase()}</div>
                                <span style="color: var(--primary); font-weight: 600; font-size: 0.85rem;">${val.cliente}</span>
                            </div>
                            <span style="color: #fbbf24; font-size: 0.9rem;">${'★'.repeat(val.puntuacion)}${'☆'.repeat(5 - val.puntuacion)}</span>
                        </div>
                        ${val.comentario ? `<p style="color: var(--text-light); font-size: 0.85rem; line-height: 1.4; margin: 0 0 0.3rem 0;">${val.comentario}</p>` : ''}
                        <span style="color: var(--text-secondary); font-size: 0.7rem;">📅 ${val.fecha}</span>
                    </div>
                `).join('')}
            </div>
        `;
        
        // Botones de paginación
        if (data.total_pages > 1) {
            html += `
                <div style="display: flex; justify-content: center; align-items: center; gap: 1.5rem; margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(139, 95, 191, 0.1);">
                    ${data.has_previous ? 
                        `<button onclick="cargarValoraciones(${peliculaId}, ${data.page - 1})" 
                                style="background: none; border: none; color: var(--primary); cursor: pointer; font-size: 0.9rem; padding: 0.2rem; transition: opacity 0.2s;"
                                onmouseover="this.style.opacity='0.6'; this.style.textDecoration='underline';"
                                onmouseout="this.style.opacity='1'; this.style.textDecoration='none';">
                            ←
                        </button>` : 
                        `<span style="color: transparent; font-size: 0.9rem; padding: 0.2rem;">← Anterior</span>`}
                    
                    <span style="color: var(--text-secondary); font-size: 0.75rem; font-weight: 500;">${data.page} / ${data.total_pages}</span>
                    
                    ${data.has_next ? 
                        `<button onclick="cargarValoraciones(${peliculaId}, ${data.page + 1})" 
                                style="background: none; border: none; color: var(--primary); cursor: pointer; font-size: 0.9rem; padding: 0.2rem; transition: opacity 0.2s;"
                                onmouseover="this.style.opacity='0.6'; this.style.textDecoration='underline';"
                                onmouseout="this.style.opacity='1'; this.style.textDecoration='none';">
                            →
                        </button>` : 
                        `<span style="color: transparent; font-size: 0.9rem; padding: 0.2rem;">Siguiente →</span>`}
                </div>
            `;
        }
        
        // Enlace para ver todas
        html += `
            <a href="/valoraciones/pelicula/${peliculaId}/comentarios/" 
               style="display: block; text-align: center; margin-top: 1rem; padding: 0.6rem; background: rgba(139, 95, 191, 0.2); border: 1px solid var(--primary); border-radius: 6px; color: var(--primary); text-decoration: none; font-weight: 600; transition: all 0.2s;"
               onmouseover="this.style.background='var(--primary)'; this.style.color='white';"
               onmouseout="this.style.background='rgba(139, 95, 191, 0.2)'; this.style.color='var(--primary)';">
                Ver todas las reseñas (${data.total}) →
            </a>
        `;
        
    } else {
        // Sin valoraciones
        html += `
            <div style="
                background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(139, 95, 191, 0.05));
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                padding: 2rem 1.5rem;
                border-radius: 10px;
                text-align: center;
                border: 1px dashed rgba(139, 95, 191, 0.2);
            ">
                <span style="font-size: 2.5rem; display: block; margin-bottom: 0.8rem; opacity: 0.3;">💬</span>
                <h4 style="color: var(--text-light); margin: 0 0 0.5rem 0; font-weight: 600;">Sé el primero en opinar</h4>
                <p style="color: var(--text-secondary); font-size: 0.85rem; margin: 0;">Comparte tu experiencia sobre esta película</p>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function mostrarErrorValoraciones() {
    const container = document.getElementById('valoracionesContainer');
    if (!container) return;
    
    container.innerHTML = `
        <div style="background: rgba(255,107,107,0.1); padding: 1rem; border-radius: 6px; text-align: center; color: #ff6b6b; font-size: 0.85rem; border: 1px solid rgba(255,107,107,0.3);">
            ⚠️ Error al cargar las valoraciones
        </div>
    `;
}

function cerrarPopupDetalles() {
    document.getElementById('popupDetalles').style.display = 'none';
}

function inicializarEventListeners() {
    // Cerrar popups al hacer clic fuera
    document.addEventListener('click', function(e) {
        if (e.target.id === 'popupCompra') {
            cerrarPopupCompra();
        }
        if (e.target.id === 'popupDetalles') {
            cerrarPopupDetalles();
        }
    });

    // Event listeners para imágenes de películas (mostrar detalles)
    document.querySelectorAll('.pelicula-imagen').forEach(function(elemento) {
        elemento.addEventListener('click', function() {
            const peliculaId = this.getAttribute('data-pelicula-id');
            mostrarDetallesPelicula(peliculaId);
        });
        
        // Efecto hover
        elemento.addEventListener('mouseenter', function() {
            const img = this.querySelector('img, div');
            if (img) img.style.transform = 'scale(1.05)';
        });
        
        elemento.addEventListener('mouseleave', function() {
            const img = this.querySelector('img, div');
            if (img) img.style.transform = 'scale(1)';
        });
    });

    // Event listeners para botones de compra (horarios)
    document.querySelectorAll('.horario-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const pelicula = this.getAttribute('data-pelicula');
            const formato = this.getAttribute('data-formato');
            const fecha = this.getAttribute('data-fecha');
            const hora = this.getAttribute('data-hora');
            const funcionId = this.getAttribute('data-funcion-id');
            const clasificacion = this.getAttribute('data-clasificacion');
            
            mostrarPopupCompra(pelicula, formato, fecha, hora, funcionId, clasificacion);
        });
    });

    // Event listeners para botones de popups
    document.getElementById('btnCancelarCompra').addEventListener('click', cerrarPopupCompra);
    document.getElementById('btnContinuarCompra').addEventListener('click', comprarEntrada);
    document.getElementById('btnCerrarDetalles').addEventListener('click', cerrarPopupDetalles);
}

function inicializarBusquedaExpandible() {
    const form = document.getElementById('filtrosForm');
    const searchContainer = document.getElementById('searchContainer');
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');

    searchBtn.addEventListener('click', function(e) {
        if (!searchContainer.classList.contains('active')) {
            e.preventDefault(); 
            searchContainer.classList.add('active');
            searchInput.focus();
        }
    });

    document.addEventListener('click', function(e) {
        if (!searchContainer.contains(e.target) && searchInput.value === '') {
             searchContainer.classList.remove('active');
        }
    });

    if (searchInput.value !== '') {
        searchContainer.classList.add('active');
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                form.submit();
            }
        });
    }
}
