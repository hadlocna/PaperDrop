import tempfile
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from printer_readiness import printer_ready, PRINTER_LOCK
import test_cousin_mail

class ReadinessProbeTests(unittest.TestCase):
    def probe(self, online, paper):
        printer=MagicMock();printer.query_status.side_effect=[online,paper]
        module=types.ModuleType('escpos.printer');module.Usb=MagicMock(return_value=printer)
        constants=types.ModuleType('escpos.constants');constants.RT_STATUS_ONLINE=b'1';constants.RT_STATUS_PAPER=b'4'
        with patch.dict(sys.modules,{'escpos':types.ModuleType('escpos'),'escpos.printer':module,'escpos.constants':constants}):
            result=printer_ready()
        printer.close.assert_called_once()
        return result

    def test_only_valid_online_and_paper_response_counts(self):
        self.assertTrue(self.probe(b'\x12',b'\x12'))
        self.assertTrue(self.probe(b'\x12',b'\x1e'))
        for online,paper in [(b'',b'\x12'),(b'\x12',b''),(b'\x1a',b'\x12'),(b'\x12',b'\x72'),(b'\x00',b'\x00')]:
            self.assertFalse(self.probe(online,paper))

    def test_active_print_cannot_be_interrupted_by_probe(self):
        with PRINTER_LOCK:self.assertFalse(printer_ready())

class ReadinessNoticeTests(unittest.TestCase):
    setUp = test_cousin_mail.CousinMailTests.setUp
    tearDown = test_cousin_mail.CousinMailTests.tearDown
    def test_notice_goes_to_printer_without_impersonating_a_child(self):
        from PIL import ImageFont
        notice=dict(id='b'*64,house='ohio',firmware='2.1.1')
        with patch('cousin_mail.ImageFont.truetype',return_value=ImageFont.load_default()):
            self.receiver.receive_notice(notice)
        self.receiver.media.print_image.assert_called_once()
        self.receiver.cloud.mail_receipt.assert_called_once_with('b'*64,'printed',notice=True)
        self.assertEqual(self.box.inbox('alma'),[])
        self.receiver.family={**self.receiver.family,'station':'ohio'}
        with self.assertRaises(ValueError):self.receiver.receive_notice(notice)
