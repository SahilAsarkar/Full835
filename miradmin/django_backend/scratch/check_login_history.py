import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'onesmarter_admin.settings')
django.setup()

from api.models import LoginHistory
from django.contrib.auth.models import User

print("--- USERS ---")
for u in User.objects.all():
    print(f"ID: {u.id}, Username: {u.username}, Is Staff: {u.is_staff}, Is Superuser: {u.is_superuser}")

print("\n--- LOGIN HISTORY ---")
for log in LoginHistory.objects.all().order_by('-login_time')[:10]:
    print(f"ID: {log.id}, Username: {log.username}, Time: {log.login_time}, Status: {log.status}, IP: {log.ip_address}")
