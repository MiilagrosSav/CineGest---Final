/**
 * iniciar_pago.js v3.0
 *
 * Flujo:
 *   1. El SDK de MP renderiza su botón oficial en #wallet_container.
 *   2. Interceptamos el click para aplicar bloqueo visual SILENCIOSO
 *      (pointer-events:none + opacity:0.7 — sin cambiar texto ni estructura).
 *   3. Mostramos el overlay "Redirigiendo..." sobre toda la pantalla.
 *   4. Notificamos al servidor (best-effort AJAX).
 *   5. Redirigimos con window.location.href → misma pestaña.
 *
 * Protección doble-click: flag en memoria (var pagando).
 *   — No usamos sessionStorage: la página navega a MP y se recarga al volver,
 *     por lo que no hay estado residual que bloquee reintentos legítimos.
 */

// ─── Flag en memoria ──────────────────────────────────────────────────────────
// Se resetea automáticamente en cada carga de página. No persiste.
var pagando = false;

// ─── SDK de Mercado Pago ──────────────────────────────────────────────────────
console.log('[CineGest] Inicializando SDK de MP — PREFERENCE_ID:', window.PREFERENCE_ID);

var mp = new MercadoPago(window.MERCADOPAGO_PUBLIC_KEY, {
    locale: 'es-AR'
});

mp.checkout({
    preference: { id: window.PREFERENCE_ID },
    render: {
        container: '#wallet_container',
        label: 'Pagar con Mercado Pago',
    },
    theme: {
        elementsColor: '#009ee3',
        headerColor: '#009ee3',
    }
});

// ─── Overlay ──────────────────────────────────────────────────────────────────

function showOverlay() {
    console.log('[CineGest] showOverlay()');
    var overlay = document.getElementById('mp-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
    } else {
        console.warn('[CineGest] #mp-overlay no encontrado');
    }
}

// ─── Countdown de expiración de reserva ──────────────────────────────────────

var _countdownInterval = null;

function formatSecs(secs) {
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

function startCountdown() {
    if (!window.VENTA_EXPIRACION_ISO) { return; }
    console.log('[CineGest] startCountdown() — expira:', window.VENTA_EXPIRACION_ISO);

    var expiry = new Date(window.VENTA_EXPIRACION_ISO);
    var countdownWrap   = document.getElementById('expiry-countdown');
    var overlayCountdown = document.getElementById('overlay-countdown');
    var timerEls = [
        document.getElementById('expiry-timer'),
        document.getElementById('overlay-timer'),
    ];

    if (countdownWrap)    countdownWrap.style.display    = 'block';
    if (overlayCountdown) overlayCountdown.style.display = 'block';

    if (_countdownInterval) clearInterval(_countdownInterval);

    _countdownInterval = setInterval(function () {
        var remaining = Math.floor((expiry.getTime() - Date.now()) / 1000);
        if (remaining <= 0) {
            clearInterval(_countdownInterval);
            timerEls.forEach(function (el) { if (el) el.textContent = '00:00'; });
            console.log('[CineGest] Reserva expirada — redirigiendo a cartelera');
            window.location.href = window.CARTELERA_URL;
            return;
        }
        timerEls.forEach(function (el) { if (el) el.textContent = formatSecs(remaining); });
    }, 1000);
}

// ─── Handler de click (intercepta el botón del SDK) ──────────────────────────

function handlePayClick(ev) {
    console.log('[CineGest] 1. handlePayClick() — pagando:', pagando);

    ev.preventDefault();
    ev.stopImmediatePropagation();

    // GUARD: doble-click en la misma carga de página
    if (pagando) {
        console.log('[CineGest] 2. Guard activo: ya se está procesando el pago');
        showOverlay();
        return;
    }

    // Paso 3: marcar flag de memoria
    pagando = true;
    console.log('[CineGest] 3. pagando = true');

    // Paso 4: bloqueo visual SILENCIOSO — solo CSS, sin cambiar texto ni estructura
    var el = ev.currentTarget;
    console.log('[CineGest] 4. Aplicando bloqueo visual al elemento:', el.tagName, el.id || '(sin id)');
    el.style.pointerEvents = 'none';
    el.style.opacity       = '0.7';
    el.style.cursor        = 'not-allowed';
    if (el.tagName === 'BUTTON') { el.disabled = true; }

    // Paso 5: mostrar overlay y countdown
    console.log('[CineGest] 5. Mostrando overlay');
    showOverlay();
    startCountdown();

    // Paso 6: notificar servidor (best-effort, no bloquea la redirección)
    console.log('[CineGest] 6. AJAX a', window.MARCAR_PAGO_URL);
    fetch(window.MARCAR_PAGO_URL, {
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN, 'Content-Type': 'application/json' },
        keepalive: true,
    }).then(function (r) {
        console.log('[CineGest] 6b. AJAX status:', r.status);
    }).catch(function (e) {
        console.warn('[CineGest] 6b. AJAX error (ignorado):', e);
    });

    // Paso 7: redirigir en la misma pestaña — a través de nuestro redirect view
    // (evita el 403 de CloudFront de MP al navegar directamente a init_point)
    console.log('[CineGest] 7. Redirigiendo con window.location.href →', window.IR_A_MP_URL);
    window.location.href = window.IR_A_MP_URL;
}

// ─── Inyección del handler en el botón del SDK ────────────────────────────────
// El SDK tarda ~700ms en inyectar su elemento. Lo interceptamos y reemplazamos
// el listener nativo por el nuestro (que hace location.href en lugar de open).

setTimeout(function () {
    console.log('[CineGest] setTimeout: buscando elemento en #wallet_container');
    var container = document.getElementById('wallet_container');
    if (!container) {
        console.warn('[CineGest] #wallet_container no encontrado');
        return;
    }

    var anchor = container.querySelector('a');
    if (anchor && window.INIT_POINT) {
        // Clonar para eliminar listeners internos del SDK
        var fresh = anchor.cloneNode(true);
        anchor.parentNode.replaceChild(fresh, anchor);
        fresh.addEventListener('click', handlePayClick);
        console.log('[CineGest] SDK <a> interceptado — handler instalado');
        return;
    }

    var btn = container.querySelector('button');
    if (btn && window.INIT_POINT) {
        var fresh = btn.cloneNode(true);
        btn.parentNode.replaceChild(fresh, btn);
        fresh.addEventListener('click', handlePayClick);
        console.log('[CineGest] SDK <button> interceptado — handler instalado');
        return;
    }

    console.warn('[CineGest] No se encontró <a> ni <button> dentro de #wallet_container después de 700ms');
}, 700);

// ─── Arrancar countdown al cargar ────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    console.log('[CineGest] DOMContentLoaded');
    console.log('[CineGest]   INIT_POINT disponible:', !!window.INIT_POINT);
    console.log('[CineGest]   VENTA_EXPIRACION_ISO:', window.VENTA_EXPIRACION_ISO);
    startCountdown();
});

