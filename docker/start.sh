#!/usr/bin/env bash

cd /app || echo "Unable to navigate to /app"

python manage.py migrate
python manage.py compilemessages
python manage.py collectstatic --noinput --clear
supercronic --quiet /etc/crontab &
(python manage.py tcuserver 0.0.0.0; [ "$?" -lt 2 ] && kill "$$") &
(daphne -b 0.0.0.0 -p 80 --access-log - "$@" carwings.asgi:application; [ "$?" -lt 2 ] && kill "$$") &
wait
