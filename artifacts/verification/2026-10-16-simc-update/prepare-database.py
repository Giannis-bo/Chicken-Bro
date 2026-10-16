from pathlib import Path
import subprocess,os,json
os.umask(0o077)
root=Path('/var/lib/chickenbro-simc-update-20261016')
old='chickenbro_badcase_candidate_20260909';new='chickenbro_simc_candidate_20261016'
run=lambda sql:subprocess.check_output(['sudo','-n','-u','postgres','psql','-XAt','-c',sql],text=True).strip()
assert run("SELECT count(*) FROM pg_database WHERE datname='"+new+"'")=='0'
owner=run("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+old+"'")
assert owner.replace('_','').isalnum()
with (root/'candidate-database.sql').open('wb') as f:subprocess.run(['sudo','-n','-u','postgres','pg_dump','-d',old,'--no-owner','--no-privileges'],stdout=f,check=True)
run('CREATE DATABASE '+new+' OWNER '+owner+" TEMPLATE template0 ENCODING 'UTF8'")
with (root/'candidate-database.sql').open('rb') as f:subprocess.run(['sudo','-n','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-d',new,'-q','-c','SET ROLE '+owner,'-f','-'],stdin=f,check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'sourceCandidate':old,'newCandidate':new,'productionDataCopied':False,'preservedDump':True}))
