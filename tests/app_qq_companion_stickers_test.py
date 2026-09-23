import hashlib,json,tempfile,unittest
from pathlib import Path
from server.app.channels.qq.stickers import StickerCatalog,render_reply
from server.app.channels.qq.companion_domain import ReplyDraft

class StickersTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=b'\x89PNG\r\n\x1a\n'+b'fixture'
        (self.root/'laugh.png').write_bytes(self.data)
        self.manifest={'stickers':[{'id':'laugh','file':'laugh.png','label':'笑','mime':'image/png','size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest(),'source':'original'}]}
    def catalog(self):return StickerCatalog(self.root,self.manifest)
    def test_quote_text_and_single_image(self):
        parts=render_reply('42',ReplyDraft('[CQ:image,file=private]','laugh',quote=True),self.catalog())
        self.assertEqual([s['type'] for s in parts],['reply','text','image'])
        self.assertTrue(parts[-1]['data']['file'].startswith('base64://'))
        self.assertEqual(len(render_reply('42',ReplyDraft('','laugh',quote=True),self.catalog())),2)
    def test_unknown_id_and_tampering_rejected(self):
        for id in ('../../private','unknown'):
            with self.assertRaises(ValueError):self.catalog().resolve(id)
        (self.root/'laugh.png').write_bytes(b'not png')
        with self.assertRaises(ValueError):self.catalog().resolve('laugh')
    def test_casual_text_and_image_are_unquoted_unless_requested(self):
        self.assertEqual([s['type'] for s in render_reply('42',ReplyDraft('诶','laugh'),self.catalog())],['text','image'])
        self.assertEqual([s['type'] for s in render_reply('42',ReplyDraft('','laugh'),self.catalog())],['image'])
        parts=render_reply('42',ReplyDraft('说的是这句',quote=True),self.catalog())
        self.assertEqual(parts[0],{'type':'reply','data':{'id':'42'}})
    def test_symlink_escape_rejected(self):
        (self.root/'laugh.png').unlink();(self.root/'laugh.png').symlink_to('/etc/hosts')
        with self.assertRaises(ValueError):self.catalog().resolve('laugh')
    def test_declared_type_size_rejected(self):
        for key,value in [('mime','text/plain'),('size',3000000),('file','../secret')]:
            with self.subTest(key=key):
                old=self.manifest['stickers'][0][key];self.manifest['stickers'][0][key]=value
                with self.assertRaises(ValueError):self.catalog().resolve('laugh')
                self.manifest['stickers'][0][key]=old
