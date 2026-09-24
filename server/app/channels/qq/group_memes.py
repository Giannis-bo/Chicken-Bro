"""Current-group image reuse and bounded meme search. No model-selected URLs."""
import base64
import hashlib
from html.parser import HTMLParser
import io
import json
import re
import socket
from threading import Event,Timer
import time
import warnings
from urllib.parse import urlsplit,quote_plus

from server.app.channels.qq.onebot import OneBotError

MAX_BYTES=2*1024**2

def image_refs(raw):
    refs=[]
    for segment in raw.get('message',[]):
        if segment.get('type')!='image':continue
        data=segment.get('data',{});file=data.get('file')
        if not isinstance(file,str) or not re.fullmatch(r'[a-zA-Z0-9_{}.-]{1,160}',file) or '..' in file:continue
        refs.append({'file':file,'summary':str(data.get('summary') or '群友图片')[:120]})
        if len(refs)==2:break
    return refs

def inspect_image(data):
    from PIL import Image,ImageOps
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES:raise ValueError('invalid image size')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                mime={'PNG':'image/png','JPEG':'image/jpeg','GIF':'image/gif','WEBP':'image/webp'}.get(source.format)
                if not mime or source.width*source.height>4_000_000 or getattr(source,'n_frames',1)>200:raise ValueError('unsupported image')
                # A bounded visual preview; outgoing content retains original animation.
                source.seek(0);preview=ImageOps.exif_transpose(source).convert('RGB');preview.thumbnail((512,512))
                out=io.BytesIO();preview.save(out,format='PNG')
                if len(out.getvalue())>700000:raise ValueError('oversized preview')
                return mime,'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
    except Exception as error:
        raise ValueError('invalid raster image') from None

def public_bytes(url,*,timeout=8,max_bytes=MAX_BYTES):
    """Pinned public DNS, HTTPS, no redirects, strict time and byte bounds."""
    from server.chickenbro_public_web_research import _safe_public_url,_resolve_public_addresses,_PinnedHTTPSConnection
    safe=_safe_public_url(url)
    if not safe:raise ValueError('invalid media URL')
    parsed=urlsplit(safe);deadline=time.monotonic()+timeout
    addresses=_resolve_public_addresses(parsed.hostname,deadline)
    if not addresses:raise ValueError('non-public media host')
    conn=_PinnedHTTPSConnection(parsed.hostname,addresses[0],timeout=max(.1,deadline-time.monotonic()))
    expired=Event();held_socket=[None]
    def interrupt():
        expired.set();active=held_socket[0] or conn.sock
        if active is not None:
            try:active.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:active.close()
            except OSError:pass
    timer=Timer(max(0,deadline-time.monotonic()),interrupt);timer.daemon=True;timer.start()
    try:
        conn.request('GET',(parsed.path or '/')+('?' + parsed.query if parsed.query else ''),headers={'Host':parsed.hostname,'User-Agent':'Mozilla/5.0','Accept':'*/*'})
        held_socket[0]=conn.sock
        response=conn.getresponse()
        if response.status!=200:raise ValueError('media response rejected')
        chunks=[];size=0
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('media deadline')
            if conn.sock:conn.sock.settimeout(remaining)
            chunk=response.read(min(65536,max_bytes+1-size))
            if expired.is_set() or time.monotonic()>=deadline:raise TimeoutError('media deadline')
            if not chunk:break
            chunks.append(chunk);size+=len(chunk)
            if size>max_bytes:raise ValueError('media too large')
        return b''.join(chunks)
    except Exception as error:
        if expired.is_set() or time.monotonic()>=deadline:raise TimeoutError('media deadline') from None
        raise
    finally:timer.cancel();conn.close()

def meme_search_query(query):
    if not isinstance(query,str) or not 1<=len(query.strip())<=40 or re.search(r'[:/\\\r\n]',query):raise ValueError('invalid meme query')
    return query.strip()+' 表情包'

def search_results(page):
    class Parser(HTMLParser):
        def __init__(self):super().__init__();self.results=[]
        def handle_starttag(self,tag,attrs):
            values=dict(attrs)
            if tag!='a' or 'iusc' not in values.get('class','').split():return
            try:
                data=json.loads(values.get('m',''));url=data.get('murl','')
                if isinstance(url,str) and url.startswith('https://') and len(self.results)<48:self.results.append((url,str(data.get('t') or '网上表情')[:120]))
            except (ValueError,TypeError):pass
    parser=Parser();parser.feed(page)
    # Image pages also contain photography/recommendation cards; prefer meme results.
    relevant=[r for r in parser.results if re.search(r'(表情|斗图|梗图|meme|sticker)',r[1],re.I)]
    return (relevant or parser.results)[:6]

class GroupMemeCatalog:
    def __init__(self,connect,bot,groups,*,onebot_factory=None,fetch=public_bytes):
        self.connect,self.bot,self.groups,self.onebot_factory,self.fetch=connect,bot,tuple(groups),onebot_factory,fetch
    def _check(self,group):
        if group not in self.groups:raise ValueError('group media denied')
    def observe(self,event,raw):
        self._check(event.group)
        if event.bot!=self.bot:raise ValueError('bot media denied')
        with self.connect() as c:
            for item in image_refs(raw):
                key='m'+hashlib.sha256((event.message_id+':'+item['file']).encode()).hexdigest()[:24]
                c.execute('''INSERT INTO qq_channel.memes(bot_id,group_id,id,source_message_id,source_sender_id,file_key,source,summary)
                    VALUES(%s,%s,%s,%s,%s,%s,'group',%s) ON CONFLICT DO NOTHING''',
                    (self.bot,event.group,key,event.message_id,event.sender,item['file'],item['summary']))
            self._prune(c,event.group)
    def _prune(self,c,group):
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,719620260926))',(self.bot+':'+group,))
        c.execute('''DELETE FROM qq_channel.memes WHERE bot_id=%s AND group_id=%s AND
            (created_at<now()-interval '7 days' OR id IN (SELECT id FROM qq_channel.memes
            WHERE bot_id=%s AND group_id=%s ORDER BY created_at DESC,id DESC OFFSET 32))''',(self.bot,group,self.bot,group))
    def _row(self,group,key):
        self._check(group)
        with self.connect() as c:
            row=c.execute('''SELECT id,source_message_id,source_sender_id,file_key,summary,content,preview,mime,sha256,source
                FROM qq_channel.memes WHERE bot_id=%s AND group_id=%s AND id=%s AND NOT failed AND created_at>now()-interval '7 days' ''',
                (self.bot,group,key)).fetchone()
        if not row:raise ValueError('unavailable group meme')
        return dict(zip(('id','message_id','sender','file','summary','content','preview','mime','sha256','source'),row))
    def _save(self,group,key,data):
        mime,preview=inspect_image(data);sha=hashlib.sha256(data).hexdigest()
        with self.connect() as c:c.execute('''UPDATE qq_channel.memes SET content=%s,preview=%s,mime=%s,sha256=%s
            WHERE bot_id=%s AND group_id=%s AND id=%s''',(data,preview,mime,sha,self.bot,group,key))
    def _load(self,group,key):
        row=self._row(group,key)
        if row['content'] is None:
            if not self.onebot_factory:raise ValueError('media transport unavailable')
            # Separate socket: never block or read from the channel's event loop socket.
            with self.onebot_factory() as client:
                client.on_event=lambda event:None
                packet=client.call('get_msg',{'message_id':int(row['message_id'])})
                if not isinstance(packet,dict) or str(packet.get('group_id'))!=group:raise ValueError('message group mismatch')
                segment=next((s for s in packet.get('message',[]) if s.get('type')=='image' and s.get('data',{}).get('file')==row['file']),None)
                if not segment:raise ValueError('source image missing')
                url=segment['data'].get('url','');host=urlsplit(url).hostname or ''
                if not any(host==h or host.endswith('.'+h) for h in ('qpic.cn','qq.com','multimedia.nt.qq.com.cn')):raise ValueError('QQ media host denied')
                if url.startswith('http://'):url='https://'+url[7:]
            self._save(group,key,self.fetch(url));row=self._row(group,key)
        data=bytes(row['content'])
        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('media integrity mismatch')
        return row
    def prepare(self,group,*,target_message_id=None,reply_to=None):
        self._check(group)
        with self.connect() as c:
            keys=[r[0] for r in c.execute('''SELECT id FROM qq_channel.memes WHERE bot_id=%s AND group_id=%s
                AND NOT failed AND created_at>now()-interval '7 days'
                ORDER BY CASE WHEN source='group' AND source_message_id=%s THEN 0
                    WHEN source='group' AND source_message_id=%s THEN 1 ELSE 2 END,created_at DESC,id DESC LIMIT 3''',
                (self.bot,group,target_message_id,reply_to)).fetchall()]
        labels=[];images=[]
        for key in keys:
            try:row=self._load(group,key)
            except (ValueError,OSError,TimeoutError,OneBotError):
                with self.connect() as c:c.execute('UPDATE qq_channel.memes SET failed=true WHERE bot_id=%s AND group_id=%s AND id=%s',(self.bot,group,key))
                continue
            labels.append({'id':key,'label':row['summary'],'source':row['source'],'source_message_id':row['message_id'],'sender':row['sender'],'image_index':len(images)+1})
            images.append(row['preview'])
        return labels,images
    def search(self,event,query):
        self._check(event.group);phrase=meme_search_query(query)
        query=' '.join(chr(34)+part.replace(chr(34),'')+chr(34) for part in phrase.split())
        page=self.fetch('https://cn.bing.com/images/search?mkt=zh-CN&setlang=zh-hans&ensearch=0&q='+quote_plus(query),timeout=8,max_bytes=1024*1024).decode('utf-8',errors='replace')
        found=False
        for url,title in search_results(page)[:3]:
            try:data=self.fetch(url,timeout=6);mime,preview=inspect_image(data)
            except (ValueError,OSError,TimeoutError):continue
            key='m'+hashlib.sha256(data).hexdigest()[:24]
            with self.connect() as c:
                c.execute('''INSERT INTO qq_channel.memes(bot_id,group_id,id,source_message_id,source_sender_id,file_key,source,summary,content,preview,mime,sha256)
                    VALUES(%s,%s,%s,%s,%s,'','web',%s,%s,%s,%s,%s) ON CONFLICT(bot_id,group_id,id) DO UPDATE SET
                    created_at=now(),failed=false,content=excluded.content,preview=excluded.preview,mime=excluded.mime,
                    sha256=excluded.sha256,summary=excluded.summary,source_message_id=excluded.source_message_id,
                    source_sender_id=excluded.source_sender_id''',
                    (self.bot,event.group,key,event.message_id,event.sender,title,data,preview,mime,hashlib.sha256(data).hexdigest()))
                self._prune(c,event.group)
            found=True
        return self.prepare(event.group) if found else ([],[])
    def for_group(self,group):
        self._check(group);parent=self
        class View:
            def image_bytes(self,key):
                row=parent._row(group,key)
                if row['content'] is None:raise ValueError('meme not cached')
                data=bytes(row['content'])
                if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('media integrity mismatch')
                return data
        return View()
