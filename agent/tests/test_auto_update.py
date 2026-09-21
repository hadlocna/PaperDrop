import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import auto_update as update

class UpdateTests(unittest.TestCase):
    def test_only_checksum_verified_same_origin_https_manifests(self):
        good={'format':2,'version':'2.0.1','sha256':'a'*64,'url':'https://api.paperdrop.me/uploads/release.tar.gz'}
        self.assertEqual(update.manifest_check(good),good)
        for changes in ({'format':1},{'version':'../../etc'},{'sha256':''},{'url':'http://api.paperdrop.me/uploads/x'},{'url':'https://other.example/uploads/x'}):
            with self.assertRaises(ValueError):update.manifest_check({**good,**changes})
    def test_traversal_and_links_never_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'a.tar.gz';target=root/'out';target.mkdir()
            for name,kind in (('../escape',tarfile.REGTYPE),('/etc/example',tarfile.REGTYPE),('link',tarfile.SYMTYPE)):
                with tarfile.open(archive,'w:gz') as tar:
                    item=tarfile.TarInfo(name);item.type=kind;item.linkname='/etc';tar.addfile(item)
                with self.assertRaises(ValueError):update.unpack(archive,target)
                self.assertEqual(list(target.iterdir()),[])
    def test_switch_is_atomic_and_previous_release_survives(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();a=base/'a';b=base/'b';a.mkdir();b.mkdir()
            with patch.object(update,'BASE',base):
                update.switch(a);self.assertEqual((base/'current').resolve(),a)
                update.switch(b);self.assertEqual((base/'current').resolve(),b)
                self.assertTrue(a.exists())
    def test_failed_release_is_not_retried_in_a_loop(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();state=base/'state';state.mkdir()
            (state/'failed.json').write_text(json.dumps({'sha256':'a'*64,'time':update.time.time()}))
            with patch.object(update,'BASE',base),patch.object(update,'STATE',state),patch.object(update.urllib.request,'urlopen') as download:
                update.install({'version':'2.0.1','sha256':'a'*64});download.assert_not_called()

    def test_unhealthy_release_rolls_back_code_and_dependencies(self):
        import hashlib
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();state=base/'state';state.mkdir();previous=base/'previous';previous.mkdir()
            (previous/'release.json').write_text(json.dumps({'version':'old'}));(base/'current').symlink_to(previous)
            archive=io.BytesIO()
            with tarfile.open(fileobj=archive,mode='w:gz') as tar:
                for name in ('runtime.py','requirements.txt','src/ws_agent.py','streamdeck/app.py','release.json'):
                    data=json.dumps({'version':'new'}).encode() if name=='release.json' else b''
                    info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
            data=archive.getvalue();digest=hashlib.sha256(data).hexdigest()
            response=io.BytesIO(data);response.url='https://api.paperdrop.me/uploads/test.tar.gz'
            with patch.object(update,'BASE',base),patch.object(update,'STATE',state),patch.object(update,'HEALTH',base/'absent-health'),patch.object(update,'idle',return_value=True),patch.object(update.urllib.request,'urlopen',return_value=response),patch.object(update.subprocess,'run') as run,patch.object(update.time,'sleep'),patch('update_guard.acquire',return_value=MagicMock()):
                with self.assertRaisesRegex(RuntimeError,'did not authenticate'):
                    update.install({'version':'new','sha256':digest,'url':response.url})
            self.assertEqual((base/'current').resolve(),previous)
            self.assertTrue((previous/'release.json').exists())
            self.assertEqual(json.loads((state/'failed.json').read_text())['sha256'],digest)
            self.assertFalse((state/'pending.json').exists())
            self.assertEqual(sum(call.args[0][:2]==['systemctl','restart'] for call in run.call_args_list),2)

if __name__=='__main__':unittest.main()
