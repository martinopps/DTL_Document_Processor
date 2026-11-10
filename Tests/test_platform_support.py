"""Platform acceptance checks with fictional workspaces only."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from dtl.models import UserError, safe_component
from dtl.platform_support import default_workspace
from dtl.storage import Store, atomic_write


@pytest.mark.parametrize('value', ['CON', 'nul', 'AUX.txt', 'COM1', 'LPT9', 'COM¹'])
def test_windows_device_names_are_safe(value):
    assert safe_component(value).startswith('_')


def test_windows_workspace_is_separate_from_program(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local App Data'))
    assert default_workspace() == tmp_path / 'Local App Data' / 'DTL Document Processor' / 'Workspace'


def test_atomic_replacement_in_unicode_path(tmp_path):
    path = tmp_path / 'Fictional José' / 'state.json'
    atomic_write(path, b'first')
    atomic_write(path, b'second')
    assert path.read_bytes() == b'second'
    assert not list(path.parent.glob('.dtl-*'))


def test_workspace_lock_between_processes_and_after_termination(tmp_path):
    root = tmp_path / 'Fictional workspace'
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'Source'))
    code = (
        'import sys; from dtl.storage import Store; '
        's=Store(sys.argv[1]); print("ready", flush=True); sys.stdin.read(); s.close()'
    )
    child = subprocess.Popen([sys.executable, '-u', '-c', code, str(root)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env)
    try:
        # Communicate readiness through a file-independent pipe, with a timeout.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            ready = pool.submit(child.stdout.readline)
            try:
                assert ready.result(timeout=20).strip() == 'ready'
            except BaseException:
                child.kill()
                raise
        with pytest.raises(UserError, match='already running'):
            Store(root)
        child.kill()
        child.wait(timeout=10)
        reopened = Store(root)
        reopened.close()
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)
