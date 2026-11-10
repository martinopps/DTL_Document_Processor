"""Platform boundaries for local workspaces; never stores records in program files."""
import errno
import os
from pathlib import Path
import sys


def default_workspace():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        return base / 'DTL Document Processor' / 'Workspace'
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parents[3]
    return Path(__file__).resolve().parents[2]


def lock_workspace(handle):
    """Lock the first byte on Windows, or the whole file on Unix, without waiting."""
    if os.name == 'nt':
        import msvcrt
        handle.seek(0)
        # Windows permits locking a region beyond EOF. Do not write a byte here:
        # another process may already hold the mandatory byte-range lock.
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def lock_is_busy(exc):
    return exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK)


def sync_directory(path):
    # Python has no portable Windows directory-fsync equivalent. Windows still
    # gets file fsync + same-directory replacement and the recovery journal.
    if os.name == 'nt':
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
