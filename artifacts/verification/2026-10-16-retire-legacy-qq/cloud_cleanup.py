"""Bounded, recoverable retirement of the personal QQ transport only.

Run as root on the authorized host. Recovery contents remain root private.
No provider credentials, DSNs, messages, or container environment are printed.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

ROOT = Path('/var/lib/chickenbro-retirement/legacy-qq-20261016')
UNITS = ['chickenbro-qq-channel', 'chickenbro-qq-worker',
         'chickenbro-qq-channel-candidate', 'chickenbro-qq-worker-candidate']
KEEP_UNITS = ['chickenbro-api', 'chickenbro-worker', 'chickenbro-qq-official',
              'chickenbro-qq-official-worker']
CONTAINERS = ['chickenbro-napcat', 'chickenbro-napcat-before-autologin-20260923']
IMAGE = 'sha256:2cc70b45244ae3fabc657ffc3aaa4de8fb893518171e519659ab83d80e6d36b5'
DATABASES = [
    'chickenbro_qq_activation_restore_20260923_084238',
    'chickenbro_qq_activation_restore_20260923_085420',
    'chickenbro_qq_badcase_candidate_20260924', 'chickenbro_qq_badcase_test_20260924',
    'chickenbro_qq_channel', 'chickenbro_qq_channel_candidate_20260923',
    'chickenbro_qq_channel_restore_20260923', 'chickenbro_qq_channel_tests_20260923',
    'chickenbro_qq_companion_candidate_20260923', 'chickenbro_qq_companion_tests_20260923',
    'chickenbro_qq_recovery_20260923_071131', 'chickenbro_qq_recovery_20260923_074034',
    'chickenbro_qq_recovery_20260923_074951',
]
PATHS = [
    '/etc/chickenbro-qq-channel', '/opt/chickenbro-qq-channel',
    '/opt/chickenbro-qq-current', '/opt/chickenbro-qq-releases',
    '/opt/chickenbro-candidates/qq-channel-20260923',
    '/opt/chickenbro-candidates/qq-companion-20260923',
    '/opt/chickenbro-candidates/qq-badcase-20260924',
    '/var/lib/chickenbro-qq-channel', '/var/lib/chickenbro/qq-channel',
    '/var/lib/chickenbro/qq-channel-candidate', '/var/lib/chickenbro/qq-companion-candidate',
    '/var/lib/chickenbro/qq-channel-recovery',
    '/var/lib/chickenbro/qq-companion-quote-release.json',
    '/var/lib/chickenbro/qq-companion-activation-release.json',
    '/var/lib/chickenbro/qq-badcase-20260924-release.json',
    '/var/lib/chickenbro/qq-companion-social-readback.json',
    '/var/lib/chickenbro/qq-companion-persona-release.json',
    '/var/lib/chickenbro/qq-companion-release.json',
    '/var/lib/chickenbro/qq-companion-social-release.json',
    '/var/lib/chickenbro/qq-companion-memes-release.json',
    '/var/backups/chickenbro/qq-activation-20260923T084238Z',
    '/var/backups/chickenbro/qq-companion-20260923T071131Z',
    '/var/backups/chickenbro/qq-persona-20260923T092109Z',
    '/var/backups/chickenbro/qq-companion-20260923T074951Z',
    '/var/backups/chickenbro/qq-activation-20260923T085420Z',
    '/var/backups/chickenbro/qq-badcase-20260924T015818Z',
    '/var/backups/chickenbro/qq-group-699343722-20260923T091631Z',
    '/var/backups/chickenbro/qq-companion-20260923T074034Z',
] + ['/etc/systemd/system/' + u + '.service' for u in UNITS]


def run(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, **kw)


def output(args):
    return run(args, text=True).stdout.strip()


def save(name, value):
    p = ROOT / name
    tmp = p.with_name(p.name + '.tmp')
    with tmp.open('w') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        f.flush()
        os.fsync(f.fileno())
    tmp.chmod(0o600)
    tmp.replace(p)
    fd = os.open(ROOT, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def sql(db, query):
    return output(['sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
                   '-d', db, '-Atc', query])


def table_fingerprints(db):
    rows = sql(db, "SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN "
               "('pg_catalog','information_schema') ORDER BY 1,2").splitlines()
    result = {}
    for row in rows:
        schema, table = row.split('|')
        ident = '"' + schema.replace('"', '""') + '"."' + table.replace('"', '""') + '"'
        result[row] = sql(db, 'SELECT count(*),md5(coalesce(string_agg(h,\'\' ORDER BY h),\'\')) '
                         'FROM (SELECT md5(row_to_json(t)::text) h FROM ' + ident + ' t) s')
    return result


def inventory(paths):
    result = {}
    def add(p):
        info = {'mode': p.lstat().st_mode & 0o7777, 'uid': p.lstat().st_uid,
                'gid': p.lstat().st_gid}
        if p.is_symlink():
            info.update(type='symlink', target=os.readlink(p))
        elif p.is_file():
            info.update(type='file', size=p.stat().st_size, sha256=sha(p))
        elif p.is_dir():
            info.update(type='directory')
        else:
            raise RuntimeError('unsupported file type in retirement manifest')
        result[str(p)] = info
        if p.is_dir() and not p.is_symlink():
            for c in sorted(p.iterdir()):
                add(c)
    for path in paths:
        p = Path(path)
        if p.exists() or p.is_symlink():
            add(p)
    return result


def keep_identity():
    result = {}
    for u in KEEP_UNITS:
        props = dict(line.split('=', 1) for line in output(
            ['systemctl', 'show', u, '-p', 'MainPID', '-p', 'ActiveState']).splitlines())
        assert props['ActiveState'] == 'active' and props['MainPID'] != '0', u
        props['cwd'] = str(Path('/proc/' + props['MainPID'] + '/cwd').resolve())
        result[u] = props
    result['web'] = str(Path('/var/www/chickenbro-web/current').resolve())
    result['backend'] = str(Path('/opt/chickenbro').resolve())
    result['engine'] = str(Path('/opt/wow-simc/current').resolve())
    return result


def no_active():
    for u in UNITS:
        assert output(['systemctl', 'show', u, '-p', 'MainPID', '--value']) == '0', u
    dbnames = set(sql('postgres', 'SELECT datname FROM pg_database').splitlines())
    for db in DATABASES:
        if db not in dbnames:
            continue
        assert sql('postgres', "SELECT count(*) FROM pg_stat_activity WHERE datname='" + db + "'") == '0', db
        assert sql(db, "SELECT count(*) FROM chat.executions WHERE stage IN ('pending','running')") == '0', db
        assert sql(db, "SELECT count(*) FROM ops.job_queue WHERE status IN ('pending','running')") == '0', db
    # Inspect all processes, including argv and environment, without printing contents.
    needles = [p.encode() for p in PATHS if not p.endswith('.service')]
    needles += [db.encode() for db in DATABASES]
    me = os.getpid()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == me:
            continue
        try:
            data = (proc / 'cmdline').read_bytes() + (proc / 'environ').read_bytes()
            cwd = os.readlink(proc / 'cwd').encode()
            links = []
            for fd in (proc / 'fd').iterdir():
                try:
                    links.append(os.readlink(fd).encode())
                except OSError:
                    pass
        except (OSError, PermissionError):
            continue
        assert not any(n in data or cwd == n or cwd.startswith(n + b'/') or any(v == n or v.startswith(n + b'/') for v in links) for n in needles), 'live process references retirement target: pid ' + proc.name
    for p in Path('/etc/systemd/system').rglob('*'):
        if not p.is_file() or p.is_symlink() or str(p) in PATHS:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        assert not any(n in data for n in needles), 'retained unit references retirement target: ' + str(p)


def backup():
    if (ROOT / 'backup-verified.json').exists():
        proof = json.loads((ROOT / 'backup-verified.json').read_text())
        assert sha(ROOT / 'files.tar.gz') == proof['fileArchiveSha256']
        assert sha(ROOT / 'napcat-image.tar') == proof['imageArchiveSha256']
        print('verified backup already exists; no mutation', flush=True)
        return
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)
    if not (ROOT / 'keep-before.json').exists():
        save('keep-before.json', keep_identity())
    assert keep_identity() == json.loads((ROOT / 'keep-before.json').read_text())
    no_active()
    if not (ROOT / 'container-inspect.json').exists():
        save('container-inspect.json', json.loads(output(['docker', 'inspect', *CONTAINERS])))
    save('network-inspect.json', json.loads(output(['docker', 'network', 'inspect', 'chickenbro-qq-channel'])))
    run(['docker', 'stop', '--time', '20', *CONTAINERS])
    run(['docker', 'update', '--restart=no', *CONTAINERS])
    no_active()
    print('legacy containers stopped; protected products unchanged', flush=True)
    for u in UNITS:
        (ROOT / (u + '.unit.txt')).write_text(output(['systemctl', 'cat', u]))
    manifest = inventory(PATHS)
    save('file-manifest.json', manifest)
    archive = ROOT / 'files.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=3, dereference=False) as tf:
        for p in PATHS:
            if p in manifest:
                tf.add(p, arcname=p.lstrip('/'), recursive=True)
    restored = ROOT / 'file-restore-verified'
    if restored.exists():
        shutil.rmtree(restored)  # Only this executor's independently reconstructed scratch.
    restored.mkdir()
    run(['tar', '-xzf', str(archive), '-C', str(restored)])
    for p, info in manifest.items():
        f = restored / p.lstrip('/')
        assert f.lstat().st_mode & 0o7777 == info['mode'], p
        assert f.lstat().st_uid == info['uid'] and f.lstat().st_gid == info['gid'], p
        if info['type'] == 'file':
            assert f.is_file() and sha(f) == info['sha256'], p
        elif info['type'] == 'symlink':
            assert f.is_symlink() and os.readlink(f) == info['target'], p
        else:
            assert f.is_dir(), p
    print('file archive independently restored and verified: ' + str(len(manifest)), flush=True)
    image_archive = ROOT / 'napcat-image.tar'
    run(['docker', 'image', 'save', '-o', str(image_archive), IMAGE])
    run(['docker', 'image', 'load', '-i', str(image_archive)])
    assert output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}']) == IMAGE
    print('offline image restore verified', flush=True)
    db_results = json.loads((ROOT / 'database-recovery.json').read_text()) if (ROOT / 'database-recovery.json').exists() else {}
    for i, db in enumerate(DATABASES):
        before = table_fingerprints(db)
        dump = ROOT / (db + '.dump')
        if db in db_results:
            assert db_results[db]['fingerprints'] == before
            assert sha(dump) == db_results[db]['dumpSha256']
            continue
        with dump.open('wb') as f:
            subprocess.run(['sudo', '-u', 'postgres', 'pg_dump', '-Fc', db], stdout=f, stderr=subprocess.PIPE, check=True)
        restore_db = 'legacyqq_restore_verify_20261016_' + str(i)
        marker = ROOT / (restore_db + '.owned')
        if restore_db in sql('postgres', 'SELECT datname FROM pg_database').splitlines():
            assert marker.exists() and marker.read_text() == db, 'unowned recovery database'
            run(['sudo', '-u', 'postgres', 'dropdb', restore_db])
        marker.write_text(db)
        run(['sudo', '-u', 'postgres', 'createdb', '-T', 'template0', restore_db])
        with dump.open('rb') as f:
            subprocess.run(['sudo', '-u', 'postgres', 'pg_restore', '--exit-on-error', '-d', restore_db], stdin=f, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        after = table_fingerprints(restore_db)
        assert before == after, db
        # Independent recovery scratch only; original DB is not touched here.
        run(['sudo', '-u', 'postgres', 'dropdb', restore_db])
        db_results[db] = {'tables': len(before), 'fingerprints': before, 'dumpSha256': sha(dump),
                          'independentlyRestored': True}
        save('database-recovery.json', db_results)
        print('database independently restored: ' + db, flush=True)
    assert keep_identity() == json.loads((ROOT / 'keep-before.json').read_text())
    save('backup-verified.json', {'files': len(manifest), 'fileArchiveSha256': sha(archive),
        'imageArchiveSha256': sha(image_archive), 'databases': len(db_results),
        'fileRestoreVerified': True, 'databaseRestoreVerified': True,
        'offlineImageRestoreVerified': True, 'verifiedAt': time.time()})
    print('backup phase complete', flush=True)


def operation(progress, key, action):
    """Persist intent before mutation and completion after an idempotent action."""
    if key in progress['done']:
        return
    progress['intent'] = key
    save('apply-progress.json', progress)
    action()
    progress['done'].append(key)
    progress['intent'] = None
    save('apply-progress.json', progress)


def verify_container(saved, current):
    assert current['Id'] == saved['Id'], 'retirement container ID changed'
    assert current['Image'] == saved['Image'], 'retirement container image changed'
    assert current['State']['Running'] is False, 'retirement container is running'


def apply():
    verified = json.loads((ROOT / 'backup-verified.json').read_text())
    manifest = json.loads((ROOT / 'file-manifest.json').read_text())
    assert sha(ROOT / 'files.tar.gz') == verified['fileArchiveSha256']
    assert sha(ROOT / 'napcat-image.tar') == verified['imageArchiveSha256']
    image_proof = json.loads((ROOT / 'isolated-image-restore.json').read_text())
    assert image_proof['imageId'] == IMAGE and image_proof['emptyIndependentDaemon']
    assert image_proof['archiveSha256'] == verified['imageArchiveSha256']
    container_proof = json.loads((ROOT / 'container-images-restore.json').read_text())
    assert container_proof['emptyIndependentDaemon'] and container_proof['allContainerConfigsAndLayersMatched']
    assert sha(ROOT / 'container-images.tar') == container_proof['archiveSha256']
    progress_path = ROOT / 'apply-progress.json'
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {'done': [], 'intent': None}
    lock = open('/var/lock/chickenbro-release.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert keep_identity() == json.loads((ROOT / 'keep-before.json').read_text()), 'protected runtime changed'
    no_active()
    accounts = json.loads((ROOT / 'account-recovery-private.json').read_text())
    account = subprocess.run(['getent', 'passwd', 'chickenbro-qq'], capture_output=True, text=True)
    if account.returncode == 0:
        assert account.stdout.strip() == accounts['passwd'], 'service account identity changed'
    else:
        assert 'account' in progress['done'] or progress['intent'] == 'account'
    originals = {x['Name'].lstrip('/'): x for x in json.loads((ROOT / 'container-inspect.json').read_text())}
    assert set(originals) == set(CONTAINERS)
    assert set(container_proof['sourceContainerIds']) == {x['Id'] for x in originals.values()}
    all_names = set(output(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines())
    for c in CONTAINERS:
        if c in all_names:
            current = json.loads(output(['docker', 'inspect', c]))[0]
            verify_container(originals[c], current)
        else:
            assert 'container:' + c in progress['done'] or progress['intent'] == 'container:' + c
    # All resource checks happen before the first removal; resumes check every survivor.
    existing_containers = set(output(['docker', 'ps', '-a', '--filter', 'ancestor=' + IMAGE,
                                      '--format', '{{.Names}}']).splitlines())
    assert existing_containers <= set(CONTAINERS), 'image referenced by another container'
    for c in existing_containers:
        assert output(['docker', 'inspect', c, '--format', '{{.State.Running}}']) == 'false'
    for path in PATHS:
        src = Path(path)
        if src.exists() or src.is_symlink():
            expected = {k: v for k, v in manifest.items() if k == path or k.startswith(path + '/')}
            assert inventory([path]) == expected, 'retirement file baseline changed: ' + path
        elif path in manifest:
            destination = ROOT / 'withdrawn' / path.lstrip('/')
            assert destination.exists() or destination.is_symlink(), 'unrecorded missing target: ' + path
            assert 'path:' + path in progress['done'] or progress['intent'] == 'path:' + path
    recovery = json.loads((ROOT / 'database-recovery.json').read_text())
    present_dbs = set(sql('postgres', 'SELECT datname FROM pg_database').splitlines())
    for db in DATABASES:
        assert recovery[db]['independentlyRestored']
        assert sha(ROOT / (db + '.dump')) == recovery[db]['dumpSha256']
        if db in present_dbs:
            assert table_fingerprints(db) == recovery[db]['fingerprints'], db
        else:
            assert 'db:' + db in progress['done'] or progress['intent'] == 'db:' + db
    no_active()
    for u in UNITS:
        def disable(u=u):
            if Path('/etc/systemd/system/' + u + '.service').exists():
                run(['systemctl', 'disable', u])
        operation(progress, 'unit:' + u, disable)
    for c in CONTAINERS:
        def remove_container(c=c):
            names = set(output(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines())
            if c in names:
                current = json.loads(output(['docker', 'inspect', c]))[0]
                verify_container(originals[c], current)
                run(['docker', 'rm', originals[c]['Id']])
        operation(progress, 'container:' + c, remove_container)
    def remove_network():
        if 'chickenbro-qq-channel' in output(['docker', 'network', 'ls', '--format', '{{.Name}}']).splitlines():
            run(['docker', 'network', 'rm', 'chickenbro-qq-channel'])
    operation(progress, 'network', remove_network)
    def remove_image():
        assert not output(['docker', 'ps', '-aq', '--filter', 'ancestor=' + IMAGE])
        if subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True).returncode == 0:
            run(['docker', 'image', 'rm', IMAGE])
    for tag in container_proof['recoveryTags']:
        def remove_recovery_image(tag=tag):
            assert not output(['docker', 'ps', '-aq', '--filter', 'ancestor=' + tag])
            if subprocess.run(['docker', 'image', 'inspect', tag], capture_output=True).returncode == 0:
                run(['docker', 'image', 'rm', tag])
        operation(progress, 'recovery-image:' + tag, remove_recovery_image)
    operation(progress, 'image', remove_image)
    quarantine = ROOT / 'withdrawn'
    for path in PATHS:
        if path not in manifest:
            continue
        def withdraw(path=path):
            src, dst = Path(path), quarantine / path.lstrip('/')
            if src.exists() or src.is_symlink():
                assert not dst.exists() and not dst.is_symlink(), path
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
            else:
                assert dst.exists() or dst.is_symlink(), path
        operation(progress, 'path:' + path, withdraw)
    run(['systemctl', 'daemon-reload'])
    for db in DATABASES:
        def drop(db=db):
            if db in sql('postgres', 'SELECT datname FROM pg_database').splitlines():
                assert sql('postgres', "SELECT count(*) FROM pg_stat_activity WHERE datname='" + db + "'") == '0'
                # Native PostgreSQL safety check; FORCE is deliberately unavailable.
                run(['sudo', '-u', 'postgres', 'dropdb', db])
        operation(progress, 'db:' + db, drop)
        print('removed database: ' + db, flush=True)
    def remove_account():
        account = subprocess.run(['getent', 'passwd', 'chickenbro-qq'], capture_output=True, text=True)
        if account.returncode == 0:
            assert account.stdout.strip() == accounts['passwd']
            uid = int(accounts['passwd'].split(':')[2])
            assert not any(p.name.isdigit() and p.stat().st_uid == uid for p in Path('/proc').iterdir())
            run(['userdel', 'chickenbro-qq'])
        group = subprocess.run(['getent', 'group', 'chickenbro-qq'], capture_output=True, text=True)
        if group.returncode == 0:
            assert group.stdout.strip() == accounts['group']
            run(['groupdel', 'chickenbro-qq'])
    operation(progress, 'account', remove_account)
    assert keep_identity() == json.loads((ROOT / 'keep-before.json').read_text())
    assert not (set(sql('postgres', 'SELECT datname FROM pg_database').splitlines()) & set(DATABASES))
    assert not any(Path(p).exists() or Path(p).is_symlink() for p in PATHS)
    save('apply-result.json', {'status': 'removed', 'units': UNITS, 'containers': CONTAINERS,
        'network': 'chickenbro-qq-channel', 'image': IMAGE, 'databases': DATABASES, 'serviceAccountRemoved': 'chickenbro-qq',
        'removedRootPaths': [p for p in PATHS if p in manifest], 'protectedIdentityUnchanged': True,
        'recoveryRoot': str(ROOT), 'completedAt': time.time()})
    print('retirement apply complete; protected products unchanged', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['backup', 'apply'])
    args = parser.parse_args()
    os.umask(0o077)
    assert os.geteuid() == 0
    {'backup': backup, 'apply': apply}[args.phase]()
