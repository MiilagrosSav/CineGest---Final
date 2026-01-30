const mp = new MercadoPago(window.MERCADOPAGO_PUBLIC_KEY, {
    locale: 'es-AR'
});

mp.checkout({
    preference: {
        id: window.PREFERENCE_ID
    },
    render: {
        container: '#wallet_container',
        label: 'Pagar con Mercado Pago',
    },
    theme: {
        elementsColor: '#009ee3',
        headerColor: '#009ee3',
    }
});

console.log('init_point:', window.INIT_POINT);
setTimeout(() => {
    console.log('Buscando botón inyectado por Mercado Pago...');
    const container = document.getElementById('wallet_container');
    if (!container) return;
    const anchor = container.querySelector('a');
    if (anchor && window.INIT_POINT) {
        anchor.setAttribute('href', window.INIT_POINT);
        anchor.setAttribute('target', '_blank');
        anchor.setAttribute('rel', 'noopener noreferrer');
        console.log('SDK button ajustado: ancla -> abrir en nueva pestaña');
        return;
    }
    const btn = container.querySelector('button');
    if (btn && window.INIT_POINT) {
        try { btn.replaceWith(btn.cloneNode(true)); } catch (e) {}
        const fresh = container.querySelector('button');
        if (fresh) {
            fresh.addEventListener('click', function (ev) {
                ev.preventDefault();
                window.open(window.INIT_POINT, '_blank', 'noopener');
            });
            console.log('SDK button ajustado: botón -> abrir en nueva pestaña');
        }
    }
}, 700);
