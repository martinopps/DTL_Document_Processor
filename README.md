# DTL Document Processor

A working offline Python / PySide6 desktop application for manually classifying attendance PDFs. The employee reads names visually, verifies the workbook assignment, enters copay information, reviews the stamp, and files a copy by contract. There is no OCR, AI, upload, telemetry, remote database, or network document processing.

## Windows installer

See [WINDOWS.md](WINDOWS.md) for the GitHub Actions installer download, local Windows build instructions, workspace locations and acceptance checks. Windows compatibility adapters and packaging are included; consult the workflow result for actual Windows validation.

## Launch on Ubuntu

Open `Build/DTL-Document-Processor.desktop` (your desktop may require **Allow Launching**) or run:

```bash
cd /home/martinprime/Scans/DTL_Document_Processor
./Build/Linux/DTL-Document-Processor/DTL-Document-Processor --root "$PWD"
```

Keep the executable together with its `_internal/` directory. The PyInstaller **Linux x86-64 onedir** bundle does not need the virtual environment or Python installed. It is not a Windows `.exe`. Build on the oldest approved Linux distribution you intend to support; a Linux build is not universally portable across glibc versions. **Local desktop blocker:** this development environment is missing `libxcb-cursor.so.0` (`libxcb-cursor0` on Ubuntu). Headless source and binary smoke tests pass, but normal X11 launch needs this package installed by the workstation administrator. Download attempts were blocked by network name resolution; no system packages were changed.

A graphical Linux session and system Qt display dependencies are required (on Ubuntu these commonly include X11/XCB, xkbcommon, and GL/EGL libraries). Headless QA uses `QT_QPA_PLATFORM=offscreen`; employees should launch normally.

Source launcher, using the included local virtual environment:

```bash
./launch.sh
```

Recreate dependencies and build, without putting records in the development environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pytest Tests --basetemp=Build/test-run
./Build/build_linux.sh
```

Package installation is development-time network activity. The running application does not install dependencies or make network requests. Source entry points use the same local engine; the packaged entry point is `Source/main.py`.

## First use: employer approval and workbook mapping

A workbook must be selected on first use; no developer-specific workbook path is configured by default. **Development never opened its client records or inspected actual attendance scans.** All fixtures, screenshots, and test outputs are fictional. The reference workbook is never included in the binary or distribution and is never written by the application.

1. Obtain employer approval and apply the security checklist below before importing real data.
2. Select **Workbook mapping…**, confirm approval, and choose the approved `.xlsx` workbook.
3. Load worksheets, choose the worksheet and header row, then load headers. Only column labels are previewed in the mapper.
4. Map Client Number and Contract Number, plus either Full Name or separate First Name / Last Name columns. Do not map any copay columns; they are never read as copay inputs. Each role uses a separate column. When Full Name is used, a separate Last Name column may supply the filing surname.
5. Accept and import. Use **Refresh approved client list** to explicitly reread the workbook after approved changes. The app does not automatically read it on startup.

Identifiers are strings. Text-cell leading zeroes are preserved. Simple numeric zero masks such as `00000` are honored, but any numeric identifiers trigger a warning: already-lost digits or leading zeroes cannot be reconstructed reliably. Verify against the employer's authoritative source, preferably storing IDs as text in an approved workbook copy. The app never fabricates missing identifiers. Blank rows are ignored; incomplete populated rows and conflicting names for the same client number block import. Exact duplicate assignments are deduplicated with a warning.

The client dropdown contains **names only** and searches first or last names, case-insensitively. Identical names appear once. After selecting a name, use the separate **Verify identity** control to choose the client number, then **Confirm contract** to explicitly choose its contract. Neither a duplicate identity nor a contract is silently guessed, even for a single match. Read-only number fields show the chosen assignment.

Full names in `Last, First` order are recognized; otherwise the final word and common suffixes form the initial filing surname. Verify **Verified filing last name**, especially compound surnames, suffixes, or unfamiliar name order. It controls the filename and master sort order. Once a client-month output exists, additional pages must use the same filing name; undo earlier actions to correct it consistently.

## Employee procedure

1. Save an attachment to `Intake/`, then click **Refresh Intake**. Wait until copying is complete; files modified within two seconds cannot be saved. The app checks readability and source integrity again when saving. Queue history includes completed archived originals.
2. Select a queued PDF. Use zoom, Fit Page, Fit Width, scrolling, and page navigation to inspect every page. Do not process a document containing different clients. **Skip / Flag** keeps the intake original and a restricted review snapshot in `Flagged/`; return it to the queue only after approved review. This app does not separate or redact documents.
3. Set the processing month and year. These settings persist on normal close and save.
4. Select the name, explicitly verify identity and contract, compare the read-only IDs with the approved source, and verify the filing surname.
5. Manually select **Copay Required: Yes or No**. There is no confirmed default. Manually enter **Copay Amount**, including `0.00` when appropriate. **Copay Paid** may remain blank when unknown / not checked; `0.00` means checked and nothing paid. Negative values, thousands separators, and amounts with more than two decimal places are rejected. Workbook values never fill these fields.
6. Confirm all pages belong to this one client and contract. Click **Preview permanent stamp**. The stamp is added to page 1 only. Upper-left is the initial placement; upper-right and **Add top margin** are alternatives. Top margin preserves all original visible writing by adding blank space above it. Other placements can cover writing. There is no automatic overlap detection: visually verify the result.
7. Check the preview-confirmation box, including the processing period, identifiers, copay, and uncovered writing. A form change invalidates preview. Click **Save & Next** or press Ctrl+Enter. Invalid input keeps the current document. Manual copay and document confirmations clear for the next scan.
8. The saved client PDF is reopened and page-count verified; the exact untouched source is archived only after output preparation succeeds. Intake removal happens after a committed audit record and a verified original archive. If deletion is unavailable, its processed status prevents another append.

**Open next queued PDF after saving** controls whether the app advances or displays the archived original. Previous changes selection without processing. Manual selection discards unsaved classification fields.

## Output and masters

Normal output: `Contract_Output/<contract>/<LastName>_DTL_<Month>_<Year>.pdf`.

The same verified client number + exact contract + month + year appends new stamped source pages to its existing PDF, in processing order. Different clients sharing a surname receive a deterministic identity-hash suffix; their pages never append to each other. Unmanaged files are not overwritten. Unsafe path traversal and separators are rejected; sanitized contract collisions receive distinct suffixes. Identical source contents are treated as already processed regardless of filename. Use Undo to reclassify an original instead of submitting it under another filename.

For the selected period, click **Generate Master Contract PDFs**. The app warns about outstanding intake / flagged files. It merges completed client-month PDFs only, ordered by verified surname, first name, then stable identity. It does not use previous masters as inputs or combine periods or contracts. The summary lists per-contract client-file counts.

Normal master output: `Master_Contracts/<contract>/<Contract>_DTL_<Month>_<Year>_MASTER.pdf`. Regeneration replaces managed masters atomically. A contract-slug collision receives a hash suffix. `.owner` files distinguish app-managed masters from unrelated preexisting files. Do not delete them.

Processing and Undo mark monthly masters stale in SQLite and place a `.STALE.txt` marker next to existing affected masters. **Never distribute a master while its marker exists or the app reports stale masters.** Regenerate after additions or corrections. Multi-contract regeneration is not one filesystem transaction: if it fails, the period stays stale and must be regenerated. If undo removes the last client in a period, old masters stay stale and cannot be used; an administrator can retain or remove these obsolete masters under the employer's retention policy.

## Undo and recovery

**Undo Last Processing Action** reverses successful processing in reverse chronological order. It restores the original intake filename and the exact prior client PDF bytes. If the action appended pages, undo removes exactly those appended pages and preserves earlier sheets. It restores the queue for reclassification and marks masters stale. To correct an older action, undo newer actions first and reprocess them in order.

SQLite journals a pending action before changing outputs. Output updates use private temporary files, flush/fsync, and atomic replacement. Earlier client PDFs are kept in `Config/recovery/`. On restart, unfinished saves roll back and interrupted undo operations finish idempotently. Unexpected external edits, damaged backups, conflicting intake filenames, or missing originals stop recovery rather than overwriting unfamiliar data. Preserve the complete workspace for an administrator to recover; do not delete the database to bypass a conflict.

Archived originals and recovery backups are intentionally retained after undo or failed actions. This costs disk space but protects originals. There is no automatic retention deletion, redo, or arbitrary historical editing. Do not manually edit generated client PDFs; their hashes are checked before append, undo, and master generation. Only one application process may use a workspace at a time.

If a PDF is corrupt, password-protected, locked, partly copied, or unreadable, wait and refresh or flag it. If storage is read-only or full, free approved disk space / restore permissions and restart to complete recovery. Error messages avoid raw exception values and record contents. Do not enable verbose dependency logging with real data. Complex PDFs, unusual rotations/crop boxes, digital signatures, and uncommon fonts need employee visual review; stamping a cryptographically signed PDF changes its signed content.

## Storage and confidentiality

- `Intake/`: unmodified waiting PDFs and flagged originals.
- `Processed_Originals/`: exact original copies, named by random action ID; the audit record links them to their intake filename.
- `Contract_Output/`: stamped client-month PDFs.
- `Flagged/`: review snapshots; returning a flag to the queue retains its snapshot for recovery.
- `Master_Contracts/`: generated monthly contract masters and management / stale markers.
- `Config/`: settings, restricted SQLite audit, preview, lock and recovery backups. This is **sensitive storage**, not a debug log. It includes names, client identity hashes, contracts, filenames, content hashes and processing links. PDFs themselves contain identifiers and entered copays. Preview is removed on normal close, but may remain after a crash.
- `Logs/`: reserved for generic operational events; never names, IDs, copays, PDF images, or sensitive full paths. Normal runtime does not emit record-level debug logs.
- `Source/`, `Tests/`, `Build/`: source, synthetic QA, and compiled distribution. Test runs and visual review write fictional workspaces under Build only.

All configurable document folders must be separate directories inside this workspace; external or overlapping storage and symlink escapes are blocked. Workbook reads are the sole external data input. On Unix, data directories use mode `0700`; created files and temporary files use `0600`. On Windows, access depends on inherited NTFS ACLs; verify the approved workspace permissions as described in `WINDOWS.md`. Existing files dropped by another process may have its permissions until archived: the private intake directory limits access. Store the whole workspace on approved local encrypted storage. Standard file permissions are not encryption and do not protect against an administrator or another process under the same account.

### Employer approval checklist

- [ ] Approve the purpose, employee workflow, minimum necessary information, and workbook / contract verification process.
- [ ] Confirm this workstation and storage location are approved; disable cloud synchronization and unapproved backups or indexing for all data, previews, swap, recovery files, and archives.
- [ ] Enable employer-approved full-disk encryption, encrypted swap or equivalent protection, individual accounts, least-privilege access, screen locking, and physical safeguards.
- [ ] Approve encrypted backups and test restoration of the **whole workspace**, including SQLite and recovery backups. Stop the app before taking a consistent backup.
- [ ] Define retention and secure disposal for intake, originals, flags, client PDFs, masters, previews, audit and recovery backups. Review snapshots remain after unflagging; undo retains archived originals.
- [ ] Validate workbook mappings and identifiers, including numeric-cell formatting, duplicate names, multiple contracts, and filing surnames.
- [ ] Train employees to flag multi-client documents for an approved separation/redaction process and to inspect stamp placement on every save.
- [ ] Approve the master review and release procedure; ensure stale files are never shared and contract recipients receive only appropriate documents.
- [ ] Validate on the actual approved desktop with synthetic records before production. Review packaging licenses and software updates with IT.

Offline operation does not make this software inherently HIPAA-compliant. Employer policy, access controls, backups, handling practices, and applicable compliance review remain necessary.

## Implementation and validation

Python 3.12, PySide6 / Qt PDF viewer, openpyxl read-only import, pypdf structural PDF assembly, ReportLab stamp generation, SQLite durable metadata, and PyInstaller Linux packaging. Scanned images are not rasterized or recompressed during stamping; the first page gains permanent text while later page content remains intact. Preview and output use the same stamp engine. A bundled DejaVu Sans font supports common accented names; employees must inspect uncommon scripts / glyphs.

The stack avoids PyMuPDF's AGPL/commercial licensing choice. Installed package metadata identifies pypdf as BSD-3-Clause, ReportLab as BSD, openpyxl as MIT, PySide6 / Qt components as LGPL/GPL alternatives, and PyInstaller as GPL with its application-bundling exception. Qt PDF includes third-party PDFium components; see the [official Qt PDF licensing page](https://doc.qt.io/qt-6/qtpdf-licensing.html). See `THIRD_PARTY_NOTICES.md` and bundled notices; employer redistribution approval must address Qt/PDFium obligations. Qt is shipped as replaceable shared libraries in an onedir bundle. Windows uses an `msvcrt` workspace-lock adapter and a separate writable data location. Windows packaging runs through GitHub Actions; see `WINDOWS.md` for validation limits and installer instructions.

Tests cover schema mappings, identifiers, exact duplicate assignments, duplicate names, multiple contracts, name-only dropdown/search, manual copay validation, unknown versus zero, preview invalidation, source changes after preview, first-page stamps, portrait/landscape/rotation, multipage preservation, append order, safe collisions, routing, master contract/period isolation and alphabetical ordering, idempotency, exact undo, simulated storage failures and interrupted recovery, permissions, and path escapes.

See `Build/VERIFICATION.md` for executed test and packaging results and remaining human acceptance work. No production workbook schema or client records have been validated in this development session.
