"""Persistent import state; each owner action and completion is a transaction."""
import json
from types import SimpleNamespace
from uuid import UUID, uuid5, NAMESPACE_URL
from server.app.poe2.application import Poe2Error, validate_result

ACTIVE=('queued','fetching','mapping','validating')

def issue(code):
    return [{'code':code,'path':'','severity':'blocking','message':code}]

class PostgresImportRepository:
    def __init__(self,connection_factory):self._connect=connection_factory

    def _row(self,cur):
        r=cur.fetchone()
        if r is None:return None
        # Explicit projection works with tuple and dict row factories.
        data=r['data'] if isinstance(r,dict) else r[0]
        if isinstance(data,str):data=json.loads(data)
        from datetime import datetime
        for k in ('id','user_id','build_id','baseline_job_id'):
            if data.get(k):data[k]=UUID(data[k])
        for k in ('updated_at','created_at','expires_at','lease_expires_at'):
            if data.get(k):data[k]=datetime.fromisoformat(data[k])
        return SimpleNamespace(**data)

    def _get(self,c,user,id,lock=False):
        c.execute('SELECT row_to_json(t) AS data FROM poe2.character_imports t WHERE user_id=%s AND id=%s'+(' FOR UPDATE' if lock else ''),(user,id))
        row=self._row(c)
        if row is None:raise Poe2Error('POE2_IMPORT_NOT_FOUND',404)
        return row

    def _owner_lock(self,c,user):
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(str(user),))

    def _existing(self,c,user,key,hash):
        c.execute('SELECT request_hash,import_id FROM poe2.character_import_actions WHERE user_id=%s AND action_key=%s',(user,key))
        r=c.fetchone()
        if r:
            h,i=(r['request_hash'],r['import_id']) if isinstance(r,dict) else r
            if h!=hash:raise Poe2Error('POE2_IDEMPOTENCY_CONFLICT',409)
            return self._get(c,user,i)

    def _active(self,c,user,id=None):
        c.execute("SELECT id FROM poe2.character_imports WHERE user_id=%s AND status IN ('queued','fetching','mapping','validating') AND (%s::uuid IS NULL OR id<>%s::uuid)",(user,id,id))
        if c.fetchone():raise Poe2Error('POE2_IMPORT_ACTIVE',409)

    def _log(self,c,user,key,hash,id):
        c.execute('INSERT INTO poe2.character_import_actions VALUES(%s,%s,%s,%s)',(user,key,hash,id))

    def create(self,user,key,data,hash):
        with self._connect() as conn,conn.cursor() as c:
            self._owner_lock(c,user)
            old=self._existing(c,user,key,hash)
            if old:return old
            if data['status'] in ACTIVE:self._active(c,user)
            c.execute('''INSERT INTO poe2.character_imports(id,user_id,provider,canonical_url,status,preview,next_action)
                VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)''',(data['id'],user,data['provider'],data['canonical_url'],data['status'],json.dumps(data['preview']) if data.get('preview') is not None else None,data.get('next_action')))
            self._log(c,user,key,hash,data['id'])
            return self._get(c,user,data['id'])

    def read(self,user,id):
        from datetime import datetime,timezone
        with self._connect() as conn,conn.cursor() as c:
            row=self._get(c,user,id)
            if row.status!='ready' and row.expires_at<=datetime.now(timezone.utc):row.source_xml=None;row.snapshot=None
            return row

    def action(self,user,id,key,hash,action,xml=None):
        with self._connect() as conn,conn.cursor() as c:
            self._owner_lock(c,user);row=self._get(c,user,id,True)
            old=self._existing(c,user,key,hash)
            if old:return old
            if row.status not in ('needs_input','blocked','failed'):
                raise Poe2Error('POE2_IMPORT_STATE_CONFLICT',409)
            self._active(c,user,id)
            if action=='retry':
                from datetime import datetime,timezone
                if row.expires_at<=datetime.now(timezone.utc):raise Poe2Error('POE2_IMPORT_EXPIRED',409)
                if row.provider=='ninja' and not row.source_xml:raise Poe2Error('POE2_IMPORT_SOURCE_REQUIRED',409)
            c.execute('''UPDATE poe2.character_imports SET status='queued',stage='queued',attempt=attempt+1,
                source_xml=CASE WHEN %s='source' THEN %s ELSE source_xml END,
                snapshot=CASE WHEN %s='source' AND expires_at<=now() THEN NULL ELSE snapshot END,
                source_relation=CASE WHEN %s='source' THEN 'user_supplied' ELSE source_relation END,
                preview=CASE WHEN %s='source' THEN COALESCE(preview,'{}'::jsonb)||'{"sourceRelation":"user_supplied"}'::jsonb ELSE preview END,
                expires_at=CASE WHEN %s='source' THEN now()+interval '7 days' ELSE expires_at END,
                infrastructure_failures=0,issues='[]',next_action=NULL,lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                WHERE id=%s''',(action,xml,action,action,action,action,id))
            self._log(c,user,key,hash,id)
            return self._get(c,user,id)

    def cancel(self,user,id):
        with self._connect() as conn,conn.cursor() as c:
            row=self._get(c,user,id,True)
            if row.status=='ready':raise Poe2Error('POE2_IMPORT_STATE_CONFLICT',409)
            if row.status!='cancelled':
                c.execute("UPDATE poe2.character_imports SET status='cancelled',stage='cancelled',attempt=attempt+1,source_xml=NULL,snapshot=NULL,lease_owner=NULL,lease_expires_at=NULL,next_action=NULL,updated_at=now() WHERE id=%s",(id,))
            return self._get(c,user,id)

    def expire(self):
        with self._connect() as conn,conn.cursor() as c:
            c.execute('''UPDATE poe2.character_imports SET source_xml=NULL,snapshot=NULL,
                status=CASE WHEN status IN ('queued','fetching','mapping','validating') THEN 'failed' ELSE status END,
                issues=CASE WHEN status IN ('queued','fetching','mapping','validating') THEN %s::jsonb ELSE issues END,
                lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                WHERE status<>'ready' AND expires_at<=now() AND (source_xml IS NOT NULL OR snapshot IS NOT NULL OR status IN ('queued','fetching','mapping','validating'))''',(json.dumps(issue('POE2_IMPORT_EXPIRED')),))

    def claim(self,lease_owner,lease_seconds=600):
        self.expire()
        with self._connect() as conn,conn.cursor() as c:
            c.execute("""UPDATE poe2.character_imports SET status='failed',issues=%s::jsonb,lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                WHERE status IN ('fetching','mapping','validating') AND lease_expires_at<=now() AND infrastructure_failures>=2""",(json.dumps(issue('POE2_IMPORT_ATTEMPTS_EXHAUSTED')),))
            c.execute("""WITH chosen AS (SELECT id FROM poe2.character_imports WHERE expires_at>now() AND
                (status='queued' OR (status IN ('fetching','mapping','validating') AND lease_expires_at<=now()))
                ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1)
                UPDATE poe2.character_imports t SET infrastructure_failures=infrastructure_failures+CASE WHEN t.status='queued' THEN 0 ELSE 1 END,
                status='fetching',stage='fetching',attempt=attempt+1,lease_owner=%s,lease_expires_at=now()+%s*interval '1 second',updated_at=now()
                FROM chosen WHERE t.id=chosen.id RETURNING row_to_json(t) AS data""",(lease_owner,lease_seconds))
            return self._row(c)

    def complete(self,id,lease_owner,attempt,data,*,xml=None,result=None):
        with self._connect() as conn,conn.cursor() as c:
            c.execute("""SELECT row_to_json(t) AS data FROM poe2.character_imports t WHERE id=%s AND lease_owner=%s AND attempt=%s
                AND status IN ('fetching','mapping','validating') AND lease_expires_at>now() AND expires_at>now() FOR UPDATE""",(id,lease_owner,attempt))
            row=self._row(c)
            if row is None:return False
            status=data['status'];build_id=job_id=None
            if status=='ready':
                if xml is None or result is None:raise Poe2Error('POE2_IMPORT_READY_RESULT_REQUIRED')
                validate_result(result)
                import hashlib
                if result['inputSha256']!=hashlib.sha256(xml.encode()).hexdigest():raise Poe2Error('POE2_RESULT_INPUT_MISMATCH')
                build_id=uuid5(NAMESPACE_URL,f'poe2-import:{id}:build');job_id=uuid5(NAMESPACE_URL,f'poe2-import:{id}:baseline')
                c.execute('''INSERT INTO poe2.builds(id,user_id,title,source_xml,game_version,league,input_sha256,engine_version,export_code,summary_json)
                    VALUES(%s,%s,%s,%s,%s,'',%s,%s,%s,%s::jsonb)''',(build_id,row.user_id,'Imported character',xml,str(result.get('summary',{}).get('treeVersion','unknown')),result['inputSha256'],result['engineVersion'],result['exportCode'],json.dumps(result.get('summary',{}))))
                c.execute('''INSERT INTO poe2.jobs(id,user_id,build_id,idempotency_key,request_hash,changes_json,status,result_json,attempt_count)
                    VALUES(%s,%s,%s,%s,%s,'{}','succeeded',%s::jsonb,1)''',(job_id,row.user_id,build_id,f'character-import:{id}',result['inputSha256'],json.dumps(result)))
            elif status not in ('blocked','needs_input','failed','queued'):raise ValueError('POE2_IMPORT_STATE_INVALID')
            if status=='queued':
                if row.infrastructure_failures>=2:status='failed'
                c.execute('UPDATE poe2.character_imports SET infrastructure_failures=infrastructure_failures+1 WHERE id=%s',(id,))
            c.execute('''UPDATE poe2.character_imports SET status=%s,stage=%s,issues=%s::jsonb,next_action=%s,
                build_id=%s,baseline_job_id=%s,lease_owner=NULL,lease_expires_at=NULL,updated_at=now(),
                source_xml=CASE WHEN %s='ready' THEN NULL ELSE source_xml END WHERE id=%s''',
                (status,status,json.dumps(data.get('issues',[])),data.get('next_action'),build_id,job_id,status,id))
            return True

    def stage(self,id,lease_owner,attempt,status,*,snapshot=None,preview=None):
        if status not in ('mapping','validating'):raise ValueError('POE2_IMPORT_STAGE_INVALID')
        with self._connect() as conn,conn.cursor() as c:
            c.execute("""UPDATE poe2.character_imports SET status=%s,stage=%s,updated_at=now(),
                snapshot=COALESCE(%s::jsonb,snapshot),preview=COALESCE(%s::jsonb,preview),
                source_relation=CASE WHEN %s THEN 'collected' ELSE source_relation END
                WHERE id=%s AND lease_owner=%s AND attempt=%s AND status IN ('fetching','mapping','validating')
                AND lease_expires_at>now() AND expires_at>now() RETURNING id""",
                (status,status,json.dumps(snapshot) if snapshot is not None else None,
                 json.dumps(preview) if preview is not None else None,snapshot is not None,id,lease_owner,attempt))
            return c.fetchone() is not None
