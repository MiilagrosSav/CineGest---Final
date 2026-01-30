// 1. Gráfico de Línea (Ocupación)
const occ = window.ocupacionData.occ;
const ctx = document.getElementById('occChart').getContext('2d');

let gradient = ctx.createLinearGradient(0, 0, 0, 400);
gradient.addColorStop(0, 'rgba(139, 95, 191, 0.5)');
gradient.addColorStop(1, 'rgba(139, 95, 191, 0.0)');

const occChart = new Chart(ctx, {
    type: 'line',
    data: { 
        labels: occ.labels, 
        datasets: [{ 
            label: '% Ocupación', 
            data: occ.values, 
            borderColor: '#9B59B6', 
            backgroundColor: gradient, 
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#ffffff',
            pointBorderColor: '#9B59B6',
            pointRadius: 5,
            pointHoverRadius: 7
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

// 2. Gráfico de Torta (Marketing)
try {
    const marketingJsonRaw = window.ocupacionData.marketing;
    let mkt = {};
    try { mkt = JSON.parse(marketingJsonRaw || '{}'); } catch(e) { mkt = {}; }

    const donutData = (mkt && mkt.data && mkt.labels) ? mkt : { labels: ['Ignorados','Canjeados'], data: [1,0] };
    const ctxM = document.getElementById('marketingDonut').getContext('2d');
    
    // keep a reference to the marketing chart so we can export image later
    window.marketingChart = new Chart(ctxM, {
        type: 'doughnut',
        data: {
            labels: donutData.labels,
            datasets: [{
                data: donutData.data,
                backgroundColor: ['rgba(255,255,255,0.05)', '#9B59B6'], // Gris sutil y Violeta vibrante
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            cutout: '75%', // Agujero más grande para el texto
            plugins: { legend: { display: false } },
            responsive: true, 
            maintainAspectRatio: false
        }
    });
} catch(e) { console.error('Error drawing marketing donut', e); }

// 3. Exportación PDF
function getCookie(name) { const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'); return v ? v.pop() : ''; }

document.getElementById('exportPdfBtn').addEventListener('click', async function(){
    const btn = this;
    const originalText = btn.innerText;
    btn.innerText = '⏳ Generando...';
    btn.disabled = true;

    try {
        const chartImage = occChart.toBase64Image();
        // marketing image: if we have the chart instance use its canvas, otherwise try DOM
        let marketingImage = null;
        try {
            // Produce a combined, higher-resolution marketing image that includes the center text
            if (window.marketingChart && window.marketingChart.canvas) {
                const origCanvas = window.marketingChart.canvas;
                // temporarily enhance colors for export to improve contrast in PDF
                let oldColors = null;
                try {
                    oldColors = window.marketingChart.data.datasets[0].backgroundColor;
                    const bright = ['#f2f2f2', '#9B59B6'];
                    window.marketingChart.data.datasets[0].backgroundColor = bright;
                    window.marketingChart.update();
                } catch (e) { oldColors = null; }
                // draw the chart image into a temp canvas
                const img = new Image();
                img.src = window.marketingChart.toBase64Image();
                await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
                // create high-res canvas (scale 2)
                const scale = 2;
                const tmp = document.createElement('canvas');
                tmp.width = origCanvas.width * scale;
                tmp.height = origCanvas.height * scale;
                const tctx = tmp.getContext('2d');
                // white background
                tctx.fillStyle = '#ffffff';
                tctx.fillRect(0,0,tmp.width,tmp.height);
                // draw scaled chart
                tctx.drawImage(img, 0, 0, tmp.width, tmp.height);

                // draw center text (read from DOM .donut-center)
                try {
                    const center = document.querySelector('.donut-center');
                    if (center) {
                        const percentEl = center.children[0];
                        const labelEl = center.children[1];
                        const pctText = percentEl ? percentEl.innerText.trim() : '';
                        const labelText = labelEl ? labelEl.innerText.trim() : '';
                        // big number
                        tctx.fillStyle = '#4B0082';
                        tctx.textAlign = 'center';
                        tctx.textBaseline = 'middle';
                        // percentage
                        tctx.font = `${28 * scale}px Arial`; 
                        tctx.fillText(pctText, tmp.width/2, tmp.height/2 - 6*scale);
                        // label smaller
                        tctx.font = `${10 * scale}px Arial`;
                        tctx.fillStyle = 'rgba(0,0,0,0.6)';
                        tctx.fillText(labelText, tmp.width/2, tmp.height/2 + 18*scale);
                    }
                } catch (e) {}

                marketingImage = tmp.toDataURL('image/png');
                // restore old colors
                try {
                    if (oldColors) {
                        window.marketingChart.data.datasets[0].backgroundColor = oldColors;
                        window.marketingChart.update();
                    }
                } catch(e) {}
            } else {
                const mCanv = document.getElementById('marketingDonut');
                if (mCanv && mCanv.toDataURL) {
                    // try higher-res export by drawing into temp canvas
                    const img = new Image();
                    img.src = mCanv.toDataURL('image/png');
                    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
                    const scale = 2;
                    const tmp = document.createElement('canvas');
                    tmp.width = mCanv.width * scale;
                    tmp.height = mCanv.height * scale;
                    const tctx = tmp.getContext('2d');
                    tctx.fillStyle = '#ffffff'; tctx.fillRect(0,0,tmp.width,tmp.height);
                    tctx.drawImage(img, 0,0,tmp.width,tmp.height);
                    marketingImage = tmp.toDataURL('image/png');
                }
            }
        } catch(e) { marketingImage = null; }

        // heatmap: render the heatmap table to a canvas using html2canvas at higher scale
        let heatmapImage = null;
        try {
            const heatEl = document.querySelector('.heatmap-table');
            if (heatEl && window.html2canvas) {
                const heatCanvas = await html2canvas(heatEl, { backgroundColor: '#ffffff', scale: 2 });
                heatmapImage = heatCanvas.toDataURL('image/png');
            }
        } catch(e) { heatmapImage = null; }
        const csrftoken = getCookie('csrftoken');
        const url = `${window.ocupacionData.exportUrl}?fecha_inicio=${window.ocupacionData.fechaInicio}&fecha_fin=${window.ocupacionData.fechaFin}`;

        const payload = { chart_image: chartImage };
        if (marketingImage) payload.marketing_image = marketingImage;
        if (heatmapImage) payload.heatmap_image = heatmapImage;

        const res = await fetch(url, { 
            method:'POST', 
            credentials: 'same-origin',
            headers:{ 'Content-Type':'application/json', 'X-CSRFToken': csrftoken }, 
            body: JSON.stringify(payload) 
        });
        
        if (!res.ok) throw new Error('Error en el servidor');
        
        const blob = await res.blob(); 
        const link = document.createElement('a'); 
        const filename = `reporte_ocupacion_${window.ocupacionData.fechaInicio}.pdf`; 
        link.href = window.URL.createObjectURL(blob); 
        link.download = filename; 
        link.click();
    } catch (e) {
        alert('Error al generar PDF');
        console.error(e);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});
