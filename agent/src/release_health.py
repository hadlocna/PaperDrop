"""Authenticated connection proof used by the independent update service."""
import json
import os
from pathlib import Path
import time

def mark_healthy():
    root = Path('/run/paperdrop')
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'healthy.json'
    temp = root / 'healthy.tmp'
    temp.write_text(json.dumps({'version': os.environ.get('PAPERDROP_FIRMWARE_VERSION', 'legacy'), 'time': time.time()}))
    temp.replace(target)
