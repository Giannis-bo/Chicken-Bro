from pathlib import Path
import hashlib,json,re,subprocess,csv
root=Path('/var/lib/chickenbro-simc-update-20261016/graph-proof');root.mkdir(exist_ok=True)
sources=[]
for build in ['12.1.0.69933','12.1.5.70391']:
 dest=root/(build+'.csv');hdr=root/(build+'.headers');url=f'https://wago.tools/db2/TraitEdge/csv?build={build}&locale=enUS'
 subprocess.run(['curl','-fsSL','--proxy','http://127.0.0.1:7890','--connect-timeout','10','--max-time','120','--max-filesize','67108864','-D',str(hdr),'-o',str(dest),url],check=True)
 cd=re.findall(r'(?im)^content-disposition:\s*(.+)$',hdr.read_text())[-1].strip();assert f'TraitEdge.{build}.csv' in cd
 with dest.open() as f:rows=list(csv.DictReader(f))
 sources.append({'build':build,'url':url,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'contentDisposition':cd,'count':len(rows),'columns':list(rows[0])})
 print(json.dumps(sources[-1]),flush=True)
(root/'manifest.json').write_text(json.dumps(sources,indent=2))
