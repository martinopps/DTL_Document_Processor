"""Run on Windows with the project development dependencies and Inno Setup 6 installed."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Build' / 'Windows'


def run(*args, timeout=300, env=None):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True, timeout=timeout, env=env)


def smoke(executable, workspace):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    run(executable, '--root', workspace, '--smoke-test', timeout=60, env=env)
    if not (workspace / 'Config' / 'audit.sqlite').is_file():
        raise RuntimeError('Packaged application did not initialize its fictional smoke workspace')


def notices(bundle):
    target = bundle / 'LICENSES'
    target.mkdir()
    for source in (ROOT / 'Packaging/LICENSES').glob('*'):
        if source.is_file():
            shutil.copy2(source, target / source.name)
    for dist in metadata.distributions():
        name = dist.metadata['Name']
        dest = target / name
        dest.mkdir(exist_ok=True)
        (dest / 'METADATA.txt').write_text(str(dist.metadata), encoding='utf-8')
        for item in dist.files or []:
            relative = Path(str(item))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            if any('license' in part.lower() or 'copying' in part.lower() for part in relative.parts):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    output = dest / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
    shutil.copy2(ROOT / 'Source/dtl/assets/FONT-LICENSE.txt', target / 'FONT-LICENSE.txt')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iscc', type=Path, default=Path(os.environ.get('ISCC_EXE', r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')))
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Run this build on Windows, or use the repository Windows installer workflow.')
    if not args.iscc.is_file():
        parser.error('Inno Setup compiler missing. Install Inno Setup 6 or pass --iscc PATH.')
    OUT.mkdir(parents=True, exist_ok=True)
    run(sys.executable, '-m', 'pip', 'check')
    run(sys.executable, '-m', 'pytest', 'Tests', '--basetemp=Build/windows-tests',
        '--junitxml=Build/Windows/test-results.xml', '-q')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', OUT / 'dist', '--workpath', OUT / 'work', ROOT / 'Packaging/windows.spec', timeout=900)
    bundle = OUT / 'dist' / 'DTL-Document-Processor'
    for name in ('README.md', 'WINDOWS.md', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, bundle / name)
    notices(bundle)
    frozen = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (bundle / 'BUILD-DEPENDENCIES.txt').write_text(frozen, encoding='utf-8')
    smoke(bundle / 'DTL-Document-Processor.exe', OUT / 'synthetic-bundle-workspace')
    sys.path.insert(0, str(ROOT / 'Source'))
    from dtl import __version__
    run(args.iscc, f'/DAppVersion={__version__}', ROOT / 'Packaging/windows.iss', timeout=300)
    installer = OUT / 'Installer' / f'DTL-Document-Processor-Setup-{__version__}-x64.exe'
    # Exercise install, upgrade, installed startup and uninstall with synthetic data.
    installed = OUT / 'install-smoke'
    workspace = OUT / 'synthetic-installed-workspace'
    for _ in range(2):
        run(installer, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', f'/DIR={installed}')
        smoke(installed / 'DTL-Document-Processor.exe', workspace)
    sentinel = workspace / 'Intake' / 'fictional-retention-check.txt'
    sentinel.write_text('Synthetic data must survive program uninstall.', encoding='utf-8')
    run(installed / 'unins000.exe', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    if not sentinel.is_file() or not (workspace / 'Config/audit.sqlite').is_file():
        raise RuntimeError('Uninstall removed the separate workspace')
    # A Windows uninstaller can finish its self-removal asynchronously.
    checksum = hashlib.sha256(installer.read_bytes()).hexdigest()
    installer.with_suffix('.exe.sha256').write_text(f'{checksum}  {installer.name}\n', encoding='ascii')
    inputs = {}
    for folder in ('Source', 'Tests', 'Packaging', '.github/workflows'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                inputs[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('requirements.txt', 'requirements-dev.txt'):
        inputs[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    (OUT / 'Installer' / 'build-manifest.json').write_text(json.dumps({
        'version': __version__, 'python': sys.version, 'source_sha256': inputs,
        'installer_sha256': checksum, 'git_commit': os.environ.get('GITHUB_SHA'),
        'checks': ['source tests', 'bundle startup', 'install', 'upgrade', 'installed startup', 'uninstall data preservation'],
        'limitations': ['unsigned', 'interactive Windows acceptance still required', 'license review still required'],
    }, indent=2), encoding='utf-8')
    print(f'Installer ready: {installer}')


if __name__ == '__main__':
    main()
