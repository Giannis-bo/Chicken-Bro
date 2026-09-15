"""Fetch the existing localization provider's exact-build sources on the cloud host."""
from pathlib import Path
import hashlib,json,re,subprocess,time
root=Path('/var/lib/chickenbro-simc-update-20260915/localization-source');root.mkdir(exist_ok=True)
build='12.1.0.69814';sources=[]
for table,locale in [('SpellName','zhCN'),('SpellName','enUS'),('Creature','zhCN'),('Creature','enUS'),('ItemSparse','zhCN')]:
 url=f'https://wago.tools/db2/{table}/csv?build={build}&locale={locale}'
 dest=root/f'{table}.{locale}.csv';hdr=root/f'{table}.{locale}.headers'
 subprocess.run(['curl','-fsSL','--proxy','http://127.0.0.1:7890','--connect-timeout','10','--max-time','120','--max-filesize','67108864','-D',str(hdr),'-o',str(dest),url],check=True)
 cd=re.findall(r'(?im)^content-disposition:\s*(.+)$',hdr.read_text())[-1].strip()
 assert f'{table}.{build}.csv' in cd
 sources.append(dict(table=table,locale=locale,url=url,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),contentDisposition=cd))
 print(table,locale,dest.stat().st_size,flush=True)
(root/'manifest.json').write_text(json.dumps(dict(build=build,retrievedAt=time.time(),sources=sources),indent=2))
