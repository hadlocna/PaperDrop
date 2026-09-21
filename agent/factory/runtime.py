#!/usr/bin/python3
"""Select the installed interface while retaining a single managed runtime."""
import json
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
os.environ['PAPERDROP_FIRMWARE_VERSION'] = json.loads((root / 'release.json').read_text())['version']
os.environ['PYTHONPATH'] = str(root / 'src')
mode_file = Path('/etc/paperdrop/mode')
mode = mode_file.read_text().strip() if mode_file.exists() else 'auto'
has_buttons = any(p.read_text().strip() == '0fd9' for p in Path('/sys/bus/usb/devices').glob('*/idVendor'))
if mode == 'streamdeck' or (mode == 'auto' and has_buttons):
    command = [sys.executable, str(root / 'streamdeck/app.py'), '--pi', '--state-dir', '/var/lib/paperdrop/streamdeck']
else:
    command = [sys.executable, str(root / 'src/ws_agent.py')]
os.execv(sys.executable, command)
