import hashlib
import json
from uuid import uuid4
from server.app.poe2.application import Poe2Error
from server.app.poe2.engine import decode_build
from .domain import ImportPacket, ImportStatus, SourceProvider, Issue, IssueSeverity
from .urls import parse_character_url
from .sources.ninja import handoff


def request_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def packet(row):
    return ImportPacket(row.id,ImportStatus(row.status),SourceProvider(row.provider),row.preview,
        tuple(Issue(x['code'],x.get('path',''),IssueSeverity(x['severity']),x['message']) for x in row.issues),
        row.next_action,row.build_id,row.baseline_job_id,row.attempt,row.updated_at)


def packet_json(p):
    return {'id':str(p.id),'status':p.status.value,'provider':p.provider.value,
        'preview':dict(p.preview) if p.preview is not None else None,
        'issues':[{'code':i.code,'path':i.path,'severity':i.severity.value,'message':i.message} for i in p.issues],
        'nextAction':p.next_action,'buildId':str(p.build_id) if p.build_id else None,
        'baselineJobId':str(p.baseline_job_id) if p.baseline_job_id else None,
        'attempt':p.attempt,'updatedAt':p.updated_at.isoformat()}


class ImportApplication:
    def __init__(self,repository):self.repository=repository

    def _key(self,key):
        if not isinstance(key,str) or not 1<=len(key)<=128:raise Poe2Error('POE2_IDEMPOTENCY_KEY_INVALID')

    def create(self,principal,provider,url,key):
        self._key(key)
        ref=parse_character_url(url,provider)
        data=handoff(ref) if ref.provider is SourceProvider.NINJA else {'status':'queued','issues':[]}
        data.update(id=uuid4(),provider=ref.provider.value,canonical_url=ref.canonical_url)
        return packet(self.repository.create(principal.user_id,key,data,request_hash(['create',provider,ref.canonical_url])))

    def read(self,principal,id):
        row=self.repository.read(principal.user_id,id)
        if row is None:raise Poe2Error('POE2_IMPORT_NOT_FOUND',404)
        return packet(row)

    def supply_source(self,principal,id,source,key):
        self.read(principal,id);self._key(key)
        xml=decode_build(source)
        return packet(self.repository.action(principal.user_id,id,key,request_hash(['source',str(id),xml]),'source',xml))

    def retry(self,principal,id,key):
        self.read(principal,id);self._key(key)
        return packet(self.repository.action(principal.user_id,id,key,request_hash(['retry',str(id)]),'retry'))

    def cancel(self,principal,id):
        return packet(self.repository.cancel(principal.user_id,id))
