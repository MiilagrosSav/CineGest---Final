/**
 * TMDB Integration para formulario de películas
 * Maneja la búsqueda de películas en The Movie Database y auto-completado del formulario
 */

(function() {
    'use strict';

    // Elementos del DOM
    const btnSearchTMDB = document.getElementById('btn-search-tmdb');
    const inputTitulo = document.getElementById('id_titulo');
    const tmdbModal = document.getElementById('tmdb-modal');
    const tmdbClose = document.getElementById('tmdb-close');
    const tmdbResultsContainer = document.getElementById('tmdb-results-container');
    const tmdbInfoBanner = document.getElementById('tmdb-info-banner');
    const tmdbPosterPreview = document.getElementById('tmdb-poster-preview');
    const tmdbPosterImg = document.getElementById('tmdb-poster-img');
    const peliculaForm = document.getElementById('pelicula-form');

    // Campos del formulario
    const formFields = {
        titulo: document.getElementById('id_titulo'),
        sinopsis: document.getElementById('id_sinopsis'),
        director: document.getElementById('id_director'),
        directorUsarManual: document.getElementById('id_director_usar_manual'),
        directorNombreManual: document.getElementById('id_director_nombre_manual'),
        directorApellidoManual: document.getElementById('id_director_apellido_manual'),
        directorFechaManual: document.getElementById('id_director_fecha_nacimiento_manual'),
        directorBioManual: document.getElementById('id_director_biografia_manual'),
        directorTmdbIdManual: document.getElementById('id_director_tmdb_id_manual'),
        duracion: document.getElementById('id_duracion'),
        fecha_estreno: document.getElementById('id_fecha_estreno'),
        clasificacion: document.getElementById('id_clasificacion'),
        imagenPortada: document.getElementById('id_imagen_portada'),
        youtubeTrailerKey: document.getElementById('id_youtube_trailer_key'),
        posterPath: document.getElementById('tmdb-poster-path'),
        movieId: document.getElementById('tmdb-movie-id')
    };
    const directorManualSummary = document.getElementById('director-manual-summary');

    // URLs de la API (usando reverse de Django desde el template)
    const API_URLS = {
        search: '/api/tmdb/search/',
        movieDetails: '/api/tmdb/movie/',
        importMovie: '/api/tmdb/import/'
    };

    /**
     * Obtiene el token CSRF de Django
     */
    function getCSRFToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }

    /**
     * Muestra el modal de búsqueda
     */
    function openModal() {
        tmdbModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    /**
     * Cierra el modal de búsqueda
     */
    function closeModal() {
        tmdbModal.classList.remove('active');
        document.body.style.overflow = '';
    }

    /**
     * Muestra el estado de carga en el modal
     */
    function showLoading() {
        tmdbResultsContainer.innerHTML = `
            <div class="tmdb-loading">
                <div class="tmdb-spinner"></div>
                <p>Buscando películas en TMDB...</p>
            </div>
        `;
    }

    /**
     * Muestra mensaje de error
     */
    function showError(message) {
        tmdbResultsContainer.innerHTML = `
            <div class="tmdb-no-results">
                <p style="font-size: 2rem; margin-bottom: 10px;">😕</p>
                <p><strong>Error</strong></p>
                <p>${message}</p>
            </div>
        `;
    }

    /**
     * Muestra mensaje cuando no hay resultados
     */
    function showNoResults(query) {
        tmdbResultsContainer.innerHTML = `
            <div class="tmdb-no-results">
                <p style="font-size: 2rem; margin-bottom: 10px;">🎬</p>
                <p><strong>No se encontraron resultados</strong></p>
                <p>No se encontraron películas con el título "${query}"</p>
                <p style="margin-top: 15px; font-size: 0.9rem; opacity: 0.7;">
                    Intenta con otro título o en inglés
                </p>
            </div>
        `;
    }

    /**
     * Formatea la fecha en formato legible
     */
    function formatDate(dateString) {
        if (!dateString) return 'Fecha desconocida';
        const date = new Date(dateString);
        return date.getFullYear();
    }

    function clearManualDirectorState() {
        if (formFields.directorUsarManual) formFields.directorUsarManual.value = '0';
        if (formFields.directorNombreManual) formFields.directorNombreManual.value = '';
        if (formFields.directorApellidoManual) formFields.directorApellidoManual.value = '';
        if (formFields.directorFechaManual) formFields.directorFechaManual.value = '';
        if (formFields.directorBioManual) formFields.directorBioManual.value = '';
        if (formFields.directorTmdbIdManual) formFields.directorTmdbIdManual.value = '';

        if (directorManualSummary) {
            directorManualSummary.textContent = '';
            directorManualSummary.style.display = 'none';
        }

        if (typeof window.clearManualDirectorSelection === 'function') {
            window.clearManualDirectorSelection();
        }
    }

    function seleccionarDirector(movieData) {
        if (!formFields.director || !movieData.director_id) {
            return;
        }

        const directorId = String(movieData.director_id);
        let option = formFields.director.querySelector(`option[value="${directorId}"]`);
        if (!option) {
            option = document.createElement('option');
            option.value = directorId;
            option.textContent = movieData.director || `Director ${directorId}`;
            formFields.director.appendChild(option);
        }

        formFields.director.value = directorId;
        clearManualDirectorState();
        formFields.director.dispatchEvent(new Event('change', { bubbles: true }));

        if (typeof window.syncDirectorSearchFromSelect === 'function') {
            window.syncDirectorSearchFromSelect();
        }
    }

    /**
     * Busca películas en TMDB
     */
    async function searchMovies(query) {
        try {
            showLoading();
            
            const url = `${API_URLS.search}?q=${encodeURIComponent(query)}`;
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error('Error al buscar películas');
            }

            const data = await response.json();

            if (!data.success) {
                showError(data.error || 'Error al buscar películas');
                return;
            }

            if (data.results.length === 0) {
                showNoResults(query);
                return;
            }

            displayResults(data.results);

        } catch (error) {
            console.error('Error en búsqueda TMDB:', error);
            showError('Error de conexión. Verifica tu conexión a internet.');
        }
    }

    /**
     * Muestra los resultados de búsqueda
     */
    function displayResults(movies) {
        const resultsHTML = movies.map(movie => {
            const posterUrl = movie.poster_path 
                ? `https://image.tmdb.org/t/p/w185${movie.poster_path}`
                : '/static/img/no-poster.jpg';
            
            const year = formatDate(movie.release_date);
            const overview = movie.overview || 'Sin sinopsis disponible';

            return `
                <div class="tmdb-movie-item" data-movie-id="${movie.id}">
                    <img src="${posterUrl}" 
                         alt="${movie.title}" 
                         class="tmdb-movie-poster"
                         onerror="this.src='/static/img/no-poster.jpg'">
                    <div class="tmdb-movie-info">
                        <div class="tmdb-movie-title">${movie.title}</div>
                        <div class="tmdb-movie-year">${year}</div>
                        <div class="tmdb-movie-overview">${overview}</div>
                    </div>
                </div>
            `;
        }).join('');

        tmdbResultsContainer.innerHTML = `
            <div class="tmdb-results">
                ${resultsHTML}
            </div>
        `;

        // Agregar event listeners a cada resultado
        document.querySelectorAll('.tmdb-movie-item').forEach(item => {
            item.addEventListener('click', function() {
                const movieId = this.getAttribute('data-movie-id');
                importMovieData(movieId);
            });
        });
    }

    /**
     * Importa los datos completos de una película
     */
    async function importMovieData(movieId) {
        try {
            // Mostrar loading en el modal
            showLoading();

            const url = `${API_URLS.importMovie}${movieId}/`;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Error al importar datos de la película');
            }

            const data = await response.json();

            if (!data.success) {
                showError(data.error || 'Error al importar película');
                return;
            }

            // Completar el formulario con los datos
            fillFormWithMovieData(data.movie);

            // Cerrar el modal
            closeModal();

            // Mostrar banner informativo
            if (tmdbInfoBanner) {
                tmdbInfoBanner.classList.add('active');
            }
            
            // Solo mostrar vista previa del póster si no hay imagen manual subida
            const hasManualImage = formFields.imagenPortada && formFields.imagenPortada.files && formFields.imagenPortada.files.length > 0;
            
            if (!hasManualImage && data.movie.poster_url && tmdbPosterPreview && tmdbPosterImg) {
                tmdbPosterImg.src = data.movie.poster_url;
                tmdbPosterPreview.classList.add('active');
            }
            
            // Scroll suave al inicio del formulario
            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (error) {
            console.error('Error al importar película:', error);
            showError('Error al importar los datos. Intenta nuevamente.');
        }
    }

    /**
     * Rellena el formulario con los datos de la película
     */
    function fillFormWithMovieData(movieData) {
        console.log('Rellenando formulario con datos:', movieData);

        // Completar campos básicos
        if (formFields.titulo && movieData.titulo) {
            formFields.titulo.value = movieData.titulo;
        }

        if (formFields.sinopsis && movieData.sinopsis) {
            formFields.sinopsis.value = movieData.sinopsis;
        }

        seleccionarDirector(movieData);

        if (formFields.duracion && movieData.duracion) {
            formFields.duracion.value = movieData.duracion;
        }

        if (formFields.fecha_estreno && movieData.fecha_estreno) {
            formFields.fecha_estreno.value = movieData.fecha_estreno;
        }

        // Completar la clasificación si se obtuvo desde TMDB
        if (formFields.clasificacion && movieData.clasificacion_id) {
            formFields.clasificacion.value = movieData.clasificacion_id;
            console.log(`Clasificación seleccionada: ${movieData.clasificacion} (ID: ${movieData.clasificacion_id})`);
        }

        // Completar el campo del trailer de YouTube
        if (formFields.youtubeTrailerKey) {
            formFields.youtubeTrailerKey.value = movieData.youtube_trailer_key || '';
        }

        // Guardar información del póster (para descargarlo al guardar)
        if (formFields.posterPath && movieData.poster_path) {
            formFields.posterPath.value = movieData.poster_path;
        }

        if (formFields.movieId) {
            formFields.movieId.value = movieData.id || '';
        }

        // Intentar seleccionar los géneros correspondientes
        if (movieData.generos && Array.isArray(movieData.generos)) {
            selectGenres(movieData.generos);
        }

        // Disparar eventos de cambio para activar validaciones
        Object.values(formFields).forEach(field => {
            if (field && field.dispatchEvent) {
                field.dispatchEvent(new Event('input', { bubbles: true }));
                field.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    /**
     * Selecciona los géneros que coincidan con los de TMDB
     */
    function selectGenres(tmdbGenres) {
        // Mapeo de géneros de TMDB a los géneros del sistema
        const genreMapping = {
            'Acción': ['accion', 'action'],
            'Aventura': ['aventura', 'adventure'],
            'Ciencia ficción': ['ciencia ficcion', 'sci-fi', 'science fiction'],
            'Comedia': ['comedia', 'comedy'],
            'Drama': ['drama'],
            'Fantasía': ['fantasia', 'fantasy'],
            'Terror': ['terror', 'horror'],
            'Romance': ['romance'],
            'Suspense': ['suspense', 'thriller'],
            'Animación': ['animacion', 'animation'],
            'Documental': ['documental', 'documentary'],
            'Musical': ['musical'],
            'Crimen': ['crimen', 'crime'],
            'Misterio': ['misterio', 'mystery'],
            'Western': ['western'],
            'Bélica': ['belica', 'war'],
            'Historia': ['historia', 'history']
        };

        // Obtener todos los checkboxes de géneros
        const genreCheckboxes = document.querySelectorAll('input[name="generos"]');
        
        genreCheckboxes.forEach(checkbox => {
            // Desmarcar todos primero
            checkbox.checked = false;

            // Obtener el label del checkbox
            const label = checkbox.parentElement?.textContent?.trim().toLowerCase() || '';

            // Verificar si algún género de TMDB coincide
            tmdbGenres.forEach(tmdbGenre => {
                const tmdbGenreLower = tmdbGenre.toLowerCase();
                
                // Buscar coincidencias en el mapeo
                for (const [localGenre, aliases] of Object.entries(genreMapping)) {
                    if (aliases.some(alias => 
                        tmdbGenreLower.includes(alias) || alias.includes(tmdbGenreLower)
                    )) {
                        if (label.includes(localGenre.toLowerCase())) {
                            checkbox.checked = true;
                        }
                    }
                }

                // Coincidencia directa
                if (label.includes(tmdbGenreLower) || tmdbGenreLower.includes(label)) {
                    checkbox.checked = true;
                }
            });
        });
    }

    /**
     * Maneja el click en el botón de búsqueda
     */
    function handleSearchClick() {
        const query = inputTitulo.value.trim();

        if (!query) {
            alert('Por favor, ingresa un título de película para buscar');
            inputTitulo.focus();
            return;
        }

        openModal();
        searchMovies(query);
    }

    /**
     * Inicializar eventos
     */
    function init() {
        // Evento para abrir modal de búsqueda
        if (btnSearchTMDB) {
            btnSearchTMDB.addEventListener('click', handleSearchClick);
        }

        // Eventos para cerrar modal
        if (tmdbClose) {
            tmdbClose.addEventListener('click', closeModal);
        }

        if (tmdbModal) {
            tmdbModal.addEventListener('click', function(e) {
                if (e.target === tmdbModal) {
                    closeModal();
                }
            });
        }

        // Permitir búsqueda con Enter en el campo título
        if (inputTitulo) {
            inputTitulo.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && e.ctrlKey) {
                    e.preventDefault();
                    handleSearchClick();
                }
            });
        }

        // Cerrar modal con tecla ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && tmdbModal.classList.contains('active')) {
                closeModal();
            }
        });

        console.log('🎬 TMDB Integration inicializada correctamente');
    }

    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
