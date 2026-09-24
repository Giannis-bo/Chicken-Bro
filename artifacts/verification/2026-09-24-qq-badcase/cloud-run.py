"""Run isolated probes with existing QQ configuration, never start a channel."""
import os,sys,pathlib,subprocess,pwd
cwd,script,*args=sys.argv[1:]
pid=subprocess.check_output(['systemctl','show','chickenbro-qq-worker','-p','MainPID','--value'],text=True).strip()
assert pid!='0'
env=dict(s.split('=',1) for s in pathlib.Path('/proc/'+pid+'/environ').read_bytes().decode().split('\0') if '=' in s)
if script.endswith('candidate-workflow.py'):
    import psycopg
    from urllib.parse import urlsplit,urlunsplit
    os.environ.update(env)
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:password=c.info.password
    assert password
    u=urlsplit(env['WOW_DATABASE_URL'])
    env['WOW_DATABASE_URL']=urlunsplit(u._replace(path='/chickenbro_qq_badcase_candidate_20260924'))
    env['PGPASSWORD']=password
    env['WOW_CHAT_WORKER_TOOL_PORT']='18796'
    env['WOW_CODEX_JOBS_DIR']=cwd+'/evidence/jobs-professional'
    env['WOW_QQ_COMPANION_ENABLED']='1'
u=pwd.getpwnam('ubuntu');os.environ.clear();os.environ.update(env)
os.initgroups(u.pw_name,u.pw_gid);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
os.chdir(cwd);sys.path.insert(0,cwd);sys.argv=[script,*args]
import runpy
runpy.run_path(script,run_name='__main__')
