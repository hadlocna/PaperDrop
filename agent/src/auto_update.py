#!/usr/bin/python3
"""Stable-channel updates, independent of the running child interface."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

BASE = Path('/opt/paperdrop')
STATE = Path('/var/lib/paperdrop/updates')
MANIFEST_URL = 'https://api.paperdrop.me/uploads/stable.json'
SERVICE = 'paperdrop-runtime.service'
HELPERS = Path('/usr/local/lib/paperdrop')
HEALTH = Path('/run/paperdrop/healthy.json')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value))
    os.chmod(temp, 0o600)
    temp.replace(path)


def manifest_check(value, origin=MANIFEST_URL):
    if value.get('format') != 2 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value.get('version', '')):
        raise ValueError('Unsupported release manifest')
    if not re.fullmatch(r'[a-f0-9]{64}', value.get('sha256', '')):
        raise ValueError('Release checksum required')
    url = urlparse(value.get('url', ''))
    if url.scheme != 'https' or url.netloc != urlparse(origin).netloc or not url.path.startswith('/uploads/'):
        raise ValueError('Release must use the trusted HTTPS origin')
    return value


def unpack(archive, target):
    with tarfile.open(archive, 'r:gz') as package:
        members = package.getmembers()
        total = 0
        for member in members:
            if member.name.startswith('/') or '..' in Path(member.name).parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member')
            total += member.size
            if total > 1200 * 1024 * 1024:
                raise ValueError('Release is too large')
        package.extractall(target, members=members)
    for name in ('runtime.py', 'requirements.txt', 'src/ws_agent.py', 'streamdeck/app.py', 'release.json'):
        if not (target / name).is_file():
            raise ValueError('Incomplete release: ' + name)


def switch(target):
    link = BASE / 'current.next'
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    link.replace(BASE / 'current')


def idle():
    state = Path('/var/lib/paperdrop/streamdeck/state.json')
    if state.exists() and time.time() - state.stat().st_mtime < 20:
        return json.loads(state.read_text()).get('mode') in ('home', 'personal', 'houses', 'games', 'people', 'compose', 'sent', 'print_done')
    return not Path('/run/paperdrop/busy').exists()


def install(manifest):
    version = manifest['version']
    current = (BASE / 'current').resolve()
    if (current / 'release.json').exists() and json.loads((current / 'release.json').read_text()).get('version') == version:
        return
    failure = STATE / 'failed.json'
    if failure.exists():
        previous_failure = json.loads(failure.read_text())
        if previous_failure.get('sha256') == manifest['sha256'] and time.time() - previous_failure['time'] < 6 * 3600:
            return
    if not idle():
        atomic_json(STATE / 'status.json', {'status': 'waiting_for_idle', 'version': version})
        return
    releases = BASE / 'releases'
    releases.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(BASE).free < 1500 * 1024 * 1024:
        raise RuntimeError('At least 1.5 GB free space is needed to update')
    target = releases / (version + '-' + manifest['sha256'][:12])
    atomic_json(STATE / 'status.json', {'status': 'downloading', 'version': version})
    with tempfile.TemporaryDirectory(dir=BASE, prefix='.download-') as directory:
        archive = Path(directory) / 'release.tar.gz'
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(manifest['url'], timeout=60) as response, archive.open('wb') as out:
            if urlparse(response.url).netloc != urlparse(MANIFEST_URL).netloc:
                raise ValueError('Unexpected download redirect')
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 600 * 1024 * 1024:
                    raise ValueError('Download is too large')
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != manifest['sha256']:
            raise ValueError('Release checksum mismatch')
        if target.exists():
            if target == current:
                raise ValueError('Refusing to replace active release')
            shutil.rmtree(target)
        target.mkdir()
        unpack(archive, target)
    if json.loads((target / 'release.json').read_text())['version'] != version:
        raise ValueError('Release version mismatch')
    # Each release owns its dependencies, so rollback restores those too.
    subprocess.run(['/usr/bin/python3', '-m', 'venv', str(target / 'venv')], check=True)
    pip = [str(target / 'venv/bin/python'), '-m', 'pip', 'install', '--disable-pip-version-check']
    wheels = BASE / 'wheels'
    if wheels.exists():
        pip += ['--find-links', str(wheels)]
    subprocess.run(pip + ['-r', str(target / 'requirements.txt')], check=True, timeout=900)
    subprocess.run([str(target / 'venv/bin/python'), '-c', 'import websockets, PIL, StreamDeck, cairosvg, escpos, vosk, audioop'], check=True)
    if not idle():
        atomic_json(STATE / 'status.json', {'status': 'waiting_for_idle', 'version': version})
        return
    from update_guard import acquire
    guard = acquire(exclusive=True)
    switched_at = time.time()
    atomic_json(STATE / 'pending.json', {'previous': str(current), 'target': str(target), 'version': version})
    try:
        switch(target)
        subprocess.run(['systemctl', 'restart', SERVICE], check=True)
        guard.close()
        for _ in range(90):
            health = HEALTH
            if health.exists():
                live = json.loads(health.read_text())
                if live.get('version') == version and live.get('time', 0) > switched_at:
                    atomic_json(STATE / 'status.json', {'status': 'installed', 'version': version, 'time': time.time()})
                    (STATE / 'pending.json').unlink(missing_ok=True)
                    # Refresh the independent updater only after the new runtime authenticates.
                    for helper in ('auto_update.py', 'update_guard.py'):
                        destination = HELPERS / helper
                        temporary = destination.with_suffix('.next')
                        shutil.copyfile(target / 'src' / helper, temporary)
                        temporary.replace(destination)
                    # Keep active and previous; clean only our release directories.
                    for old in releases.iterdir():
                        if old.is_dir() and not old.is_symlink() and old not in (target, current):
                            shutil.rmtree(old)
                    return
            time.sleep(2)
        raise RuntimeError('New release did not authenticate with the backend')
    except Exception:
        guard.close()
        switch(current)
        subprocess.run(['systemctl', 'restart', SERVICE], check=False)
        atomic_json(failure, {'sha256': manifest['sha256'], 'time': time.time()})
        (STATE / 'pending.json').unlink(missing_ok=True)
        raise


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        # A power cut while checking a release returns to the previous version.
        pending = STATE / 'pending.json'
        if pending.exists():
            old = Path(json.loads(pending.read_text())['previous'])
            if old.is_dir():
                switch(old)
                subprocess.run(['systemctl', 'restart', SERVICE], check=False)
            pending.unlink()
        try:
            with urllib.request.urlopen(MANIFEST_URL, timeout=25) as response:
                manifest = manifest_check(json.loads(response.read(16384)))
            install(manifest)
        except Exception as error:
            atomic_json(STATE / 'status.json', {'status': 'retry_later', 'error': type(error).__name__, 'time': time.time()})
            print('Update deferred:', type(error).__name__, flush=True)


if __name__ == '__main__':
    main()
