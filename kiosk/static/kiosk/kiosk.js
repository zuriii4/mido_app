(function() {
    'use strict';

    // === KIOSK DEVICE TOKEN ===
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

    // Posielaj X-Device-Token pri KAZDOM requeste (aj klasicka navigacia / page load,
    // nielen HTMX) - inak po strate session (restart servera, expiracia cookie) kiosk
    // skonci na device-setup, aj ked token zije v localStorage. Server (middleware)
    // token overi a session si obnovi sam.
    function _isSameOrigin(url) {
        if (typeof url !== 'string' || url.startsWith('/')) return true;
        return url.indexOf(window.location.origin) === 0 || !/^https?:\/\//.test(url);
    }

    function _injectDeviceToken() {
        // fetch (htmx 2.x a vsetko ostatne)
        const origFetch = window.fetch;
        if (origFetch && !window.__xdtFetchWrapped) {
            window.__xdtFetchWrapped = true;
            window.fetch = function (input, init) {
                const token = getDeviceToken();
                if (token && _isSameOrigin(input)) {
                    init = init || {};
                    init.headers = Object.assign({}, init.headers, {'X-Device-Token': token});
                }
                return origFetch.call(this, input, init);
            };
        }

        // XMLHttpRequest (htmx 1.x ho pouziva interne)
        const origOpen = XMLHttpRequest.prototype.open;
        const origSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
        if (!window.__xdtXhrWrapped) {
            window.__xdtXhrWrapped = true;
            XMLHttpRequest.prototype.open = function (method, url, async, user, pass) {
                const result = origOpen.call(this, method, url, async, user, pass);
                this.__xdtHeaderSet = false;
                const token = getDeviceToken();
                if (token && _isSameOrigin(url)) {
                    try {
                        origSetRequestHeader.call(this, 'X-Device-Token', token);
                        this.__xdtHeaderSet = true;
                    } catch (e) {}
                }
                return result;
            };
            // zabran duplicite hlavicky (keby ju niekto chcel nastavit znova)
            XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
                if (this.__xdtHeaderSet && String(name).toLowerCase() === 'x-device-token') return;
                return origSetRequestHeader.call(this, name, value);
            };
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _injectDeviceToken);
    } else {
        _injectDeviceToken();
    }

    // === Device-setup page: ak mame token v localStorage, skus sa rovno prihlasit ===
    // (prva navigacia po strate session nemoze mat hlavicku - JS este nebezel,
    //  takze tu token overime a middleware obnovi session)
    if (window.location.pathname === '/kiosk/device-setup/') {
        const token = getDeviceToken();
        if (token) {
            fetch('/kiosk/', {
                credentials: 'same-origin',
                redirect: 'manual',
                headers: {'X-Device-Token': token},
            }).then((resp) => {
                if (resp.type !== 'opaqueredirect' && resp.ok) {
                    window.location.reload();  // session obnovena -> nacita sa home
                }
            }).catch(() => {});
        }
    }

    // === Handle 401 (invalid device) ===
    document.body.addEventListener('htmx:responseError', (event) => {
        const xhr = event.detail.xhr;
        if (xhr && xhr.status === 401) {
            clearDeviceToken();
            window.location.href = '/kiosk/device-setup/';
        }
    });

    // === Device setup page: uloz token po uspesnom validovani ===
    document.body.addEventListener('htmx:afterRequest', (event) => {
        if (event.detail.pathInfo && event.detail.pathInfo.requestPath === '/kiosk/device-setup/') {
            if (event.detail.successful) {
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

    if (!input || !content || !form || !status) {
        return;
    }

    // === FOCUS GUARD ===
    // 1. Okamzity refocus na blur 
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

    // === zabran dvojitemu submitu ===
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
