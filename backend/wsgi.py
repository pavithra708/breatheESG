"""
WSGI config for Breathe ESG project.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path so settings can be imported
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

application = get_wsgi_application()
