// ===========================================
// EXPORTACIÓN A PDF CON ESTADO DE TABLAS
// ===========================================
function getCookie(name) { 
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'); 
    return v ? v.pop() : ''; 
}

document.getElementById('exportPdfBtn').addEventListener('click', async function(){
    const btn = this;
    const originalText = btn.innerText;
    btn.innerText = '⏳ Generando...';
    btn.disabled = true;

    try {
        // CAPTURAR ESTADO DE LAS TABLAS (ordenamiento)
        const tableStates = {};
        
        if (window.tablaRevpasInstance) {
            const order = window.tablaRevpasInstance.order();
            tableStates.revpas_order_col = order[0][0];
            tableStates.revpas_order_dir = order[0][1];
        }
        
        if (window.tablaRevenueDiaInstance) {
            const order = window.tablaRevenueDiaInstance.order();
            tableStates.dia_order_col = order[0][0];
            tableStates.dia_order_dir = order[0][1];
        }
        
        if (window.tablaDetallePeliculasInstance) {
            const order = window.tablaDetallePeliculasInstance.order();
            tableStates.detalle_order_col = order[0][0];
            tableStates.detalle_order_dir = order[0][1];
        }
        
        if (window.tablaEficienciaPromocionesInstance) {
            const order = window.tablaEficienciaPromocionesInstance.order();
            tableStates.promo_order_col = order[0][0];
            tableStates.promo_order_dir = order[0][1];
        }
        
        // Debug: Mostrar estado capturado
        console.log('📊 Estado de tablas capturado:', tableStates);
        console.log('📅 Fechas:', {
            inicio: window.financieroData.fechaInicio,
            fin: window.financieroData.fechaFin
        });
        
        const csrftoken = getCookie('csrftoken');
        
        // Construir URL preservando filtros actuales + estado de tablas
        const params = new URLSearchParams(window.location.search);
        params.set('fecha_inicio', window.financieroData.fechaInicio);
        params.set('fecha_fin', window.financieroData.fechaFin);
        Object.entries(tableStates).forEach(([key, value]) => params.set(key, value));
        
        const url = `${window.financieroData.exportUrl}?${params.toString()}`;
        console.log('🔗 URL de exportación:', url);

        const res = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 
                'Content-Type': 'application/json', 
                'X-CSRFToken': csrftoken 
            }
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
