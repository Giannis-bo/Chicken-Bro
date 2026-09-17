"""Exact backend-only release. Readiness is never business acceptance.

Run on the cloud host with its existing application Python. The helper itself is
stdlib/import-safe; the connection factory is loaded lazily from the pinned base.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4

ALLOWED = frozenset(('server/app/chickenbro/research_budget.py',))
UNITS = ('chickenbro-api', 'chickenbro-worker')
VOLATILE_ENV = frozenset(('INVOCATION_ID', 'JOURNAL_STREAM', 'SYSTEMD_EXEC_PID'))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scoped(root, name):
    p = Path(name)
    require(isinstance(name, str) and name and not p.is_absolute()
            and '..' not in p.parts and str(p) == name, 'invalid relative path')
    require(not root.is_symlink(), 'root symlink prohibited')
    result = root / p
    require(not any((root / Path(*p.parts[:i])).is_symlink()
                    for i in range(1, len(p.parts) + 1)), 'symlink prohibited')
    require(result.resolve().is_relative_to(root.resolve()), 'path escapes root')
    return result


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), 'inventory root invalid')
    result = {}
    for p in root.rglob('*'):
        require(not p.is_symlink(), 'inventory symlink prohibited')
        if '__pycache__' in p.parts or p.suffix == '.pyc':
            continue
        require(p.is_file() or p.is_dir(), 'nonregular inventory entry')
        if p.is_file():
            result[str(p.relative_to(root))] = sha(p)
    return result


def env_digest(env):
    return hashlib.sha256(json.dumps({k: v for k, v in env.items()
        if k not in VOLATILE_ENV}, sort_keys=True).encode()).hexdigest()


class ServiceUnavailable(RuntimeError):
    pass


def require_private(metadata, directory=False):
    require(metadata.st_uid == 0, 'recovery metadata must be root-owned')
    require(stat.S_IMODE(metadata.st_mode) == (0o700 if directory else 0o600),
            'recovery metadata must be private')
    require((stat.S_ISDIR if directory else stat.S_ISREG)(metadata.st_mode),
            'recovery metadata has invalid type')
    if not directory:
        require(metadata.st_nlink == 1, 'recovery snapshot hardlink prohibited')


def environment(unit):
    pid = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip()
    require(pid.isdigit(), 'invalid service PID')
    if int(pid) == 0:
        raise ServiceUnavailable('service not running: ' + unit)
    try:
        values = Path('/proc/' + pid + '/environ').read_text()
    except FileNotFoundError as exc:
        raise ServiceUnavailable('service exited: ' + unit) from exc
    return dict(v.split('=', 1) for v in values.split('\0') if '=' in v)


def service(*args):
    subprocess.run(['systemctl', *args], check=True, stdout=subprocess.DEVNULL, timeout=45)


def switch(link, destination):
    require(link.is_symlink(), 'production pointer must be symlink')
    temporary = link.with_name('.badcase-next-' + uuid4().hex)
    temporary.symlink_to(destination)
    try:
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)


def database_connector(env):
    # libpq does not see AppSettings or the captured service environment.
    # Pass its configured password file explicitly; never mutate process env.
    passfile = env.get('PGPASSFILE')
    def connect(dsn, **kwargs):
        import psycopg
        if passfile:
            kwargs['passfile'] = passfile
        return psycopg.connect(dsn, **kwargs)
    return connect


class Release:
    def __init__(self, manifest, connect=None):
        self.path = Path(manifest)
        self.m = json.loads(self.path.read_text())
        m = self.m
        require(set(m) <= {'sourceCommit', 'expectedBackend', 'expectedWeb', 'baseInventory',
                'files', 'baseHashes', 'webFiles', 'environmentHashes'}, 'unknown manifest fields')
        require(re.fullmatch('[0-9a-f]{40}', m['sourceCommit']) is not None, 'invalid commit')
        self.base, self.web = Path(m['expectedBackend']), Path(m['expectedWeb'])
        require(self.base.parent == Path('/opt/chickenbro-releases') and not self.base.is_symlink(), 'invalid base')
        require(self.web.parent == Path('/var/www/chickenbro-web/releases') and not self.web.is_symlink(), 'invalid Web base')
        self.target = Path('/opt/chickenbro-releases/badcase-' + m['sourceCommit'])
        require(self.target != self.base, 'target equals base')
        self.link, self.web_link = Path('/opt/chickenbro'), Path('/var/www/chickenbro-web/current')
        self.overlay = self.path.parent / 'overlay'
        require(bool(m['files']) and set(m['files']) <= ALLOWED, 'overlay outside allowlist')
        require(set(m['baseHashes']) == set(m['files']), 'base hashes mismatch')
        for key in ('baseInventory', 'files', 'baseHashes', 'webFiles'):
            for name, value in m[key].items():
                scoped(self.base, name)
                require((key == 'baseHashes' and value is None) or
                        isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid hash')
        for name, value in m['baseHashes'].items():
            require(m['baseInventory'].get(name) == value, 'base hash contradicts inventory')
        self.connect = connect
        self.envs = None

    def baseline(self, current):
        require(self.link.is_symlink() and self.link.resolve() == current, 'backend pointer drift')
        require(self.web_link.is_symlink() and self.web_link.resolve() == self.web, 'Web pointer drift')
        require(inventory(self.base) == self.m['baseInventory'], 'base inventory drift')
        require(inventory(self.web) == self.m['webFiles'], 'Web inventory drift')

    def staged(self):
        require(inventory(self.target) == {**self.m['baseInventory'], **self.m['files']}, 'target inventory drift')

    def stage(self):
        self.baseline(self.base)
        require(inventory(self.overlay) == self.m['files'], 'overlay inventory drift')
        if not self.target.exists():
            temporary = self.target.with_name('.badcase-stage-' + uuid4().hex)
            # No existing directory is removed, even on failure.
            shutil.copytree(self.base, temporary, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            for name in self.m['files']:
                dest = scoped(temporary, name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(scoped(self.overlay, name), dest)
            require(inventory(temporary) == {**self.m['baseInventory'], **self.m['files']}, 'copy drift')
            self.baseline(self.base)
            os.rename(temporary, self.target)
        self.staged()

    def recovery_path(self):
        parent = self.path.absolute().parent
        require(parent.resolve() == parent, 'recovery directory symlink prohibited')
        require_private(parent.lstat(), directory=True)
        return parent / 'badcase-recovery.json'

    def recovery_record(self):
        return {'sourceCommit': self.m['sourceCommit'], 'manifestSha256': sha(self.path),
                'environments': self.envs}

    def read_recovery(self):
        path = self.recovery_path()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as handle:
            require_private(os.fstat(handle.fileno()))
            record = json.load(handle)
        require(set(record) == {'sourceCommit', 'manifestSha256', 'environments'}, 'invalid recovery snapshot')
        require(record['sourceCommit'] == self.m['sourceCommit'] and
                record['manifestSha256'] == sha(self.path), 'recovery identity mismatch')
        envs = record['environments']
        require(set(envs) == set(UNITS), 'recovery unit identity mismatch')
        expected = self.m.get('environmentHashes')
        require(expected is not None and set(expected) == set(UNITS), 'recovery requires environment hashes')
        require(all(isinstance(e, dict) and all(isinstance(k, str) and isinstance(v, str)
                    for k, v in e.items()) for e in envs.values()), 'invalid recovery environments')
        require({u: env_digest(e) for u, e in envs.items()} == expected, 'recovery environment hash mismatch')
        return record

    def save_recovery(self):
        expected = self.m.get('environmentHashes')
        require(expected is not None and set(expected) == set(UNITS), 'promotion requires environment hashes')
        require({u: env_digest(e) for u, e in self.envs.items()} == expected, 'effective environment drift')
        path = self.recovery_path()
        record = self.recovery_record()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            require(self.read_recovery() == record, 'existing recovery snapshot differs')
            return
        with os.fdopen(fd, 'w') as handle:
            require_private(os.fstat(handle.fileno()))
            json.dump(record, handle)
            handle.flush()
            os.fsync(handle.fileno())
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def runtime(self, allow_recovery=False):
        captured = None
        self.envs = {}
        for unit in UNITS:
            try:
                self.envs[unit] = environment(unit)
            except ServiceUnavailable:
                require(allow_recovery, 'missing live service environment')
                if captured is None:
                    captured = self.read_recovery()['environments']
                self.envs[unit] = captured[unit]
        expected = self.m.get('environmentHashes')
        if expected:
            require(set(expected) == set(UNITS), 'environment hash units mismatch')
            require({u: env_digest(e) for u, e in self.envs.items()} == expected, 'effective environment drift')
        require(self.envs[UNITS[0]]['WOW_DATABASE_URL'] == self.envs[UNITS[1]]['WOW_DATABASE_URL'], 'database mismatch')
        if self.connect is None:
            sys.path.insert(0, str(self.base))
            from server.app.platform.config import AppSettings
            from server.app.platform.postgres import PostgresConnectionFactory
            self.connect = PostgresConnectionFactory(AppSettings.from_env(self.envs[UNITS[0]]),
                connector=database_connector(self.envs[UNITS[0]])).connection

    def active(self, conn):
        queries = {'chat': "chat.agent_runs WHERE status='streaming'",
            'executions': "chat.executions WHERE stage IN ('pending','queued','running')",
            'simc': "simc.simulation_jobs WHERE status IN ('queued','running')",
            'queue': "ops.job_queue WHERE status IN ('queued','running')"}
        return {k: conn.execute('SELECT count(*) FROM ' + v).fetchone()[0] for k, v in queries.items()}

    @contextmanager
    def idle_fence(self):
        deadline = time.monotonic() + 120
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'active tasks prevent release')
            with self.connect() as conn:
                timeout_ms = max(1, min(5000, int(remaining * 1000)))
                conn.execute("SET LOCAL lock_timeout='" + str(timeout_ms) + "ms'")
                conn.execute("SET LOCAL statement_timeout='" + str(timeout_ms) + "ms'")
                conn.execute('LOCK TABLE chat.agent_runs,chat.executions,simc.simulation_jobs,ops.job_queue IN SHARE MODE')
                counts = self.active(conn)
                if not any(counts.values()):
                    yield conn
                    return
            # Release locks between checks so active tasks can finish naturally.
            require(time.monotonic() < deadline, 'active tasks prevent release')
            time.sleep(min(1, max(0, deadline - time.monotonic())))

    def start(self):
        service('start', UNITS[1])
        port = int(self.envs[UNITS[1]].get('WOW_CHAT_WORKER_TOOL_PORT', '28794'))
        require(0 < port < 65536, 'invalid tool port')
        for _ in range(20):
            pid = subprocess.check_output(['systemctl', 'show', UNITS[1], '-p', 'MainPID', '--value'], text=True).strip()
            listeners = subprocess.check_output(['ss', '-ltnp', 'sport = :' + str(port)], text=True)
            if pid != '0' and ('pid=' + pid + ',') in listeners:
                service('start', UNITS[0])
                return
            time.sleep(1)
        raise RuntimeError('worker listener failed; API admission stays closed')

    def ready(self):
        for _ in range(30):
            try:
                with urlopen('http://127.0.0.1:8790/api/v2/health/readiness', timeout=2) as response:
                    if json.load(response).get('status') == 'ready':
                        return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError('readiness failed')

    def verify(self, current):
        self.baseline(current)
        if current == self.target:
            self.staged()
        self.ready()
        for unit in UNITS:
            require(env_digest(environment(unit)) == env_digest(self.envs[unit]), 'effective environment drift')
            pid = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip()
            require(Path('/proc/' + pid + '/cwd').resolve() == current, 'runtime cwd mismatch')

    def activate(self, current, destination):
        with self.idle_fence() as conn:
            self.baseline(current)
            if destination == self.target:
                self.staged()
            service('stop', UNITS[0])
            service('stop', UNITS[1])
            require(not any(self.active(conn).values()), 'active execution after stop')
            switch(self.link, destination)
        self.start()
        self.verify(destination)

    def promote(self):
        self.baseline(self.base)
        self.staged()
        try:
            self.activate(self.base, self.target)
        except Exception as original:
            # A running/new task prevents all stops and pointer restoration.
            try:
                current = self.link.resolve()
                require(current in (self.base, self.target), 'foreign pointer prevents rollback')
                self.activate(current, self.base)
            except Exception:
                raise RuntimeError('activation failed; controlled recovery unsafe or failed; inspect services') from original
            raise RuntimeError('activation failed; idle-fenced base recovery verified') from original

    def run(self, action):
        current = self.target if action in ('rollback', 'verify') else self.base
        self.baseline(current)
        if action == 'stage':
            self.stage()
        elif action in ('promote', 'rollback', 'verify'):
            self.runtime(allow_recovery=action == 'rollback')
            if action == 'promote':
                self.save_recovery()
                self.promote()
            elif action == 'rollback':
                self.activate(self.target, self.base)
            else:
                self.verify(self.target)
        else:
            require(inventory(self.overlay) == self.m['files'], 'overlay inventory drift')
            self.runtime()
            with self.connect() as conn:
                require(conn.execute('SELECT 1').fetchone() == (1,), 'database preflight failed')
        return {'action': action, 'sourceCommit': self.m['sourceCommit'],
                'backend': str(self.link.resolve()), 'web': str(self.web),
                'businessSmoke': 'required'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('action', choices=('preflight', 'stage', 'promote', 'rollback', 'verify'))
    args = parser.parse_args()
    with open('/run/lock/chickenbro-release.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(Release(args.manifest).run(args.action)))


if __name__ == '__main__':
    main()
