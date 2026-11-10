# Observed verification — 2026-11-09

- Automated suite: **55 passed, 0 failures**, synthetic records/PDFs only; the final output is in `Build/test-results.txt`.
- Headless Qt GUI tests exercise mapping with approval, a name-only dropdown, first/last matching, separate duplicate-name identity and contract selection, manual confirmation reset, preview, save, exact undo and source-change rejection.
- Core tests cover Excel mappings/zeroes/duplicates, missing records, copay validation, page/rotation preservation, permanent first-page text, unsupported-font rejection, append/idempotency, contract and filename collisions, alphabetized contract/period-specific masters, permissions, instance locking, simulated disk-write failures and recovery from interrupted save/undo.
- PyInstaller built a Linux x86-64 onedir executable successfully. See `Build/packaging.log`. The release directory includes dependency metadata and available license texts.
- The packaged binary was smoke-tested with `QT_QPA_PLATFORM=offscreen`, including a workspace with a synthetic queued PDF. This verifies startup, Qt PDF loading and shutdown without opening the real workbook.
- A synthetic interface image was rendered and visually inspected at 1400×900: `Build/visual-review/synthetic-interface.png`. The three panels, viewer, stamp preview and verification controls fit and are legible.
- **Interactive desktop launch remains blocked on this host:** `ldd` reports missing `libxcb-cursor.so.0` for Qt's X11 plugin. Ubuntu package `libxcb-cursor0` must be installed by the workstation administrator. Download attempts failed because repository DNS was unavailable. A preflight check reports the dependency and exits without invoking the failing platform plugin.
- The supplied workbook and real attendance PDFs were not opened during development. Test inputs were generated locally. No data directories, configuration, audit database, logs or intake documents are added by the explicit PyInstaller packaging command.

Human testing remains: actual workstation interaction/display scaling after dependency installation, representative approved scans, printer readability, less common fonts/page boxes, large-document performance, employer storage/backup approval, real filesystem locking/atomicity, and physical power-loss or actual full-disk scenarios. The automated failure tests simulate faults and do not establish those environmental guarantees. No claim of HIPAA compliance is made.

Do not permit concurrent builds to rewrite the source while testing or packaging. A second process was observed modifying files during development; final verification uses the source remaining at the end of the session. `Build/source-sha256.txt` records the final source/requirements/build-script hashes.

Additional final validation and observed sandbox limits are recorded in `Build/VALIDATION.md`.
