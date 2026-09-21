"""Cross-process lock keeps updates out of active child sessions and printing."""
import fcntl
import os
from pathlib import Path
from contextlib import contextmanager

PATH = Path('/run/paperdrop/activity.lock')

def acquire(exclusive=False):
    if not os.environ.get('PAPERDROP_FIRMWARE_VERSION') and not exclusive:
        return None
    PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = PATH.open('a')
    try:
        fcntl.flock(handle, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        return handle
    except BlockingIOError:
        handle.close()
        raise RuntimeError('PaperDrop is updating. Please try again shortly.')

@contextmanager
def activity():
    handle = acquire()
    try:
        yield
    finally:
        if handle: handle.close()

def protects(function):
    async def wrapped(*args, **kwargs):
        with activity():
            return await function(*args, **kwargs)
    return wrapped
