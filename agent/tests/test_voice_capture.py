import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from voice_capture import RequestCapture

class CaptureTests(unittest.TestCase):
    def test_short_pause_does_not_cut_off_prompt(self):
        c = RequestCapture(0)
        for i in range(10): c.add(b'\x00\x10' * 1600, i / 10)
        self.assertEqual(c.add(b'\0' * 3200, 2), 'listening')
        self.assertEqual(c.add(b'\x00\x10' * 1600, 3), 'listening')
        self.assertEqual(c.add(b'\0' * 3200, 6.9), 'listening')
        self.assertEqual(c.add(b'\0' * 3200, 7), 'complete')
        self.assertEqual(c.wav()[:4], b'RIFF')

    def test_silence_and_one_click_do_not_submit(self):
        c = RequestCapture(0)
        c.add(b'\x00\x10' * 1600, 0)
        self.assertEqual(c.add(b'\0' * 3200, 5), 'listening')
        self.assertEqual(c.add(b'\0' * 3200, 15), 'no_request')

    def test_limit_rejects_instead_of_printing_truncated_prompt(self):
        c = RequestCapture(0)
        self.assertEqual(c.add(b'\x00\x10' * 1600, 45), 'too_long')
