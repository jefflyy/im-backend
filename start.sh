#!/bin/sh
mkdir -p database/media
python3 manage.py makemigrations im
python3 manage.py migrate

# python3 manage.py runserver 0.0.0.0:80
# uwsgi --module=DjangoHW.wsgi:application \
#     --env DJANGO_SETTINGS_MODULE=DjangoHW.settings \
#     --master \
#     --http=0.0.0.0:8001 \
#     --processes=5 \
#     --harakiri=20 \
#     --max-requests=5000 \
#     --vacuum

daphne -b 0.0.0.0 -p 80 DjangoHW.asgi:application
