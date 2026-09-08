import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('publish',Path(__file__).with_name('publish.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class PublishTest(unittest.TestCase):
    def test_overlay_preserves_every_unrelated_file_and_rejects_modified_stage(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d).resolve();old=b/'old';payload=b/'payload';target=b/'new';old.mkdir();payload.mkdir()
            (old/'unrelated').write_text('keep')
            for f in p.FILES:
                dest=payload/f;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('new')
            m={'previousCode':str(old),'beforeFiles':{f:None for f in p.FILES},'files':p.hashes(payload)}
            p.stage(m,payload,target)
            self.assertEqual((target/'unrelated').read_text(),'keep')
            (target/'unrelated').write_text('changed')
            with self.assertRaises(ValueError):p.stage(m,payload,target)

    def test_failure_restores_pointer_and_restarts_both_services(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d).resolve();old=b/'old';old.mkdir();new=b/'new';new.mkdir();code=b/'code';code.symlink_to(old);web=b/'web';web.symlink_to(old)
            m={'previousCode':str(old),'previousWeb':str(old),'migrations':[]};calls=[]
            def run(*args):
                calls.append(args)
                if args[:2]==('systemctl','show'):return str(code)
                if args[:2]==('systemctl','start'):raise RuntimeError('injected failure')
                return ''
            with patch.multiple(p,CODE=code,WEB=web),patch.object(p,'run',side_effect=run),patch.object(p,'active_jobs',return_value=0),patch.object(p,'ready',return_value=True):
                with self.assertRaises(RuntimeError):p.promote(m,new,{},True)
            self.assertEqual(code.resolve(),old)
            for u in p.UNITS:self.assertIn(('systemctl','restart',u),calls)

if __name__=='__main__':unittest.main()
