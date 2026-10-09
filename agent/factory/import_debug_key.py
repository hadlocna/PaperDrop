#!/usr/bin/python3
"""Opt-in maintenance access using an owner's public key on bootfs, never a default key."""
import os
from pathlib import Path
import pwd
import subprocess

source = Path('/boot/firmware/paperdrop-authorized-keys')
if source.exists():
    data = source.read_text()
    lines = [line.strip() for line in data.splitlines() if line.strip() and not line.startswith('#')]
    if not lines or len(data) > 16384 or any(not line.startswith(('ssh-ed25519 ', 'ssh-rsa ', 'ecdsa-sha2-')) for line in lines):
        raise ValueError('Expected SSH public keys, not a private key or password')
    user = pwd.getpwnam('paperdrop')
    folder = Path(user.pw_dir) / '.ssh'
    folder.mkdir(mode=0o700, exist_ok=True)
    key = folder / 'authorized_keys'
    key.write_text('\n'.join(lines) + '\n')
    key.chmod(0o600)
    os.chown(folder, user.pw_uid, user.pw_gid)
    os.chown(key, user.pw_uid, user.pw_gid)
    config = Path('/etc/ssh/sshd_config.d/90-paperdrop-debug.conf')
    config.write_text('PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n')
    sudoers = Path('/etc/sudoers.d/90-paperdrop-debug')
    sudoers.write_text('paperdrop ALL=(ALL) NOPASSWD: ALL\n')
    sudoers.chmod(0o440)
    subprocess.run(['ssh-keygen', '-A'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'ssh.service'], check=True)
    source.unlink()
