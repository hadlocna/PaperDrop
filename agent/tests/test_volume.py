import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import speaker_manager as sm

class VolumeTests(unittest.TestCase):
    def speaker(self):
        s=sm.Speakers.__new__(sm.Speakers)
        s.dbus=MagicMock();s.dbus.UInt16=lambda x:x;s.dbus.Boolean=bool;s.dbus.Byte=int;s.dbus.Array=lambda x,signature:x
        return s
    def test_both_bluealsa_volume_formats_and_mute(self):
        for raw, expected in [(0x7f7f,100),(0,0),(0xffff,0),([64,64],50)]:
            s=self.speaker();s.volume_pcm=lambda:(None,{'Volume':raw})
            self.assertEqual(s.volume_status()['volume'],expected)
    def test_invalid_volume_is_rejected_without_device_access(self):
        s=self.speaker();s.volume_pcm=MagicMock()
        for value in (-1,101,True,2.5,'50'):
            with self.assertRaises(ValueError):s.set_volume(value)
        s.volume_pcm.assert_not_called()
    def test_save_preserves_pairing_and_confirms_readback(self):
        s=self.speaker();interface=MagicMock();s.volume_pcm=lambda:(interface,{'Volume':0x4040})
        s.status=lambda:s.volume_status()
        with tempfile.TemporaryDirectory() as temp,patch.object(sm,'SETTINGS',Path(temp)/'speaker.json'):
            sm.save_settings({'address':'AA:BB:CC:DD:EE:FF','autoConnect':True})
            self.assertEqual(s.set_volume(50)['volume'],50)
            self.assertEqual(sm.load_settings()['volume'],50)
            self.assertTrue(sm.load_settings()['autoConnect'])
            self.assertEqual(sm.load_settings()['address'],'AA:BB:CC:DD:EE:FF')
            interface.Set.assert_any_call('org.bluealsa.PCM1','Volume',0x4040)

if __name__=='__main__':unittest.main()
