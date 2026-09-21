"""Verify actual t=0 state and aggregate independent phase iterations."""
import math
from copy import deepcopy
from statistics import mean, stdev
from server.app.simulation.phase_state import number, token


def _fail():raise ValueError('SIMC_PHASE_STATE_MISMATCH')


def _rows(value, maximum=4096):
    if not isinstance(value,list) or len(value)>maximum:_fail()
    return value


def _amount(value):
    return number(value,0,1e18)


def initial_snapshot(actor):
    rows=_rows(actor.get('collected_data',{}).get('action_sequence_precombat'))
    if len(rows)!=1 or rows[0].get('name')!='snapshot_stats' or rows[0].get('time')!=0:_fail()
    return rows[0]


def _buffs(row):
    result={}
    for b in _rows(row.get('buffs',[]),256):
        name=token(b.get('name'))
        if name in result:_fail()
        result[name]={'stacks':_amount(b.get('stacks')), 'remains':(None if b.get('remains') == -9223372036854776.0 else _amount(b.get('remains',0))), 'spellId':int(_amount(b.get('id',0)))}
    return result


def inspect_iteration(actor, scenario):
    initial=initial_snapshot(actor);state=scenario['initialState'];cd=actor['collected_data']
    duration=scenario['measurement']['durationSeconds']
    if abs(_amount(cd.get('fight_length',{}).get('mean'))-duration)>.01:_fail()
    resources=initial.get('resources',{});maximum=initial.get('resources_max',{})
    actual_resources={}
    for name,wanted in state['resources'].items():
        observed=_amount(resources.get(name));cap=_amount(maximum.get(name))
        if cap<=0:_fail()
        expected=cap if wanted=='max' else wanted
        if abs(observed-expected)>.02 or expected>cap:_fail()
        actual_resources[name]={'value':observed,'maximum':cap}
    buffs=_buffs(initial)
    for name,wanted in state['buffs'].items():
        b=buffs.get(name)
        if not b or b['stacks']!=wanted['stacks']:_fail()
        if b['remains'] is None:_fail()
        if wanted['remainingSeconds']!='full' and abs(b['remains']-wanted['remainingSeconds'])>.02:_fail()
        if b['remains']<=0:_fail()
    cds={c['name']:c for c in _rows(initial.get('cooldowns',[]),256)}
    for name,wanted in state['cooldowns'].items():
        c=cds.get(name)
        # The engine serializes max charges here: multi-charge restoration is not supported.
        if not c or c.get('stacks')!=1 or abs(_amount(c.get('remains'))-wanted)>.02:_fail()
    sequence=[]; last=0.0; present=set(buffs)
    for ordinal,row in enumerate(_rows(cd.get('action_sequence'))):
        t=_amount(row.get('time'))
        if t<last or t>duration+.01:_fail()
        last=t
        if 'name' not in row:continue
        if row.get('queue_failed') is True:_fail()
        name=token(row['name']); bs=_buffs(row);present.update(bs)
        sequence.append({'eventIndex':ordinal,'time':t,'name':name,'spellId':int(_amount(row.get('id',0))),
                         'buffs':bs, 'resources':{token(k):_amount(v) for k,v in row.get('resources',{}).items()}})
    if not sequence:_fail()
    for b in _rows(actor.get('buffs',[]),256)+_rows(actor.get('buffs_constant',[]),256):
        if _amount(b.get('start_count',0))>0:present.add(token(b.get('name')))
    actions=[]
    for condition in scenario['measurement']['actions']:
        rows=[r for r in sequence if r['name']==condition['action']]
        actions.append({**condition,'casts':len(rows),**({'withBuff':sum(condition['buff'] in r['buffs'] for r in rows)} if 'buff' in condition else {})})
    overflow={}
    for gain in _rows(actor.get('gains',[]),256):
        for resource,value in gain.items():
            if resource=='name':continue
            token(resource)
            if not isinstance(value,dict):_fail()
            overflow[resource]=overflow.get(resource,0)+_amount(value.get('overflow',0))
    assertions=[];checks=scenario['assertions']
    opening=checks.get('openingActions',[])
    # Ignore utility/item/proc actions not named in this explicit order constraint.
    observed=[r['name'] for r in sequence if r['name'] in opening][:len(opening)]
    if opening:assertions.append({'kind':'openingActions','expected':opening,'observed':observed,'satisfied':opening==observed})
    for buff in checks.get('requiredBuffs',[]):
        assertions.append({'kind':'requiredBuff','buff':buff,'satisfied':buff in present})
    for resource,limit in checks.get('maxResourceOverflow',{}).items():
        if resource not in maximum:_fail()
        assertions.append({'kind':'maxResourceOverflow','resource':resource,'observed':overflow.get(resource,0),'maximum':limit,'satisfied':overflow.get(resource,0)<=limit})
    damage=_amount(cd.get('compound_dmg',{}).get('mean'))
    native_dps=_amount(cd.get('dps',{}).get('mean'))
    if damage<=0 or not math.isclose(damage/duration,native_dps,rel_tol=1e-6):_fail()
    return {'status':'satisfied' if all(c['satisfied'] for c in assertions) else 'violated',
            'initialState':{'resources':actual_resources,'buffs':{k:buffs[k] for k in state['buffs']},
                            'cooldowns':{k:cds[k]['remains'] for k in state['cooldowns']}},
            'damage':damage,'actions':actions,'resourceOverflow':overflow,
            'assertions':assertions,'sample':sequence[:40],'sampleTruncated':len(sequence)>40}


def distribution(values):
    if not values:_fail()
    values=[_amount(v) for v in values]
    n=len(values)
    # Conservative t critical values for small independent batches (95% two-sided).
    critical=12.706 if n==2 else 4.303 if n==3 else 3.182 if n<=5 else 2.776 if n<=10 else 2.262 if n<=20 else 2.093 if n<=32 else 2.04
    return {'mean':mean(values),'min':min(values),'max':max(values),
            'error95':critical*stdev(values)/math.sqrt(n) if n>1 else None}


def aggregate_phase(members, scenario, profile_sha256):
    if len(members)!=scenario['iterations']:_fail()
    duration=scenario['measurement']['durationSeconds']
    resources=sorted(set().union(*(m['resourceOverflow'] for m in members)))
    actions=[]
    for index,condition in enumerate(scenario['measurement']['actions']):
        actions.append({**condition,'casts':distribution([m['actions'][index]['casts'] for m in members]),
                        **({'withBuff':distribution([m['actions'][index]['withBuff'] for m in members])} if 'buff' in condition else {})})
    return {'status':'satisfied' if all(m['status']=='satisfied' for m in members) else 'violated',
            'profileSha256':profile_sha256,'iterations':len(members),'durationSeconds':duration,
            'initialState':members[0]['initialState'],'allInitialStatesVerified':True,
            'damage':distribution([m['damage'] for m in members]),
            'dps':distribution([m['damage']/duration for m in members]),'actions':actions,
            'resourceOverflow':{r:distribution([m['resourceOverflow'].get(r,0) for m in members]) for r in resources},
            'assertions':members[0]['assertions'],'failedIterations':sum(m['status']!='satisfied' for m in members),
            'sample':members[0]['sample'],'sampleTruncated':members[0]['sampleTruncated'],
            'limitations':['Statistics cover every independent iteration; displayed action sequence is only the first iteration.',
                'withBuff counts buff presence at action execution, not confirmed damage amplification or buff consumption.',
                'Native precombat state restoration is experimental; hidden counters, pets, DoTs and proc history are not restored.',
                'Opening order checks the first occurrences among listed actions; other actions may occur between them.',
                'This is a fixed-time target experiment; encounter-specific damage modifiers are not modeled.']}


def aggregate_reports(reports, phase):
    """Average measured rows; leave non-composable crit percentages unknown."""
    result=deepcopy(reports[0]);n=len(reports)
    result['metric'].update(value=phase['dps']['mean'],error=phase['dps']['error95'])
    result['statistics'].update(iterations=phase['iterations'],fightLengthSeconds=phase['durationSeconds'],elapsedSeconds=phase.get('elapsedSeconds'))
    for section,fields in [('abilities',('amount','executions')),('buffs',('uptime',)),('resources',('gained','lost'))]:
        maps=[{r['name']:r for r in p[section]} for p in reports]
        names=set().union(*(m.keys() for m in maps));rows=[]
        for name in sorted(names):
            template=deepcopy(next(m[name] for m in maps if name in m))
            for field in fields:
                values=[m.get(name,{}).get(field,0) for m in maps]
                template[field]=sum(values)/n if all(type(v) in (int,float) for v in values) else None
            if section=='abilities':template['critPercent']=None
            rows.append(template)
        if section=='abilities':
            rows.sort(key=lambda r:r['amount'],reverse=True);total=sum(r['amount'] for r in rows)
            for row in rows:row['portion']=row['amount']/total*100 if total else None
        result[section]=rows[:256]
    return result


def aggregate_identity(identities, report):
    from server.app.simulation.report_identity import report_digest, validate_report_identity
    result={'schemaVersion':1,'reportSha256':report_digest(report)}
    for section in ('abilities','buffs'):
        names={}
        for identity in identities:
            for row in identity[section]:
                names.setdefault(row['token'],row)
        result[section]=[deepcopy(names[row['name']]) for row in report[section]]
    if not validate_report_identity(result,report):_fail()
    return result
