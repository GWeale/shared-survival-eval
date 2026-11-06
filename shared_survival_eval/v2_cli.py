"""V2 batch evaluation and private simultaneous-player sessions."""
import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

from .agents import Baseline, request_for
from .session_lock import serialized
from .runner import atomic_json, run_batch, source_hash
from .v2 import Config, StationEnv, TIERS


def restore(state):
    if state['source_hash']!=source_hash():raise ValueError('session source changed')
    env=StationEnv(state['mode'],state['communication'],Config(**state['config']))
    env.reset(state['seed'],state['split'])
    for frame in state['turns']:env.step({int(s):d for s,d in frame.items()})
    return env


def envelope(state, env, seat):
    if type(seat) is not int or seat not in range(4):raise ValueError('seat must be 0..3')
    if env.phase=='terminal':return {'done':True,'observation':env.observe(seat),'reward':env.result()['rewards'][seat]}
    token=hashlib.sha256(f"{state['source_hash']}:{state['seed']}:{state['mode']}:{state['config']}:{len(state['turns'])}:{seat}".encode()).hexdigest()[:24]
    return {'done':False,'waiting':str(seat) in state['pending'],'decision_id':token,**request_for(env.observe(seat),env.phase)}


@serialized
def create(path, *, mode='shared', seed=0, split='test', difficulty='standard', communication='full', focal=None, background='planner', workload='solo', allocation=False):
    if path.exists():raise ValueError('session already exists')
    if focal is not None and (type(focal) is not int or focal not in range(4)):raise ValueError('invalid focal seat')
    from .allocation import POLICIES
    if background not in (*POLICIES, 'planner','greedy','reactive','reciprocal','opportunist','deceptive','coordinator','local_worker','maintenance'):raise ValueError('invalid background')
    if workload == 'joint' and background in ('reactive','reciprocal'):
        raise ValueError('joint sessions require a joint-compatible background policy')
    config=replace(Config.tier(difficulty), workload=workload, allocation=allocation)
    env=StationEnv(mode,communication,config);env.reset(seed,split)
    state={'protocol':'station-v2','source_hash':source_hash(),'mode':mode,'seed':seed,'split':split,
           'communication':communication,'config':asdict(config),'focal':focal,'background':background,
           'turns':[],'pending':{},'accepted':{}}
    atomic_json(path,state)
    return {'created':True,'seats':list(range(4)) if focal is None else [focal]}


@serialized
def submit(path, seat, reply):
    state=json.loads(path.read_text());env=restore(state)
    if not isinstance(reply,dict) or set(reply)!={'decision_id','decision'}:raise ValueError('expected decision_id and decision')
    token=reply['decision_id']
    if not isinstance(token,str):raise ValueError('decision_id must be text')
    if state['focal'] is not None and state['focal']!=seat:raise ValueError('only focal seat accepts external input')
    if token in state['accepted']:
        prior=state['accepted'][token]
        if prior!={'seat':seat,'decision':reply['decision']}:raise ValueError('cannot revise accepted input')
        return envelope(state,env,seat)
    current=envelope(state,env,seat)
    if current['done'] or current['decision_id']!=token:raise ValueError('stale or wrong decision_id')
    state['pending'][str(seat)]=reply['decision']
    state['accepted'][token]={'seat':seat,'decision':reply['decision']}
    if state['focal'] is not None:
        for s in range(4):
            if s!=seat:state['pending'][str(s)]=Baseline(state['background'],0).respond(env.observe(s),env.phase).decision
    if len(state['pending'])==4:
        frame=state['pending'];env.step({int(s):d for s,d in frame.items()})
        state['turns'].append(frame);state['pending']={}
    atomic_json(path,state)
    return envelope(state,env,seat)


def main(argv=None, default_mode='shared'):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('allocation-certificate')
    audit=commands.add_parser('research')
    audit.add_argument('--out',type=Path,required=True)
    audit.add_argument('--validation-seeds',type=int,default=20)
    audit.add_argument('--test-seeds',type=int,default=100)
    audit.add_argument('--test-start',type=int,default=40000)
    run=commands.add_parser('run')
    run.add_argument('--plan',type=Path,required=True);run.add_argument('--out',type=Path,required=True)
    run.add_argument('--eval',choices=['shared','individual','both'],default=default_mode)
    run.add_argument('--difficulty',choices=TIERS,default='hard')
    run.add_argument('--allocation',action='store_true',help='enable allocation-v1 incentive diagnostic; requires joint workload')
    run.add_argument('--workload', choices=['solo','joint'], default='solo')
    run.add_argument('--seeds',type=int,default=100);run.add_argument('--seed-start',type=int,default=0)
    run.add_argument('--split',choices=['train','validation','test'],default='test')
    run.add_argument('--rotations',type=int,choices=range(1,5),default=4);run.add_argument('--repeats',type=int,default=1)
    run.add_argument('--communication',choices=['full','public','none'],default='full')
    run.add_argument('--probes',action='store_true');run.add_argument('--max-calls',type=int,default=1000000)
    run.add_argument('--enable-external',action='store_true');run.add_argument('--resume',action='store_true')
    for flag,kind in [('rounds',int),('repair-delay',int),('pressure',int),('sensor-accuracy',float),('integrity',int)]:run.add_argument('--'+flag,type=kind)
    curve=commands.add_parser('curve')
    curve.add_argument('--workload',choices=['solo','joint'],default='solo')
    curve.add_argument('--checkpoints',type=Path,required=True);curve.add_argument('--out',type=Path,required=True)
    curve.add_argument('--seeds',type=int,default=100);curve.add_argument('--seed-start',type=int,default=10000)
    curve.add_argument('--difficulty',choices=TIERS,default='hard');curve.add_argument('--rotations',type=int,choices=range(1,5),default=4)
    curve.add_argument('--max-calls',type=int,default=1000000);curve.add_argument('--enable-external',action='store_true');curve.add_argument('--resume',action='store_true')
    new=commands.add_parser('session-create');new.add_argument('state',type=Path)
    new.add_argument('--eval',choices=['shared','individual'],default=default_mode)
    new.add_argument('--allocation',action='store_true')
    new.add_argument('--workload', choices=['solo','joint'], default='solo')
    new.add_argument('--difficulty',choices=TIERS,default='hard');new.add_argument('--seed',type=int,default=0)
    new.add_argument('--split',choices=['train','validation','test'],default='test')
    new.add_argument('--communication',choices=['full','public','none'],default='full')
    new.add_argument('--focal',type=int,choices=range(4))
    from .allocation import POLICIES
    new.add_argument('--background',default='planner',choices=[*POLICIES, 'planner','greedy','reactive','reciprocal','opportunist','deceptive','coordinator','local_worker','maintenance'])
    for command in ('observe','submit','export'):
        p=commands.add_parser(command);p.add_argument('state',type=Path);p.add_argument('--seat',type=int,choices=range(4),required=True)
    try:
        args=parser.parse_args(argv)
        if args.command=='allocation-certificate':
            from .allocation import certificate
            print(json.dumps(certificate()));return 0
        if args.command=='research':
            from .v2_research import research
            result=research(args.out,validation_seeds=args.validation_seeds,test_seeds=args.test_seeds,test_start=args.test_start)
            print(json.dumps({'status':result['status'],'out':str(args.out),'gates':result.get('holdout_gates')}))
            return 0 if result['status']=='holdout_complete' and all(result['holdout_gates'].values()) else 2
        if args.command=='curve':
            from .v2_experiments import learning_curve
            if args.seeds<1 or args.seed_start<0:raise ValueError('invalid seed range')
            result=learning_curve(json.loads(args.checkpoints.read_text()),args.out,seeds=list(range(args.seed_start,args.seed_start+args.seeds)),
                difficulty=args.difficulty,rotations=args.rotations,max_calls=args.max_calls,enable_external=args.enable_external,resume=args.resume,workload=args.workload)
            print(json.dumps({'checkpoints':len(result['rows']),'out':str(args.out)}))
            return 2 if any(row['errors'] for cp in result['rows'] for row in cp['rows']) else 0
        if args.command=='run':
            if args.seeds<1 or args.seed_start<0:raise ValueError('invalid seed range')
            config=asdict(Config.tier(args.difficulty))
            for key in config:
                if getattr(args,key) is not None:config[key]=getattr(args,key)
            Config(**config)
            result=run_batch(json.loads(args.plan.read_text()),args.out,list(range(args.seed_start,args.seed_start+args.seeds)),
                split=args.split,rotations=args.rotations,repeats=args.repeats,modes=('shared','individual') if args.eval=='both' else (args.eval,),
                communication=args.communication,probes=args.probes,max_calls=args.max_calls,enable_external=args.enable_external,resume=args.resume,
                protocol='station-v2',difficulty=args.difficulty,config=config)
            print(json.dumps({'out':str(args.out),'rows':[{k:r[k] for k in ('eval','crew','planned','completed','errors')} for r in result['rows']]}))
            return 2 if any(r['errors'] for r in result['rows']) else 0
        if args.command=='session-create':
            result=create(args.state,mode=args.eval,seed=args.seed,split=args.split,difficulty=args.difficulty,communication=args.communication,focal=args.focal,background=args.background,workload=args.workload,allocation=args.allocation)
        elif args.command=='submit':result=submit(args.state,args.seat,json.load(sys.stdin))
        else:
            state=json.loads(args.state.read_text());env=restore(state)
            result=envelope(state,env,args.seat) if args.command=='observe' else env.observe(args.seat)
        print(json.dumps(result,allow_nan=False));return 0
    except (ValueError,OSError,KeyError) as exc:
        print(f'Error: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
