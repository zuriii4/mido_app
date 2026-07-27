# MIDo App

Django backend pre správu internej dokumentácie (sync zo SharePointu, RFID prihlasovanie na kioskoch, elektronické podpisy).

## Prvé spustenie

```bash
cd ~/Desktop/mido_app
python3.13 -m venv .venv          # len ak .venv este neexistuje
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Aplikácia bude bežať na http://127.0.0.1:8000/, admin na http://127.0.0.1:8000/admin/.

## Každodenný štart (venv už existuje)

```bash
cd ~/Desktop/mido_app
source .venv/bin/activate
python manage.py runserver
```

`deactivate` na ukončenie virtuálneho prostredia. Aktivácia platí len pre dané okno terminálu.

## Základné príkazy

### Server

```bash
python manage.py runserver          # spusti dev server na porte 8000
python manage.py runserver 8080     # na inom porte
```

Server sa pri zmene `.py` súborov (views, modely, ...) reštartuje automaticky. Zmeny v `settings.py` alebo novo nainštalované balíčky vyžadujú ručný reštart (`Ctrl+C` a znova `runserver`).

### Zmeny v models.py → migrácie

Vždy po úprave niektorého modelu:

```bash
python manage.py makemigrations     # vygeneruje migračné súbory zo zmien v modeloch
python manage.py migrate            # aplikuje ich na databázu (db.sqlite3)
python manage.py showmigrations     # prehľad, ktoré migrácie sú/nie sú aplikované
```

Ak chceš vidieť SQL, ktoré sa spustí, bez toho aby sa naozaj aplikovalo:

```bash
python manage.py sqlmigrate documents 0004
```

### Admin a používatelia

```bash
python manage.py createsuperuser
```

### Shell a diagnostika

```bash
python manage.py shell              # Python shell s načítaným Django projektom
python manage.py check              # skontroluje projekt na chyby bez spustenia servera
```

### Testy

```bash
python manage.py test                        # spusti všetky testy v projekte
python manage.py test documents              # len testy pre app documents
python manage.py test rfid_auth              # len testy pre app rfid_auth
python manage.py test documents.tests.SyncDocumentsTests   # len jedna trieda testov
python manage.py test -v 2                   # verbose (vypíše názov každého testu)
```

## Sync dokumentov zo SharePointu (`documents/tasks.py`, `documents/sync.py`)

Sync beží normálne automaticky cez Celery Beat (`sync-documents-daily` o 3:00, `sweep-attachments-weekly` v nedeľu o 4:00 — pozri `CELERY_BEAT_SCHEDULE` v `config/settings.py`). Na ručné otestovanie počas vývoja **netreba spúšťať Celery ani Redis** — dá sa to zavolať priamo cez management command alebo shell.

### Ručné spustenie cez management command (odporúčané)

```bash
python manage.py sync_documents                 # plny sync vsetkych dokumentov z acLibPlatne
python manage.py sync_documents --limit 5        # len prvych 5 poloziek (rychle overenie, nerobi deaktivaciu chybajucich)
python manage.py sweep_attachments               # zosynchronizuje prilohy vsetkych aktivnych dokumentov
```

Vypíše JSON so štatistikami (`documents`, `versions_created`, `versions_updated`, `unchanged`, `skipped_no_number`, `deactivated`, `errors`).

### Verziovanie dokumentov

Identita dokumentu je **Číslo dokumentu** (`acColCisloDokumentu`, napr. `OS-90-01/21`) — v SharePointe nie je unikátne v čase. Každá položka v `acLibPlatne` je jedna **verzia** (`acColVerzia`: `-` = prvé vydanie, potom `A`, `B`, `C`…). Revízia dokumentu vzniká ako **nová položka s rovnakým číslom a vyšším písmenom**.

Sync preto:
- zoskupuje položky podľa čísla dokumentu (`Document`), jednotlivé verzie ukladá ako `DocumentVersion` (`version_label`),
- **aktuálna verzia = najvyššie písmeno prítomné v Platných**; staršie verzie ostávajú ako história a ich podpisy platia len na nich (nová verzia = nutnosť podpísať znova),
- položky bez čísla (stav „Príprava dokumentu…") preskakuje (`skipped_no_number`).

### Cez shell (keď chceš vidieť detaily / debugovať)

```bash
python manage.py shell
```

```python
from documents.sync import sync_documents, sweep_attachments
stats = sync_documents(limit=5)
stats
```

### Cez Celery task priamo (bez brokeru, synchrónne)

Ak chceš otestovať aj `documents/tasks.py` (napr. kvôli logovaniu cez `shared_task`), zavolaj task synchrónne pomocou `.run()` alebo `.apply()` — nepotrebuje bežiaci Redis/worker:

```python
from documents.tasks import sync_documents_task, sweep_attachments_task
sync_documents_task.run()          # spusti telo tasku priamo, v tomto procese
sweep_attachments_task.apply()     # alternativa, vracia AsyncResult (ale beží tiež synchrónne bez brokeru)
```

Skutočné asynchrónne spustenie cez `.delay()`/`.apply_async()` vyžaduje bežiaci Redis (`brew services start redis`) aj Celery worker:

```bash
celery -A config worker -l info
celery -A config beat -l info       # ak chceš aj periodický scheduler
```

## API endpointy

| Endpoint | Auth | Účel |
|---|---|---|
| `POST /api/auth/rfid-login/` | `X-Device-Token` | karta → session token (+ `unsigned_count`); throttling 60/min |
| `POST /api/auth/logout/` | Bearer | revokácia session |
| `GET /api/users/me/` | Bearer | profil prihláseného používateľa |
| `GET /api/users/` | Bearer (staff) | zoznam používateľov; `?search=`, `?is_active=`, `?business_unit__code=` |
| `POST /api/users/` | Bearer (staff) | vytvorenie používateľa |
| `GET /api/users/{id}/` | Bearer (staff) | detail používateľa |
| `PATCH /api/users/{id}/` | Bearer (staff) | úprava — priradenie/zmena RFID karty (`rfid_uid`), aktivácia/deaktivácia |
| `GET /api/users/business-units/` | Bearer | číselník prevádzok (kódy pre výber pri správe používateľov) |
| `GET /api/users/profession-categories/` | Bearer | číselník profesných kategórií |
| `GET /api/documents/?unsigned=true&search=OS-90` | Bearer | viditeľné dokumenty; `unsigned` filter na nepodpísané, `search` hľadá v čísle dokumentu a názve |
| `GET /api/documents/{id}/` | Bearer | detail + aktuálna verzia + prílohy |
| `GET /api/documents/{id}/versions/` | Bearer | história verzií + počty podpisov |
| `GET /api/documents/versions/{id}/file/` | Bearer | PDF verzie (404 kým nie je stiahnuté) |
| `GET /api/documents/attachments/{id}/file/` | Bearer | stream prílohy |
| `POST /api/signatures/sign/` | Bearer + RFID re-tap | podpis; 403 cudzia karta, 400 neaktuálna/neviditeľná, 409 duplicita |
| `GET /api/signatures/mine/` | Bearer | moja história podpisov |
| `GET /api/signatures/reports/document/{id}/` | Bearer (staff) | kto podpísal ktorú verziu |
| `GET /api/signatures/reports/unsigned/?document_id=&business_unit=` | Bearer (staff) | kto ešte nepodpísal aktuálnu verziu |

Podpis vyžaduje **opätovné fyzické priloženie karty** — `POST /api/signatures/sign/` s telom `{"document_version_id": "...", "rfid_uid": "..."}`; server overí, že `rfid_uid` patrí prihlásenému používateľovi (proof-of-presence).

### Interaktívna API dokumentácia (pre frontend)

```
http://127.0.0.1:8000/api/docs/      # Swagger UI (klikacia dokumentacia vsetkych endpointov)
http://127.0.0.1:8000/api/schema/    # surova OpenAPI 3 schema (YAML) na import do klientov
```

Generuje ju `drf-spectacular` automaticky z views/serializerov — netreba ju udržiavať ručne.

### Údržba RFID session-í

Expirované/revokované session-y sa dajú upratať (nie sú audit záznam — tým sú podpisy):

```bash
python manage.py cleanup_sessions            # zmaze neplatne staršie ako 7 dni
python manage.py cleanup_sessions --days 1   # agresivnejšie
```

Beží aj automaticky cez Celery beat (`cleanup-sessions-daily` o 2:30). Pri novom prihlásení sa navyše predošlé ešte platné session-y toho istého používateľa **revokujú** (jedna aktívna session na používateľa).

## Produkčné nastavenia (`.env`)

Pre dev bežia rozumné defaulty. Pred nasadením nastav v `.env`:

```dotenv
SECRET_KEY=<vygeneruj nahodny 50-znakovy retazec>
DEBUG=False
ALLOWED_HOSTS=kiosk.firma.sk,10.0.0.5
```

Časové pásmo je `Europe/Bratislava` (Celery beat aj admin časy sú v lokálnom čase). PDF dokumentov sa **neservujú** cez `/media/` — dostupné sú len cez autentifikované API (`/api/documents/versions/{id}/file/`), aby sa neobchádzala viditeľnosť.

Viditeľnosť dokumentov sa riadi cez `required_bu`/`required_pc` na dokumente + `DocumentVisibilityRule` pravidlá (spravujú sa v admine): inclusion/exclusion, typy ALL / BUSINESS_UNIT / PROFESSION_CATEGORY / BOTH / USER_EXPLICIT, voliteľné časové okno.

## RFID prihlásenie (`rfid_auth`)

```bash
python manage.py create_kiosk_device --name "Vrátnica" --location "Hlavný vchod"
```

Vypíše `X-Device-Token` — kiosk ho posiela v hlavičke `X-Device-Token` pri volaní `POST /api/auth/rfid-login/` (telo `{"rfid_uid": "..."}`). Úspešná odpoveď vráti `Bearer` token, ktorý sa posiela v `Authorization: Bearer <token>` pri ďalších requestoch a pri odhlásení `POST /api/auth/logout/`.

## Redis / Celery

Redis je potrebný **len** pre Celery worker/beat (asynchrónne úlohy), nie pre bežný `runserver`.

```bash
brew services start redis    # spustí Redis na pozadí natrvalo
redis-server                 # alternativa: spustí ho na popredí len teraz
redis-cli ping                # overenie, že beží (má vrátiť PONG)
```

## Inštalácia závislostí

```bash
pip install -r requirements.txt
```

Spusti vždy po `git pull`, ak sa zmenil `requirements.txt`, alebo po prvom nastavení venv.

## Logy

Logy z appiek (`documents`, `rfid_auth`, `integrations`, ...) sa vypisujú do terminálu (`runserver`, `manage.py test`, ...) a zároveň sa ukladajú do súboru:

```
logs/django.log
```

Rotuje automaticky po 5 MB (max 5 záložných súborov: `django.log.1` ... `django.log.5`). Priečinok `logs/` je v `.gitignore`, necommituje sa.
