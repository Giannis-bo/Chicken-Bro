"""Exact owner retirement. Private backup and independent restore required before apply.
Run as postgres on the verified cloud host; emits counts/hashes, never row payloads.
"""
import argparse, hashlib, json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg import sql

DATABASE='chickenbro_prod'
TABLES=['identity.users','identity.user_identities','identity.auth_sessions','identity.web_login_sessions','identity.qq_login_attempts','chat.conversations','chat.messages','chat.agent_runs','chat.images','chat.executions','chat.tool_results','simc.source_snapshots','simc.simulation_jobs','simc.simulation_attempts','simc.simulation_results','ops.job_queue','ops.audit_events','ops.usage_counters','ops.schema_migrations']
ORDER=['chat.tool_results','chat.executions','ops.job_queue','ops.audit_events','ops.usage_counters','chat.agent_runs','simc.simulation_results','simc.simulation_attempts','simc.simulation_jobs','simc.source_snapshots','chat.images','chat.messages','chat.conversations','identity.auth_sessions','identity.web_login_sessions','identity.user_identities','identity.users']

def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def ident(table): return sql.Identifier(*table.split('.'))
def save(path,data):
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n');path.chmod(0o600)
def read_all(conn):
    actual={f'{a}.{b}' for a,b in conn.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")}
    assert actual==set(TABLES), 'database table inventory changed'
    external=conn.execute("SELECT conrelid::regclass::text FROM pg_constraint WHERE contype='f' AND confrelid IN (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','chat','simc','ops')) AND conrelid NOT IN (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','chat','simc','ops'))").fetchall()
    assert not external, 'unexpected external foreign keys'
    rows={}; keys={}
    for t in TABLES:
        rows[t]=[r[0] for r in conn.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t').format(ident(t)))]
        keys[t]=[r[0] for r in conn.execute("SELECT a.attname FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum WHERE i.indrelid=%s::regclass AND i.indisprimary ORDER BY k.ord",(t,))]
        assert keys[t], 'table without primary key'
    return rows,keys

UUID_RE=re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',re.I)
def references(value,ids):
    if isinstance(value,str): return bool(ids.intersection(x.lower() for x in UUID_RE.findall(value)))
    if isinstance(value,list): return any(references(x,ids) for x in value)
    if isinstance(value,dict): return any(references(x,ids) for x in value.values())
    return False

def partition(rows,owners):
    owners=set(owners)
    providers={u:{i['provider'] for i in rows['identity.user_identities'] if i['user_id']==u} for u in owners}
    assert all(v=={'wechat_mini'} for v in providers.values()), 'owner provider changed or missing'
    assert owners<={r['id'] for r in rows['identity.users']}, 'approved owner missing'
    selected={t:[] for t in TABLES}
    for t in TABLES:
        selected[t]=[r for r in rows[t] if (r.get('id') if t=='identity.users' else r.get('user_id')) in owners]
    run_ids={r['run_id'] for r in selected['chat.executions']}
    selected['chat.tool_results']=[r for r in rows['chat.tool_results'] if r['run_id'] in run_ids]
    target_ids=owners | {r['id'] for values in selected.values() for r in values if isinstance(r.get('id'),str)}
    # Queue payloads reference snapshotId, while aggregate_id references a job.
    selected['ops.job_queue']=[r for r in rows['ops.job_queue'] if references(r,target_ids)]
    for r in rows['ops.audit_events']:
        if r not in selected['ops.audit_events'] and references(r,target_ids):
            assert r.get('user_id') is None, 'retained owner audit references a target'
            selected['ops.audit_events'].append(r)
    target_ids |= {r['id'] for values in selected.values() for r in values if isinstance(r.get('id'),str)}
    remaining={t:[r for r in rows[t] if r not in selected[t]] for t in TABLES}
    for t,values in remaining.items():
        assert not any(references(r,target_ids) for r in values), f'unresolved retained references in {t}'
    for t in ['chat.agent_runs','simc.simulation_jobs','ops.job_queue']:
        assert all(r['status'] in ('succeeded','failed') for r in selected[t]), f'active target in {t}'
    now=datetime.now(timezone.utc)
    assert all(not r.get('lease_expires_at') or datetime.fromisoformat(r['lease_expires_at'])<=now for r in selected['chat.executions']), 'active execution lease'
    return selected,remaining

def fingerprints(rows): return {t:{'count':len(v),'sha256':digest(sorted(digest(r) for r in v))} for t,v in rows.items()}
def trigger_identity(conn):
    return [list(r) for r in conn.execute("SELECT tgrelid::regclass::text,tgname,tgenabled,pg_get_triggerdef(oid),md5(pg_get_functiondef(tgfoid)) FROM pg_trigger WHERE NOT tgisinternal ORDER BY 1,2")]

def exact_keys(selected,keys):
    return {t:sorted([{k:r[k] for k in keys[t]} for r in selected[t]],key=lambda r:json.dumps(r,sort_keys=True)) for t in TABLES}

def delete_exact(conn,selected,keys):
    triggers=trigger_identity(conn)
    expected=[r for r in triggers if r[0:2]==['simc.simulation_results','trg_simulation_results_immutable']]
    assert len(expected)==1 and expected[0][2]=='O', 'immutable result guard drift'

    result={}
    for t in ORDER:
        pk=keys[t]; count=0
        if t=='simc.simulation_results' and selected[t]:
            conn.execute('ALTER TABLE simc.simulation_results DISABLE TRIGGER trg_simulation_results_immutable')
        query=sql.SQL('DELETE FROM {} WHERE {}').format(ident(t),sql.SQL(' AND ').join(sql.SQL('{} = %s').format(sql.Identifier(k)) for k in pk))
        for row in selected[t]:
            n=conn.execute(query,tuple(row[k] for k in pk)).rowcount
            assert n==1, f'exact row missing in {t}'
            count+=n
        if t=='simc.simulation_results' and selected[t]:
            conn.execute('ALTER TABLE simc.simulation_results ENABLE TRIGGER trg_simulation_results_immutable')
        result[t]=count
    assert trigger_identity(conn)==triggers, 'trigger definition or enabled state changed'
    return result

def prepare(root,scope):
    assert not root.exists(), 'backup destination must be new'
    root.mkdir(mode=0o700)
    save(root/'scope.json',scope)
    with psycopg.connect(dbname=DATABASE) as conn:
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        rows,keys=read_all(conn); selected,remaining=partition(rows,scope['users'])
        expected={r['id'] for r in rows['identity.users'] if {i['provider'] for i in rows['identity.user_identities'] if i['user_id']==r['id']}=={'wechat_mini'}}
        assert expected==set(scope['users']) and len(expected)==186, 'approved scope has drifted'
        snapshot=conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
        subprocess.run(['pg_dump','-Fc','--no-owner','--snapshot='+snapshot,'-f',str(root/'before.dump'),DATABASE],check=True,capture_output=True)
        backup={'snapshot':fingerprints(rows),'targets':fingerprints(selected),'keys':keys,'manifest':exact_keys(selected,keys),'triggers':trigger_identity(conn)}
        save(root/'manifest.json',backup)
    restore='cb_mini_restore_'+root.name.replace('-','_')
    subprocess.run(['createdb','--template=template0',restore],check=True,capture_output=True)
    with psycopg.connect(dbname='postgres',autocommit=True) as conn:
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(restore)))
    subprocess.run(['pg_restore','--exit-on-error','--no-owner','--dbname',restore,str(root/'before.dump')],check=True,capture_output=True)
    with psycopg.connect(dbname=restore) as conn:
        rows,keys=read_all(conn)
        assert fingerprints(rows)==backup['snapshot'], 'independent full restore mismatch'
        assert trigger_identity(conn)==backup['triggers'], 'restored trigger mismatch'
        selected,remaining=partition(rows,scope['users'])
        assert fingerprints(selected)==backup['targets'], 'restored target mismatch'
        deleted=delete_exact(conn,selected,keys)
        after,_=read_all(conn)
        assert fingerprints(after)==fingerprints(remaining), 'rehearsal altered retained rows'
        conn.rollback() # Keep the restored recovery database intact after proving deletion ordering.
    receipt={'backupPath':str(root/'before.dump'),'backupSha256':hashlib.sha256((root/'before.dump').read_bytes()).hexdigest(),'restoreDatabase':restore,'restoreVerified':True,'rehearsalVerified':True,'targetCounts':{t:v['count'] for t,v in backup['targets'].items()},'scopeSha256':digest(scope),'dataApplied':False}
    save(root/'recovery.json',receipt)
    print(json.dumps(receipt))

def apply(root,scope):
    recovery=json.loads((root/'recovery.json').read_text());manifest=json.loads((root/'manifest.json').read_text())
    assert recovery['scopeSha256']==digest(scope) and recovery['restoreVerified'] and recovery['rehearsalVerified']
    assert hashlib.sha256((root/'before.dump').read_bytes()).hexdigest()==recovery['backupSha256']
    assert not (root/'applied.json').exists(), 'already applied'
    with psycopg.connect(dbname=recovery['restoreDatabase']) as restore:
        rows,_=read_all(restore)
        assert fingerprints(rows)==manifest['snapshot'], 'recovery database changed'
    with psycopg.connect(dbname=DATABASE) as conn:
        conn.execute("SET LOCAL lock_timeout='5s'")
        conn.execute("SET LOCAL statement_timeout='60s'")
        # Lock the complete known data surface only during final comparison/delete.
        conn.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(sql.SQL(',').join(ident(t) for t in sorted(TABLES))))
        rows,keys=read_all(conn);selected,remaining=partition(rows,scope['users'])
        assert keys==manifest['keys'] and fingerprints(selected)==manifest['targets'], 'target data changed since verified backup'
        assert exact_keys(selected,keys)==manifest['manifest'], 'exact manifest drift'
        assert trigger_identity(conn)==manifest['triggers'], 'production triggers drifted'
        before=fingerprints(remaining)
        deleted=delete_exact(conn,selected,keys)
        after,_=read_all(conn)
        assert fingerprints(after)==before, 'retained records changed during cleanup'
        assert not (set(scope['users']) & {r['id'] for r in after['identity.users']}), 'target users remain'
        result={'dataApplied':True,'deleted':deleted,'retained':before,'retainedRowsMatched':True,'backupSha256':recovery['backupSha256'],'scopeSha256':digest(scope),'appliedAt':datetime.now(timezone.utc).isoformat()}
        conn.commit()
    save(root/'applied.json',result)
    print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','apply']);parser.add_argument('root');parser.add_argument('scope');args=parser.parse_args()
    os.umask(0o077)
    root=Path(args.root)
    assert str(root.parent)=='/var/backups/chickenbro-mini-retirement'
    scope=json.loads(Path(args.scope).read_text())
    (prepare if args.mode=='prepare' else apply)(root,scope)
