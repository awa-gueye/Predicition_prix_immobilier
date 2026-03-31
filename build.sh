set -o errexit

pip install -r requirement.txt
python manage.py collectstatic --noinput
python manage.py makemigrations listings --noinput
python manage.py migrate
python manage.py shell -c "
from django.contrib.auth.models import User
try:
    u = User.objects.get(username='admin')
    u.set_password('Admin2026!')
    u.is_superuser = True
    u.is_staff = True
    u.is_active = True
    u.save()
    print('Admin mis a jour')
except User.DoesNotExist:
    User.objects.create_superuser('admin','admin@immopredict.sn','Admin2026!')
    print('Admin cree')
"