# Build and install on Windows

The repository includes a Windows build workflow and compatibility adapters. A successful Windows workflow run is required before treating an installer as available. Linux tests alone do not establish Windows behavior.

## Get the installer from GitHub

1. Open this repository's **Actions** tab and select **Windows installer**.
2. Open the run for the latest commit. Wait for it to finish successfully. You can also select **Run workflow** on the default branch.
3. Download the **DTL-Document-Processor-Windows-x64** artifact and extract its ZIP.
4. Run `DTL-Document-Processor-Setup-1.0.0-x64.exe` on a Windows 11 x64 workstation.

The artifact contains the setup executable, a SHA-256 checksum and a build manifest. An artifact appears only after the tests, bundle startup, install, upgrade, installed startup and uninstall preservation checks pass. The initial installer is unsigned. A failed workflow is not a release; inspect the failed step and the Windows-test-results artifact.

The build runs on GitHub's Windows Server 2025 x64 runner. It does not substitute for interactive acceptance on the intended Windows 11 desktop. The installer is restricted to Windows build 22000 or newer. ARM64 and Windows 10 have not been validated.

## Installation and records

Installation is per user and does not normally request administrator elevation. Program files go under `%LOCALAPPDATA%\Programs\DTL Document Processor`. No Python installation is required to run the finished application.

Records, SQLite, settings and recovery files go under `%LOCALAPPDATA%\DTL Document Processor\Workspace`, separately from the installed program. First use requires selecting and approving a workbook. A different approved local workspace can be supplied using `--root "C:\approved\workspace"`. Keep all workspace directories together. Uninstall and program upgrades preserve the separate workspace.

Existing Linux workspaces are not automatically transferred. With the application stopped, copy the complete workspace to the approved Windows location, retain an original backup, select the Windows workbook path and validate with synthetic records before production. Do not put records in the repository or installer.

Windows relies on inherited NTFS ACLs for its user profile/workspace; POSIX mode bits are not a Windows access-control guarantee. Use an employer-approved local encrypted location and verify ACLs, backup and retention policy. Windows writes flush the temporary file before same-directory replacement and keep the recovery journal; the Unix directory-fsync step is unavailable through this implementation on Windows. Real power-loss and full-disk testing remain environmental acceptance work.

## Build locally on Windows

Install Python 3.12 x64 and Inno Setup 6. Open PowerShell in the checkout:

```powershell
py -3.12 -m venv .venv-windows
.\.venv-windows\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-windows\Scripts\python.exe Packaging\build_windows.py
```

If the compiler is installed elsewhere:

```powershell
.\.venv-windows\Scripts\python.exe Packaging\build_windows.py --iscc "C:\path\to\ISCC.exe"
```

The installer is written under `Build\Windows\Installer`. The exact resolved Python packages are recorded in the application bundle's `BUILD-DEPENDENCIES.txt`; the manifest records source hashes and the CI commit. The top-level dependencies are pinned, while transitive dependencies are resolved at build time and must be reviewed when they change.

## Before production

Use fictional workbooks and PDFs to check workbook mapping, preview, save/append, exact undo, restart recovery, contract masters, stale markers, keyboard use, display scaling and printed readability on the actual Windows desktop. Verify that an update preserves a populated workspace and uninstall preserves its records. Complete the existing employer handling and Qt/PDFium redistribution review. The scripts collect available package notices and include the supplied GPL/LGPL texts, but collecting notices alone does not establish that all redistribution obligations have been fulfilled.

GitHub source and Actions uploads must contain application code and synthetic fixtures only. Never commit workbooks, scans, settings, audit databases, recovery files, previews or production logs. No production records are needed to build the application.
