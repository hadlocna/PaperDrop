import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import wave
from PIL import Image, ImageFont
from cousin_mail import Receiver
from store import Mailbox
from pi_cloud import Cloud

FAMILY = json.loads(Path(__file__).with_name('family.json').read_text())

class CousinMailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.box = Mailbox(self.root)
        self.receiver = Receiver.__new__(Receiver)
        self.receiver.root, self.receiver.mailbox, self.receiver.family = self.root, self.box, FAMILY
        self.receiver.people = {p['id']:p for p in FAMILY['children']}
        self.receiver.cloud = MagicMock()
        self.receiver.media = MagicMock()

    def tearDown(self):
        self.box.close()
        self.temp.cleanup()

    def message(self, kind='voice'):
        out = io.BytesIO()
        if kind == 'voice':
            with wave.open(out, 'wb') as wav:
                wav.setparams((1,2,16000,0,'NONE','not compressed'))
                wav.writeframes(b'\x01\x00'*16000)
        else:
            Image.new('RGB',(576,100),'white').save(out,format='PNG')
        return dict(id='a'*64,sender='andy',recipient='alma',kind=kind,media=base64.b64encode(out.getvalue()).decode())

    def test_voice_persists_with_sender_badge_no_autoplay_or_print(self):
        msg = self.message()
        self.receiver.receive(msg);self.receiver.receive(msg)
        inbox=self.box.inbox('alma',unread=True)
        self.assertEqual(len(inbox),1);self.assertEqual(inbox[0]['sender'],'andy')
        self.assertEqual(self.box.inbox('theodore'),[])
        self.receiver.media.play.assert_not_called();self.receiver.media.print_image.assert_not_called()
        self.box.close();self.box=Mailbox(self.root);self.receiver.mailbox=self.box
        self.assertTrue(Path(self.box.inbox('alma')[0]['audio']).exists())
        self.box.mark_seen(inbox[0]);self.receiver.receive(msg)
        self.receiver.cloud.mail_receipt.assert_called_with(msg['id'],'read')

    def test_picture_is_labelled_and_automatically_printed(self):
        font=ImageFont.load_default()
        with patch('cousin_mail.ImageFont.truetype',return_value=font), patch('cousin_mail.ImageDraw.Draw') as draw:
            self.receiver.receive(self.message('drawing'))
            captions=[call.args[1] for call in draw.return_value.text.call_args_list]
            self.assertEqual(captions,['To: Alma','From: Andi'])
        self.receiver.media.print_image.assert_called_once()
        self.receiver.cloud.mail_receipt.assert_called_with('a'*64,'printed')
        self.assertEqual(self.box.inbox('alma')[0]['kind'],'drawing')

    def test_tall_mail_uses_full_width_and_retains_bottom(self):
        out = io.BytesIO()
        Image.new('RGB', (288, 2000), 'black').save(out, format='PNG')
        msg = {**self.message('drawing'), 'media': base64.b64encode(out.getvalue()).decode()}
        with patch('cousin_mail.ImageFont.truetype', return_value=ImageFont.load_default()):
            self.receiver.receive(msg)
        path = self.receiver.media.print_image.call_args.args[0]
        with Image.open(path) as image:
            self.assertEqual(image.size, (576, 4112))
            self.assertEqual(image.getpixel((575, 4099)), (0, 0, 0))

    def test_wrong_house_and_path_escape_cannot_enter_mailbox(self):
        for changes in ({'recipient':'lore'}, {'id':'../outside'}):
            with self.assertRaises(ValueError):self.receiver.receive({**self.message(),**changes})
        self.assertEqual(self.box.inbox('alma'),[])

    def test_cloud_stages_incoming_without_interrupting_generation(self):
        cloud=Cloud.__new__(Cloud);cloud.root=self.root;cloud.lock=threading.RLock()
        cloud.request={'session':'drawing'}
        cloud.event({'type':'cousin_mail','message':self.message()})
        self.assertEqual(cloud.request,{'session':'drawing'})
        self.assertTrue((self.root/'incoming-mail'/('a'*64+'.json')).exists())

    def test_uncertain_print_is_reported_failed_and_not_acknowledged_printed(self):
        from pi_media import PrintOutcomeUnknown
        self.receiver.media.print_image.side_effect=PrintOutcomeUnknown()
        with patch('cousin_mail.ImageFont.truetype',return_value=ImageFont.load_default()):
            self.receiver.receive(self.message('drawing'))
        self.receiver.cloud.mail_receipt.assert_called_once_with('a'*64,'failed')

if __name__=='__main__':unittest.main()
