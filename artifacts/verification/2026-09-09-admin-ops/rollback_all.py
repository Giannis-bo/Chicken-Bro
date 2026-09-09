"""Restore this exact admin release only; refuse any later foreign release."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
m_path=Path(sys.argv[1]);m=json.loads(m_path.read_text());w=json.loads(Path(sys.argv[2]).read_text())
backend=Path('/opt/chickenbro');web=Path('/var/www/chickenbro-web/current')
assert backend.resolve()==Path('/opt/chickenbro-releases/admin-ops-'+m['sourceCommit'])
assert web.resolve()==Path('/var/www/chickenbro-web/releases/admin-ops-web-'+w['sourceCommit'])
intermediate=Path(w['expectedWeb'])
assert intermediate==Path('/var/www/chickenbro-web/releases/admin-ops-'+m['sourceCommit'])
for name,sha in m['webFiles'].items():assert hashlib.sha256((intermediate/name).read_bytes()).hexdigest()==sha
# The intermediate Web has the same APIs/authorization, only older control styles.
temporary=web.with_name('.admin-rollback-'+uuid4().hex);temporary.symlink_to(intermediate);os.replace(temporary,web)
subprocess.run([sys.executable,str(m_path.parent/'deploy.py'),str(m_path),'rollback'],check=True)
