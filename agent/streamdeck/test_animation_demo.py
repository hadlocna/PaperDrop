import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from controller import Controller
from demo import reset_examples
from render import Renderer
from store import Mailbox
from test_controller import FakeMedia

FAMILY=json.loads((Path(__file__).parent/'family.json').read_text())

class AnimationDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.renderer=Renderer(FAMILY)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.box=Mailbox(self.tmp.name)
        self.c=Controller(FAMILY,self.box,FakeMedia())
    def tearDown(self):
        self.c.close();self.box.close();self.tmp.cleanup()
    def test_examples_reset_only_examples(self):
        self.box.send(dict(id='real',sender='rue',recipient='margo',kind='voice',audio='real.wav'))
        reset_examples(self.box)
        examples=self.box.inbox('alma')
        self.assertEqual(len(examples),2)
        self.assertTrue(all(m['demo'] for m in examples))
        self.box.mark_seen(examples[0]);reset_examples(self.box)
        self.assertEqual(len(self.box.inbox('alma',unread=True)),2)
        self.assertEqual(len(self.box.inbox('margo')),1)
        self.c.person='alma';self.c.mode='personal'
        tiles=self.c.snapshot()['tiles']
        self.assertEqual((tiles[3]['person'],tiles[3]['type_badge']),('andy','Mic'))
        self.assertEqual((tiles[4]['person'],tiles[4]['type_badge']),('elise','Pencil'))
    def test_mail_moves_without_moving_other_keys_or_actions(self):
        reset_examples(self.box)
        snapshot=self.c.snapshot()
        with patch('render.time.monotonic',return_value=.1):a=self.renderer.keys(snapshot)
        with patch('render.time.monotonic',return_value=.3):b=self.renderer.keys(snapshot)
        self.assertNotEqual(a[0].tobytes(),b[0].tobytes())
        self.assertEqual(a[3].tobytes(),b[3].tobytes())
        self.assertEqual(snapshot,self.c.snapshot())
    def test_idle_is_static(self):
        snapshot=self.c.snapshot()
        self.assertFalse(self.renderer.animated(snapshot))
        with patch('render.time.monotonic',return_value=1):a=self.renderer.keys(snapshot)
        with patch('render.time.monotonic',return_value=2):b=self.renderer.keys(snapshot)
        self.assertEqual([x.tobytes() for x in a],[x.tobytes() for x in b])
    def test_pencil_moves_while_buttons_remain_disabled(self):
        self.c.mode='generating';s=self.c.snapshot()
        self.assertTrue(all(t['disabled'] for t in s['tiles']))
        with patch('render.time.monotonic',return_value=1):a=self.renderer.keys(s)
        with patch('render.time.monotonic',return_value=2):b=self.renderer.keys(s)
        self.assertNotEqual(a[4].tobytes(),b[4].tobytes())

if __name__=='__main__':unittest.main()
