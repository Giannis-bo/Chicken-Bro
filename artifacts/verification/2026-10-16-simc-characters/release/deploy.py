"""Pinned Web/API release; additive migration is retained on application recovery."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

import backend_release_helpers as base

FILES = frozenset(('server/app/api/routes/simc.py', 'server/app/simulation/application.py',
    'server/app/simulation/repository.py', 'server/app/simulation/sources.py',
    'server/app/simulation/characters.py', 'server/migrations/product/0021_simc_characters.sql'))
UNITS = base.UNITS
require, sha, inventory, switch, service = base.require, base.sha, base.inventory, base.switch, base.service


class Release(base.Release):
    def __init__(self, manifest):
        self.path = Path(manifest)
        self.m = json.loads(self.path.read_text())
        m = self.m
        require(set(m) == {'sourceCommit', 'sourceUncommitted', 'releaseId', 'expectedBackend', 'expectedWeb',
            'targetBackend', 'targetWeb', 'baseInventory', 'files', 'baseHashes', 'webFiles', 'newWebFiles',
            'environmentHashes', 'enginePath', 'compilerRevision'}, 'manifest fields differ')
        require(m['sourceUncommitted'] is True, 'release source must be described explicitly')
        require(len(m['sourceCommit']) == 40 and len(m['releaseId']) == 64, 'invalid source identity')
        self.base, self.web = Path(m['expectedBackend']), Path(m['expectedWeb'])
        self.target, self.web_target = Path(m['targetBackend']), Path(m['targetWeb'])
        require(self.base.parent == self.target.parent == Path('/opt/chickenbro-releases'), 'backend root mismatch')
        require(self.web.parent == self.web_target.parent == Path('/var/www/chickenbro-web/releases'), 'Web root mismatch')
        require(self.target.name == self.web_target.name == 'simc-characters-20261016-'+m['releaseId'][:16], 'target identity mismatch')
        self.link, self.web_link = Path('/opt/chickenbro'), Path('/var/www/chickenbro-web/current')
        self.overlay = self.path.parent/'overlay'
        self.connect = None
        self.envs = None
        require(set(m['files']) == FILES == set(m['baseHashes']), 'overlay outside exact scope')
        for name in FILES:
            base.scoped(self.base, name)
            require(m['baseInventory'].get(name) == m['baseHashes'][name], 'base source identity differs')

    def baseline(self, current):
        expected_web = self.web_target if current == self.target else self.web
        require(self.link.is_symlink() and self.link.resolve() == current, 'backend pointer changed')
        require(self.web_link.is_symlink() and self.web_link.resolve() == expected_web, 'Web pointer changed')
        require(inventory(self.base) == self.m['baseInventory'], 'preserved backend changed')
        require(inventory(self.web) == self.m['webFiles'], 'preserved Web changed')
        require(str(Path('/opt/wow-simc/current').resolve()) == self.m['enginePath'], 'engine pointer changed')

    def staged(self):
        require(inventory(self.target) == {**self.m['baseInventory'], **self.m['files']}, 'staged backend changed')
        require(inventory(self.web_target) == self.m['newWebFiles'], 'staged Web changed')

    def stage(self):
        self.baseline(self.base)
        require(inventory(self.overlay) == self.m['files'], 'overlay hash mismatch')
        if not self.target.exists():
            temporary = self.target.with_name('.simc-characters-'+uuid4().hex)
            shutil.copytree(self.base, temporary, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            for name in FILES:
                target = base.scoped(temporary, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(base.scoped(self.overlay, name), target)
            require(inventory(temporary) == {**self.m['baseInventory'], **self.m['files']}, 'backend stage copy differs')
            os.rename(temporary, self.target)
        source = Path('/opt/chickenbro-candidates/simc-character-bindings-20261016/apps/mini-taro/dist/h5')
        require(inventory(source) == self.m['newWebFiles'], 'built Web changed')
        if not self.web_target.exists():
            temporary = self.web_target.with_name('.simc-characters-'+uuid4().hex)
            shutil.copytree(source, temporary)
            require(inventory(temporary) == self.m['newWebFiles'], 'Web stage copy differs')
            for file in temporary.rglob('*'):
                file.chmod(0o755 if file.is_dir() else 0o644)
            temporary.chmod(0o755)
            os.rename(temporary, self.web_target)
        self.staged()
        recovery = self.path.parent/'recovery'
        recovery.mkdir(mode=0o700, exist_ok=True)
        for name, source, expected in [('backend',self.base,self.m['baseInventory']), ('web',self.web,self.m['webFiles'])]:
            copy = recovery/name
            if not copy.exists():
                shutil.copytree(source, copy, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            require(inventory(copy) == expected, 'recovery copy differs')
            require(all((copy/key).stat().st_ino != (source/key).stat().st_ino for key in expected), 'recovery copy shares inodes')

    def migration(self):
        require((self.path.parent/'database-recovery.json').is_file(), 'independent database recovery required')
        proof = json.loads((self.path.parent/'database-recovery.json').read_text())
        require(proof['restoreCountsMatched'] and proof['newMigrationVerified'], 'database recovery proof incomplete')
        sql_path = self.target/'server/migrations/product/0021_simc_characters.sql'
        require(sha(sql_path) == self.m['files']['server/migrations/product/0021_simc_characters.sql'], 'migration hash differs')
        description = 'simc-characters-release:'+self.m['releaseId']
        with self.connect() as connection:
            current = connection.execute("SELECT description FROM ops.schema_migrations WHERE id='0021_simc_characters'").fetchone()
            if current is not None:
                require(current == (description,), 'migration belongs to another activation')
                require(connection.execute("SELECT to_regclass('simc.character_preferences')").fetchone()[0] is not None, 'migration table missing')
                require(connection.execute("SELECT has_table_privilege('wow_app','simc.character_preferences','SELECT,INSERT,UPDATE')").fetchone()[0], 'runtime privileges missing')
                return
            require(connection.execute("SELECT to_regclass('simc.character_preferences')").fetchone()[0] is None, 'pre-existing character preferences table')
        # Schema creation runs under the existing administrative local channel, never the request role.
        migrated = subprocess.run(['sudo','-n','-u','postgres','psql','-X','-q','--single-transaction',
            '-v','ON_ERROR_STOP=1','-v','release_description='+description,'-d','chickenbro_prod','-f','-'],
            input=sql_path.read_text()+"\nINSERT INTO ops.schema_migrations (id,description) VALUES ('0021_simc_characters',:'release_description');\n",
            text=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        require(migrated.returncode == 0, 'additive production migration failed')
        with self.connect() as connection:
            require(connection.execute("SELECT has_table_privilege('wow_app','simc.character_preferences','SELECT,INSERT,UPDATE')").fetchone()[0], 'runtime privileges missing')

    def verify(self, current):
        self.baseline(current)
        self.staged()
        self.ready()
        for unit in UNITS:
            require(base.env_digest(base.environment(unit)) == base.env_digest(self.envs[unit]), 'effective service configuration changed')
            pid = subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
            require(Path('/proc/'+pid+'/cwd').resolve() == current, 'service source directory differs')
        with self.connect() as connection:
            require(connection.execute("SELECT 1 FROM ops.schema_migrations WHERE id='0021_simc_characters'").fetchone() == (1,), 'migration registry missing')

    def activate(self, old_backend, old_web, new_backend, new_web):
        with self.idle_fence() as connection:
            require(self.link.resolve() == old_backend and self.web_link.resolve() == old_web, 'activation base drift')
            require(inventory(self.base) == self.m['baseInventory'] and inventory(self.web) == self.m['webFiles'], 'recovery base drift')
            self.staged()
            service('stop',UNITS[0])
            service('stop',UNITS[1])
            require(not any(self.active(connection).values()), 'execution appeared after API stop')
            switch(self.link,new_backend)
            switch(self.web_link,new_web)
        self.start()
        self.verify(new_backend)

    def run(self, action):
        if action == 'stage':
            self.stage()
        elif action == 'preflight':
            self.baseline(self.base)
            self.runtime()
            self.staged()
            with self.connect() as connection:
                require(connection.execute('SELECT current_database()').fetchone()[0] == 'chickenbro_prod', 'wrong database')
                counts = self.active(connection)
            return {'action':action,'active':counts,'sourceBaseCommit':self.m['sourceCommit'],'releaseId':self.m['releaseId']}
        else:
            self.runtime(allow_recovery=action == 'rollback')
            self.staged()
            if action == 'promote':
                self.baseline(self.base)
                self.save_recovery()
                self.migration()
                try:
                    self.activate(self.base,self.web,self.target,self.web_target)
                except Exception:
                    current_backend, current_web = self.link.resolve(), self.web_link.resolve()
                    require(current_backend in (self.base,self.target) and current_web in (self.web,self.web_target), 'foreign pointers prevent recovery')
                    unchanged = current_backend == self.base and current_web == self.web
                    running = all(subprocess.run(['systemctl','is-active','--quiet',unit]).returncode == 0 for unit in UNITS)
                    if unchanged and running:
                        raise RuntimeError('cutover not performed; prior services still running; additive table retained') from None
                    # Idle-fenced recovery also handles a failure between the two pointer updates.
                    self.activate(current_backend,current_web,self.base,self.web)
                    raise RuntimeError('activation failed; prior backend/Web recovered; additive table retained') from None
            elif action == 'rollback':
                self.activate(self.target,self.web_target,self.base,self.web)
            elif action == 'verify':
                self.verify(self.target)
            else:
                raise ValueError('unsupported action')
        return {'action':action,'sourceBaseCommit':self.m['sourceCommit'],'releaseId':self.m['releaseId'],
                'backend':str(self.link.resolve()),'web':str(self.web_link.resolve()),'businessSmoke':'required'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('action',choices=('stage','preflight','promote','verify','rollback'))
    args=parser.parse_args()
    with open('/run/lock/chickenbro-release.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=Release(args.manifest).run(args.action)
        target=Path(args.manifest).parent/(args.action+'-result.json')
        target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))


if __name__=='__main__':main()
