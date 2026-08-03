
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.test import Client

c = Client()

# 1. Home page
resp = c.get('/kiosk/')
print(f"1. HOME GET: {resp.status_code}")
content = resp.content.decode()
print(f"   'Prilozte kartu': {'Priložte kartu' in content}")
print(f"   CSRF token: {'csrfmiddlewaretoken' in content}")

# 2. POST s rfid_uid=000000
resp = c.post('/kiosk/', {'rfid_uid': '000000'}, follow=True)
print(f"2. HOME POST rfid_uid=000000: status={resp.status_code}")
print(f"   redirect_chain: {resp.redirect_chain}")
content = resp.content.decode()
if 'Ahoj' in content:
    print(f"   ✓ Dashboard s pozdravom uzivatela")
if 'Neznáma' in content:
    print(f"   CHYBA: karta nebola najdena")

# 3. Dashboard bez auth
c2 = Client()
resp2 = c2.get('/kiosk/dashboard/')
print(f"3. DASHBOARD bez auth: {resp2.status_code}")

# 4. Logout
resp3 = c.get('/kiosk/logout/', follow=True)
print(f"4. LOGOUT: {resp3.status_code}, chain: {resp3.redirect_chain}")
