/**
 * Kiosk - JavaScript
 *
 * Sprava:
 * - Focus guard (vratenie focusu na skryty RFID input)
 * - Debounce pre HTMX submit
 * - Vizualna odozva pri citani karty
 * - window.kioskApp API pre HTMX event handlery
 */
(function() {
    'use strict';

    // === KIOSK DEVICE TOKEN ===
    // LocalStorage key
    const DEVICE_TOKEN_KEY = 'kiosk_device_token';

    // Nacitaj ulozeny token
    function getDeviceToken() {
        try {
            return localStorage.getItem(DEVICE_TOKEN_KEY);
        } catch (e) {
            return null;
        }
    }

    function setDeviceToken(token) {
        try {
            localStorage.setItem(DEVICE_TOKEN_KEY, token);
        } catch (e) {
            console.warn('kiosk: localStorage nie je dostupny', e);
        }
    }

    function clearDeviceToken() {
        try {
            localStorage.removeItem(DEVICE_TOKEN_KEY);
        } catch (e) {}
    }

    // Nastav X-Device-Token pre vsetky HTMX requesty
    function setHtmxHeader() {
        const token = getDeviceToken();
        if (token && window.htmx) {
            // Odstran stary header ak existuje
            delete window.htmx.config.headers['X-Device-Token'];
            if (token) {
                window.htmx.config.headers['X-Device-Token'] = token;
            }
        }
    }

    // Po nacitani nastav header
    document.addEventListener('DOMContentLoaded', setHtmxHeader);
    document.addEventListener('htmx:configRequest', (event) => {
        const token = getDeviceToken();
        if (token) {
            event.detail.headers['X-Device-Token'] = token;
        }
    });

    // === Handle 401 (invalid device) ===
    document.body.addEventListener('htmx:responseError', (event) => {
        // Ak server poslal HX-Redirect na device-setup, presmeruj
        const xhr = event.detail.xhr;
        if (xhr && xhr.status === 401) {
            clearDeviceToken();
            window.location.href = '/kiosk/device-setup/';
        }
    });

    // === Device setup page: uloz token po uspesnom validovani ===
    // Sleduj uspesne submit na device-setup form
    document.body.addEventListener('htmx:afterRequest', (event) => {
        if (event.detail.pathInfo && event.detail.pathInfo.requestPath === '/kiosk/device-setup/') {
            if (event.detail.successful) {
                // Precitaj X-Device-Token z response (ak by server poslal)
                // alebo z formulára
                const input = document.getElementById('device-token-input');
                if (input && input.value) {
                    setDeviceToken(input.value);
                }
            }
        }
    });

    const input = document.getElementById('rfid-input');
    const content = document.getElementById('kiosk-content');
    const form = input ? input.form : null;
    const status = document.getElementById('login-status');

    // null guard - ak nie su potrebne elementy, koniec
    if (!input || !content || !form || !status) {
        // Na inych strankach (dashboard, login-status) tieto elementy nie su
        // Tu nic nerobime
        return;
    }

    // === FOCUS GUARD ===
    // 1. Okamzity refocus na blur (primarna strategia)
    input.addEventListener('blur', () => {
        setTimeout(() => {
            if (document.activeElement !== input &&
                !document.activeElement.closest('a') &&
                document.activeElement.tagName !== 'A') {
                input.focus();
            }
        }, 30);
    });

    // 2. Refocus pri navrate do tabu
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) input.focus();
    });

    // 3. Refocus po bfcache restore
    window.addEventListener('pageshow', (e) => {
        if (e.persisted) input.focus();
    });

    // 4. Klik mimo linku vrati focus
    document.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        if (e.target === input) return;
        setTimeout(() => input.focus(), 50);
    });

    // 5. Fallback - kazde 2s kontrola
    setInterval(() => {
        if (document.activeElement !== input && !document.hidden) {
            input.focus();
        }
    }, 2000);

    // === DEBOUNCE: zabran dvojitemu submitu ===
    let isProcessing = false;
    let lastSubmitAt = 0;

    form.addEventListener('htmx:beforeRequest', (event) => {
        if (!input.value.trim()) {
            event.preventDefault();
            input.value = '';
            input.focus();
            return;
        }
        const now = Date.now();
        if (isProcessing || (now - lastSubmitAt) < 600) {
            event.preventDefault();
            return;
        }
        isProcessing = true;
        lastSubmitAt = now;
    });

    form.addEventListener('htmx:afterRequest', () => {
        setTimeout(() => { isProcessing = false; }, 600);
    });

    // === APP API pre HTMX event handlery ===
    window.kioskApp = {
        afterScan(event) {
            input.value = '';
            content.classList.add('scanning');
            setTimeout(() => content.classList.remove('scanning'), 500);
            setTimeout(() => input.focus(), 100);
        },
        handleError(event) {
            console.warn('kiosk: request error', event.detail);
            input.value = '';
            input.focus();
        }
    };

    // Po nacitani zabezpec focus
    if (document.readyState === 'complete') {
        input.focus();
    } else {
        window.addEventListener('load', () => input.focus());
    }
})();
