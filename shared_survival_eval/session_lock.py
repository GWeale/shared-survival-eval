"""POSIX advisory locks: kernel releases ownership when a writer exits or dies."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import fcntl
import os


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('session is locked by an active writer; retry the same envelope') from None
        yield
    finally:
        os.close(fd)
    # Never unlink: waiters must always contend on the same inode.


def serialized(function):
    @wraps(function)
    def call(path, *args, **kwargs):
        with locked(Path(path).with_suffix(Path(path).suffix + '.lock')):
            return function(path, *args, **kwargs)
    return call
