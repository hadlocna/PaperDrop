#!/usr/bin/env python3
"""Build a sanitized flashable image from export-working-system.sh over SSH.

Linux root and filesystem tools are required; ARM emulation validates imports on x86.
The SSH command JSON is a list of arguments (no password). No physical disk is written.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sanitize(root, revision):
    for file in (root / 'etc/ssl/private').glob('*'):
        if file.is_file():
            file.unlink()
    for name in ('var/lib/systemd/credential.secret', 'var/lib/systemd/random-seed'):
        (root / name).unlink(missing_ok=True)
    current = root / 'opt/paperdrop/current'
    if current.is_symlink():
        target = os.readlink(current)
        if target.startswith('/opt/paperdrop/releases/'):
            current.unlink()
            current.symlink_to(target.removeprefix('/opt/paperdrop/'))
    factory = Path(__file__).resolve().parents[1] / 'agent/factory'
    shutil.copyfile(factory / 'import_debug_key.py', root / 'usr/local/lib/paperdrop/import_debug_key.py')
    shutil.copyfile(factory / 'paperdrop-debug-key.service', root / 'etc/systemd/system/paperdrop-debug-key.service')
    # Password hashes are excluded at export. Retain system users, not their credentials.
    users = [line.split(':') for line in (root / 'etc/passwd').read_text().splitlines()]
    (root / 'etc/shadow').write_text(''.join(f'{u[0]}:*:20000:0:99999:7:::\n' for u in users))
    (root / 'etc/shadow').chmod(0o640)
    groups = [line.split(':')[0] for line in (root / 'etc/group').read_text().splitlines()]
    (root / 'etc/gshadow').write_text(''.join(f'{name}:*::\n' for name in groups))
    (root / 'etc/gshadow').chmod(0o640)
    shadow_group = next((int(line.split(':')[2]) for line in
                         (root / 'etc/group').read_text().splitlines() if line.startswith('shadow:')), 0)
    os.chown(root / 'etc/shadow', 0, shadow_group)
    os.chown(root / 'etc/gshadow', 0, shadow_group)
    for user in users:
        home = root / user[5].lstrip('/')
        if user[5].startswith('/home/'):
            home.mkdir(parents=True, exist_ok=True)
            os.chown(home, int(user[2]), int(user[3]))
            home.chmod(0o700)
    (root / 'etc/machine-id').touch()
    # Imager's original cloud-init seed is deliberately absent; our helpers own provisioning.
    (root / 'etc/cloud').mkdir(exist_ok=True)
    (root / 'etc/cloud/cloud-init.disabled').touch()
    for directory in ('etc/paperdrop', 'var/lib/paperdrop/streamdeck', 'var/log/paperdrop',
                      'var/lib/bluetooth', 'var/cache/apt/archives/partial',
                      'var/lib/NetworkManager', 'var/log/journal'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / 'etc/paperdrop').chmod(0o700)
    boot = root / 'boot/firmware'
    command = (boot / 'cmdline.txt').read_text()
    command = re.sub(r'\broot=\S+', 'root=PARTUUID=70647031-02', command)
    command = re.sub(r'\s+ds=\S+', '', command)
    (boot / 'cmdline.txt').write_text(command.strip() + '\n')
    (root / 'etc/fstab').write_text(
        'proc /proc proc defaults 0 0\n'
        'PARTUUID=70647031-01 /boot/firmware vfat defaults 0 2\n'
        'PARTUUID=70647031-02 / ext4 defaults,noatime 0 1\n')
    (boot / 'PAPERDROP-START-HERE.txt').write_text(
        'PaperDrop sanitized working-system image\n'
        'Copy a fresh paperdrop-enrollment.json here before first boot to restore your device.\n'
        'Connect Ethernet to a router, or use PaperDrop-Setup Wi-Fi and http://10.42.0.1:8080.\n'
        'Pair the speaker again in the web app. No Wi-Fi or Bluetooth pairing is included.\n'
        'SSH is disabled: no account password or authorized keys are distributed.\n'
        'For key-only SSH, copy your public key to paperdrop-authorized-keys on this boot drive.\n'
        'That explicitly enables the paperdrop maintenance account with passwordless sudo.\n'
        'Automatic firmware updates are disabled pending a controlled release.\n')
    system = root / 'etc/systemd/system'
    wants = system / 'multi-user.target.wants'
    wants.mkdir(exist_ok=True)
    for name in ('paperdrop-setup.service', 'paperdrop-enroll.service',
                 'paperdrop-runtime.service', 'paperdrop-debug-key.service'):
        link = wants / name
        link.unlink(missing_ok=True)
        link.symlink_to('/etc/systemd/system/' + name)
    for link in system.rglob('*'):
        if link.is_symlink() and link.name in ('paperdrop-update.timer', 'ssh.service', 'sshd.service', 'ssh.socket'):
            link.unlink()
    for link in (root / 'etc').glob('rc*.d/S*ssh'):
        link.unlink()
    for directory in ('dev', 'proc', 'sys', 'run', 'tmp', 'mnt', 'media'):
        (root / directory).mkdir(exist_ok=True)
    (root / 'tmp').chmod(0o1777)
    # Image-only device node for dependency checks; udev populates /dev at real boot.
    null = root / 'dev/null'
    if not null.exists():
        os.mknod(null, stat.S_IFCHR | 0o666, os.makedev(1, 3))
        null.chmod(0o666)
    # The source desktop auto-login must not grant an unauthenticated admin shell.
    for config in (root / 'etc/lightdm').glob('**/*.conf'):
        text = config.read_text()
        config.write_text(re.sub(r'(?m)^\s*autologin-user\s*=.*$', '# autologin-user disabled for distribution', text))
    for link in (root / 'etc/systemd/system').glob('**/*autologin*'):
        if link.is_symlink() or link.is_file():
            link.unlink()
    metadata = {'source_git_commit': revision, 'source': 'sanitized working Pi filesystem',
                'credentials_included': False, 'automatic_updates_enabled': False,
                'hardware_boot_test': 'required after flashing',
                'release': json.loads((root / 'opt/paperdrop/current/release.json').read_text())}
    (root / 'etc/paperdrop/image-build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def verify(root, emulated=False):
    forbidden = ['etc/paperdrop/device.json', 'etc/paperdrop/enrollment.json',
                 'etc/paperdrop/speaker.json', 'boot/firmware/paperdrop-enrollment.json']
    for name in forbidden:
        if (root / name).exists():
            raise RuntimeError('Private state present: ' + name)
    for directory in ('home', 'root', 'etc/NetworkManager/system-connections', 'etc/netplan',
                      'var/lib/bluetooth', 'var/lib/paperdrop', 'var/log'):
        for file in (root / directory).rglob('*'):
            if file.is_file():
                raise RuntimeError('Unexpected user/state file: ' + str(file.relative_to(root)))
    if list((root / 'etc/ssh').glob('ssh_host_*')):
        raise RuntimeError('SSH host keys present')
    if list((root / 'etc/ssl/private').glob('*')):
        raise RuntimeError('TLS private key present')
    if any(line.split(':')[1] != '*' for line in (root / 'etc/shadow').read_text().splitlines()):
        raise RuntimeError('Account password retained')
    prefix = ['chroot', str(root)] + (['/usr/bin/qemu-aarch64-static'] if emulated else [])
    run(*prefix, '/opt/paperdrop/current/venv/bin/python', '-c',
        'import websockets, PIL, StreamDeck, cairosvg, escpos, vosk, audioop; print("Runtime imports passed")')
    run(*prefix, '/usr/bin/python3', '-c', 'import dbus; print("System D-Bus import passed")')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-command-file', type=Path)
    parser.add_argument('--finalize-existing', action='store_true',
                        help='Finalize a previously captured image, only after independently verifying capture completeness')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Linux root is required for image mounts')
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if Path(str(output) + '.xz').exists() or (output.exists() and not args.finalize_existing):
        parser.error('Refusing to overwrite an existing image')
    if args.finalize_existing:
        if not output.is_file() or output.stat().st_size != 8 * 1024**3:
            parser.error('Expected the previously captured regular 8 GiB image file')
    else:
        if not args.ssh_command_file:
            parser.error('--ssh-command-file is required for a new capture')
        ssh = json.loads(args.ssh_command_file.read_text())
        if not isinstance(ssh, list) or not ssh or not all(isinstance(s, str) for s in ssh):
            parser.error('SSH command must be a JSON argument list')
    # 8 GiB is comfortably below the tested 16 GB card capacity.
    layout = 'label: dos\nlabel-id: 0x70647031\nunit: sectors\n\nstart=2048,size=1048576,type=c\nstart=1050624,type=83\n'
    if not args.finalize_existing:
        run('truncate', '-s', '8G', str(output))
        run('sfdisk', str(output), input=layout, text=True)
    loop = subprocess.check_output(['losetup', '--find', '--show', '--partscan', str(output)], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='paperdrop-image-') as directory:
        root = Path(directory)
        boot_mounted = mounted = False
        emulator = None
        verified = False
        try:
            if not args.finalize_existing:
                run('mkfs.vfat', '-F', '32', '-n', 'bootfs', loop + 'p1')
                run('mkfs.ext4', '-F', '-L', 'rootfs', loop + 'p2')
            run('mount', loop + 'p2', str(root))
            mounted = True
            (root / 'boot/firmware').mkdir(parents=True, exist_ok=True)
            run('mount', loop + 'p1', str(root / 'boot/firmware'))
            boot_mounted = True
            if not args.finalize_existing:
                with subprocess.Popen(ssh + ['cat /run/paperdrop-image/export.fifo'], stdout=subprocess.PIPE) as source:
                    run('tar', '--extract', '--file=-', '--numeric-owner', '--no-acls', '--no-xattrs',
                        '-C', str(root), stdin=source.stdout)
                    source.stdout.close()
                    if source.wait() != 0:
                        raise RuntimeError('SSH export failed')
                result = subprocess.check_output(ssh + ['cat /run/paperdrop-image/result'], text=True).strip()
                if result != '0':
                    raise RuntimeError('Source export/runtime restoration did not succeed: ' + result)
            metadata = sanitize(root, args.revision)
            if os.uname().machine != 'aarch64':
                emulator = root / 'usr/bin/qemu-aarch64-static'
                shutil.copyfile('/usr/bin/qemu-aarch64-static', emulator)
                emulator.chmod(0o755)
            verify(root, emulated=bool(emulator))
            verified = True
            if emulator:
                emulator.unlink()
            run('sync')
        finally:
            if boot_mounted:
                run('umount', str(root / 'boot/firmware'))
            if mounted:
                run('umount', str(root))
            try:
                if verified:
                    # Scrub freed blocks as well as directory entries before distributing an image.
                    run('e2fsck', '-fn', loop + 'p2', stdout=subprocess.DEVNULL)
                    run('zerofree', loop + 'p2')
            finally:
                run('losetup', '-d', loop)
    run('xz', '-T2', '-3', '--keep', str(output))
    compressed = Path(str(output) + '.xz')
    with compressed.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    Path(str(compressed) + '.sha256').write_text(f'{digest}  {compressed.name}\n')
    Path(str(compressed) + '.json').write_text(json.dumps(metadata | {'sha256': digest}, indent=2) + '\n')
    print(compressed)


if __name__ == '__main__':
    main()
