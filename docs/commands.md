# Management Commands

Prehľad všetkých Django management commands v projekte.

## Použitie

```bash
py manage.py <app_name>.<command_name> [args]
```

Príklad: `py manage.py notifications.remind_unsigned --dry-run`

## documents

### sync_documents
Synchronizuje dokumenty (a ich prílohy) z SharePointu (acLibPlatne/acLibPrilohy).

```bash
py manage.py documents.sync_documents
py manage.py documents.sync_documents --limit 10   # len 10 dokumentov (pre testovanie)
```

### sweep_attachments
Prechádza všetky dokumentové verzie a stahuje chýbajúce prílohy zo SharePointu.

```bash
py manage.py documents.sweep_attachments
```

## notifications

### remind_unsigned
Posiela pripomienky na podpis dokumentov, ktoré ešte neboli podpísané.

```bash
py manage.py notifications.remind_unsigned                   # všetky dokumenty
py manage.py notifications.remind_unsigned --document-number OS-90-01/21   # len jeden dokument
py manage.py notifications.remind_unsigned --dry-run       # náhľad bez zmeny dát
py manage.py notifications.remind_unsigned --document-number OS-90-01/21 --dry-run
```

Beží denne automaticky cez Celery Beat (každý deň o 6:00).

## rfid_auth

### create_kiosk_device
Vytvorí nový kiosk device. Token sa zobrazí len raz — treba si ho zapísať.

```bash
py manage.py rfid_auth.create_kiosk_device --name "Výroba kiosk 1" --location "Výroba"
```

### cleanup_sessions
Zmaže expirované a revokované RFID session-y staršie ako N dní.

```bash
py manage.py rfid_auth.cleanup_sessions             # default 30 dní
py manage.py rfid_auth.cleanup_sessions --days 7    # staršie ako 7 dní
py manage.py rfid_auth.cleanup_sessions --dry-run  # len náhľad
```

Beží automaticky cez Celery Beat (každý deň o 2:30).

## users

### sync_users (nedokončené)
Prázdny súbor — príkaz ešte nie je implementovaný.

---

## Vlastné argumenty (spoločné)

| Argument | Popis |
|---|---|
| --dry-run | Len náhľad, nič nemení |
| -v, --verbosity 0-3 | Úroveň detailu výstupu |

## Zoznam všetkých

| Príkaz | Čo robí |
|---|---|
| documents.sync_documents | Sync dokumentov zo SharePointu |
| documents.sweep_attachments | Stiahni prílohy zo SharePointu |
| notifications.remind_unsigned | Pripomienky nepodpísaných dokumentov |
| rfid_auth.create_kiosk_device | Vytvor kiosk device + token |
| rfid_auth.cleanup_sessions | Zmaž staré RFID session |
| users.sync_users | *(nedokončené)* |
