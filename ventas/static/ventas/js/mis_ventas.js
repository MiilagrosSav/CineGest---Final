(function(){
    const buttons = document.querySelectorAll('.filter-btn');
    const historyContainer = document.getElementById('ventasHistorialContainer');
    const historyTitle = document.getElementById('historial-titulo');
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const clearSearchBtn = document.getElementById('clearSearchBtn');

    if (!buttons || buttons.length === 0) return;

    function fetchPartial(filter, page, search){
        const url = new URL(window.location.pathname, window.location.origin);
        url.searchParams.set('filter', filter || 'confirmadas');
        url.searchParams.set('page', page || 1);
        if (search) {
            url.searchParams.set('search', search);
        }

        return fetch(url.toString(), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(resp => {
            if (!resp.ok) throw new Error('Network response was not ok');
            return resp.text();
        }).then(html => {
            if(historyContainer) historyContainer.innerHTML = html;

            const newUrl = url.toString();
            window.history.pushState({filter: filter, page: page, search: search}, '', newUrl);

            if(historyTitle){
                if(filter === 'confirmadas') historyTitle.innerText = '✅ Compras Confirmadas';
                else if(filter === 'intercambiadas') historyTitle.innerText = '🔄 Compras Intercambiadas';
                else if(filter === 'expiradas') historyTitle.innerText = '⏳ Compras Expiradas';
            }
        }).catch(err => {
            console.error('Error fetching partial:', err);
        });
    }

    document.addEventListener('click', function(e){
        const a = e.target.closest('.ventas-pagination a');
        if(!a) return;
        e.preventDefault();
        const href = a.getAttribute('href');
        if(!href) return;
        const parsed = new URL(href, window.location.origin);
        const params = parsed.searchParams;
        const filter = params.get('filter') || window.CURRENT_FILTER || 'confirmadas';
        const p = params.get('page') || 1;
        const search = params.get('search') || '';
        fetchPartial(filter, p, search);
    });

    buttons.forEach(btn => {
        btn.addEventListener('click', function(){
            const filter = this.dataset.filter;
            buttons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const search = searchInput ? searchInput.value.trim() : '';
            fetchPartial(filter, 1, search);
        });
    });

    if (searchBtn) {
        searchBtn.addEventListener('click', function(e){
            e.preventDefault();
            const currentFilter = document.querySelector('.filter-btn.active')?.dataset.filter || 'confirmadas';
            const search = searchInput.value.trim();
            fetchPartial(currentFilter, 1, search);
        });
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function(e){
            if(e.key === 'Enter'){
                e.preventDefault();
                searchBtn.click();
            }
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', function(e){
            e.preventDefault();
            if (searchInput) searchInput.value = '';
            const currentFilter = document.querySelector('.filter-btn.active')?.dataset.filter || 'confirmadas';
            fetchPartial(currentFilter, 1, '');
        });
    }

    window.addEventListener('popstate', function(ev){
        const state = ev.state || {};
        const filter = state.filter || new URL(window.location.href).searchParams.get('filter') || window.CURRENT_FILTER || 'confirmadas';
        const page = state.page || new URL(window.location.href).searchParams.get('page') || 1;
        const search = state.search || new URL(window.location.href).searchParams.get('search') || '';
        if (searchInput) searchInput.value = search;
        fetchPartial(filter, page, search);
    });
})();
