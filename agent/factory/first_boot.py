#!/usr/bin/python3
"""Restore an owner-issued enrollment, or create a new identity without cloning one."""
import json
import os
from pathlib import Path
import secrets
import urllib.request

root = Path('/etc/paperdrop')
root.mkdir(parents=True, exist_ok=True)
os.chmod(root, 0o700)
identity = root/'device.json'
boot = Path('/boot/firmware/paperdrop-enrollment.json')
pending = root/'enrollment.json'
if boot.exists():
    # Move the bearer token off the computer-readable boot partition promptly.
    pending.write_bytes(boot.read_bytes());os.chmod(pending,0o600);boot.unlink()
if pending.exists():
    value = json.loads(pending.read_text())
    request = urllib.request.Request('https://api.paperdrop.me/api/device-enrollment',
        data=json.dumps({'token':value['token']}).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=20) as response:
        result=json.loads(response.read(16384))
    if not result.get('device_code') or not result.get('device_secret'):
        raise RuntimeError('Enrollment was not accepted')
    temp=root/'device.tmp';temp.write_text(json.dumps({k:result[k] for k in ('device_code','device_secret')}));os.chmod(temp,0o600);temp.replace(identity)
    if result.get('station') in ('portugal','ohio','dusseldorf'):
        (root/'station').write_text(result['station'])
    pending.unlink()
elif not identity.exists():
    identity.write_text(json.dumps({'device_code':'PD-'+secrets.token_hex(4).upper(),'device_secret':secrets.token_urlsafe(32)}))
    os.chmod(identity,0o600)
value=json.loads(identity.read_text())
(root/'device-id').write_text(value['device_code'])
