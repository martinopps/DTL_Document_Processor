#!/bin/sh
set -eu
umask 077
APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$APP_ROOT"
sha256sum Source/main.py Source/dtl/*.py requirements.lock Build/build_linux.sh > Build/source-sha256.txt
export XDG_CACHE_HOME="$APP_ROOT/Build/cache"
.venv/bin/python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name DTL-Document-Processor --distpath Build/Linux --workpath Build/pyinstaller \
  --specpath Build --paths Source \
  --add-data "$APP_ROOT/Source/dtl/assets:dtl/assets" \
  --hidden-import PySide6.QtPdf --hidden-import PySide6.QtPdfWidgets \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets \
  --exclude-module PySide6.QtWebEngineQuick Source/main.py

cp README.md THIRD_PARTY_NOTICES.md Build/Linux/DTL-Document-Processor/
cp -R Build/LICENSES Build/Linux/DTL-Document-Processor/

sha256sum --check Build/source-sha256.txt
