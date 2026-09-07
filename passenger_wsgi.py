import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'suray_web.settings')

from suray_web.wsgi import application  # noqa: E402,F401
