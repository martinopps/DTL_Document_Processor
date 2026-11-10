# Validation record — 2026-11-09

Final automated run: **55 passed, 0 failed**, in 2.43 seconds on Python 3.12.3 / Ubuntu 24.04.4 x86-64. Exact output: `Build/test-results.txt`. All fixtures are synthetic and remain under Build. The supplied workbook and actual attendance scans were not opened.

Executed successfully:

- Workbook schema/mapping, full/separate names, text leading zeroes, numeric formatting warnings, duplicate names/assignments, conflicting identities, and multiple contracts.
- Qt GUI approval/mapping, name-only options and first/last autocomplete, explicit record and contract selection, manual copay confirmation, unknown versus zero payment, validation retention, preview invalidation and changed-source rejection.
- Complete headless GUI workflow: preview, confirm, save, archived original byte equality, field reset, processed queue status, and undo.
- Portrait/landscape and rotated first-page stamps, multipage preservation, unsupported-font rejection, and identical scanned-image pixel content before/after stamping.
- Contract routing, surname and sanitized-contract collisions, unmanaged output protection, same-client append order, exact undo of appended pages, and source-content idempotency.
- Master sorting, contract/month isolation, safe regeneration, stale markers and unmanaged master protection.
- Simulated archive/output write failures, unfinished append rollback on actual Store reopen, interrupted undo recovery, access permissions, instance locking, and path/symlink escape rejection.
- PyInstaller Linux x86-64 onedir build: `Build/final-packaging.log`. `Build/source-sha256.txt` verifies source, requirements and build script agree with the build snapshot.
- Built executable headless startup/shutdown: `QT_QPA_PLATFORM=offscreen ... --root Build/final-binary-smoke --smoke-test` exited 0.
- Synthetic stamp rendered through Poppler and inspected visually. `qpdf --check Build/QA/stamp-preview.pdf` found no syntax or stream-encoding errors. Synthetic UI screenshots inspected at laptop size (1280×800) and larger.

Observed platform blocker:

- Qt's X11 platform plugin needs `libxcb-cursor.so.0`, absent here. The executable's X11 preflight exits 2 with a clear instruction to install Ubuntu package `libxcb-cursor0`. Public package-download attempts failed due network name resolution; no system directories/packages were changed. The employee's administrator must install it before ordinary X11 launch. Offscreen testing does not replace testing on an actual desktop.

Limits and required human acceptance:

- Real workbook columns/records deliberately uninspected: map and verify locally only after employer approval.
- Test actual desktop scaling, mouse/keyboard flow, representative approved scans, printer readability, large-document performance and unusual page boxes/fonts.
- Simulated failures are not physical power-loss, actual full-disk, or all-filesystem tests. Validate approved local filesystem atomicity, backups, restoration and retention policy.
- Runtime source has no HTTP/socket/cloud integration; WebEngine modules are excluded. An attempted `strace` network smoke audit was blocked by the sandbox's ptrace restriction, so there is no syscall-level no-network proof from this session.
- Finish employer privacy/storage/access approval and redistribution license review. Offline software alone is not HIPAA compliance.
