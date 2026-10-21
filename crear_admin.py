import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "suray_web.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
u, creado = User.objects.get_or_create(username=os.environ["ADMIN_USER"])
u.is_staff = u.is_superuser = True
u.set_password(os.environ["ADMIN_PASSWORD"])
u.save()
print("creado" if creado else "actualizado", u.username)