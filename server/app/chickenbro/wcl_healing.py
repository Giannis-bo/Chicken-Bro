"""Paired WCL Healing tables: top-level totals, compact spell breakdowns."""
from math import isfinite


def number(value):
    return type(value) in (int,float) and isfinite(value) and value >= 0


def project_healing(effective, raw):
    left = effective.get('data', {}) if isinstance(effective,dict) else {}
    right = raw.get('data', {}) if isinstance(raw,dict) else {}
    if not isinstance(left,dict):left={}
    if not isinstance(right,dict):right={}
    a,b=left.get('entries'),right.get('entries')
    valid = isinstance(a,list) and isinstance(b,list) and number(left.get('totalTime')) and left.get('totalTime')==right.get('totalTime') and left['totalTime']>0
    a=a if isinstance(a,list) else [];b=b if isinstance(b,list) else []
    def key(row):return (row.get('guid',row.get('id')),row.get('name'))
    valid = valid and all(isinstance(r,dict) and number(r.get('total')) for r in a+b)
    valid = valid and len({key(r) for r in a})==len(a) and len({key(r) for r in b})==len(b) and {key(r) for r in a}=={key(r) for r in b}
    totals=None
    if valid:
        effective_total,raw_total=sum(r['total'] for r in a),sum(r['total'] for r in b)
        raw_by_key={key(r):r['total'] for r in b}
        valid = all(raw_by_key[key(r)] >= r['total'] for r in a)
        if valid:
            seconds=left['totalTime']/1000
            totals={'effective':effective_total,'raw':raw_total,'overheal':raw_total-effective_total,
                    'effectiveHps':effective_total/seconds,'rawHps':raw_total/seconds}
    fields=('guid','id','name','type','total','overheal','totalReduced','hitCount','tickCount','critHitCount','critTickCount','uptime','composite')
    def compact(row,depth=0):
        result={k:row[k][:160] if isinstance(row[k],str) else row[k] for k in fields if k in row and (row[k] is None or isinstance(row[k],(str,int,float,bool)))}
        result['hitdetails']=[{k:d[k] for k in ('type','count','total','absorbOrOverheal','min','max') if k in d} for d in row.get('hitdetails',[])[:8] if isinstance(d,dict)] if isinstance(row.get('hitdetails',[]),list) else []
        if depth<1 and isinstance(row.get('subentries'),list):
            result['subentries']=[compact(c,depth+1) for c in row['subentries'][:16] if isinstance(c,dict)]
            result['subentriesTruncated']=len(row['subentries'])>16
        return result
    return {'complete':bool(valid),'totals':totals,'totalTimeMs':left.get('totalTime'),
        'entries':[compact(r) for r in b[:80] if isinstance(r,dict)],'rowsTruncated':len(b)>80,
        'coverage':'Paired Healing tables, identical fight/source/time filters. Effective includes credited absorbs; raw includes overheal. Sum top-level entries only, never add their subentries again.',
        'limitations':['Separate absorb totals are not inferred when the upstream table does not explicitly distinguish them. Spell hit/tick counts are logged healing impacts, not manual casts.',
                       'Raw rows and hitdetails use viewOptions=8. totalReduced is preserved as an upstream field, not relabelled as effective healing.']}
