"""Bounded benchmark development: select on validation, then audit a frozen holdout.

No model training or inference calls occur here. Each control has the same
scenario; conclusions concern these policies, not all possible agents.
"""
from dataclasses import asdict, replace
from pathlib import Path
import json
import statistics

from .agents import Baseline
from .runner import atomic_json, interval_by_seed, source_hash
from .v2 import Config, StationEnv

CONDITIONS = ('coordinator', 'local_worker', 'maintenance', 'no_messages', 'fixed_schedule',
              'focal_local_0', 'focal_local_1', 'focal_local_2', 'focal_local_3', 'misinformation')


def episode(config, seed, split, condition, schedule=None, capture=False):
    env = StationEnv('shared', communication='none' if condition == 'no_messages' else 'full', config=config)
    env.reset(seed, split)
    turns = []
    while env.phase != 'terminal':
        if condition == 'fixed_schedule':
            decisions = schedule[len(turns)] if len(turns) < len(schedule) else {s:{'action':'wait'} for s in range(4)}
        else:
            decisions = {}
            for seat in range(4):
                policy = condition if condition in ('local_worker','maintenance') else 'coordinator'
                if condition == f'focal_local_{seat}': policy = 'local_worker'
                if condition == 'misinformation' and seat == 3: policy = 'deceptive'
                decisions[seat] = Baseline(policy, seed+seat).respond(env.observe(seat), env.phase).decision
        turns.append(decisions)
        env.step(decisions)
    r = env.result()
    case = {'seed':seed, 'survived':r['survived'], 'delivered_value':r['delivered_value'],
            'shared_reward':r['rewards'][0], 'invalid':r['invalid_decisions'],
            'completed_orders':r['completed_orders'], 'failed_work_actions':r['failed_work_actions']}
    return (case, turns) if capture else case


def aggregate(cases):
    return {'scenarios':len(cases),
            **{key:statistics.mean(c[key] for c in cases) for key in cases[0] if key != 'seed'},
            'positive_delivery_rate':statistics.mean(c['delivered_value'] > 0 for c in cases),
            'delivery_ci95':interval_by_seed({c['seed']:[c['delivered_value']] for c in cases})}


def paired_gain(reference, control):
    if [c['seed'] for c in reference] != [c['seed'] for c in control]:
        raise ValueError('paired scenarios must match')
    differences = {a['seed']:[a['delivered_value']-b['delivered_value']] for a,b in zip(reference,control)}
    return {'mean':statistics.mean(v[0] for v in differences.values()), 'ci95':interval_by_seed(differences)}


def select_candidate(rows):
    """Predeclared viability gates; choose longest viable horizon, never a model order."""
    eligible = [r for r in rows if r['reference']['survived'] >= .95
                and r['reference']['positive_delivery_rate'] >= .95 and r['reference']['invalid'] == 0
                and r['paired_gain']['ci95'] is not None and r['paired_gain']['ci95'][0] > 0]
    return max(eligible, key=lambda r:r['config']['rounds']) if eligible else None


def research(out, *, validation_seeds=20, test_seeds=100, test_start=40000, tiers=('standard','hard','extreme')):
    if type(validation_seeds) is not int or validation_seeds < 2 or type(test_seeds) is not int or test_seeds < 2:
        raise ValueError('at least two scenarios per split required')
    if type(test_start) is not int or test_start < 0 or not tiers or len(set(tiers)) != len(tiers):
        raise ValueError('invalid seed range or candidate tiers')
    configs = {tier:replace(Config.tier(tier), workload='joint') for tier in tiers}
    out = Path(out)
    if out.exists() and any(out.iterdir()): raise ValueError('research output must be empty; use a new directory')
    out.mkdir(parents=True, exist_ok=True)
    manifest = {'source_hash':source_hash(), 'protocol':'station-v2', 'workload':'joint',
                'candidates':{k:asdict(v) for k,v in configs.items()},
                'validation_seeds':list(range(validation_seeds)), 'test_seeds':list(range(test_start,test_start+test_seeds)),
                'selection':'Longest horizon with >=95% reference survival and positive delivery, zero reference invalid actions, and positive lower paired delivery bootstrap bound versus local_worker on validation only.',
                'holdout_conditions':CONDITIONS, 'fixed_schedule_source':{'split':'train','seed':0},
                'note':'Scripted controls only; no LLM calls, no RL training, no automatic model ranking or recurring job.'}
    atomic_json(out/'manifest.json',manifest)
    candidates = []
    for tier,config in configs.items():
        cases = {policy:[episode(config,s,'validation',policy) for s in range(validation_seeds)]
                 for policy in ('coordinator','local_worker')}
        row = {'tier':tier, 'config':asdict(config), 'reference':aggregate(cases['coordinator']),
               'control':aggregate(cases['local_worker']), 'paired_gain':paired_gain(cases['coordinator'],cases['local_worker'])}
        candidates.append(row)
        atomic_json(out/f'validation-{tier}.json', {'summary':row, 'cases':cases})
        print(json.dumps({'stage':'validation','tier':tier,'reference':row['reference'],'paired_gain':row['paired_gain']}),flush=True)
    chosen = select_candidate(candidates)
    # Freeze selection on disk BEFORE evaluating any test scenarios.
    atomic_json(out/'selection.json', {'candidates':candidates,'selected':chosen})
    if chosen is None:
        result = {'status':'no_candidate_passed_validation','manifest':manifest,'candidates':candidates,'holdout':None}
        atomic_json(out/'research.json',result)
        return result
    config = Config(**chosen['config'])
    _,schedule = episode(config,0,'train','coordinator',capture=True)
    holdout = {}
    for condition in CONDITIONS:
        cases = [episode(config,s,'test',condition,schedule) for s in range(test_start,test_start+test_seeds)]
        holdout[condition] = cases
        atomic_json(out/f'test-{condition}.json', {'summary':aggregate(cases),'cases':cases})
        print(json.dumps({'stage':'test','condition':condition,**aggregate(cases)}),flush=True)
    reference = holdout['coordinator']
    result = {'status':'holdout_complete','manifest':manifest,'selected':chosen,
              'holdout':{k:aggregate(v) for k,v in holdout.items()},
              'paired_delivery_gain':{k:paired_gain(reference,v) for k,v in holdout.items() if k != 'coordinator'},
              'limitations':['Policy ablations do not establish causal necessity for every possible strategy.',
                             'The matching bound is optimistic, not a full-game optimum.',
                             'No LLM model separation or incentive adaptation has been measured.',
                             'Published holdout seeds become development data for subsequent revisions. Do not retune this run on its holdout.']}
    result['holdout_gates'] = {
        'reference_viable':result['holdout']['coordinator']['survived'] >= .95 and result['holdout']['coordinator']['positive_delivery_rate'] >= .95,
        'reference_legal':result['holdout']['coordinator']['invalid'] == 0,
        'maintenance_earns_no_delivery_reward':all(c['shared_reward'] <= 0 and c['delivered_value'] == 0 for c in holdout['maintenance']),
        'coordination_delivery_gain':result['paired_delivery_gain']['local_worker']['ci95'][0] > 0,
        'blind_schedule_delivery_gain':result['paired_delivery_gain']['fixed_schedule']['ci95'][0] > 0,
    }
    atomic_json(out/'research.json',result)
    return result
