"""Bounded, class-independent phase contract and native state compilation."""
import math
import re
from collections.abc import Mapping

PHASE_FIELDS = {'initialState', 'measurement', 'assertions'}
MAX_PHASE_ITERATIONS = 128
_TOKEN = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_]{0,79}\Z')
RESOURCES = frozenset(('health','mana','rage','focus','energy','combo_points','runic_power','rune','soul_shard','astral_power','holy_power','maelstrom','chi','insanity','fury','pain','essence'))


def token(value):
    if not isinstance(value,str) or not _TOKEN.fullmatch(value):raise ValueError('PHASE_INVALID')
    return value


def number(value, minimum=0, maximum=600):
    if type(value) not in (int,float) or not math.isfinite(value) or not minimum<=value<=maximum:raise ValueError('PHASE_INVALID')
    return value


def obj(value, allowed, maximum=32):
    if not isinstance(value,Mapping) or len(value)>maximum or set(value)-set(allowed):raise ValueError('PHASE_INVALID')
    return value


def normalize_phase(scenario):
    if not PHASE_FIELDS.intersection(scenario):return {}
    measurement=obj(scenario.get('measurement'), {'durationSeconds','actions'})
    duration=number(measurement.get('durationSeconds'),20,120)
    if type(duration) is not int:raise ValueError('PHASE_INVALID')
    if scenario.get('maxTime',duration)!=duration or scenario.get('varyCombatLength',0)!=0 or scenario.get('targetError',0)!=0:
        raise ValueError('PHASE_CONFLICTING_WINDOW')
    count=scenario.get('iterations',32)
    if type(count) is not int or not 1<=count<=MAX_PHASE_ITERATIONS:raise ValueError('PHASE_ITERATIONS_INVALID')
    lists=scenario.get('actionLists',{})
    if not isinstance(lists,Mapping) or not lists.get('default'):raise ValueError('PHASE_ACTION_LIST_REQUIRED')
    if 'precombat' in lists and lists['precombat']!=['snapshot_stats']:raise ValueError('PHASE_PRECOMBAT_UNSUPPORTED')
    if any(isinstance(a,str) and a.split(',',1)[0] in {'sequence','strict_sequence'} for actions in lists.values() if isinstance(actions,list) for a in actions):
        raise ValueError('PHASE_OPAQUE_SEQUENCE_UNSUPPORTED')
    state=obj(scenario.get('initialState',{}),{'resources','buffs','cooldowns'})
    resources=state.get('resources',{})
    obj(resources,RESOURCES)
    resources={k:('max' if v=='max' else number(v,0,10000000)) for k,v in resources.items()}
    buffs=state.get('buffs',{}); obj(buffs,buffs)
    result_buffs={}
    for name,b in buffs.items():
        token(name); obj(b,{'stacks','remainingSeconds'})
        stacks=b.get('stacks'); remaining=b.get('remainingSeconds')
        if type(stacks) is not int or not 1<=stacks<=100:raise ValueError('PHASE_INVALID')
        if remaining!='full':number(remaining,0.001,600)
        result_buffs[name]={'stacks':stacks,'remainingSeconds':remaining}
    cooldowns=state.get('cooldowns',{});obj(cooldowns,cooldowns)
    cooldowns={token(k):number(v,0.001,600) for k,v in cooldowns.items()}
    actions=measurement.get('actions',[])
    if not isinstance(actions,list) or len(actions)>16:raise ValueError('PHASE_INVALID')
    normalized_actions=[]
    for row in actions:
        obj(row,{'action','buff'});entry={'action':token(row.get('action'))}
        if 'buff' in row:entry['buff']=token(row['buff'])
        if entry in normalized_actions:raise ValueError('PHASE_INVALID')
        normalized_actions.append(entry)
    assertions=obj(scenario.get('assertions',{}),{'openingActions','requiredBuffs','maxResourceOverflow'})
    checks={}
    for key in ('openingActions','requiredBuffs'):
        if key in assertions:
            values=assertions[key]
            if not isinstance(values,list) or not 1<=len(values)<=16:raise ValueError('PHASE_INVALID')
            checks[key]=[token(v) for v in values]
    if 'maxResourceOverflow' in assertions:
        overflow=assertions['maxResourceOverflow'];obj(overflow,RESOURCES)
        checks['maxResourceOverflow']={k:number(v,0,10000000) for k,v in overflow.items()}
    return {'initialState':{'resources':resources,'buffs':result_buffs,'cooldowns':cooldowns},
            'measurement':{'durationSeconds':duration,'actions':normalized_actions},'assertions':checks,
            'maxTime':duration,'varyCombatLength':0.0,'iterations':count}


def compile_phase(state, resolved_resources=None):
    lines=[]
    resources=state.get('resources',{})
    resolved_resources=resolved_resources or {}
    for name,value in sorted(resources.items()):
        if value=='max':
            if name not in resolved_resources:continue  # Resolved by cloud preflight, never a magic number.
            value=resolved_resources[name]
        lines.append(f'initial_resource={name}={value:g}')
    for name,buff in sorted(state.get('buffs',{}).items()):
        lines.append(f'override.precombat_state=buff.{name}.stack={buff["stacks"]}')
        if buff['remainingSeconds']!='full':lines.append(f'override.precombat_state=buff.{name}.remains={buff["remainingSeconds"]:g}')
    for name,value in sorted(state.get('cooldowns',{}).items()):
        lines.append(f'override.precombat_state=cooldown.{name}={value:g}')
    return lines
