#!/bin/sh

python manage.py collectstatic --noinput
python manage.py migrate
gunicorn bridged.wsgi -b 0.0.0.0:8000 -w 3 -t 300
