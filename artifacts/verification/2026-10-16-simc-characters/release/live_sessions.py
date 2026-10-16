"""Short-lived sessions for existing dedicated smoke owners; never print bearer tokens."""
import json
import os
from pathlib import Path
import sys
from datetime import datetime,timedelta,timezone

from deploy import Release,require
os.umask(0o077)
packet=Path(__file__).resolve().parent
release=Release(packet/'manifest.json')
release.runtime()
sys.path.insert(0,str(release.target))
from server.app.identity.domain import digest,new_opaque_token
from server.app.identity.repository import PostgresIdentityRepository
from server.app.platform.config import AppSettings
identity=PostgresIdentityRepository(release.connect)
settings=AppSettings.from_env(release.envs['chickenbro-api'])
fixture=packet/'live-sessions.json'
now=datetime.now(timezone.utc)
if sys.argv[1]=='create':
 require(not fixture.exists(),'existing live fixture must be inspected or revoked first')
 with release.connect() as c:
  owners=c.execute("SELECT DISTINCT user_id FROM identity.user_identities WHERE provider='qq' AND provider_subject LIKE 'simc-all-smoke-%' ORDER BY user_id LIMIT 2").fetchall()
  require(len(owners)==2,'two pre-existing smoke identities required')
  for (owner,) in owners:
   current=c.execute('SELECT preferences FROM simc.character_preferences WHERE user_id=%s',(owner,)).fetchone()
   require(current is None or current[0]=={'items':[],'selectedId':None},'smoke owner has existing bindings')
 sessions={}
 for key,(owner,) in zip(('A','B'),owners):
  token,csrf=new_opaque_token(),new_opaque_token()
  identity.issue_auth_session(token_hash=digest(token),user_id=owner,kind='web_cookie',expires_at=now+timedelta(minutes=40))
  sessions[key]={'token':token,'csrf':csrf,'owner':str(owner)}
 fixture.write_text(json.dumps({'origin':settings.web_origin,'cookie':settings.web_cookie_name,'csrfCookie':settings.web_csrf_cookie_name,'sessions':sessions}))
 fixture.chmod(0o600)
 print(json.dumps({'sessionsIssued':2,'existingDedicatedOwnersOnly':True,'expiresMinutes':40}))
elif sys.argv[1]=='revoke':
 data=json.loads(fixture.read_text())
 for session in data['sessions'].values():identity.revoke_auth_session(token_hash=digest(session['token']),kind='web_cookie',now=now)
 print(json.dumps({'sessionsRevoked':2}))
else:raise ValueError('create or revoke required')
