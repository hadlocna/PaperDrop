"""Exercise Pi drawing against the actual backend handler over a local socket.

Capture, AI, database and USB are fixtures. Controller, Pi WAV validation,
WebSocket protocol, image preparation, review and print receipts are real code.
Build backend/dist before running this test (Node dependencies are required).
"""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import MagicMock, patch
import wave

from PIL import Image
from websockets.sync.client import connect
from controller import Controller
from media import Media
from pi_cloud import Cloud
from pi_media import PiMedia
from store import Mailbox
from test_controller import FAMILY


class FinishedCapture:
    def poll(self): return 0
    def wait(self, timeout=None): return 0


class FixtureMedia(PiMedia):
    def __init__(self, root, cloud):
        Media.__init__(self, root)
        self.cloud = cloud
        self.record_calls = self.finish_calls = 0

    def start_guidance(self, text): return None
    def cue(self, text): pass
    def start_recording(self, path):
        self.record_calls += 1
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\xe8\x03' * 48000)
        self.recording = FinishedCapture()
        self.capture_done = threading.Event()
        self.capture_done.set()
        self.record_error = None
        self.record_ready.set()

    def finish_recording(self, path):
        self.finish_calls += 1
        return super().finish_recording(path)

    def close(self):
        Media.close(self)
        self.cloud.close()


class DrawingFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        picture = BytesIO()
        Image.new('RGB', (32, 32), 'black').save(picture, format='PNG')
        repo = Path(__file__).resolve().parents[2]
        environment = {**os.environ, 'PAPERDROP_TEST_IMAGE': base64.b64encode(picture.getvalue()).decode()}
        environment.pop('PAPERDROP_FIRMWARE_VERSION', None)
        self.server = subprocess.Popen(
            ['node', str(repo / 'backend/tests/fixtures/streamdeckDrawingServer.cjs')],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
        self.addCleanup(self.stop_server)
        self.assertTrue(select.select([self.server.stdout], [], [], 5)[0], 'Backend fixture did not start')
        ready = self.server.stdout.readline()
        self.assertTrue(ready, 'Backend fixture failed to start; build backend/dist first')
        port = json.loads(ready)['port']
        cloud = Cloud.__new__(Cloud)
        cloud.root = self.root
        cloud.lock = threading.RLock()
        cloud.connected = threading.Event(); cloud.connected.set()
        cloud.stop = threading.Event()
        cloud.request = None
        cloud.ack_dir = self.root / 'cloud-status'; cloud.ack_dir.mkdir()
        cloud.ws = connect(f'ws://127.0.0.1:{port}')
        self.addCleanup(cloud.close)
        self.cloud = cloud
        self.stats_ready = threading.Event()
        self.stats = None
        self.transport_errors = []

        def receive():
            try:
                for raw in cloud.ws:
                    event = json.loads(raw)
                    if event['type'] == 'test_stats':
                        self.stats = event
                        self.stats_ready.set()
                    elif event['type'] == 'fixture_error':
                        self.transport_errors.append(event['error'])
                    else:
                        cloud.event(event)
            except Exception as error:
                if not cloud.stop.is_set():
                    self.transport_errors.append(str(error))
        self.receiver = threading.Thread(target=receive, daemon=True)
        self.receiver.start()
        self.media = FixtureMedia(self.root, cloud)
        self.box = Mailbox(self.root)
        self.addCleanup(self.box.close)
        self.controller = Controller(FAMILY, self.box, self.media)
        self.addCleanup(self.controller.close)
        self.printer = MagicMock()
        printer_module = types.ModuleType('escpos.printer')
        printer_module.Usb = MagicMock(return_value=self.printer)
        usb_patch = patch.dict(sys.modules, {'escpos': types.ModuleType('escpos'), 'escpos.printer': printer_module})
        usb_patch.start(); self.addCleanup(usb_patch.stop)
        self.timers = []
        timers = self.timers
        class ManualTimer:
            def __init__(self, interval, function):
                self.interval, self.function = interval, function
            def start(self): timers.append(self)
        timer_patch = patch('controller.threading.Timer', ManualTimer)
        timer_patch.start(); self.addCleanup(timer_patch.stop)

    def stop_server(self):
        self.server.terminate()
        try: self.server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.server.kill(); self.server.wait(timeout=3)
        self.server.stdout.close(); self.server.stderr.close()

    def wait_mode(self, mode):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if self.controller.mode == mode: return
            if self.controller.mode == 'error':
                self.fail(self.controller.snapshot()['hint'])
            time.sleep(.005)
        self.fail(f'Expected {mode}; found {self.controller.mode}')

    def tap(self, key):
        self.controller.block_until = 0
        self.controller.press(key, True)
        self.controller.press(key, False)

    def server_stats(self):
        self.stats_ready.clear()
        self.cloud.send({'type': 'test_stats'})
        self.assertTrue(self.stats_ready.wait(3))
        self.assertFalse(self.transport_errors)
        return self.stats

    def exercise(self, finish):
        for cycle in (1, 2):
            self.tap(5)  # Home -> Draw on the Pi-attached Stream Deck.
            self.wait_mode('recording')
            self.controller.record_latched = True
            timer = self.timers[-1]
            self.assertEqual(timer.interval, 15)
            if finish == 'done':
                self.tap(5)
            else:
                timer.function()  # Fire the actual 15-second completion callback.
            self.wait_mode('print_review')
            timer.function()  # A late callback must not generate another drawing.
            self.assertEqual(self.media.finish_calls, cycle)
            self.assertEqual(self.media.record_calls, cycle)
            self.assertEqual(self.printer.image.call_count, cycle - 1)
            self.assertTrue(Path(self.controller.draft['image']).is_file())
            stats = self.server_stats()
            self.assertEqual((stats['transcriptions'], stats['images'], stats['messages']), (cycle,) * 3)
            self.assertTrue(all(start['mode'] == 'recorded' for start in stats['starts']))
            self.tap(5)  # Explicit preview confirmation -> guarded print.
            self.wait_mode('print_done')
            self.assertEqual(self.printer.image.call_count, cycle)
            self.assertEqual(self.printer.cut.call_count, cycle)
            stats = self.server_stats()
            self.assertEqual(len(stats['statuses']), cycle)
            self.assertEqual(stats['statuses'][-1]['status'], 'printed')
            self.tap(5)
            self.assertEqual(self.controller.mode, 'home')

    def test_done_button_draws_reviews_and_prints_twice_with_wake_listening_off(self):
        self.exercise('done')

    def test_15_second_timeout_draws_reviews_and_prints_twice_with_wake_listening_off(self):
        self.exercise('timeout')


if __name__ == '__main__': unittest.main()
