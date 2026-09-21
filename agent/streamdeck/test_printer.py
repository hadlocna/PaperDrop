import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from printer import print_image

class PrinterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.image=self.root/'image.png';self.image.write_bytes(b'test image')
    def tearDown(self):self.tmp.cleanup()
    def test_absent_epson_does_not_submit(self):
        with patch('printer.request',return_value={'response':{'stdout':'USB audio device'}}) as req:
            with self.assertRaises(RuntimeError):print_image(self.image,'one',self.root)
            self.assertEqual(req.call_count,1)
    def test_success_is_idempotent(self):
        with patch('printer.request',side_effect=[{'response':{'stdout':'04b8:0e28 Epson'}},{'sent':True}]) as req:
            self.assertEqual(print_image(self.image,'one',self.root)['status'],'sent')
            self.assertEqual(print_image(self.image,'one',self.root)['status'],'sent')
            self.assertEqual(req.call_count,2)
    def test_timeout_never_resubmits(self):
        with patch('printer.request',side_effect=[{'response':{'stdout':'04b8:0e28 Epson'}},TimeoutError()]) as req:
            with self.assertRaises(TimeoutError):print_image(self.image,'one',self.root)
            with self.assertRaises(RuntimeError):print_image(self.image,'one',self.root)
            self.assertEqual(req.call_count,2)

if __name__=='__main__':unittest.main()
