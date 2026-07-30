# MIDo App - Frontend plan (kiosk UI, HTMX + Bootstrap)

Ciel: funkcne kiosk UI pre podpisovanie dokumentov. HTMX (bez Node.js),
Bootstrap 5 (velke tlacidla pre dotykovy display). Backend uz existuje.

## Architektonicke rozhodnutie: Auth pre HTML

API pouziva Bearer token (RfidSession). HTMX pouziva cookies + CSRF.
Riesenie:
1. RFID login view (HTML) zavola tu istu logiku ako API - vytvori RfidSession
2. Token ulozi do Django session (request.session['rfid_token'])
3. Custom middleware: precita token z Django session, overi voci RfidSession
   modelu (platnost, revokacia), nastavi request.user
4. Vsetky HTML views potom bezia ako klasicke Django views s request.user

Zachovavame: re-tap revokuje staru session, TTL, device tracking.
Ziskavame: CSRF ochrana, Django messages, standardny template flow.

## Adresarova struktura (nova appka: kiosk)

kiosk/
├── __init__.py
├── apps.py
├── middleware.py          # RfidSessionMiddleware
├── urls.py                # HTML routy (/kiosk/...)
├── views.py               # HTML views
├── templates/
│   └── kiosk/
│       ├── base.html      # Bootstrap + HTMX CDN, layout
│       ├── home.html      # uvodna obrazovka (priloz kartu)
│       ├── dashboard.html # nepodpisane dokumenty + notifikacie
│       ├── document_detail.html
│       ├── notifications.html
│       └── partials/
│           ├── _document_list.html
│           ├── _notification_badge.html
│           ├── _sign_modal.html
│           └── _messages.html
└── static/
    └── kiosk/
        └── kiosk.css      # velke tlacidla, dotyk, idle fade

Settings zmeny:
- INSTALLED_APPS += 'kiosk'
- MIDDLEWARE += 'kiosk.middleware.RfidSessionMiddleware' (za AuthenticationMiddleware)
- config/urls.py: path('kiosk/', include('kiosk.urls'))

## User flow

1. HOME: velka obrazovka "Priloz kartu". Skryty input ma focus,
   USB citacka karty napise UID + Enter -> submit form.
2. LOGIN POST /kiosk/login/: vytvori RfidSession, token do Django session,
   redirect na dashboard. Neznama karta -> chybova hlaska, ostane na home.
3. DASHBOARD: meno usera, zoznam nepodpisanych dokumentov
   (get_unsigned_documents), zvoncek s poctom neprecitanych notifikacii.
4. DOCUMENT DETAIL: nazov, metadata, PDF v iframe (file_url z API view),
   tlacidlo Podpisat.
5. SIGN MODAL: "Priloz kartu znova" -> POST /kiosk/sign/ s rfid_uid +
   document_version_id -> zavola create_signature() (uz existuje!)
   -> success obrazovka -> auto redirect na dashboard po 3s.
6. NOTIFICATIONS: zoznam, klik = mark as read (HTMX PATCH, bez reloadu).
7. IDLE: JS timer 60s bez aktivity -> POST /kiosk/logout/ -> home.
   TTL session tiez zobrazi countdown.

## Etapy

### Etapa 1 - Zaklady (appka, base template)
- vytvor kiosk appku, zaregistruj, urls
- base.html: Bootstrap 5 CDN + HTMX CDN + kiosk.css
- home.html: uvodna obrazovka, skryty RFID input s autofocusom
- views.py: HomeView (render), zatial bez logiky
- AKCEPCIA: http://127.0.0.1:8000/kiosk/ zobrazi uvodnu obrazovku

### Etapa 2 - Login flow
- LoginView: POST rfid_uid -> authenticate() -> RfidSession ->
  request.session['rfid_token'] -> redirect dashboard
- middleware.py: precita token, nastavi request.user (alebo None)
- neznama karta -> Django messages error, ostane na home
- AKCEPCIA: rfid_uid=000000 prihlasi testusera, dashboard ukaze meno

### Etapa 3 - Dashboard
- DashboardView: get_unsigned_documents(request.user) cez existujucu service
- _document_list.html partial: karty dokumentov (cislo, nazov, datum)
- zvoncek: get_unread_notifications().count() ako badge
- AKCEPCIA: dashboard ukazuje nepodpisane dokumenty usera

### Etapa 4 - Detail dokumentu + PDF
- DocumentDetailView: detail + current_version.file_url
- iframe s PDF (file endpoint uz existuje, middleware ho autentifikuje)
- AKCEPCIA: klik na dokument -> PDF sa zobrazi v stranke

### Etapa 5 - Podpis (hlavna funkcia!)
- _sign_modal.html: Bootstrap modal, input na rfid re-tap
- SignView: POST -> create_signature() (EXISTUJUCI service, neprepisovat!)
- osetri vynimky: AlreadySigned (409), zla karta (403), stara verzia (400)
- success stranka s checkmark + JS auto redirect po 3s
- AKCEPCIA: podpis funguje, dokument zmizne z dashboardu

### Etapa 6 - Notifikacie UI
- NotificationsView: zoznam notifikacii
- klik na polozku: HTMX POST mark-as-read, polozka zbledne bez reloadu
- badge sa aktualizuje (HTMX swap)
- AKCEPCIA: precitanie notifikacie bez reloadu stranky

### Etapa 7 - Idle timeout + polish
- JS: 60s neaktivita -> logout POST -> home
- countdown zobrazenie TTL session
- kiosk.css: velke tlacidla (min 48px), kontrast, ziadne scrollovanie
- AKCEPCIA: po 60s sa kiosk sam odhlasi

### Etapa 8 - Testy HTML views
- Django test client: home 200, login 302, dashboard s auth,
  bez auth redirect na home, sign POST vytvori Signature
- AKCEPCIA: py manage.py test kiosk -> zelene

## Backend veci na dorobenie (bokom)

| Vec | Preco | Kedy |
|---|---|---|
| users.sync_users command | prazdny subor, treba dokoncit | ked bude AD/LDAP source |
| CORS | HTMX netreba (same-origin), az ak bude SPA | odlozit |
| file endpoint auth v HTML | vyriesi middleware z Etapy 2 | Etapa 2 |
| PDF nahravanie vekych suborov | iframe streaming uz funguje | overit v Etape 4 |
| cleanup test dat v DB | TEST-NOTIF-001 dokument, TESTOU BU | niekedy |

## Co sa NEBUDE robit (zamer)
- ziadny React/Vue/Node.js
- ziadne WebSockety (HTMX polling staci)
- admin UI (django admin staci, dorobi sa neskor ak treba)
- responsivita na mobily (kiosk = fixny display 1080p)
