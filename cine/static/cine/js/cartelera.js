let funcionIdSeleccionada = null;
let intercambioVentaId = '';
let peliculasData = {};

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
        // Si estamos en modo intercambio (se pasó intercambio_for), redirigir al selector en modo intercambio
        if (intercambioVentaId && intercambioVentaId.length > 0) {
            window.location.href = `/ventas/seleccionar-butacas/intercambio/${intercambioVentaId}/${funcionIdSeleccionada}/`;
            return;
        }
        // Redirigir a la página de selección de butacas (compra normal)
        window.location.href = `/ventas/seleccionar-butacas/${funcionIdSeleccionada}/`;
    }
}

function mostrarDetallesPelicula(peliculaId) {
    const pelicula = peliculasData[peliculaId];
    if (!pelicula) return;
    
    const contenido = `
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
        
        <div style="background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 6px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">
            <span style="font-size: 1.5rem; display: block; margin-bottom: 0.3rem;">🎥</span>
            <span>Tráiler no disponible</span>
        </div>
    `;
    
    document.getElementById('detallesContenido').innerHTML = contenido;
    document.getElementById('popupDetalles').style.display = 'flex';
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

    // Event listeners para botones de compra
    document.querySelectorAll('.btn-compra').forEach(function(btn) {
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
