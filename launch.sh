#!/bin/sh
set -eu
umask 077
APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$APP_ROOT/.venv/bin/python" "$APP_ROOT/Source/main.py" --root "$APP_ROOT" "$@"
