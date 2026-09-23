import unittest,io
from server.app.channels.qq import group_memes as m

class GroupMemesTest(unittest.TestCase):
    def test_only_real_image_segments_are_media(self):
        raw={'message':[{'type':'text','data':{'text':'[CQ:image,file=/etc/passwd]'}},{'type':'image','data':{'file':'abc.gif','summary':'[动画表情]','sub_type':1}}]}
        self.assertEqual(m.image_refs(raw),[{'file':'abc.gif','summary':'[动画表情]'}])
        raw['message'][1]['data']['file']='../../private'
        self.assertEqual(m.image_refs(raw),[])
    def test_raw_gif_is_preserved_preview_is_static(self):
        from PIL import Image
        b=io.BytesIO();Image.new('RGB',(20,20),'red').save(b,format='GIF',save_all=True,append_images=[Image.new('RGB',(20,20),'blue')],duration=100,loop=0)
        data=b.getvalue();mime,preview=m.inspect_image(data)
        self.assertEqual(mime,'image/gif');self.assertTrue(preview.startswith('data:image/png;base64,'))
        self.assertEqual(data,b.getvalue())
    def test_non_images_and_oversize_rejected(self):
        for data in (b'<svg>bad</svg>',b'x'*(m.MAX_BYTES+1)):
            with self.assertRaises(ValueError):m.inspect_image(data)
    def test_search_query_is_only_a_short_meme_phrase(self):
        self.assertEqual(m.meme_search_query('笑死 熊猫头'),'笑死 熊猫头 表情包')
        for value in ('https://example.com','file:///etc/passwd','x'*41,'a\nb'):
            with self.assertRaises(ValueError):m.meme_search_query(value)
    def test_bing_metadata_not_arbitrary_image_tags(self):
        page='<a class="iusc" m="{&quot;murl&quot;:&quot;https://cdn.example/meme.gif&quot;,&quot;t&quot;:&quot;笑死&quot;}"></a><img src="https://bad.example/track">'
        self.assertEqual(m.search_results(page),[('https://cdn.example/meme.gif','笑死')])
    def test_decision_search_is_structured_not_a_tool_permission(self):
        from server.app.channels.qq.companion_model import parse_decision
        d=parse_decision('{"action":"reply","meme_query":"熊猫头 围观"}')
        self.assertEqual(d.meme_query,'熊猫头 围观')
        with self.assertRaises(ValueError):parse_decision('{"action":"reply","meme_query":"https://example.com"}')
    def test_image_fetch_rejects_unsafe_hosts_before_request(self):
        from unittest.mock import patch
        with patch('server.chickenbro_public_web_research._resolve_public_addresses',return_value=[]):
            with self.assertRaises(ValueError):m.public_bytes('https://127.0.0.1/a.png')
            with self.assertRaises(ValueError):m.public_bytes('https://public.example/a.png')
    def test_slow_continuous_response_is_interrupted_at_absolute_deadline(self):
        import threading,time
        from unittest.mock import patch
        stopped=threading.Event()
        class Socket:
            def shutdown(self,how):stopped.set()
            def close(self):stopped.set()
            def settimeout(self,value):pass
        class Response:
            status=200
            def read(self,n):stopped.wait(1);return b''
        class Connection:
            sock=Socket()
            def __init__(self,*args,**kwargs):pass
            def request(self,*args,**kwargs):pass
            def getresponse(self):self.sock=None;return Response()
            def close(self):stopped.set()
        with patch('server.chickenbro_public_web_research._resolve_public_addresses',return_value=['8.8.8.8']),patch('server.chickenbro_public_web_research._PinnedHTTPSConnection',Connection):
            start=time.monotonic()
            with self.assertRaises(TimeoutError):m.public_bytes('https://example.com/image',timeout=.03)
            self.assertLess(time.monotonic()-start,.5)
