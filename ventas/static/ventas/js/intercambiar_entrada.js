(function(){
    const buttons = document.querySelectorAll('.ver-detalles-btn');
    
    function hideAll(){
        document.querySelectorAll('.detalles-funcion').forEach(d=>d.style.display='none');
    }
    
    function formatMoney(n){
        return Number(n).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    }
    
    buttons.forEach(btn=>{
        btn.addEventListener('click', function(){
            const id = this.dataset.funcionId;
            const total = parseFloat(this.dataset.total) || 0;
            const pen = parseFloat(this.dataset.pen) || 0;
            const detalles = document.getElementById('detalles-'+id);
            if(!detalles) return;
            
            hideAll();
            
            const penAmount = (total * pen / 100.0).toFixed(2);
            detalles.querySelector('.pen-amount').innerText = formatMoney(penAmount);
            detalles.style.display = 'block';
            detalles.scrollIntoView({behavior:'smooth', block:'center'});
        });
    });
})();
