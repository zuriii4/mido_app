# MIDo App - Ucebny plan 2 (pripomienkovy system / reminders)

Ciel: naucit sa periodicke Celery ulohy a pokrocilejsi ORM. Staviame na
module 1 (notifications) a signatures.

## Biznis pozadie
Dnes sa notifikacie vytvoria LEN pri syncu dokumentu. Ak pouzivatel dokument
nepodpise, nikto mu to nepripomenie. Reminder = notifikacia tym, ktori maju
aktualnu verziu dokumentu nepodpisanu.

## Co sa naucis noveho
- exclude() cez subquery (kto UZ podpisal aktualnu verziu)
- vlastne tasks.py v notifications appke (zatial mas len hook v cudzom tasku)
- Celery beat: periodicka uloha v CELERY_BEAT_SCHEDULE (crontab)
- ladenie periodickej ulohy bez cakania na 6:00 rano (management command)

## Pravidla hry (rovnake ako modul 1)
1. Mentor nepise kod - da zadanie + akceptacne kriteria. Ty pises.
2. Poradie pri zaseknuti: skus sam -> referencna appka -> pytaj sa.
3. Koniec etapy = explain back + zeleny manage.py check + commit.
4. Po kazdom auto-importe skontroluj from riadky hore v subore.

## Stav
- [ ] Etapa 1: Service - najdi nepodpisujucich (get_unsigned_users_for_document)
- [ ] Etapa 2: Service - vytvor pripomienky (create_reminder_notifications)
- [ ] Etapa 3: Management command remind_unsigned
- [ ] Etapa 4: Celery task v notifications/tasks.py
- [ ] Etapa 5: Beat schedule (denne 6:00)
- [ ] Etapa 6: Testy
- [ ] Etapa 7: Explain back + review celeho modulu

---

## Etapa 1 - Service: kto este nepodpisal
**Ciel:** funkcia, ktora pre dokument vrati queryset userov, ktori ho maju
podpisat ale aktualnu verziu este nepodpisali.

**Koncepty:** exclude() so subquery, __in lookup, get_required_users.

**Kroky:**
1. `notifications/services.py`: nova funkcia `get_unsigned_users_for_document(document)`.
2. Zaklad: `get_required_users(document)` z documents/services.py (uz existuje,
   vrati userov podla BU/PC pravidiel).
3. Z nej VYFILTRUJ tych, co podpisali aktualnu verziu:
   `Signature.objects.filter(document_version=document.current_version)` -> ich user_id.
4. `.exclude(id__in=<signed_user_ids>)`.
5. Hrany pripad: dokument bez aktualnej verzie (current_version je None) -> vrat `User.objects.none()`.

**Akceptacne kriteria:**
- User co podpisal aktualnu verziu NIE je vo vysledku
- User co podpisal len STARSIU verziu JE vo vysledku (novu verziu musi podpisat znova)
- Dokument bez current_version -> prazdny queryset, ziaden crash

**Referencie:** documents/services.py (get_required_users), signatures/models.py (Signature).

---

## Etapa 2 - Service: vytvor pripomienky
**Ciel:** `create_reminder_notifications(document)` - bulk_create notifikacii
pre nepodpisujucich, idempotentne.

**Koncepty:** recyklacia vzoru z Etapy 8 (modul 1), odlisny text spravy.

**Kroky:**
1. Pouzi `get_unsigned_users_for_document(document)` z Etapy 1.
2. Idempotencia: preskoc userov, ktori uz pre TENTO dokument notifikaciu maju
   (rovnaky trik s already_notified_ids ako v create_notifications_for_document).
3. Message: `f"Pripomienka: dokument '{document.title}' stale caka na vas podpis."`
4. bulk_create, vrat pocet vytvorenych.

**Otazka na zamyslenie:** Preco reminder nerobime samostatnym modelom
(Reminder), ale len inym textom Notification? (Jednoduchost: jeden inbox,
jeden mark-as-read, ziadna duplicitna logika.)

**Akceptacne kriteria:**
- Prvy beh: N notifikacii. Druhy beh: 0.
- Podpisany user pripomienku nedostane.

---

## Etapa 3 - Management command
**Ciel:** rucne spustenie bez cakania na Celery.

**Koncepty:** BaseCommand, add_arguments, self.stdout.write(style uspechu).

**Kroky:**
1. `notifications/management/__init__.py` + `notifications/management/commands/__init__.py` + `notifications/management/commands/remind_unsigned.py`.
2. Argument `--document-number` (volitelny; bez neho prejde VSETKY aktivne dokumenty s current verziou).
3. Pre kazdy dokument zavolaj `create_reminder_notifications`, vypis sumar.
4. Referencia struktury: pozri existujuci command v projekte (napr. create_kiosk_device).

**Akceptacne kriteria:**
- `python manage.py remind_unsigned --document-number TEST-NOTIF-001` -> vypise pocet
- `python manage.py remind_unsigned` -> prejde vsetky aktivne dokumenty, vypise sumar
- Druhe spustenie -> 0 novych

---

## Etapa 4 - Celery task
**Ciel:** tvoje PRVE tasks.py vo vlastnej appke.

**Koncepty:** @shared_task, autodiscover_tasks (uz je zapnuty v config/celery.py).

**Kroky:**
1. `notifications/tasks.py` - pozri ako referenciu documents/tasks.py (14 riadkov).
2. Task `notifications.remind_unsigned` - loop cez aktivne dokumenty s current
   verziou, vola service, loguje sumar, vracia stats dict.
3. Over ze Celery task vidi: spusti cez shell `from notifications.tasks import remind_unsigned_task`.

**Akceptacne kriteria:**
- `remind_unsigned_task.delay()` (alebo `.apply()` v eager mode) bezi bez chyby
- Log obsahuje sumar: kolko dokumentov, kolko pripomienok

---

## Etapa 5 - Beat schedule
**Ciel:** uloha bezi sama kazdy den.

**Koncepty:** CELERY_BEAT_SCHEDULE, crontab, DatabaseScheduler (uz nastaveny).

**Kroky:**
1. `config/settings.py` -> CELERY_BEAT_SCHEDULE (riadok ~199, su tam 3 ulohy).
2. Pridaj stvrtu: `schedule: crontab(hour=6, minute=0)`, task: 'notifications.remind_unsigned'.
3. Restartuj beat proces ak bezi.

**Otazka na explain back:** Preco 6:00 rano a nie 3:00 (kedy bezi sync)?
(Navod: sync musi stihnut dobehnut, aby reminders nesli nad starymi datami.)

**Akceptacne kriteria:**
- Entry v CELERY_BEAT_SCHEDULE
- `python manage.py check` zeleny

---

## Etapa 6 - Testy
**Ciel:** 4 testy do notifications/tests.py.

**Kroky:**
1. `get_unsigned_users_for_document`: podpisany vyluceny, nepodpisany zahrnuty.
2. `create_reminder_notifications`: prvy beh N, druhy beh 0.
3. Dokument bez current_version -> 0, ziadna chyba.
4. User co podpisal starsiu verziu -> DOSTANE pripomienku (novu verziu nepodpisal).

**Referencie:** tvoje existujuce testy z modulu 1, core/testutils.py fabriky.

---

## Etapa 7 - Explain back
Vlastnymi slovami vysvetli:
1. Ako funguje exclude() so subquery a preco je to jeden SQL dotaz.
2. Cely retazec: beat 6:00 -> task -> service -> bulk_create -> notifikacia v inboxe.
3. Preco je reminder len Notification s inym textom a nie novy model.
4. Co by sa stalo, keby sme idempotenciu vynechali a beat bezal tyzdeň?

---

## Za modulom 2 (nahlad do buducna)
- Modul 3: Reporty a statistiky (annotate/Count agregacie, CSV export, IsAdminUser)
- Modul 4: Audit log (kto sa kedy prihlasil, podpisal; middleware; date_hierarchy)
