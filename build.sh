#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py setup_roles
