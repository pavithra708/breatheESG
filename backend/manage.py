#!/usr/bin/env python
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    # Add the backend directory to the path so settings can be imported
    backend_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(backend_dir))
    
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    
    from django.core.management import execute_from_command_line
    
    execute_from_command_line(sys.argv)
