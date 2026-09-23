"""Only manifest-pinned local images may become OneBot image segments."""
import base64
import hashlib
import json
from pathlib import Path
import re
from server.app.channels.qq.policy import reply_segments

class StickerCatalog:
    def __init__(self,root,manifest=None):
        self.root=Path(root).resolve()
        data=manifest if isinstance(manifest,dict) else json.loads(Path(manifest or self.root/'manifest.json').read_text())
        self.items={}
        for item in data['stickers']:
            key=item['id']
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}',key) or key in self.items:raise ValueError('invalid sticker catalog')
            self.items[key]=dict(item)
        if sum(i['size'] for i in self.items.values())>12*1024**2:raise ValueError('catalog too large')
    def labels(self):return [{'id':k,'label':v['label']} for k,v in self.items.items()]
    def resolve(self,sticker_id):
        item=self.items.get(sticker_id)
        if not item:raise ValueError('unknown sticker')
        path=(self.root/item['file']).resolve()
        if path.parent!=self.root or item['mime']!='image/png' or not 0<item['size']<=2*1024**2:raise ValueError('invalid sticker file')
        if path.stat().st_size!=item['size']:raise ValueError('sticker size mismatch')
        data=path.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('sticker integrity mismatch')
        return path

def render_reply(message_id,draft,catalog):
    parts=reply_segments(message_id,draft.text,quote=draft.quote)
    if draft.sticker_id:
        data=catalog.image_bytes(draft.sticker_id) if hasattr(catalog,'image_bytes') else catalog.resolve(draft.sticker_id).read_bytes()
        parts.append({'type':'image','data':{'file':'base64://'+base64.b64encode(data).decode(),'sub_type':1}})
    return parts
