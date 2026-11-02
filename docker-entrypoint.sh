#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py shell -c 'from django.core.management import call_command; from store.models import Product; call_command("seed_raw") if not Product.objects.exists() else None'
exec "$@"
