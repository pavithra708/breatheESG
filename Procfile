release: python backend/manage.py migrate
web: gunicorn -w 4 -b 0.0.0.0:$PORT backend.wsgi:application
