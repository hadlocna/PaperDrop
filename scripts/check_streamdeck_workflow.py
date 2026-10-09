"""Run an isolated live drawing probe with prerecorded audio and simulated printing.

Run as root using the installed release's virtualenv. The regular runtime is
stopped to avoid two sockets competing for the same device, then restored.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import wave


def wait_for(predicate, timeout, description):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError(description)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--report', type=Path, default=Path('/tmp/paperdrop-sil-report.json'))
    parser.add_argument('--connection-only', action='store_true', help='Test authenticated reconnect without image generation.')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Root access is required for the protected device identity and runtime service.')
    audio = args.audio.resolve()
    with wave.open(str(audio)) as source:
        duration = source.getnframes() / source.getframerate()
    release = Path('/opt/paperdrop/current').resolve()
    sys.path[:0] = [str(release / 'streamdeck'), str(release / 'src')]
    os.environ['PAPERDROP_FIRMWARE_VERSION'] = json.loads((release / 'release.json').read_text())['version']
    from controller import Controller
    from media import Media
    from pi_cloud import Cloud
    from store import Mailbox

    report = {'generation': 'not_run', 'print': 'simulated_only', 'steps': []}
    was_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'paperdrop-runtime.service']).returncode == 0
    controller = cloud = None
    scratch = tempfile.TemporaryDirectory(prefix='paperdrop-sil-')
    try:
        subprocess.run(['systemctl', 'stop', 'paperdrop-runtime.service'], check=True)
        root = Path(scratch.name)
        cloud = Cloud(root)
        wait_for(cloud.connected.is_set, 30, 'Backend authentication failed')
        report['steps'].append('backend_authenticated')
        if args.connection_only:
            previous_socket = cloud.ws
            previous_socket.close()
            wait_for(lambda: cloud.ws is not None and cloud.ws is not previous_socket and cloud.connected.is_set(),
                     35, 'Cloud connection did not recover after a forced disconnect')
            report['steps'].append('backend_reauthenticated_after_disconnect')
            return 0

        class ProbeMedia(Media):
            local_printer = True

            def start_guidance(self, text):
                return None

            def cue(self, text):
                pass

            def cue_sequence(self, texts, star=False):
                pass

            def start_recording(self, path):
                shutil.copyfile(audio, path)
                self.record_ready.set()

            def finish_recording(self, path):
                return duration

            def draw(self, recorded, target, progress):
                return cloud.draw(recorded, target, progress)

            def print_image(self, path, ident):
                from PIL import Image
                with Image.open(path) as image:
                    image.verify()
                report['steps'].append('simulated_print_submission')
                return {'status': 'simulated'}

            def discard_image(self, path):
                mapping = Path(path).with_suffix('.cloud.json')
                if mapping.exists():
                    ident = json.loads(mapping.read_text())['message_id']
                    cloud.status(ident, 'failed', 'Software probe: physical printing intentionally skipped')

        family = json.loads((release / 'streamdeck/family.json').read_text())
        station = Path('/etc/paperdrop/station')
        if station.exists():
            family['station'] = station.read_text().strip()
        controller = Controller(family, Mailbox(root / 'mailbox'), ProbeMedia(root))
        controller.press(5, True)
        controller.press(5, False)
        wait_for(lambda: controller.mode in ('recording', 'error'), 5, 'Simulated button did not start recording')
        if controller.mode == 'error':
            raise RuntimeError(controller.note)
        report['steps'].append('button_recording_started')
        # Exercise the production 15-second timer rather than calling generate directly.
        wait_for(lambda: controller.mode in ('print_review', 'error'), 190, 'Drawing did not reach review')
        if controller.mode == 'error':
            raise RuntimeError(controller.note)
        report['generation'] = 'passed'
        report['steps'].append('server_drawing_review_ready')
        report['prompt'] = controller.draft.get('prompt')
        time.sleep(0.9)
        controller.press(1, True)
        controller.press(1, False)
        if controller.mode != 'preview':
            raise RuntimeError('Preview button failed')
        time.sleep(0.3)
        controller.press(0, True)
        controller.press(0, False)
        if controller.mode != 'print_review':
            raise RuntimeError('Preview return failed')
        time.sleep(0.9)
        controller.press(5, True)
        controller.press(5, False)
        wait_for(lambda: controller.mode in ('print_done', 'error'), 5, 'Simulated print transition failed')
        if controller.mode != 'print_done':
            raise RuntimeError(controller.note)
        report['steps'].append('print_done_screen')
    except Exception as error:
        report['error'] = str(error)
    finally:
        if controller:
            try:
                controller.discard()
                controller.close()
                controller.mailbox.db.close()
            except Exception as error:
                report['cleanup_error'] = type(error).__name__
        if cloud:
            cloud.close()
        if was_active:
            restored = subprocess.run(['systemctl', 'start', 'paperdrop-runtime.service']).returncode == 0
            report['runtime_restart_requested'] = restored
        scratch.cleanup()
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        args.report.chmod(0o644)
        print(json.dumps(report))
    return 1 if 'error' in report else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
