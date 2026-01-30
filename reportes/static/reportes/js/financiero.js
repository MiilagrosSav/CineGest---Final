const fin = window.financieroData.fin;
const ctx = document.getElementById('finChart').getContext('2d');

// Colores de CineGest (Tonos de violeta, verde, naranja, azul)
const palette = [
    '#9B59B6', // Primary Violet
    '#4ecdc4', // Teal
    '#FF6B6B', // Red
    '#ffc107', // Amber
    '#3498db', // Blue
    '#e91e63', // Pink
    '#00b894', // Green
    '#6c5ce7'  // Deep Purple
];

const bgColors = fin.labels.map((l, i) => palette[i % palette.length]);

const finChart = new Chart(ctx, {
    type: 'bar',
    data: {
        labels: fin.labels,
        datasets: [{ 
            label: 'Ingresos', 
            data: fin.values, 
            backgroundColor: bgColors, 
            borderRadius: 8, // Barras redondeadas
            borderSkipped: false
        }]
    },
    options: {
        plugins: {
            legend: { display: false }, // Ocultar leyenda porque los colores varían
            datalabels: {
                color: '#ffffff',
                anchor: 'end',
                align: 'end',
                formatter: function(value){ 
                    if(!value || value===0) return ''; 
                    return '$' + Number(value).toLocaleString(); 
                },
                font: { weight: 'bold', size: 11 },
                offset: 4
            },
            tooltip: { callbacks: { label: function(ctx){ return '$' + Number(ctx.parsed.y || ctx.parsed).toLocaleString(); } } }
        },
        scales: { 
            x: { 
                grid: { display: false },
                ticks: { color: '#b0b0b0', autoSkip: false, maxRotation: 45, minRotation: 0 } 
            }, 
            y: { 
                beginAtZero: true, 
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#b0b0b0', callback: v => '$' + Number(v).toLocaleString() } 
            } 
        },
        responsive: true, 
        maintainAspectRatio: false
    },
    plugins: [ChartDataLabels]
});

// Exportar PDF
function getCookie(name) { const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'); return v ? v.pop() : ''; }

document.getElementById('exportPdfBtn').addEventListener('click', async function(){
    const btn = this;
    const originalText = btn.innerText;
    btn.innerText = '⏳ Generando...';
    btn.disabled = true;

    try {
        const chartImage = finChart.toBase64Image();
        const csrftoken = getCookie('csrftoken');
        const url = `${window.financieroData.exportUrl}?fecha_inicio=${window.financieroData.fechaInicio}&fecha_fin=${window.financieroData.fechaFin}`;

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ chart_image: chartImage })
        });

        if (!res.ok) throw new Error('Error al generar PDF');

        const blob = await res.blob();
        const link = document.createElement('a');
        const filename = `reporte_financiero_${window.financieroData.fechaInicio}_${window.financieroData.fechaFin}.pdf`;
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
