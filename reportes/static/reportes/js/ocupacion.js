// ===========================================
// OCUPACION.JS - Dashboard de Ocupación
// ===========================================

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    
    // ===========================================
    // 1. GRÁFICO DE OCUPACIÓN (Línea)
    // ===========================================
    const occ = window.ocupacionData.occ;
    const ctxOcc = document.getElementById('occChart');
    
    if (ctxOcc) {
        const ctx = ctxOcc.getContext('2d');
        
        let gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(139, 95, 191, 0.5)');
        gradient.addColorStop(1, 'rgba(139, 95, 191, 0.0)');

        // Determinar tipo de gráfico según cantidad de datos
        const isShortRange = occ.labels.length <= 3;
        const chartType = isShortRange ? 'bar' : 'line';

        window.occChart = new Chart(ctx, {
            type: chartType,
            data: { 
                labels: occ.labels, 
                datasets: [{ 
                    label: '% Ocupación', 
                    data: occ.values, 
                    borderColor: '#9B59B6', 
                    backgroundColor: isShortRange ? 'rgba(155, 89, 182, 0.6)' : gradient, 
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#ffffff',
                    pointBorderColor: '#9B59B6',
                    pointRadius: isShortRange ? 0 : 5,
                    pointHoverRadius: isShortRange ? 0 : 7
                }] 
            },
            options: {
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        color: '#ffffff', 
                        anchor: 'end', 
                        align: 'top', 
                        formatter: v => v ? v.toFixed(1) + '%' : '', 
                        font: { weight: 'bold', size: 11 },
                        offset: 4
                    }
                },
                scales: { 
                    y: { 
                        beginAtZero: true, 
                        max: 100, 
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#b0b0b0' } 
                    }, 
                    x: { 
                        grid: { display: false },
                        ticks: { color: '#b0b0b0' } 
                    } 
                },
                responsive: true, 
                maintainAspectRatio: false
            },
            plugins: [ChartDataLabels]
        });
    }

    // ===========================================
    // 2. GRÁFICO DE MARKETING (Donut) - OPCIONAL
    // ===========================================
    const ctxMarketing = document.getElementById('marketingDonut');
    if (ctxMarketing) {
        try {
            const marketingJsonRaw = window.ocupacionData.marketing;
            let mkt = {};
            try { mkt = JSON.parse(marketingJsonRaw || '{}'); } catch(e) { mkt = {}; }

            const donutData = (mkt && mkt.data && mkt.labels) ? mkt : { labels: ['Ignorados','Canjeados'], data: [1,0] };
            
            window.marketingChart = new Chart(ctxMarketing.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: donutData.labels,
                    datasets: [{
                        data: donutData.data,
                        backgroundColor: ['rgba(255,255,255,0.05)', '#9B59B6'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    cutout: '75%',
                    plugins: { legend: { display: false } },
                    responsive: true, 
                    maintainAspectRatio: false
                }
            });
        } catch(e) { 
            console.warn('Marketing donut chart not available:', e.message); 
        }
    }

    // ===========================================
    // 3. EXPORTACIÓN A PDF
    // ===========================================
    const exportBtn = document.getElementById('exportPdfBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', async function(){
            const btn = this;
            const originalText = btn.innerText;
            btn.innerText = '⏳ Generando...';
            btn.disabled = true;

            try {
                // Capturar imagen del gráfico de ocupación
                const chartImage = window.occChart ? window.occChart.toBase64Image() : null;
                
                // Capturar imagen del gráfico de marketing (si existe)
                let marketingImage = null;
                if (window.marketingChart && window.marketingChart.canvas) {
                    try {
                        const origCanvas = window.marketingChart.canvas;
                        // Temporalmente mejorar colores para el PDF
                        const oldColors = window.marketingChart.data.datasets[0].backgroundColor;
                        window.marketingChart.data.datasets[0].backgroundColor = ['#f2f2f2', '#9B59B6'];
                        window.marketingChart.update();
                        
                        // Capturar imagen
                        const img = new Image();
                        img.src = window.marketingChart.toBase64Image();
                        await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
                        
                        // Crear canvas de alta resolución
                        const scale = 2;
                        const tmp = document.createElement('canvas');
                        tmp.width = origCanvas.width * scale;
                        tmp.height = origCanvas.height * scale;
                        const tctx = tmp.getContext('2d');
                        tctx.fillStyle = '#ffffff';
                        tctx.fillRect(0, 0, tmp.width, tmp.height);
                        tctx.drawImage(img, 0, 0, tmp.width, tmp.height);

                        // Agregar texto central (si existe .donut-center)
                        try {
                            const center = document.querySelector('.donut-center');
                            if (center) {
                                const percentEl = center.children[0];
                                const labelEl = center.children[1];
                                const pctText = percentEl ? percentEl.innerText.trim() : '';
                                const labelText = labelEl ? labelEl.innerText.trim() : '';
                                
                                tctx.fillStyle = '#4B0082';
                                tctx.textAlign = 'center';
                                tctx.textBaseline = 'middle';
                                tctx.font = `${28 * scale}px Arial`; 
                                tctx.fillText(pctText, tmp.width/2, tmp.height/2 - 6*scale);
                                tctx.font = `${10 * scale}px Arial`;
                                tctx.fillStyle = 'rgba(0,0,0,0.6)';
                                tctx.fillText(labelText, tmp.width/2, tmp.height/2 + 18*scale);
                            }
                        } catch (e) {}

                        marketingImage = tmp.toDataURL('image/png');
                        
                        // Restaurar colores originales
                        window.marketingChart.data.datasets[0].backgroundColor = oldColors;
                        window.marketingChart.update();
                    } catch(e) { 
                        console.warn('Could not capture marketing image:', e); 
                    }
                }

                // Capturar heatmap (si existe)
                let heatmapImage = null;
                try {
                    const heatEl = document.querySelector('.heatmap-table');
                    if (heatEl && window.html2canvas) {
                        const heatCanvas = await html2canvas(heatEl, { backgroundColor: '#ffffff', scale: 2 });
                        heatmapImage = heatCanvas.toDataURL('image/png');
                    }
                } catch(e) { 
                    console.warn('Could not capture heatmap:', e); 
                }
                
                // CAPTURAR ESTADO DE LAS TABLAS (ordenamiento)
                const tableStates = {};
                
                if (window.tablaPeliculasInstance) {
                    const order = window.tablaPeliculasInstance.order();
                    tableStates.peliculas_order_col = order[0][0];
                    tableStates.peliculas_order_dir = order[0][1];
                }
                
                if (window.tablaHorariosInstance) {
                    const order = window.tablaHorariosInstance.order();
                    tableStates.horarios_order_col = order[0][0];
                    tableStates.horarios_order_dir = order[0][1];
                }
                
                if (window.tablaSalasInstance) {
                    const order = window.tablaSalasInstance.order();
                    tableStates.salas_order_col = order[0][0];
                    tableStates.salas_order_dir = order[0][1];
                }
                
                if (window.tablaDetalleInstance) {
                    const order = window.tablaDetalleInstance.order();
                    tableStates.detalle_order_col = order[0][0];
                    tableStates.detalle_order_dir = order[0][1];
                }
                
                // Debug: Mostrar estado capturado
                console.log('📊 Estado de tablas capturado:', tableStates);
                console.log('📅 Fechas:', {
                    inicio: window.ocupacionData.fechaInicio,
                    fin: window.ocupacionData.fechaFin
                });
                
                // Obtener CSRF token
                function getCookie(name) { 
                    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'); 
                    return v ? v.pop() : ''; 
                }
                const csrftoken = getCookie('csrftoken');
                
                // Construir URL preservando filtros actuales + estado de tablas
                const params = new URLSearchParams(window.location.search);
                params.set('fecha_inicio', window.ocupacionData.fechaInicio);
                params.set('fecha_fin', window.ocupacionData.fechaFin);
                Object.entries(tableStates).forEach(([key, value]) => params.set(key, value));
                
                const url = `${window.ocupacionData.exportUrl}?${params.toString()}`;
                console.log('🔗 URL de exportación:', url);

                // Preparar payload con imágenes
                const payload = { chart_image: chartImage };
                if (marketingImage) payload.marketing_image = marketingImage;
                if (heatmapImage) payload.heatmap_image = heatmapImage;

                // Enviar solicitud POST
                const res = await fetch(url, { 
                    method: 'POST', 
                    credentials: 'same-origin',
                    headers: { 
                        'Content-Type': 'application/json', 
                        'X-CSRFToken': csrftoken 
                    }, 
                    body: JSON.stringify(payload) 
                });
                
                if (!res.ok) {
                    throw new Error(`Error del servidor: ${res.status} ${res.statusText}`);
                }
                
                // Descargar PDF
                const blob = await res.blob(); 
                const link = document.createElement('a'); 
                const filename = `reporte_ocupacion_${window.ocupacionData.fechaInicio}.pdf`; 
                link.href = window.URL.createObjectURL(blob); 
                link.download = filename; 
                link.click();
                
                console.log('✅ PDF generado exitosamente');
                
            } catch (e) {
                alert('Error al generar PDF: ' + e.message);
                console.error('❌ Error en exportación PDF:', e);
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        });
    }

});