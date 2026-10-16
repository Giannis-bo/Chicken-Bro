"""Cloud-only real-source probe; sends no QQ messages and prints no credentials."""
import json
import os
from pathlib import Path
import subprocess
import time

from server.app.channels.qq_official.battle_source import BattleSource
from server.app.channels.qq_official.battle_commands import parse_battle,format_battle


def credentials():
    pid=subprocess.check_output(['systemctl','show','chickenbro-qq-official.service',
                                 '--property=MainPID','--value'],text=True).strip()
    for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
        if item.startswith(b'WOW_WARCRAFTLOGS_'):
            key,value=item.decode().split('=',1);os.environ[key]=value


if __name__=='__main__':
    credentials()
    results=[]
    for code,fight in [('mZBg8DbyNdTrXcFL',3),('QqrT6Nkg7jRBWCMH',49),('QqrT6Nkg7jRBWCMH',51)]:
        before=time.monotonic()
        packet=BattleSource().query(parse_battle('/战斗分析 https://www.warcraftlogs.com/reports/'+code+'?fight='+str(fight)))
        texts={kind:format_battle(packet,kind) for kind in ('battle_summary','battle_good','battle_review')}
        results.append({'code':code,'fight':fight,'seconds':round(time.monotonic()-before,2),
                        'packet':packet,'messages':texts})
        print(json.dumps({'code':code,'fight':fight,'status':packet.get('status'),
                          'coverage':packet.get('causalCoverage'),'calls':packet.get('sourceCalls'),
                          'seconds':results[-1]['seconds'],'lengths':{k:len(v) for k,v in texts.items()}},ensure_ascii=False),flush=True)
        if code=='mZBg8DbyNdTrXcFL':print(texts['battle_summary'],flush=True)
        assert packet['status']=='ready'
        assert all(len(v)<=1200 for v in texts.values())
        assert len(packet['review'])<=3
        if code=='mZBg8DbyNdTrXcFL':
            assert len(packet['causes'])==6,packet.get('gaps')
            assert {r['cause'] for r in packet['causes']} >= {'non_tank_melee','repeated_hits','over_max_health','dot_finisher'}
            assert all(s in texts['battle_summary'] for s in ('137.6万','116.3万','80.2万','152.5万','115.1万'))
        if fight==51:assert not packet['deaths'] and not packet['review']
    out=Path('/var/lib/chickenbro/qq-official/battle-depth-probe-'+str(os.getpid())+'.json')
    out.write_text(json.dumps({'qqMessagesSent':0,'modelCalls':0,'root':os.getcwd(),'results':results},ensure_ascii=False,indent=2))
    print('evidence='+str(out),flush=True)
