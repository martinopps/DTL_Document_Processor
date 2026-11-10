#!/usr/bin/env python3
import os
os.umask(0o077)
if os.name == 'posix':
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import argparse
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from dtl.ui_backend import Store
from dtl.ui import Window
from dtl.platform_support import default_workspace

def main():
    parser = argparse.ArgumentParser(description='Offline DTL Document Processor')
    parser.add_argument('--root', type=Path, default=default_workspace())
    parser.add_argument('--smoke-test', action='store_true', help='Open UI briefly without reading any workbook')
    args = parser.parse_args()
    if sys.platform.startswith('linux') and os.environ.get('QT_QPA_PLATFORM', 'xcb') == 'xcb' and not os.environ.get('WAYLAND_DISPLAY'):
        import ctypes
        try:
            ctypes.CDLL('libxcb-cursor.so.0')
        except OSError:
            print('DTL needs the Ubuntu desktop package libxcb-cursor0. Ask your administrator to install it, then launch again.', file=sys.stderr)
            return 2
    import logging
    logging.getLogger('pypdf').addHandler(logging.NullHandler())
    logging.getLogger('pypdf').propagate = False
    from PySide6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(lambda *args: None)
    app = QApplication(sys.argv[:1])
    app.setApplicationName('DTL Document Processor')
    def safe_exception_hook(*_):
        QMessageBox.warning(None, 'Needs attention', 'An unexpected interface error occurred. Close and restart DTL to recover. Originals are preserved.')
    sys.excepthook = safe_exception_hook
    app.setStyle('Fusion')
    try:
        store = Store(args.root)
        window = Window(store)
        window.show()
        if args.smoke_test:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, window.close)
        return app.exec()
    except Exception as exc:
        from dtl.models import UserError
        message = str(exc) if isinstance(exc, UserError) else 'Cannot start. Check application folder permissions, disk space and local state. Contact your administrator.'
        QMessageBox.critical(None, 'DTL startup needs attention', message)
        return 1

if __name__ == '__main__':
    sys.exit(main())
