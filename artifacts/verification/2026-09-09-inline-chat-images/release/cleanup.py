import os,sys,json,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
from uuid import UUID
mode=sys.argv[1];assert mode in {'candidate','production'}
unit='chickenbro-inline-candidate' if mode=='candidate' else 'chickenbro-api'
pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v);os.environ.update(env);sys.path.insert(0,env['PYTHONPATH'])
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.platform.config import AppSettings
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.repository import PostgresIdentityRepository
import httpx
p=Path('/var/lib/chickenbro/inline-'+mode+'-private.json');a=json.loads(p.read_text());factory=PostgresConnectionFactory(AppSettings.from_env(env));repo=PostgresChatRepository(factory.connection)
with factory.connection() as conn:
 with conn.cursor() as cur:
  cur.execute("SELECT count(*) AS n FROM chat.agent_runs WHERE user_id=%s AND status='streaming'",(UUID(a['owner']),));assert cur.fetchone()[0]==0
  cur.execute('SELECT id FROM chat.conversations WHERE user_id=%s',(UUID(a['owner']),));convs=[r[0] for r in cur.fetchall()]
with httpx.Client(trust_env=False) as client:
 for cid in convs:
  r=client.get('http://127.0.0.1:'+('8793' if mode=='candidate' else '8790')+'/api/v2/chat/conversations/'+str(cid),headers={'Host':'www.chickenbro.cloud','Cookie':'__Host-chickenbro-session='+a['otherToken']});assert r.status_code==404
for cid in convs:repo.archive_conversation(UUID(a['owner']),cid)
identity=PostgresIdentityRepository(factory.connection)
for key in ['token','otherToken']:identity.revoke_auth_session(token_hash=hashlib.sha256(a[key].encode()).hexdigest(),kind='web_cookie',now=datetime.now(timezone.utc))
with factory.connection() as conn:
 with conn.cursor() as cur:
  cur.execute("UPDATE identity.users SET status='disabled',updated_at=now() WHERE id IN (%s,%s)",(UUID(a['owner']),UUID(a['other'])));assert cur.rowcount==2
p.unlink();print(json.dumps({'mode':mode,'archivedSyntheticConversations':len(convs),'allActualConversationsOwnerIsolated':True,'revokedSessions':2,'disabledSyntheticUsers':2,'activeRuns':0,'privateFileRemoved':True}))
