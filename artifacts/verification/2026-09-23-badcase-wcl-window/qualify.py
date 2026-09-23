"""Five-class deterministic source/gateway qualification; no external calls."""
import hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from server.app.chickenbro import wcl_source as w
from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
cases=[
 ('original',42,6854810,7080831,{'view':'events','startTime':222000,'endTime':226021},[],False),
 ('variant',7,1000,9000,{'view':'events','startTime':8000,'endTime':10000},[{'type':'damage','timestamp':8000}],False),
 ('holdout',81,12000000,12240000,{'view':'events','endTime':240000},[],False),
 ('normal_empty',5,1000,9000,{'view':'events','startTime':3000,'endTime':4000},[],True),
 ('normal_full',5,1000,9000,{'view':'events'},[{'type':'damage','timestamp':3000}],True),
 ('statistics',7,1000,9000,{'view':'statistics','startTime':0,'endTime':8000},[],False),
]
rows=[]
for kind,fid,start,end,options,events,want in cases:
 report={'fights':[{'id':fid,'startTime':start,'endTime':end}],'events':{'data':events,'nextPageTimestamp':None}}
 with patch.object(w,'warcraftlogs_credentials_state',return_value={'configured':True,'mode':'v2_oauth','api':'v2'}),patch.object(w,'_graphql',return_value={'reportData':{'report':report}}):
  result=ServerConfiguredSourceQuery().query('warcraftlogs',f'https://www.warcraftlogs.com/reports/CCCCCCCCCCCCCCCC?fight={fid}&source=5',options)
 verified=result['status']=='verified'
 hint=' '.join(result.get('limitations',[])+result.get('nextActions',[]))
 rows.append({'class':kind,'status':result['status'],'factsCount':len(result['facts']),'evidenceRefs':result['evidenceRefs'],'meetsCriterion':verified==want and (want or not result['facts']), 'boundHintPresent':str(start) in hint and 'report-relative' in hint})
with patch.object(w,'warcraftlogs_credentials_state',return_value={'configured':False,'mode':'none','api':'v2'}),patch.object(w,'_graphql',side_effect=AssertionError('unauthorized upstream')):
 result=ServerConfiguredSourceQuery().query('warcraftlogs','https://www.warcraftlogs.com/reports/DDDDDDDDDDDDDDDD?fight=8',{'view':'events','startTime':1,'endTime':10})
 rows.append({'class':'permission','status':result['status'],'factsCount':len(result['facts']),'evidenceRefs':result['evidenceRefs'],'meetsCriterion':result['status']!='verified' and not result['facts'] and not result['evidenceRefs']})
print(json.dumps({'source':sys.argv[1],'sourceHashes':{f:hashlib.sha256((Path(sys.argv[1])/f).read_bytes()).hexdigest() for f in ['server/app/chickenbro/wcl_source.py','server/app/chickenbro/wcl_statistics.py']},'results':rows,'allPassed':all(r['meetsCriterion'] for r in rows)},indent=2))
