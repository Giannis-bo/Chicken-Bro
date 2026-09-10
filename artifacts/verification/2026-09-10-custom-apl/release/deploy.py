"""Exact custom APL release: backend, Web and one additive compiler override."""
import argparse,fcntl,json,os,shutil,subprocess
from pathlib import Path
import base_release as base
from base_release import require,sha,inventory,env_digest,environment,UNITS,service,switch

class Release(base.Release):
    def __init__(self, manifest):
        super().__init__(manifest)
        suffix=self.m['sourceCommit'][:12]
        self.new_web=Path('/var/www/chickenbro-web/releases/custom-apl-'+self.m['sourceCommit'])
        self.env_file=Path('/etc/chickenbro-custom-apl-'+suffix+'.env')
        self.drops=[Path('/etc/systemd/system/'+u+'.service.d/99-zzzzzz-custom-apl-'+suffix+'.conf') for u in UNITS]
        self.env_text='WOW_SIMC_COMPILER_REVISION=chickenbro-simc-compiler-v6\n'
        self.drop_text='[Service]\nEnvironmentFile='+str(self.env_file)+'\n'
    def baseline(self,current):
        require(self.link.is_symlink() and self.link.resolve()==current,'backend pointer drift')
        expected_web=self.new_web if current==self.target else self.web
        require(self.web_link.is_symlink() and self.web_link.resolve()==expected_web,'Web pointer drift')
        require(inventory(self.base)==self.m['baseInventory'],'base inventory drift')
        require(inventory(self.web)==self.m['webFiles'],'old Web inventory drift')
    def staged(self):
        super().staged()
        require(inventory(self.new_web)==self.m['newWebFiles'],'new Web inventory drift')
    def stage(self):
        self.baseline(self.base)
        payload=self.path.parent/'web'
        require(inventory(payload)==self.m['newWebFiles'],'Web payload drift')
        if not self.new_web.exists():shutil.copytree(payload,self.new_web)
        super().stage()
    def runtime(self,allow_recovery=False):
        if self.link.resolve()!=self.target:
            return super().runtime(allow_recovery)
        originals=self.read_recovery()['environments']
        for unit in UNITS:
            try: current=environment(unit)
            except base.ServiceUnavailable:
                require(allow_recovery,'service unavailable');continue
            require(current.get('WOW_SIMC_COMPILER_REVISION')=='chickenbro-simc-compiler-v6','compiler drift')
            if 'WOW_SIMC_COMPILER_REVISION' in originals[unit]:current['WOW_SIMC_COMPILER_REVISION']=originals[unit]['WOW_SIMC_COMPILER_REVISION']
            else:current.pop('WOW_SIMC_COMPILER_REVISION',None)
            require(env_digest(current)==env_digest(originals[unit]),'unrelated environment drift')
        self.envs=originals
        connector=base.database_connector(originals[UNITS[0]])
        self.connect=lambda:connector(originals[UNITS[0]]['WOW_DATABASE_URL'])
    def configure(self,destination):
        if destination==self.target:
            if self.env_file.exists():require(self.env_file.read_text()==self.env_text,'existing override differs')
            else:
                fd=os.open(self.env_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'w') as f:f.write(self.env_text);f.flush();os.fsync(f.fileno())
            for drop in self.drops:
                drop.parent.mkdir(parents=True,exist_ok=True)
                require(not drop.is_symlink(),'drop symlink')
                if drop.exists():require(drop.read_text()==self.drop_text,'existing drop differs')
                else:drop.write_text(self.drop_text)
        else:
            for drop in self.drops:
                if drop.exists():
                    require(not drop.is_symlink() and drop.read_text()==self.drop_text,'foreign drop prevents rollback')
                    drop.unlink()
        service('daemon-reload')
    def activate(self,current,destination):
        with self.idle_fence() as conn:
            self.baseline(current)
            if destination==self.target:self.staged()
            service('stop',UNITS[0]);service('stop',UNITS[1])
            require(not any(self.active(conn).values()),'work appeared after stop')
            self.configure(destination)
            switch(self.link,destination)
            switch(self.web_link,self.new_web if destination==self.target else self.web)
        self.start();self.verify(destination)
    def verify(self,current):
        self.baseline(current)
        if current==self.target:self.staged()
        self.ready()
        for unit in UNITS:
            expected=dict(self.envs[unit])
            if current==self.target:expected['WOW_SIMC_COMPILER_REVISION']='chickenbro-simc-compiler-v6'
            require(env_digest(environment(unit))==env_digest(expected),'effective environment drift')
            pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
            require(Path('/proc/'+pid+'/cwd').resolve()==current,'runtime cwd differs')
    def run(self,action):
        result=super().run(action)
        result.update(web=str(self.web_link.resolve()),compiler='chickenbro-simc-compiler-v6' if self.link.resolve()==self.target else 'previous')
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('action',choices=['preflight','stage','promote','rollback','verify']);a=p.parse_args()
    with open('/run/lock/chickenbro-release.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        print(json.dumps(Release(a.manifest).run(a.action)))
