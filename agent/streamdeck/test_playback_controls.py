import signal
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from media import Media


class PlaybackControlsTests(unittest.TestCase):
    def test_real_process_pauses_resumes_and_stops_while_paused(self):
        with tempfile.TemporaryDirectory() as directory:
            progress=Path(directory)/'progress'
            source = "import pathlib,sys,time\np=pathlib.Path(sys.argv[1])\nfor n in range(1000):\n t=p.with_suffix('.tmp');t.write_text(str(n));t.replace(p);time.sleep(.02)\n"
            process=subprocess.Popen([sys.executable,'-c',source,str(progress)])
            media=Media(directory);media.player=media.playback_process=process
            try:
                deadline=time.monotonic()+3
                while not progress.exists() and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(progress.exists())
                media.pause_playback();time.sleep(.05)
                paused=int(progress.read_text());time.sleep(.15)
                self.assertEqual(int(progress.read_text()),paused)
                media.pause_playback();time.sleep(.15)
                self.assertGreater(int(progress.read_text()),paused)
                media.pause_playback();media.stop_audio()
                self.assertNotEqual(process.wait(timeout=2),0)
            finally:
                if process.poll() is None:process.kill();process.wait()
    def test_pause_resume_and_stop_resume_before_terminating(self):
        with tempfile.TemporaryDirectory() as directory:
            media=Media(directory)
            process=MagicMock();process.poll.return_value=None
            media.player=media.playback_process=process
            self.assertTrue(media.pause_playback())
            process.send_signal.assert_called_with(signal.SIGSTOP)
            self.assertTrue(media.playback_paused)
            self.assertTrue(media.pause_playback())
            process.send_signal.assert_called_with(signal.SIGCONT)
            self.assertFalse(media.playback_paused)
            media.pause_playback();process.reset_mock()
            media.stop_audio()
            self.assertEqual(process.method_calls[1].args,(signal.SIGCONT,))
            process.terminate.assert_called_once()
            self.assertFalse(media.playback_paused)

    def test_paused_time_does_not_exhaust_playback_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            media=Media(directory);process=MagicMock();process.returncode=0
            process.poll.side_effect=[None,None,0,0]
            media.player=media.playback_process=process;media.playback_paused=True
            with patch('media.time.sleep'),patch('media.time.monotonic',side_effect=[0,100,200]):
                media.wait_playback(process)
            process.kill.assert_not_called()
            self.assertIsNone(media.playback_process)

    def test_finished_process_cannot_be_paused(self):
        with tempfile.TemporaryDirectory() as directory:
            media=Media(directory);process=MagicMock();process.poll.return_value=0
            media.playback_process=process
            self.assertFalse(media.pause_playback())
            process.send_signal.assert_not_called()
