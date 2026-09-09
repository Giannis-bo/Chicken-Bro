"""Read-only runtime, retained recovery and public artifact reconciliation."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import httpx,psycopg
m=json.loads(Path(sys.argv[1]).read_text());base=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve()
assert str(base).endswith(m['sourceCommit']) and str(web).endswith(m['sourceCommit'])
def inv(root):return {str(p.relative_to(root)):('link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob('*') if (p.is_file() or p.is_symlink()) and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert inv(base)=={k:v for k,v in {**m['baseInventory'],**m['files']}.items() if k not in m['deleted']}
assert inv(Path(m['expectedBackend']))==m['baseInventory']
assert inv(web)==m['webFiles'] and inv(Path(m['expectedWeb']))==m['previousWebFiles']
services={}
for unit in ['chickenbro-api','chickenbro-worker']:
    pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
    assert Path('/proc/'+pid+'/cwd').resolve()==base
    env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
    assert env['WOW_CHAT_DURABLE_ENABLED']=='1' and env['WOW_SIMC_SUPPORTED_SPECS']=='all'
    assert env['WOW_SIMC_COMPILER_REVISION']=='chickenbro-simc-compiler-v5'
    services[unit]={'pid':int(pid),'cwd':str(base),'durable':True,'simcSpecs':'all','compiler':env['WOW_SIMC_COMPILER_REVISION']}
os.environ.update(env)
with httpx.Client(base_url='https://www.chickenbro.cloud',timeout=30) as c:
    for name,sha in m['webFiles'].items():
        r=c.get('/'+name,headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'})
        assert r.status_code==200 and hashlib.sha256(r.content).hexdigest()==sha,'public artifact mismatch: '+name
    readiness=c.get('/api/v2/health/readiness').json();assert readiness['status']=='ready'
with psycopg.connect(env['WOW_DATABASE_URL']) as c:
    providers=dict(c.execute('SELECT provider,count(*) FROM identity.user_identities GROUP BY provider').fetchall())
    assert providers.get('wechat_mini',0)==0
    triggers=dict(c.execute("SELECT tgname,tgenabled FROM pg_trigger WHERE tgname IN ('trg_simulation_results_immutable','trg_simulation_results_truncate')").fetchall())
    assert triggers == {'trg_simulation_results_immutable':'O','trg_simulation_results_truncate':'O'}
    invalid=c.execute('SELECT count(*) FROM pg_constraint WHERE NOT convalidated').fetchone()[0];assert invalid==0
print(json.dumps({'sourceCommit':m['sourceCommit'],'backendInventoryMatched':True,'publicWebFilesMatched':len(m['webFiles']),'oldBackendAndWebUnchanged':True,'services':services,'readiness':readiness,'providerCounts':providers,'resultProtectionTriggers':triggers,'invalidConstraints':invalid},indent=2))
