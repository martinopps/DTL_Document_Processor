# Third-party components

The application uses these local Python distributions; versions are pinned in `requirements.lock`. Installed package metadata was checked during development.

| Component | Installed license declaration |
| --- | --- |
| PySide6 / Qt bindings and Qt PDF | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; commercial terms may also be available from the vendor |
| pypdf | BSD-3-Clause |
| reportlab | BSD (additional bundled fonts have their own terms) |
| openpyxl | MIT |
| PyInstaller | GPLv2-or-later with its bootloader distribution exception |
| DejaVu Sans | See `Source/dtl/assets/FONT-LICENSE.txt` |

The output is an onedir bundle with dynamically loaded Qt shared libraries. Keep shared libraries replaceable and preserve applicable license notices. Qt and its third-party components have additional notices/source obligations; employer or distributor review must confirm compliance before distributing outside the approved environment. No claim of blanket license compliance is made by this build. PySide6's wheel metadata declares alternative licenses but did not supply all Qt license texts in this environment.

`Build/LICENSES/` contains license files available in the installed packages and system common-license directory, plus distribution metadata. The font license is also bundled with the executable. Application source and build instructions are delivered alongside the executable. PyInstaller's bootloader exception permits distributing applications under their own terms; this document does not choose a license for employer-owned application code.

Official references: [Qt PDF licensing and PDFium component list](https://doc.qt.io/qt-6/qtpdf-licensing.html), [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations), and [PyInstaller license / exception](https://www.pyinstaller.org/en/stable/license.html). These references were checked during development; no confidential data was transmitted. The runtime has no web access feature.

Qt PDF licensing was checked against the official Qt documentation: https://doc.qt.io/qt-6/qtpdf-licensing.html . Qt PDF is offered under commercial terms, LGPLv3 or GPLv2, and embeds PDFium plus third-party components whose notices must also be respected. The installed wheel metadata alone does not enumerate every embedded dependency.
