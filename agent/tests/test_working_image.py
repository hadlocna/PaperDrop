import io
import importlib.util
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'posix', 'Image building requires Linux')
class WorkingImageTests(unittest.TestCase):
    def test_sanitization_preserves_runtime_but_resets_access_and_boot_ids(self):
        spec = importlib.util.spec_from_file_location('working_image', REPO / 'scripts/build_working_pi_image.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                'etc/passwd': 'root:x:0:0:root:/root:/bin/bash\npaperdrop:x:1000:1000::/home/paperdrop:/bin/bash\n',
                'etc/group': 'root:x:0:\nshadow:x:42:\n',
                'boot/firmware/cmdline.txt': 'root=PARTUUID=old-02 rootwait ds=nocloud;i=private\n',
                'opt/paperdrop/releases/test/release.json': '{"format":2,"version":"test"}',
                'etc/lightdm/lightdm.conf': '[Seat:*]\nautologin-user=paperdrop\n',
                'etc/ssl/private/test.key': 'private fixture',
            }
            for name, content in files.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content)
            for name in ('usr/local/lib/paperdrop', 'etc/systemd/system/timers.target.wants',
                         'etc/systemd/system/multi-user.target.wants'):
                (root / name).mkdir(parents=True, exist_ok=True)
            (root / 'opt/paperdrop/current').symlink_to('/opt/paperdrop/releases/test')
            (root / 'etc/systemd/system/timers.target.wants/paperdrop-update.timer').symlink_to('/unit')
            (root / 'etc/systemd/system/multi-user.target.wants/ssh.service').symlink_to('/unit')
            with patch.object(module.os, 'chown'), patch.object(module.os, 'mknod', side_effect=lambda path, *args: Path(path).touch()):
                metadata = module.sanitize(root, 'test-commit')
            self.assertEqual(metadata['release']['version'], 'test')
            self.assertFalse((root / 'etc/ssl/private/test.key').exists())
            self.assertTrue((root / 'etc/cloud/cloud-init.disabled').exists())
            self.assertTrue(all(line.split(':')[1] == '*' for line in (root / 'etc/shadow').read_text().splitlines()))
            self.assertNotIn('ds=', (root / 'boot/firmware/cmdline.txt').read_text())
            self.assertIn('root=PARTUUID=70647031-02', (root / 'boot/firmware/cmdline.txt').read_text())
            wants = root / 'etc/systemd/system/multi-user.target.wants'
            self.assertTrue((wants / 'paperdrop-debug-key.service').is_symlink())
            self.assertFalse((wants / 'ssh.service').is_symlink())
            self.assertFalse((root / 'etc/systemd/system/timers.target.wants/paperdrop-update.timer').is_symlink())

    def test_export_excludes_credentials_but_keeps_ssh_software(self):
        source = (REPO / 'agent/factory/export-working-system.sh').read_text()
        excludes = [arg for arg in shlex.split(source) if arg.startswith('--exclude=')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = ['etc/ssh/sshd_config', 'etc/ssh/ssh_host_ed25519_key',
                     'etc/paperdrop/device.json', 'etc/shadow', 'home/paperdrop/.ssh/authorized_keys',
                     'etc/netplan/private.yaml', 'var/lib/bluetooth/bond',
                     'boot/firmware/ssh', 'boot/firmware/paperdrop-enrollment.json',
                     'boot/firmware/kernel_2712.img', 'usr/bin/ssh']
            for name in files:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('fixture')
            result = subprocess.run(['tar', '-cf', '-', *excludes, '-C', directory, '.', 'boot/firmware'],
                                    capture_output=True, check=True)
            with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
                names = {name.removeprefix('./') for name in archive.getnames()}
            for name in ('etc/ssh/sshd_config', 'usr/bin/ssh', 'boot/firmware/kernel_2712.img'):
                self.assertIn(name, names)
            for name in set(files) - {'etc/ssh/sshd_config', 'usr/bin/ssh', 'boot/firmware/kernel_2712.img'}:
                self.assertNotIn(name, names)

    def run_key_import(self, key):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'boot/firmware/paperdrop-authorized-keys'
            source.parent.mkdir(parents=True)
            source.write_text(key)
            for name in ('etc/ssh/sshd_config.d', 'etc/sudoers.d', 'home/paperdrop'):
                (root / name).mkdir(parents=True)
            real_path = type(root)
            def mapped(value):
                return real_path(root / str(value).lstrip('/'))
            user = Mock(pw_dir='/home/paperdrop', pw_uid=1000, pw_gid=1000)
            with patch('pathlib.Path', side_effect=mapped), patch('pwd.getpwnam', return_value=user), \
                 patch('os.chown'), patch('subprocess.run') as run:
                runpy.run_path(str(REPO / 'agent/factory/import_debug_key.py'))
            self.assertFalse(source.exists())
            self.assertEqual((root / 'home/paperdrop/.ssh/authorized_keys').stat().st_mode & 0o777, 0o600)
            self.assertIn('PasswordAuthentication no', (root / 'etc/ssh/sshd_config.d/90-paperdrop-debug.conf').read_text())
            run.assert_any_call(['systemctl', 'enable', '--now', 'ssh.service'], check=True)

    def test_owner_key_enables_explicit_key_only_maintenance(self):
        self.run_key_import('ssh-ed25519 AAAATEST test-fixture\n')

    def test_private_key_is_rejected_before_enabling_access(self):
        with self.assertRaises(ValueError):
            self.run_key_import('-----BEGIN OPENSSH PRIVATE KEY-----\n')


if __name__ == '__main__':
    unittest.main()
