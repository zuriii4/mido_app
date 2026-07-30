# MIDo App - Ucebny plan Django (modul notifications)

Ciel: naucit sa Django/DRF prakticky, na realnom projekte. Kazda etapa = jedna
vrstva frameworku. Mentor dava zadania a robi review, kod pises ty.

## Pravidla hry
1. Mentor nepise kod - da zadanie + akceptacne kriteria. Ty pises, aj ked to trva.
2. Poradie pri zaseknuti: skus sam -> pozri referencnu appku -> pytaj sa (napoveda, nie riesenie).
3. Koniec etapy = explain back vlastnymi slovami + zeleny `manage.py check` + commit.
4. Po kazdom auto-importe v IDE skontroluj riadky `from ...` hore v subore.

## Stav
- [x] Etapa 1: Model + migracia (Notification, related_name, UUID, BaseModel)
- [x] Etapa 2: Serializer + ListAPIView (GET /api/notifications/)
- [x] Etapa 3: URLs + test cez REST Client (kiosk login -> Bearer -> 200/403)
- [x] Etapa 4: PATCH mark-read (prvy zapis cez API) - UpdateAPIView, idempotencia, update_fields
- [x] Etapa 5: Services + permissions (architektura) - tenke views, ORM v services.py
- [x] Etapa 6: Admin (list_display, list_filter, search_fields, readonly_fields)
- [x] Etapa 7: Testy (anonym 403, vlastne/cudzie, mark-read 200/404)
- [x] Etapa 8: Tvorba notifikacii (bulk_create, OR filter Q, idempotencia, hook v syncu)
- [-] Etapa 9: Filtre a cistenie - PRESKOCENE (dva endpointy stacia)

## Modul 1 HOTOVO. Pokracovanie: docs/learning-plan-2.md (pripomienkovy system)

---

## Etapa 4 - PATCH mark-read
**Ciel:** PATCH /api/notifications/{id}/read/ oznaci notifikaciu ako precitanu.

**Koncepty:** APIView s metodou patch, get_object_or_404, save(update_fields=...), status kody.

**Kroky:**
1. `notifications/views.py`: nova trieda `NotificationMarkReadView(APIView)` s metodou `patch(self, request, pk)`.
2. Vnutri: najdi notifikaciu kde `pk=pk` A `user=request.user` (inak Http404), nastav `is_read=True`, uloz, vrat serializer.
3. `notifications/urls.py`: `path('<uuid:pk>/read/', NotificationMarkReadView.as_view(), name='notification-read')`.
4. `notifications.http`: pridaj request 4 (PATCH s Bearer tokenom).

**Akceptacne kriteria:**
- PATCH na svoju notifikaciu -> 200, `is_read: true`
- PATCH na cudziu -> 404 (nie 403 - prezradzalo by to, ze existuje)
- GET zoznam potom ukazuje `is_read: true`

**Otazky na rozmyslenie:** Preco 404 a nie 403 pri cudzej? Co robi `update_fields` a preco ho pouzit?

**Referencia:** `documents/views.py` (DocumentVersionsView - APIView s get), `rfid_auth/views.py` (RfidLogoutView - POST co meni stav).

---

## Etapa 5 - Services + permissions
**Ciel:** presun biznis logiky z views do `notifications/services.py` (tenke views).

**Kroky:**
1. `notifications/services.py`: `get_user_notifications(user)`, `mark_notification_read(user, pk)`.
2. Views uz len volaju services - ziaden ORM kod vo views.

**Otazky:** Co ziskas service vrstvou pri testovani? Preco je vo views `get_queryset` teraz jednoriadkovy?

**Referencia:** `documents/services.py` (`get_visible_documents`).

---

## Etapa 6 - Admin
**Ciel:** notifikacie v /admin/.

**Kroky:** `notifications/admin.py` - `NotificationAdmin` s `list_display`, `list_filter`, `search_fields`.

**Akceptacne kriteria:** zoznam s message/user/document/is_read; filter podla is_read; hladanie v message.

**Referencia:** `documents/admin.py`, `users/admin.py`.

---

## Etapa 7 - Testy
**Ciel:** `notifications/tests.py` so 4 testami.

**Koncepty:** TestCase, DRF APIClient, fabriky z `core/testutils.py`, force_authenticate.

**Testy:** list vrati len moje; anonym 403; mark-read 200; mark-read na cudziu 404.

**Referencia:** `documents/tests.py`, `core/testutils.py`.

---

## Etapa 8 - Tvorba notifikacii (Celery hook + mgmt command)
**Ciel:** ked sync najde novy dokument, vytvoria sa notifikacie userom, ktori ho musia podpisat.

**Koncepty:** Celery task, `bulk_create`, idempotencia (ziadne duplicity pri opakovani).

**Kroky:**
1. `notifications/services.py`: `create_notifications_for_document(document)` - useri podla `required_bu` / `required_pc`.
2. Napojenie na `documents/sync.py` po vytvoreni novej verzie (diskusia: kam presne a preco).
3. `notifications/management/commands/notify_test.py` - rucne spustenie z CLI.

**Otazky:** `bulk_create` vs `create` v cykle? Ako zabezpecis, ze druhy sync nevytvori duplicitne notifikacie?

**Referencia:** `documents/tasks.py`, `documents/sync.py`, `rfid_auth/tasks.py`.

---

## Etapa 9 - Filtre a cistenie
**Ciel:** `GET /api/notifications/?unread=true` + cleanup starych precitanych.

**Kroky:**
1. `get_queryset`: citaj `self.request.query_params.get('unread')`.
2. Management command / Celery Beat task na mazanie starych precitanych.

**Referencia:** `documents/views.py` (param `unsigned`), `rfid_auth/tasks.py` (cleanup_sessions), `CELERY_BEAT_SCHEDULE` v settings.

---

## Zdroje
- Django tutorial: https://docs.djangoproject.com/en/5.2/intro/tutorial01/
- DRF: https://www.django-rest-framework.org/ (Views, Serializers, Permissions)
- Referencne appky v projekte: documents/, signatures/, rfid_auth/
- Testovanie API: `notifications/notifications.http` (REST Client)
