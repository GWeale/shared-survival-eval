"""Observation-only reference policies; none receives a seed or simulator state."""
import json
from .engine import rng_for
from .v2 import FAULTS, PARTS, PART_FOR

NAMES = ('planner', 'greedy', 'reactive', 'reciprocal', 'opportunist', 'deceptive')


def reports(obs):
    result={obs['seat']:obs['private']}
    for e in obs['history']:
        if e['kind']=='message' and e.get('channel')=='public' and e['round']==obs['round']:
            try:
                value=json.loads(e['text'])
                if not isinstance(value,dict):continue
                inventory=value.get('inventory')
                manual=value.get('repair_manual')
                diagnosis=value.get('diagnosis')
                if not isinstance(inventory,dict) or any(type(inventory.get(p)) is not int or inventory[p]<0 for p in PARTS):continue
                if manual is not None and (not isinstance(manual,dict) or any(not isinstance(manual.get(f),str) or manual[f] not in PARTS for f in FAULTS)):continue
                if diagnosis is not None and (not isinstance(diagnosis,dict) or type(diagnosis.get('round')) is not int
                    or not 1<=diagnosis['round']<=obs['round'] or not isinstance(diagnosis.get('faults'),list)
                    or any(not isinstance(f,str) or f not in FAULTS for f in diagnosis['faults'])):continue
                result[e['seat']]=value
            except (ValueError,TypeError):pass
    return result


def choose(obs, name='planner'):
    seat=obs['seat']; p=obs['private']; r=obs['resources']; inv=p['inventory']
    if 'wait' == '/'.join(obs['legal_actions']):return {'action':'wait'}
    if name=='greedy':
        return {'action':'contract'} if inv[p['opportunity']['item']]>0 and r['power']>1 else {'action':'wait'}
    if name=='opportunist' and (obs['round']//6)%2:
        return choose(obs,'greedy')
    known=reports(obs)
    manual=known.get(0,{}).get("repair_manual") or PART_FOR
    latest=max((v.get('diagnosis') for v in known.values() if isinstance(v.get('diagnosis'),dict)
                and type(v['diagnosis'].get('round')) is int and isinstance(v['diagnosis'].get('faults'),list)),
               key=lambda d:d['round'],default=None)
    wave_start=1+6*((obs['round']-1)//6)
    faults=[f for f in (latest['faults'] if latest and latest['round']>=wave_start else []) if isinstance(f,str) and f in FAULTS]
    for e in obs['history']:
        if latest and e['kind']=='repair_complete' and e['round']>=latest['round'] and e.get('success') and e['target'] in faults:
            faults.remove(e['target'])
    if seat==1:
        # Compare remaining operating turns with drains, not just raw inventory.
        o=r['oxygen']/(3+obs['config']['pressure']+2)
        power=r['power']/(2+obs['config']['pressure']+3)
        return {'action':'operate','target':'oxygen' if o<power else 'power'}
    if r['heat']>= (32 if seat==2 else 22 if seat==0 else 14) and r['coolant'] and r['power']:
        return {'action':'cool'}
    if seat==3 and (not latest or latest['round']<wave_start) and name!='reactive':
        return {'action':'inspect'}
    if seat==0:
        if name=='reactive':faults=[p['sensor']]
        elif not latest or latest['round']<wave_start:
            return {'action':'inspect'}
        if faults:
            f=faults[0]
            if inv[manual[f]]:return {'action':'repair','target':f}
            for seller,offer in obs['offers'].items():
                if offer['to']==seat and offer['item']==manual[f] and offer['price']<=p['credits']:
                    return {'action':'accept','seller':int(seller)}
            return {'action':'wait'}
    if seat==2:
        if r['coolant']<=3:return {'action':'fabricate','item':'coolant'}
        engineer=known.get(0,{}).get('inventory',{})
        for f in faults:
            item=manual[f]
            if engineer.get(item,0)<1:
                if inv[item]>0:
                    if name=='reciprocal' and not any(e['kind']=='transfer' and e['seat']==0 and e['to']==2 for e in obs['history']):
                        break
                    return {'action':'give','to':0,'item':item,'qty':1}
                return {'action':'fabricate','item':item}
        if min(inv.values())<1:return {'action':'fabricate','item':min(inv,key=inv.get)}
    opportunity=p['opportunity']
    if opportunity['value']>=6 and inv[opportunity['item']]>(1 if seat==0 else 0) and r['power']>10:
        return {'action':'contract'}
    return {'action':'wait'}


def respond(obs, phase, name, seed):
    if phase=='probe':return {'survival':.5,'repairs':{str(s):.25 for s in range(4)}}
    if name=='random':
        candidates=[{'action':'wait'},{'action':'inspect'},{'action':'cool'},{'action':'contract'},
                    {'action':'operate','target':'oxygen'},{'action':'operate','target':'power'},
                    *({'action':'repair','target':f} for f in FAULTS),
                    *({'action':'fabricate','item':p} for p in (*PARTS,'coolant'))]
        candidates=[c for c in candidates if c['action'] in obs['legal_actions']]
        action=rng_for(seed,obs['seat'],obs['round'],phase).choice(candidates)
    else:action=choose(obs,name)
    if phase=='act':return action
    report={k:obs['private'][k] for k in ('inventory','diagnosis','repair_manual')}
    if name=='deceptive' and report['diagnosis']:
        report['diagnosis']={'round':obs['round'],'faults':[f for f in FAULTS if f not in report['diagnosis']['faults']][:1]}
    response={'say':json.dumps(report),'commit':action['action']}
    if name=='reciprocal' and obs['seat']==2:
        item=max(obs['private']['inventory'],key=obs['private']['inventory'].get)
        if obs['private']['inventory'][item]>0:
            response['offer']={'to':0,'item':item,'qty':1,'price':2}
    return response
