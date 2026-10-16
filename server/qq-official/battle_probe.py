"""Read-only source verification on the cloud; no QQ sends, secrets, or AI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True,choices=[
        '/opt/chickenbro-qq-official-query-staging-20261014',
        '/opt/chickenbro-qq-official-candidate-20261014'])
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    pid=subprocess.check_output(['systemctl','show','chickenbro-qq-official.service','-p','MainPID','--value'],text=True).strip()
    env=dict(s.split('=',1) for s in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in s)
    os.environ.update({k:v for k,v in env.items() if k.startswith('WOW_WARCRAFTLOGS_')})
    sys.path.insert(0,args.root)
    from server.app.channels.qq_official.battle_commands import parse_battle,format_battle
    from server.app.channels.qq_official.battle_source import BattleSource
    from server.app.channels.qq_official.query_commands import markdown_parts
    results=[]
    url='https://www.warcraftlogs.com/reports/QqrT6Nkg7jRBWCMH'
    for code,fight,expected in [('QqrT6Nkg7jRBWCMH',51,True),('QqrT6Nkg7jRBWCMH',49,False),
                               ('mZBg8DbyNdTrXcFL',3,None)]:
        url='https://www.warcraftlogs.com/reports/'+code
        started=time.monotonic()
        packet=BattleSource().query(parse_battle('/战斗分析 '+url+' 场次='+str(fight)))
        assert packet.get('status')=='ready',packet.get('status')
        assert packet['fightId']==fight
        if expected is not None:assert packet['fight']['kill']==expected
        texts={kind:format_battle(packet,kind) for kind in ('battle_summary','battle_good','battle_review')}
        assert all(len(text)<=1200 and len(markdown_parts(text))==1 for text in texts.values())
        assert len(packet['good'])<=3 and len(packet['review'])<=3
        assert all(row.get('evidence') for row in packet['good']+packet['review'])
        if fight==49:assert packet['deaths'] and packet['review']
        results.append({'packet':packet,'messages':texts,'elapsedSeconds':round(time.monotonic()-started,3)})
    output={'root':args.root,'realPublicSource':True,'qqMessagesSent':0,'modelCalls':0,'results':results}
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':args.output,'cases':[{'fightId':r['packet']['fightId'],
        'kill':r['packet']['fight']['kill'],'coverage':r['packet']['coverage'],
        'deaths':len(r['packet']['deaths']),'good':len(r['packet']['good']),
        'review':len(r['packet']['review']),'characters':{k:len(v) for k,v in r['messages'].items()},
        'elapsedSeconds':r['elapsedSeconds']} for r in results]}))


if __name__=='__main__':main()
