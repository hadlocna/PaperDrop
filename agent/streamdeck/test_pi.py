import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
from app import Bench
from pi_cloud import Cloud
from pi_media import PiMedia
from test_controller import FAMILY, FakeMedia
from controller import Controller
from store import Mailbox

class PiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def cloud(self):
        cloud=Cloud.__new__(Cloud);cloud.root=self.root;cloud.lock=threading.RLock()
        cloud.request=dict(session='current',ready=threading.Event(),done=threading.Event(),progress=lambda _:None)
        return cloud
    def test_playback_resamples_24k_without_changing_speech_duration(self):
        import wave
        media=PiMedia.__new__(PiMedia);media.root=self.root
        path=self.root/'voice.wav'
        with wave.open(str(path),'wb') as out:
            out.setparams((1,2,24000,0,'NONE','not compressed'))
            out.writeframes(b'\x10\x00'*24000)
        with patch.dict('os.environ',{'PAPERDROP_PLAYBACK_PCM':'test-pcm'}):
            command=media.playback_command(path)
        self.assertEqual(command[:4],['aplay','-q','-D','test-pcm'])
        with wave.open(command[-1]) as wav:
            self.assertEqual(wav.getframerate(),44100)
            self.assertEqual(wav.getnchannels(),2)
            self.assertAlmostEqual(wav.getnframes()/44100,1.55,places=3)

    def test_cloud_requires_session_and_message_match(self):
        cloud=self.cloud()
        cloud.event({'type':'voice_print_pending','session_id':'current','message_id':'wanted'})
        for session,ident in [('old','wanted'),('current','other')]:
            cloud.event({'type':'new_message','session_id':session,'message':{'id':ident,'contentType':'image','content':'image'}})
        self.assertFalse(cloud.request['done'].is_set())
        cloud.event({'type':'new_message','session_id':'current','message':{'id':'wanted','contentType':'image','content':'image'}})
        self.assertTrue(cloud.request['done'].is_set());self.assertEqual(cloud.request['content'],'image')
    def test_disconnect_cancels_recording_and_clears_held_keys(self):
        box=Mailbox(self.root);media=FakeMedia();c=Controller(FAMILY,box,media)
        c.block_until=0;c.press(5,True)
        bench=Bench.__new__(Bench);bench.controller=c;bench.bridge_lost()
        self.assertFalse(c.down);self.assertFalse(bench.bridge_connected)
        self.assertNotEqual(c.mode,'recording')
        c.close();box.close()
    def media_fixture(self, failure=False):
        from PIL import Image
        import types
        media=PiMedia.__new__(PiMedia);media.root=self.root;media.cloud=MagicMock()
        image=self.root/'drawing.png';Image.new('RGB',(64,64),'white').save(image)
        printer=MagicMock()
        if failure:printer.image.side_effect=OSError('USB lost')
        module=types.ModuleType('escpos.printer');module.Usb=MagicMock(return_value=printer)
        return media,image,printer,module
    def test_print_uncertainty_blocks_second_usb_job(self):
        import sys,types
        media,image,printer,module=self.media_fixture(True)
        with patch.dict(sys.modules,{'escpos':types.ModuleType('escpos'),'escpos.printer':module}):
            with self.assertRaises(RuntimeError):media.print_image(image,'drawing')
            with self.assertRaises(RuntimeError):media.print_image(image,'drawing')
            self.assertEqual(module.Usb.call_count,1);self.assertEqual(printer.image.call_count,1)
        self.assertEqual(json.loads((self.root/'print-receipts/drawing.json').read_text())['status'],'uncertain')
        media.cloud.status.assert_not_called()
    def test_successful_print_is_idempotent_and_updates_backend(self):
        import sys,types
        media,image,printer,module=self.media_fixture()
        image.with_suffix('.cloud.json').write_text(json.dumps({'message_id':'cloud-job'}))
        with patch.dict(sys.modules,{'escpos':types.ModuleType('escpos'),'escpos.printer':module}):
            self.assertEqual(media.print_image(image,'drawing')['status'],'printed')
            self.assertEqual(media.print_image(image,'drawing')['status'],'printed')
            self.assertEqual(printer.image.call_count,1);self.assertEqual(printer.cut.call_count,1)
        media.cloud.status.assert_called_once_with('cloud-job','printed')
if __name__=='__main__':unittest.main()
