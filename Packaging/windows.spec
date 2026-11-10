# Build with PyInstaller on Windows; paths are relative to this spec, not the checkout.
from pathlib import Path

root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(root / 'Source/main.py')],
    pathex=[str(root / 'Source')],
    binaries=[],
    datas=[(str(root / 'Source/dtl/assets'), 'dtl/assets')],
    hiddenimports=['PySide6.QtPdf', 'PySide6.QtPdfWidgets'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='DTL-Document-Processor', debug=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DTL-Document-Processor')
