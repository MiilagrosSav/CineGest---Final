// Usar datos inyectados desde el template
const fin = window.dashboardData.fin;
const occ = window.dashboardData.occ;

// Financial stacked bar chart
const ctxFin = document.getElementById('finChart').getContext('2d');
// compute totals per label (full + promo) so we can set a sensible y-axis max
const finTotals = fin.labels.map((_, i) => ((fin.data_full[i] || 0) + (fin.data_promo[i] || 0)));
const finMax = finTotals.length ? Math.max(...finTotals) : 0;

// compute a "nice" maximum for the axis (1,2,5,10 * 10^n) to avoid runaway scales
function computeNiceMax(value){
  if (!value || value <= 0) return 100;
  const pow = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / pow;
  let niceNorm = 10;
  if (normalized <= 1) niceNorm = 1;
  else if (normalized <= 2) niceNorm = 2;
  else if (normalized <= 5) niceNorm = 5;
  else niceNorm = 10;
  return niceNorm * pow;
}

const finNiceMax = computeNiceMax(finMax);
const finSuggestedMax = Math.ceil(finNiceMax * 1.05);

const finChart = new Chart(ctxFin, {
  type: 'bar',
  data: {
    labels: fin.labels,
    datasets: [
      {
        label: 'Precio Full',
        data: fin.data_full,
        backgroundColor: '#10b981',
        stack: 'stack1'
      },
      {
        label: 'Con Promo',
        data: fin.data_promo,
        backgroundColor: '#a855f7',
        stack: 'stack1'
      }
    ]
  },
  options: {
    plugins: {
      legend: { labels: { color: '#e0e0e0' } },
      datalabels: {
        color: '#ffffff',
        anchor: 'end',
        align: 'end',
        formatter: function(value) {
          if (!value || value === 0) return '';
          return '$' + Number(value).toLocaleString();
        },
        font: {
          weight: 'bold',
          size: 11
        }
      },
      tooltip: {
        callbacks: {
          label: function(ctx){
            const v = ctx.parsed.y || ctx.parsed || 0;
            return ctx.dataset.label + ': $' + Number(v).toLocaleString();
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: '#e0e0e0' }, grid: { color: 'rgba(255,255,255,0.03)' } },
      y: {
        ticks: {
          color: '#e0e0e0',
          callback: function(value){ return '$' + Number(value).toLocaleString(); }
        },
        grid: { color: 'rgba(255,255,255,0.03)' },
        beginAtZero: true,
        suggestedMax: finSuggestedMax
      }
    },
    interaction: { mode: 'index', intersect: false },
    elements: {
      bar: {
        maxBarThickness: 60,
        borderRadius: 6
      }
    },
    maintainAspectRatio: false,
    responsive: true
  }
});

// Occupation line chart
const ctxOcc = document.getElementById('occChart').getContext('2d');
const gradient = ctxOcc.createLinearGradient(0, 0, 0, 300);
gradient.addColorStop(0, 'rgba(168,85,247,0.45)');
gradient.addColorStop(1, 'rgba(168,85,247,0.05)');

const occChart = new Chart(ctxOcc, {
  type: 'line',
  data: {
    labels: occ.labels,
    datasets: [{
      label: '% Ocupación',
      data: occ.data,
      borderColor: '#a855f7',
      backgroundColor: gradient,
      fill: true,
      tension: 0.4,
      pointBackgroundColor: '#a855f7'
    }]
  },
  options: {
    plugins: {
      legend: { labels: { color: '#e0e0e0' } },
      datalabels: {
        color: '#ffffff',
        anchor: 'end',
        align: 'top',
        formatter: function(value) {
          if (!value || value === 0) return '';
          return Number(value).toFixed(1) + '%';
        },
        font: {
          weight: 'bold',
          size: 11
        }
      }
    },
    scales: {
      x: { ticks: { color: '#e0e0e0' }, grid: { color: 'rgba(255,255,255,0.03)' } },
      y: { ticks: { color: '#e0e0e0' }, grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true, max: 100 }
    },
    responsive: true,
    maintainAspectRatio: false
  }
});
