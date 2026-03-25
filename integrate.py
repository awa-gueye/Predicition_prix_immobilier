"""
integrate.py — Intégration ImmoAnalytics dans Django (django-plotly-dash).

USAGE : python integrate.py
Placer à la racine du projet Django (à côté de manage.py).
"""
import os, sys, shutil, subprocess

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
INTEGRATION_DIR = os.path.join(BASE_DIR, "integration")
DJANGO_PROJECT  = "immobilier_project"
PYTHON          = sys.executable


def run(cmd):
    print(f"    $ {cmd}")
    return subprocess.run(cmd, shell=True, cwd=BASE_DIR).returncode == 0


def step(n, title):
    print(f"\n{'─'*60}\n  {n}. {title}\n{'─'*60}")


# ── 1. Dépendances ────────────────────────────────────────────────────────────
step(1, "Installation des dépendances")
run(f"{PYTHON} -m pip install "
    "django-plotly-dash==2.3.1 channels==4.0.0 "
    "dash==2.14.2 dash-bootstrap-components==1.5.0 plotly==5.18.0")

# ── 2. App immoanalytics_dash ─────────────────────────────────────────────────
step(2, "Copie de immoanalytics_dash/")
src  = os.path.join(INTEGRATION_DIR, "immoanalytics_dash")
dest = os.path.join(BASE_DIR,        "immoanalytics_dash")
if os.path.exists(dest):
    shutil.copytree(os.path.join(src,"dash_apps"), os.path.join(dest,"dash_apps"), dirs_exist_ok=True)
    print("    ✅ dash_apps/ mis à jour")
else:
    shutil.copytree(src, dest)
    print("    ✅ immoanalytics_dash/ copié")

# ── 3. Templates + CSS ───────────────────────────────────────────────────────
step(3, "Copie des templates et du CSS")
for f in os.listdir(os.path.join(INTEGRATION_DIR,"templates","immoanalytics")):
    dest_tpl = os.path.join(BASE_DIR,"templates","immoanalytics"); os.makedirs(dest_tpl,exist_ok=True)
    shutil.copy(os.path.join(INTEGRATION_DIR,"templates","immoanalytics",f), os.path.join(dest_tpl,f))
print("    ✅ templates/immoanalytics/ mis à jour")

css_src = os.path.join(INTEGRATION_DIR,"static","immoanalytics","css","modern-ui.css")
css_dst = os.path.join(BASE_DIR,"static","immoanalytics","css"); os.makedirs(css_dst,exist_ok=True)
shutil.copy(css_src, os.path.join(css_dst,"modern-ui.css"))
print("    ✅ static/immoanalytics/css/modern-ui.css copié")

# ── 4. settings.py ───────────────────────────────────────────────────────────
step(4, "Patch de settings.py")
sp = os.path.join(BASE_DIR, DJANGO_PROJECT, "settings.py")
with open(sp,"r",encoding="utf-8") as f: s = f.read()

if "django_plotly_dash" not in s:
    s = s.replace(
        "'django.contrib.staticfiles',",
        "'django.contrib.staticfiles',\n"
        "    'django_plotly_dash.apps.DjangoPlotlyDashConfig',\n"
        "    'channels',\n"
        "    'immoanalytics_dash.apps.ImmoAnalyticsDashConfig',",
    )
    print("    ✅ INSTALLED_APPS")

if "BaseMiddleware" not in s:
    s = s.replace(
        "'django.contrib.sessions.middleware.SessionMiddleware',",
        "'django.contrib.sessions.middleware.SessionMiddleware',\n"
        "    'django_plotly_dash.middleware.BaseMiddleware',",
    )
    print("    ✅ MIDDLEWARE")

if "DashAssetsFinder" not in s:
    s += f"""
# django-plotly-dash
X_FRAME_OPTIONS = 'SAMEORIGIN'
PLOTLY_DASH = {{
    "ws_route":"dpd/ws/channel","http_route":"dpd/views",
    "http_poke_enabled":True,"view_decorator":None,
    "cache_arguments":True,"serve_locally":True,"insert_demo_viewer":False,
}}
ASGI_APPLICATION = '{DJANGO_PROJECT}.asgi.application'
CHANNEL_LAYERS = {{"default":{{"BACKEND":"channels.layers.InMemoryChannelLayer"}}}}
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django_plotly_dash.finders.DashAssetsFinder',
]
STATICFILES_DIRS = [BASE_DIR / 'static']
LOGIN_URL = '/immo/login/'
"""
    print("    ✅ Config django-plotly-dash + STATICFILES_FINDERS + LOGIN_URL")

with open(sp,"w",encoding="utf-8") as f: f.write(s)

# ── 5. urls.py ───────────────────────────────────────────────────────────────
step(5, "Remplacement de urls.py")
up = os.path.join(BASE_DIR, DJANGO_PROJECT, "urls.py")
with open(up,"r") as f: existing = f.read()

if "dpd/" not in existing:
    shutil.copy(os.path.join(INTEGRATION_DIR,"urls_patch.py"), up)
    print("    ✅ urls.py remplacé")
else:
    print("    ℹ️  urls.py déjà configuré")

# ── 6. asgi.py ───────────────────────────────────────────────────────────────
step(6, "Création de asgi.py")
asgi_dest = os.path.join(BASE_DIR, DJANGO_PROJECT, "asgi.py")
shutil.copy(os.path.join(INTEGRATION_DIR,"asgi.py"), asgi_dest)
with open(asgi_dest,"r") as f: ac = f.read()
ac = ac.replace("immobilier_project.settings", f"{DJANGO_PROJECT}.settings")
with open(asgi_dest,"w") as f: f.write(ac)
print("    ✅ asgi.py créé")

# ── 7. Migrations ────────────────────────────────────────────────────────────
step(7, "Migrations")
run(f"{PYTHON} manage.py migrate")

# ── 8. Collectstatic ─────────────────────────────────────────────────────────
step(8, "Collecte des fichiers statiques")
run(f"{PYTHON} manage.py collectstatic --noinput")

# ── 9. Utilisateurs démo ─────────────────────────────────────────────────────
step(9, "Création des utilisateurs démo")
script = f"""
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','{DJANGO_PROJECT}.settings')
django.setup()
from django.contrib.auth.models import User
for ud in [
    dict(username='admin',  password='admin123',  email='admin@immoanalytics.sn',
         first_name='Admin',  last_name='ImmoAnalytics', is_superuser=True,  is_staff=True),
    dict(username='analyst',password='analyst123',email='analyst@immoanalytics.sn',
         first_name='Analyste',last_name='Senior',     is_superuser=False, is_staff=True),
    dict(username='viewer', password='viewer123', email='viewer@immoanalytics.sn',
         first_name='Visiteur',last_name='Demo',       is_superuser=False, is_staff=False),
]:
    if not User.objects.filter(username=ud['username']).exists():
        u=User.objects.create_user(username=ud['username'],password=ud['password'],
          email=ud['email'],first_name=ud['first_name'],last_name=ud['last_name'],
          is_superuser=ud['is_superuser'],is_staff=ud['is_staff'])
        print(f"    ✅ {{ud['username']}} / {{ud['password']}}")
    else:
        print(f"    ℹ️  {{ud['username']}} existe déjà")
"""
exec(compile(script,"<string>","exec"),{})

print("""
╔══════════════════════════════════════════════════════════════╗
║   ✅  Intégration terminée !                                  ║
╠══════════════════════════════════════════════════════════════╣
║   python manage.py runserver                                  ║
╠══════════════════════════════════════════════════════════════╣
║   /immo/login/   → Connexion                                  ║
║   /dashboard/    → Dashboard   (staff/admin)                  ║
║   /analytics/    → Analytics   (staff/admin)                  ║
║   /viewer/       → Recherche IA (tous)                        ║
║   /map/          → Carte        (staff/admin)                 ║
║   /immo-admin/   → Admin Panel  (admin)                       ║
║   /admin/        → Django Admin                               ║
║   /api/          → API REST (inchangée)                       ║
╠══════════════════════════════════════════════════════════════╣
║ admin / admin123  |  analyst / analyst123  |  viewer / viewer123  ║
╚══════════════════════════════════════════════════════════════╝
""")
