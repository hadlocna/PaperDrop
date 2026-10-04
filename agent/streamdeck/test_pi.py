import json
import shutil
import sys
import types
import uuid
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
        self.root=Path(tempfile.gettempdir())/('paperdrop-test-'+uuid.uuid4().hex)
        self.root.mkdir()
    def tearDown(self):shutil.rmtree(self.root, ignore_errors=True)
    def cloud(self):
        cloud=Cloud.__new__(Cloud);cloud.root=self.root;cloud.lock=threading.RLock()
        cloud.speaker_lock=threading.Lock()
        cloud.printer=None;cloud.ack_dir=self.root/'cloud-status';cloud.ack_dir.mkdir()
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

    def test_capture_pcm_prefers_detected_usb_microphone_card(self):
        media=PiMedia.__new__(PiMedia)
        cards = ' 0 [Microphone     ]: USB-Audio - USB Microphone\n 1 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0\n'
        with patch.dict('os.environ', {}, clear=True), patch('pi_media.Path.read_text', return_value=cards):
            self.assertEqual(media.capture_pcm(), 'plughw:CARD=Microphone,DEV=0')

    def test_capture_pcm_honors_environment_override(self):
        media=PiMedia.__new__(PiMedia)
        with patch.dict('os.environ', {'PAPERDROP_CAPTURE_PCM': 'plughw:CARD=Custom,DEV=0'}):
            self.assertEqual(media.capture_pcm(), 'plughw:CARD=Custom,DEV=0')

    def media_with_finished_recording(self, path):
        class Proc:
            returncode = 0
            def poll(self): return 0
            def wait(self, timeout=None): return 0
            def send_signal(self, signal): pass
            def kill(self): pass
        media=PiMedia.__new__(PiMedia)
        media.audio_lock=threading.RLock()
        media.recording=Proc()
        media.capture_done=threading.Event();media.capture_done.set()
        media.record_error=None
        return media

    def test_finish_recording_reports_quiet_signal(self):
        import wave
        path=self.root/'quiet.wav'
        with wave.open(str(path),'wb') as out:
            out.setparams((1,2,24000,0,'NONE','not compressed'))
            out.writeframes(b'\0\0'*24000)
        media=self.media_with_finished_recording(path)
        with self.assertRaises(Exception) as error:
            media.finish_recording(path)
        self.assertIn('quiet', str(error.exception))
        self.assertEqual(getattr(error.exception, 'public_message', ''), 'I could not hear enough audio. Please speak close to the PaperDrop microphone and try again.')

    def test_finish_recording_logs_signal_and_returns_duration(self):
        import wave
        path=self.root/'voice.wav'
        with wave.open(str(path),'wb') as out:
            out.setparams((1,2,24000,0,'NONE','not compressed'))
            out.writeframes(b'\xe8\x03'*24000)
        media=self.media_with_finished_recording(path)
        with self.assertLogs(level='INFO') as logs:
            self.assertEqual(media.finish_recording(path), 1.0)
        self.assertTrue(any('mic_recording_finished' in line and 'rms=' in line and 'peak=' in line for line in logs.output))

    def test_cloud_requires_session_and_message_match(self):
        cloud=self.cloud()
        cloud.event({'type':'voice_print_pending','session_id':'current','message_id':'wanted'})
        for session,ident in [('old','wanted'),('current','other')]:
            cloud.event({'type':'new_message','session_id':session,'message':{'id':ident,'contentType':'image','content':'image'}})
        self.assertFalse(cloud.request['done'].is_set())
        cloud.event({'type':'new_message','session_id':'current','message':{'id':'wanted','contentType':'image','content':'image'}})
        self.assertTrue(cloud.request['done'].is_set());self.assertEqual(cloud.request['content'],'image')

    def test_cloud_prints_ordinary_app_image_message(self):
        from io import BytesIO
        from PIL import Image
        import base64
        cloud=self.cloud();cloud.request=None;cloud.printer=MagicMock();cloud.send=MagicMock()
        cloud.printer.print_image.return_value={'status':'printed'}
        output=BytesIO();Image.new('RGB',(8,8),'white').save(output,format='PNG')
        cloud.ordinary_message({'type':'new_message','message':{'id':'ordinary','contentType':'image',
            'content':base64.b64encode(output.getvalue()).decode()}})
        printed=self.root/'app-messages/ordinary.png'
        self.assertTrue(printed.exists())
        cloud.printer.print_image.assert_called_once_with(printed,'ordinary')
        self.assertEqual([call.args[0]['status'] for call in cloud.send.call_args_list], ['printing','printed'])

    def test_cloud_prints_ordinary_app_image_without_duplicate_status_from_pi_media(self):
        from io import BytesIO
        from PIL import Image
        import base64
        cloud=self.cloud();cloud.request=None;cloud.send=MagicMock()
        printer=MagicMock();printer.cloud=cloud;printer.print_image.return_value={'status':'printed'}
        cloud.printer=printer
        output=BytesIO();Image.new('RGB',(8,8),'white').save(output,format='PNG')
        cloud.ordinary_message({'type':'new_message','message':{'id':'ordinary','contentType':'image',
            'content':base64.b64encode(output.getvalue()).decode()}})
        self.assertEqual([call.args[0]['status'] for call in cloud.send.call_args_list], ['printing'])

    def test_cloud_fetch_logs_returns_log_bundle(self):
        import subprocess
        cloud=self.cloud();cloud.send=MagicMock()
        completed=subprocess.CompletedProcess(['journalctl'],0,stdout='hello',stderr='')
        with patch('pi_cloud.subprocess.run', return_value=completed) as run:
            cloud.fetch_logs({'request_id':'req','log_type':'agent','lines':500})
        self.assertIn('paperdrop-runtime.service', run.call_args.args[0])
        cloud.send.assert_called_once_with({'type':'log_bundle','request_id':'req','log_type':'agent','content':'hello'})

    def test_cloud_speaker_command_accepts_microphone_and_play_actions(self):
        async def run_speaker(action, address=None, audio=None, volume=None):
            return {'ok': True, 'action': action, 'audio': audio}
        module=types.ModuleType('speaker_control');module.run_speaker=run_speaker
        cloud=self.cloud();cloud.send=MagicMock()
        with patch.dict(sys.modules, {'speaker_control': module}):
            cloud.speaker_command({'request_id':'mic','action':'microphone_test'})
            cloud.speaker_command({'request_id':'play','action':'play','audio':'abc'})
        self.assertEqual(cloud.send.call_args_list[0].args[0]['action'], 'microphone_test')
        self.assertEqual(cloud.send.call_args_list[1].args[0]['audio'], 'abc')
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
    def test_long_print_reaches_usb_without_squashing_and_cuts_once(self):
        import sys, types
        from PIL import Image
        media, image, printer, module = self.media_fixture()
        Image.new('RGB', (288, 2000), 'black').save(image)
        with patch.dict(sys.modules, {'escpos': types.ModuleType('escpos'), 'escpos.printer': module}):
            media.print_image(image, 'long')
        args, kwargs = printer.image.call_args
        self.assertEqual(args[0].size, (576, 4000))
        self.assertEqual(kwargs['fragment_height'], 960)
        printer.cut.assert_called_once()

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
