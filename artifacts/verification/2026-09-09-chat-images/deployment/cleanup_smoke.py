import os,sys,json,subprocess,hashlib
from pathlib import Path
from uuid import UUID
import psycopg
mode=sys.argv[1];assert mode in {'candidate','production'}
unit='chickenbro-images-candidate' if mode=='candidate' else 'chickenbro-api'
pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v);os.environ.update(env);sys.path.insert(0,env['PYTHONPATH'])
p=Path('/var/lib/chickenbro/images-release-'+mode+'-private.json');a=json.loads(p.read_text())
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
factory=PostgresConnectionFactory(AppSettings.from_env(env))
PostgresChatRepository(factory.connection).archive_conversation(UUID(a['owner']),UUID(a['conversationId']))
with factory.connection() as c:
 for key in ['token','otherToken']:
  c.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE token_hash=%s',(hashlib.sha256(a[key].encode()).hexdigest(),))
 c.execute("UPDATE identity.users SET status='disabled',updated_at=now() WHERE id IN (%s,%s)",(UUID(a['owner']),UUID(a['other'])))
 assert c.execute("SELECT count(*) FROM chat.agent_runs WHERE user_id=%s AND status='streaming'",(UUID(a['owner']),)).fetchone()[0]==0
 assert c.execute('SELECT expires_at IS NOT NULL FROM chat.images WHERE id=%s',(UUID(a['imageId']),)).fetchone()[0]
p.unlink()
print(json.dumps({'mode':mode,'testConversationArchived':True,'testSessionsRevoked':2,'testUsersDisabled':2,'imageExpiryScheduled':True,'privateTokenFileRemoved':True}))
