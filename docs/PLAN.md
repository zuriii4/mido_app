# Plán: Systém oboznamovania s platnými dokumentmi (mido_app)

## Kontext

Django/DRF aplikácia pre oboznamovanie zamestnancov s platnými dokumentmi: používatelia sa denne synchronizujú z externého HR programu, prihlasujú sa RFID kartou na kiosku, vidia nepodpísané dokumenty (denne synchronizované zo SharePointu `sites/acRd/acLibPlatne`, >1000 položiek + prílohy z `acLibPrilohy`) a podpisujú ich opätovným priložením karty.

**Súčasný stav:** dátový model (Document, DocumentVersion, Attachment, DocumentVisibilityRule, Signature, User/BusinessUnit/ProfessionCategory) existuje a je zmigrovaný. Celá aplikačná vrstva je prázdna: všetky `services.py`, `views.py`, `serializers.py`, `urls.py`, `users/tasks.py`, `rfid_auth/backends.py`, Celery beat schedule. Modelom chýbajú SharePoint identifikátory.

**Rozhodnutia (potvrdené používateľom):**
- Súbory sa ukladajú ako **lokálne PDF snapshoty per verzia** (Graph vie pri stiahnutí konvertovať docx→pdf cez `?format=pdf`) — podpísaná verzia je vždy zobraziteľná, aj keď ju SharePoint neskôr zmení.
- Zatiaľ **len backend API**, frontend neskôr (API kontrakt je definovaný nižšie).
- Podpis vyžaduje **opätovné priloženie RFID karty** (proof-of-presence).
- **Update:** Azure app registrácia je už k dispozícii (`APP_ID`, `TENANT_ID`, `SECRET` v `.env`, client-credentials flow, overené funkčné volanie na Graph). Postupujeme **priamo reálnym `GraphSharePointClient`** namiesto mocku — mock ostáva len ako voliteľná alternatíva pre neskoršie testy (za rovnakým rozhraním `SharePointClient`), nie ako prvý krok.

**Overené volaním Graph API priamo (bez Power Automate):**
- Site: `GET /v1.0/sites/tatravagonkask.sharepoint.com:/sites/acRd` → `site_id = tatravagonkask.sharepoint.com,e75c4f7c-e857-4d0f-bbf3-1cdb8faf6df9,f7a37397-3fa7-47d6-aaa1-e229b56cd76c`.
- Listy: `acLibPlatne` id `9bede49e-4aae-4d38-8b5e-e25d2ab82016` (documentLibrary), `acLibPrilohy` id `a0a7001b-007c-4a57-b3f7-101c48ebe71a` (documentLibrary).
- `GET /v1.0/sites/{site_id}/lists/{list_id}/items?$expand=fields&$top=200` vracia iný (jednoduchší) tvar polí než dump z Power Automate: `acColStavDokumentu` je tu **priamy string** `"Platný"` (Choice field, netreba lookup expand); `acColDokumentID`/`acColMasterID` prichádzajú ako float (`784.0`) → treba `int()`; verzia je v `_UIVersionString` (napr. `"20.0"`); zmena = `@odata.etag` / `eTag` na položke. **Chýbajú `DriveId`/`DriveItemId`** — tie boli špecifické pre Power Automate konektor; treba ich dotiahnuť cez samostatný vzťah `GET /sites/{site_id}/lists/{list_id}/items/{item_id}/driveItem` (vráti `id` = drive item id a `parentReference.driveId`), ešte neoverené sťahovanie/PDF konverzia cez `GET /drives/{drive_id}/items/{drive_item_id}/content?format=pdf`.

**Odpoveď na otázku „ako zistím zmenu, ak verzia ostáva rovnaká?":** V SharePointe verzia NEMÔŽE ostať rovnaká — každé uloženie súboru (aj oprava chyby na mieste, aj úprava metadát) inkrementuje verziu a zmení `@odata.etag`. Primárny signál zmeny = **etag** (uložený vs. aktuálny), doplnkovo `Modified` timestamp. Prílohy sú v inej knižnici, takže etag dokumentu ich NEpokrýva → samostatná rekonciliácia príloh.

---

## A. Schéma (aditívne migrácie)

### `documents/models.py` → migrácia `documents/0002`
Polia priamo na modeloch (jeden zdrojový systém, netreba link-model):

- **Document** (nové, null/blank kde treba): `sharepoint_id` (IntegerField, unique — upsert kľúč = SP `ID`), `ac_dokument_id` (CharField, db_index — `acColDokumentID`, názov priečinka príloh), `ac_master_id`, `drive_id`, `drive_item_id`, `etag` (posledný videný `@odata.etag` — signál zmeny), `content_type_name` (napr. „Organizačná smernica"), `effective_date` (DateField — `acColDatUcinnosti`), `sp_state` (`acColStavDokumentu`), `note` (TextField — `acColPoznamkaMulti`), `full_path`, `sp_link`, `sp_modified_at`, `last_synced_at`.
- **DocumentVersion** (nové): `sp_version_label` (CharField — surové `"20.0"`), `etag` (etag zachytený pri vzniku verzie), `sp_modified_at`.
  - `version_number` ostáva **interné monotónne počítadlo** (max+1), NIE parsovaný SP major — SP môže zmeniť etag bez zmeny major čísla a `unique_together(document, version_number)` by kolidoval. SP label je len na zobrazenie.
- **Attachment** (nové): `etag`, `server_relative_url` (db_index — identita súboru v priečinku), `sp_unique_id`, `file_size`, `sp_modified_at`.

### Nová app `integrations` → migrácia `integrations/0001`
- **SyncRun**: `sync_type` (USERS/DOCUMENTS/ATTACHMENT_SWEEP/DOWNLOADS), `status` (RUNNING/SUCCESS/PARTIAL/FAILED), `started_at`, `finished_at`, `stats` (JSONField — pages/seen/created/updated/deactivated/enqueued), `error_log`.
- **DownloadJob** — DB fronta sťahovania (prežije reštart workera, viditeľná v admine, funguje aj bez Celery): `job_type` (DOCUMENT_PDF/ATTACHMENT), FK `document_version`/`attachment`, `drive_id`+`drive_item_id` resp. `server_relative_url`, `convert_to_pdf`, `status` (PENDING/DOWNLOADING/DONE/FAILED, db_index), `attempts`, `max_attempts=5`, `last_error`, `next_retry_at`, FK `sync_run`.

### `rfid_auth/models.py` → migrácia `rfid_auth/0001`
- **KioskDevice**: `name` (unique), `token` (unique, `secrets.token_hex(32)`), `location`, `is_active`, `last_seen_at`.
- **RfidSession**: `token` (unique), FK `user`, FK `device`, `expires_at`, `revoked_at`, metóda `is_valid()`.

---

## B. Integračná vrstva — app `integrations/`

```
integrations/clients/
  base.py            # ABC: SharePointClient, HRClient
  dto.py             # frozen dataclasses: SPDocumentItem, SPFolderFile, HRUserRecord
  graph_parsers.py   # raw JSON → DTO (zdieľané mock aj real klientom, testovateľné)
  mock_sharepoint.py # číta fixtures, download_* vracia sample PDF bytes
  mock_hr.py
  graph_sharepoint.py# skeleton: MSAL client-credentials, Graph volania v docstringoch
  __init__.py        # get_sharepoint_client(), get_hr_client() cez import_string(settings.…)
integrations/fixtures/
  sharepoint/documents_page_1.json … page_N.json   # presný tvar Power Automate itemov, ≥2 stránky po ≤200
  sharepoint/attachments/<acColDokumentID>.json    # tvar GetFolderByServerRelativeUrl(...)/Files
  hr/users.json
  files/sample.pdf
```

Rozhranie:
```python
class SharePointClient(ABC):
    def iter_documents(self, page_size=200) -> Iterator[list[SPDocumentItem]]
    def list_attachment_folder(self, ac_dokument_id) -> list[SPFolderFile]
    def download_file_as_pdf(self, drive_id, drive_item_id) -> bytes
    def download_file(self, server_relative_url) -> bytes
class HRClient(ABC):
    def iter_users(self) -> Iterator[HRUserRecord]
```

Prepínanie: `SHAREPOINT_CLIENT_BACKEND` / `HR_CLIENT_BACKEND` v `.env` (default **`GraphSharePointClient`**, keďže Azure prístup už je funkčný — overené vyššie). Mock zostáva dostupný cez rovnaké prepnutie pre testy/CI bez sieťového prístupu.

`GraphSharePointClient` implementácia (nie skeleton, rovno reálna):
- Auth: `msal.ConfidentialClientApplication(APP_ID, authority=f"https://login.microsoftonline.com/{TENANT_ID}", client_credential=SECRET)`, `acquire_token_for_client(["https://graph.microsoft.com/.default"])`, token cachovaný a obnovovaný.
- `site_id` a `list_id` (acLibPlatne, acLibPrilohy) sa vyriešia raz pri štarte (cache v Django cache/settings, nemenia sa) — hodnoty vyššie sú overené a môžu byť predvyplnené v `.env` (`SP_SITE_ID`, `SP_LIST_PLATNE_ID`, `SP_LIST_PRILOHY_ID`), aby sa ušetrilo volanie pri každom syncu.
- `iter_documents(page_size=200)`: `GET /sites/{site_id}/lists/{list_id}/items?$expand=fields&$top=200`, stránkovanie cez `@odata.nextLink`; parser (`graph_parsers.py`) mapuje `fields.*` → `SPDocumentItem`, `int(float(...))` na `acColDokumentID`/`acColMasterID`, `_UIVersionString` → `version_label`, item-level `eTag` → `etag`.
- Drive item + PDF: pre každý item, ktorého treba stiahnuť, `GET /sites/{site_id}/lists/{list_id}/items/{id}/driveItem` → `drive_item_id`, `drive_id`; potom `GET /drives/{drive_id}/items/{drive_item_id}/content?format=pdf`. (Toto dodatočné volanie na driveItem sa robí len pre nové/zmenené položky, nie pre celý list — inak by to bolo 1000+ extra requestov na každý sync.)
- Prílohy: `list_attachment_folder(ac_dokument_id)` cez rovnaký vzorec ako `acLibPlatne` — buď `GET /sites/{site_id}/lists/{acLibPrilohy_list_id}/items?$expand=fields&$filter=...` (ak priečinky sú reprezentované ako foldre v tej istej knižnici, treba doriešiť filter podľa cesty) alebo `GET /sites/{site_id}/drive/root:/acLibPrilohy/{ac_dokument_id}:/children` — **treba ešte overiť, ktorý z týchto dvoch prístupov skutočne vráti súbory v podpriečinku** (nasledujúci krok probe skriptu).

---

## C. Sync pipeline

### Users — `users/services.py: sync_users_from_hr(client, sync_run)`
Upsert cez `update_or_create(external_id=…)`, `get_or_create` BusinessUnit/ProfessionCategory, kolízie `rfid_uid` logovať+preskočiť. Nevidení používatelia → `is_active=False` (nikdy nemazať — Signature má PROTECT). Task `users.sync_users` v `users/tasks.py` (guard proti súbežnému behu cez RUNNING SyncRun) + príkaz `manage.py sync_users`.

### Dokumenty — nový modul `documents/sync.py: sync_documents(client, sync_run)`
Pre každú stránku (200 ks) a item:
1. Upsert `Document` podľa `sharepoint_id`, zápis metadát + `last_synced_at`; `is_active = (stav == 'Platný')`.
2. **Detekcia zmeny:** nový dokument ALEBO `item.etag != document.etag` →
   - existujúcim verziám `is_current=False`; nová `DocumentVersion(version_number=next, sp_version_label, etag, is_current=True)` s prázdnym súborom,
   - enqueue `DownloadJob(DOCUMENT_PDF)`,
   - `reconcile_attachments(doc, new_version, client)`,
   - **až potom** uložiť nový `etag` na Document (pád uprostred = item sa spracuje znova → idempotencia).
3. Po slučke: dokumenty s `last_synced_at < run_start` → `is_active=False` (zmizli z knižnice Platné).
4. Opakovaný beh s nezmenenými dátami = no-op (etagy sedia); duplicitné DownloadJoby bráni get_or_create na (version, job_type, status PENDING/DOWNLOADING).

### Prílohy — `documents/sync.py: reconcile_attachments(document, version, client)`
Porovnanie remote (folder podľa `ac_dokument_id`) vs. lokálne prílohy verzie, kľúč `server_relative_url`:
- nová → `Attachment` + `DownloadJob(ATTACHMENT)`; zmenený etag → update + re-download; zmiznutá → zmazať **len na aktuálnej verzii** (historické verzie si snapshot držia).
- Pri novej verzii dokumentu: ak predchádzajúca verzia má prílohu s identickým etagom, **skopírovať už stiahnutý súbor** namiesto sťahovania (veľká úspora pri 1000+ dokumentoch).
- **Update:** prílohy sa (rovnako ako hlavné dokumenty) ukladajú ako **PDF snapshoty**, nie v pôvodnom formáte. `download_attachment()` skúsi `?format=pdf` (funguje pre doc/docx/xls/xlsx/tif/md a i.), a len ak Graph vráti 4xx (`InputFormatNotSupported` — napr. json, obrázky, zip), padne na stiahnutie originálu. Overené naživo: 48/49 reálnych príloh sa skonvertovalo, 1 fallback (`.jpg`). `Attachment.converted_to_pdf` (BooleanField) zaznamenáva, ktorý prípad nastal — dôležité pre zobrazovací frontend (fallback prílohy sa nedajú vykresliť ako PDF).

`sweep_attachments()` — periodický plný prechod aktívnych dokumentov (zmeny príloh nemenia etag dokumentu!). **Implementované** (`documents/sync.py`), Celery task `documents.sweep_attachments` + beat nedeľa 4:00. Rozhodnutie: aktualizuje prílohy **na mieste na existujúcej aktuálnej verzii** (rovnaké `Attachment.pk`), NEvytvára novú `DocumentVersion` — zmena prílohy sama o sebe nevyžaduje nové oboznámenie/podpis. Overené: simulovaná zastaraná príloha → `updated:1`, rovnaké `pk`, počet verzií dokumentu nezmenený. Príkaz: `manage.py sweep_attachments`.

### Fronta sťahovania — `integrations/services.py: process_download_queue(client, limit=50)`
Vyberie PENDING + FAILED s `attempts < max_attempts` a `next_retry_at <= now`; stiahne (PDF pre dokumenty, as-is pre prílohy), uloží cez `FileField.save(f'{doc.id}_v{n}.pdf', ContentFile(bytes))`; pri chybe `attempts+=1`, exponenciálny backoff `next_retry_at = now + 5min * 2**attempts`.

### Tasky a príkazy
Celery: `users.sync_users`, `documents.sync_documents` (po skončení reťazí drain fronty), `documents.sweep_attachments`, `integrations.process_download_queue`.
Management príkazy (dev bez Celery/Redis): `sync_users`, `sync_documents`, `sync_attachments`, `process_downloads`, `create_kiosk_device --name kiosk-1`.

---

## D. Autentifikácia (bez JWT, bez DRF authtoken — vlastné opaque tokeny s TTL + revokáciou)

Nový `rfid_auth/authentication.py`:
- `KioskDeviceAuthentication` — hlavička `X-Device-Token` → aktívny `KioskDevice`, vracia `(None, device)`.
- `RfidSessionAuthentication` — `Authorization: Bearer <token>` → platná `RfidSession`, vracia `(session.user, session)`.

`rfid_auth/backends.py: RfidBackend.authenticate(request, rfid_uid)` → aktívny User podľa `rfid_uid`; pridať do `AUTHENTICATION_BACKENDS`. `rfid_auth/permissions.py: IsKioskDevice`.

**Flow:** kiosk má statický device token (provisioning cez príkaz) → priloženie karty → `POST /api/auth/rfid-login {rfid_uid}` s `X-Device-Token` → vytvorí `RfidSession` (TTL `RFID_SESSION_TTL`, default 10 min), vráti `{token, expires_at, user, unsigned_count}` → všetky volania s Bearer tokenom → **podpis = ďalšie fyzické priloženie karty**: `POST /api/signatures/sign {document_version_id, rfid_uid}` — server overí `rfid_uid == request.user.rfid_uid`, nesúlad → 403.

Fix v settings: vyhodiť `TokenAuthentication` (authtoken nie je nainštalovaný), nasadiť tieto dve triedy.

**Implementované a otestované naživo (real HTTP cez `manage.py runserver`):** `rfid_auth/{models,authentication,permissions,backends,views,serializers,urls}.py`, `users/{views,serializers,urls}.py`, `create_kiosk_device` príkaz, `KioskDevice`/`RfidSession` v admine. Testovaný celý flow so skutočným testovacím používateľom (`rfid_uid=1183524315`): login bez device tokenu → 403, login s neznámou kartou → 404, login so správnou kartou → 201 + Bearer token, `/api/users/me/` bez tokenu → 403, s tokenom → 200, logout → 204, opätovné použitie tokenu po logout → 403 ("Session expirovala alebo bola odhlásená"). `unsigned_count` v login response zatiaľ vynechaný (čaká na krok 8 — viditeľnosť dokumentov).

## E. API kontrakt (DRF)

| Endpoint | Auth | Účel |
|---|---|---|
| `POST /api/auth/rfid-login` | device token | karta → session token |
| `POST /api/auth/logout` | session | revokácia session |
| `GET /api/users/me` | session | profil |
| `GET /api/documents/?unsigned=true` | session | viditeľné dokumenty; filter na nepodpísanú aktuálnu verziu |
| `GET /api/documents/{id}/` | session | detail + aktuálna verzia + prílohy (file URL) |
| `GET /api/documents/{id}/versions/` | session/staff | história verzií + počty podpisov |
| `GET /api/documents/versions/{id}/file/` | session | FileResponse lokálneho PDF (404 kým download nie je DONE) |
| `GET /api/documents/attachments/{id}/file/` | session | stream prílohy |
| `POST /api/signatures/sign` | session + re-tap | 201; 409 už podpísané; 403 rfid mismatch; 400 neaktuálna/neviditeľná verzia |
| `GET /api/signatures/mine` | session | moja história podpisov |
| `GET /api/signatures/reports/document/{id}/` | staff | kto podpísal ktorú verziu (user, signed_at, rfid_uid_used, device) |
| `GET /api/signatures/reports/unsigned/?document_id=&business_unit=` | staff | kto ešte nepodpísal aktuálnu verziu |

Súbory: `documents/{views,serializers,permissions,urls}.py`, `signatures/{views,serializers,services,urls}.py` (`create_signature()` v transakcii, IntegrityError→409), `users/{views,serializers,urls}.py`, `rfid_auth/{views,serializers,urls}.py`.

## F. Viditeľnosť — `documents/services.py`
`get_visible_documents(user)`, `get_unsigned_documents(user)`, `get_required_users(document)` (pre reporty). Sémantika: bázová brána `required_bu`/`required_pc` (null = bez obmedzenia) → ak existujú inclusion pravidlá (v platnom časovom okne), aspoň jedno musí sedieť → akékoľvek exclusion pravidlo dokument odoberie. Implementácia cez `Q` + `Exists` subquery (jeden dotaz). Unsigned filter vylúči aj dokumenty, ktorých aktuálna verzia ešte nemá stiahnutý súbor (kiosk nikdy neukáže neotvoriteľný dokument).

## G. Settings / Celery / .env
- Redis broker (dev: docker), `CELERY_TASK_ALWAYS_EAGER` pre testy, `DatabaseScheduler`.
- Beat: users 02:00, documents 03:00 denne, attachment sweep nedeľa 04:00, drain fronty každých 10 min.
- Začať používať `python-decouple` (`config()`) aj pre SECRET_KEY/DEBUG; `MEDIA_ROOT/MEDIA_URL`.
- `.env.example` s kľúčmi: `SHAREPOINT_CLIENT_BACKEND`, `HR_CLIENT_BACKEND`, `CELERY_BROKER_URL`, `RFID_SESSION_TTL_SECONDS` + rezervované pre Graph: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `SP_SITE_ID`, `SP_DOCS_DRIVE_ID`, `SP_ATTACH_DRIVE_ID`, `SP_ATTACH_LIBRARY_PATH=/sites/acRd/acLibPrilohy`, `HR_API_BASE_URL`, `HR_API_TOKEN`.
- Housekeeping: zmazať `from pickle import FALSE` (users/models.py), duplicitný `AUTH_USER_MODEL`, pridať `msal`, `pytest`, `pytest-django` do requirements.

## H. Testy (pytest + pytest-django, mock klienti, tmp MEDIA_ROOT)
Kľúčové prípady: idempotencia syncov (druhý beh = nuly); **zmena etagu pri rovnakom názve súboru** → nová interná verzia + flip is_current + download job; dokument zmiznutý z fixtures → inactive; stránkovanie cez ≥2 fixture stránky; rekonciliácia príloh (nová/zmenená/zmazaná, historická verzia nedotknutá, kópia pri zhodnom etagu); backoff a terminálny FAILED v download fronte; matica viditeľnosti; RFID login/expiry/logout; podpis — happy path, **rfid mismatch → 403 bez záznamu**, duplicita → 409, neaktuálna verzia → 400.

## I. Poradie implementácie (fázy = samostatne overiteľné PR)

**Update:** keďže Azure prístup je funkčný, poradie sa mení tak, aby sme čo najskôr mali reálne fungujúce sťahovanie dokumentov + scheduled task (explicitná požiadavka používateľa začať práve tu). Mock klient a `integrations` app scaffold okolo neho sa presúvajú na neskôr / robia sa len ak/keď treba testovať bez siete.

1. **Housekeeping + schéma** — sekcia G housekeeping + migrácie (documents/0002, integrations/0001, rfid_auth/0001) + admin registrácie. Overenie: `makemigrations --check`, `migrate`, admin.
2. **Integrations app: DTO, ABC + rovno `GraphSharePointClient`** (bez mocku) — `iter_documents`, driveItem+PDF download, `.env` doplniť o `SP_SITE_ID`, `SP_LIST_PLATNE_ID`, `SP_LIST_PRILOHY_ID`. Overenie: v shelli `get_sharepoint_client().iter_documents()` vráti reálne stránky z `acLibPlatne`; ručné stiahnutie jedného PDF.
3. **Document sync + download fronta (reálne dáta).** Overenie: `sync_documents && process_downloads` → PDF v `media/documents/` zo skutočného SharePointu; zmena etagu na existujúcom dokumente v SharePointe → nová verzia po ďalšom synchu, starý súbor nedotknutý.
4. **Celery beat pre document sync** — `documents.sync_documents` scheduled task (denne), `integrations.process_download_queue` (drain fronty). Overenie: s Redisom beat registruje tasky, vynútený beh end-to-end na reálnych dátach.
5. **User sync** — service + task + príkaz (HR endpoint zatiaľ nie je dostupný → tu ostáva mock/`HRClient` rozhranie). Overenie: `manage.py sync_users` 2× → druhý beh nuly.
6. **Rekonciliácia príloh + sweep** (po doriešení, ako sa v Graph adresujú priečinky v `acLibPrilohy`). Overenie na reálnych dátach.
7. **Auth stack** — authentication.py, backends, login/logout, create_kiosk_device. Overenie curl-om: device token → Bearer → `/api/users/me`.
8. **Viditeľnosť + documents API + streaming súborov.** Overenie: pravidlá v admine, curl `?unsigned=true`, stiahnutie PDF.
9. **Podpisovanie + reporty.** Overenie: podpis → dokument zmizne z unsigned; mismatch → 403; reporty sedia cez 2 verzie.
10. **Mock klienty + fixtures + testy** — doplniť `MockSharePointClient`/`MockHRClient` za rovnaké rozhranie (pre CI/testy bez siete) a pytest sadu podľa sekcie H.

**Keď príde HR endpoint:** doimplementovať `GraphHRClient`/reálny HR klient, prepnúť env premennú — zvyšok systému sa nemení.

---

## Stav implementácie (update 2026-07-16)

- **Fázy 1–4, 6, 7: hotové** (housekeeping čiastočne — `pickle` import zmazaný, `is_staff` pole doplnené na User + migrácia `users/0002`; download fronta z plánu nahradená synchrónnym sťahovaním priamo v `sync_documents` — DownloadJob/SyncRun modely sa zatiaľ nerealizovali).
- **Fáza 8: hotová** — `documents/services.py` (get_visible_documents/get_unsigned_documents/get_required_users, Q+Exists), documents API + file streaming, `DocumentVisibilityRule` v admine.
- **Fáza 9: hotová** — `signatures/{services,serializers,views,urls}.py`: POST sign s RFID re-tap (mismatch → 403 bez záznamu, neaktuálna/neviditeľná → 400, duplicita → 409), mine, staff reporty (document, unsigned), `unsigned_count` doplnený do rfid-login response, Signature v admine (read-only).
- **Fáza 10: čiastočne** — testy pre sync, sweep, viditeľnosť, documents API, rfid_auth a podpisovanie (bez pytest, Django TestCase s fake SharePoint klientom namiesto formálnych mock tried).
- **Fáza 5 (user sync z HR): nezačatá** — `users/{services,tasks}.py` a `sync_users` command sú prázdne, čaká na HR endpoint.

## Stav implementácie (update 2026-07-17)

Doplnené medzery mimo pôvodných fáz (správa používateľov + prevádzka), keďže bez nich sa systém nedal spravovať inak než cez Django admin:

- **Users staff API** — `users/{serializers,views,urls}.py`: `GET/POST /api/users/` (zoznam + create, filtre `is_active`/`is_staff`/`business_unit__code`, search), `GET/PATCH /api/users/{id}/` (detail + úprava). Kľúčové: **priradenie/zmena RFID karty a deaktivácia cez PATCH**. `UserAdminSerializer` (BU/profesia cez kód/názov, `rfid_uid` unique + blank→NULL). Bez PUT. `IsAdminUser`.
- **Throttling** — `rfid-login` má `ScopedRateThrottle` 60/min (proti brute-force `rfid_uid`).
- **Cleanup session-í** — `manage.py cleanup_sessions [--days N]` maže expirované/revokované `RfidSession`.
- **OpenAPI dokumentácia** — `drf-spectacular`: `/api/docs/` (Swagger UI) + `/api/schema/`. Vlastné auth triedy zaregistrované cez `rfid_auth/schema.py`; APIViews anotované `@extend_schema`. Schéma sa generuje bez warningov/errorov.
- **Testy:** 109 (bolo 93), +16 pre users API, throttle scope a cleanup command.

Stále nezačaté: **Fáza 5 (HR sync)** — čaká na HR endpoint; a formálne mock triedy + pytest (fáza 10).

## Verziovanie dokumentov — prepracované (update 2026-07-17)

Pôvodné verziovanie podľa `etag` bolo **nesprávne**. Overené na živej vzorke (680 položiek `acLibPlatne`):

- **Identita dokumentu = Číslo dokumentu** (`acColCisloDokumentu`, napr. `OS-90-01/21`) — nie je unikátne v čase.
- **Verzia = `acColVerzia`**: `-` (prvé vydanie) < `A` < `B` < … < `N`.
- Revízia = **nová list-item položka** (nový `sharepoint_id`) s rovnakým číslom a vyšším písmenom (potvrdené prípadom `31250008`: položky `-` a `A`).

Zmeny:
- `Document`: identita `document_number` (unique); `sharepoint_id`/`etag` presunuté na úroveň verzie.
- `DocumentVersion`: `version_number` (interný counter) → `version_label` (`acColVerzia`); pribudlo `sharepoint_id` (per položka), `title` (názov verzie), `sp_ui_version` (`_UIVersionString`), `effective_date`.
- `sync.py`: zoskupenie podľa čísla, aktuálna = najvyššie prítomné písmeno, položky bez čísla sa preskakujú.
- API: `?search=` v `/api/documents/` hľadá v čísle dokumentu aj názve; `document_number` v list/detail.
- Migrácie `documents/0004` (vyčistenie dev dát — 0 podpisov) + `0005` (nová schéma).
- Overené naživo: sync 25 dokumentov (25 verzií, 0 chýb), 2. beh idempotentný (0 vytvorených, 25 unchanged). Testy: 112 (sync testy prepísané na novú sémantiku).

## Zaplátané medzery (update 2026-07-17, časť 2)

Z analýzy kódu (okrem git init a rotácie kiosk tokenu — vynechané zámerne):

- **Media leak** — zrušené `static()` servovanie `/media/` (obchádzalo viditeľnosť); PDF idú len cez autentifikované API. Overené: reálny súbor cez `/media/` → 404.
- **users/admin.py** — zaregistrované `User`, `BusinessUnit`, `ProfessionCategory` (predtým prázdny admin; opravený aj rozbitý raw_id lookup vo visibility rules).
- **Číselníky API** — `GET /api/users/business-units/` a `/profession-categories/`.
- **Produkčné settings** — `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` z `.env` cez `config()` (dev defaulty zachované); `TIME_ZONE = 'Europe/Bratislava'`.
- **cleanup_sessions** — pridaný do `CELERY_BEAT_SCHEDULE` (denne 2:30) + Celery task `rfid_auth.cleanup_sessions` (command a task zdieľajú `delete_stale_sessions`).
- **Single-session** — nový login revokuje predošlé platné session-y používateľa.
- **Sync robustnosť** — pád jednej verzie nezhodí skupinu ani nastavenie aktuálnej; `_version_key` znesie viacpísmenové verzie; aktuálna verzia uprednostní tú so stiahnutým súborom.
- Testy: **117** (+5).

Stále nezačaté: **Fáza 5 (HR sync)**, git init a rotácia kiosk tokenu (vedome vynechané), formálne mock triedy + pytest.
