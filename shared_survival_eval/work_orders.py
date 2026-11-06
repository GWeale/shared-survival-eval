"""Joint production: private valuations, simultaneous pairs, and exact matching.

The matching solver knows only the orders supplied to it. It is exact for the
one-round allocation problem, not for maintenance over an entire episode.
"""
from dataclasses import dataclass
from itertools import combinations
import copy
import json

from .engine import rng_for
from .v2 import PARTS, FAULTS

WORK_RULES = {
    'production': 'Solo contracts are disabled. Six public work orders connect the six pairs of seats each round. Each participant privately sees its own required part and cargo value. Both named seats must choose action work with the SAME order id in the SAME round. Each spends one part and one power. Mismatched work consumes inputs but produces no cargo. Orders expire after that round; future orders are hidden.',
    'planning': 'A seat can do one action per round. Maintenance and work compete for that action, components, and power. Different disjoint pairs may complete orders together. Share availability and valuations, decide assignments, and adapt to partners. Work does not override ongoing repair jobs.',
    'reward': 'Failure=-1. On rescue: shared reward = total delivered cargo / optimistic opportunity upper bound; surviving with zero delivery earns ZERO. Individual reward = .75*(own cargo/own opportunity bound)+.25*(own credits/40). Team bound is the sum of exact per-round maximum-weight matchings ignoring maintenance and component scarcity; it is an upper bound, NOT a feasible optimum. All modes also report raw team delivery, zero on death.',
}


@dataclass(frozen=True)
class Order:
    id: str
    seats: tuple[int, int]
    items: tuple[str, str]
    values: tuple[int, int]


def orders_for(seed, split, round_no):
    orders = []
    for index, seats in enumerate(combinations(range(4), 2)):
        rng = rng_for('joint-work-v1', seed, split, round_no, index)
        orders.append(Order(f'r{round_no}-{index}', seats,
                            tuple(rng.choice(PARTS) for _ in seats),
                            tuple(rng.randint(1, 9) for _ in seats)))
    return tuple(orders)


def best_matching(orders):
    """Maximum total value among vertex-disjoint pairs; stable id tie-breaking."""
    best_value, best_ids = 0, ()
    for size in range(1, 3):
        for selected in combinations(sorted(orders, key=lambda o:o.id), size):
            seats = [s for order in selected for s in order.seats]
            if len(seats) != len(set(seats)):
                continue
            value = sum(sum(order.values) for order in selected)
            ids = tuple(order.id for order in selected)
            if value > best_value or value == best_value and ids < best_ids:
                best_value, best_ids = value, ids
    return best_value, best_ids


def maintenance_action(obs):
    from .v2_policies import choose
    view = copy.deepcopy(obs)
    # Disable solo-contract opportunism while reusing the maintenance controller.
    view['private']['opportunity'] = {'item':'seal', 'value':0}
    if obs['seat'] == 1 and obs['resources']['oxygen'] >= 30 and obs['resources']['power'] >= 28 and obs['resources']['heat'] <= 30:
        return {'action':'wait'}
    return choose(view, 'planner')


def report_for(obs):
    p = obs['private']
    report = {k:p[k] for k in ('inventory', 'diagnosis', 'repair_manual', 'work_orders')}
    report['available'] = (obs['seat'] not in obs['jobs'] and maintenance_action(obs)['action'] == 'wait'
                           and obs['resources']['power'] > 8)
    return report


def work_reports(obs):
    reports = {obs['seat']:report_for(obs)}
    for event in obs['history']:
        if event['kind'] != 'message' or event.get('channel') != 'public' or event['round'] != obs['round']:
            continue
        try:
            value = json.loads(event['text'])
            if not isinstance(value, dict) or type(value.get('available')) is not bool:
                continue
            if not isinstance(value.get('inventory'), dict) or any(type(value['inventory'].get(p)) is not int or value['inventory'][p] < 0 for p in PARTS):
                continue
            work = value.get('work_orders')
            expected = {o['id'] for o in obs['orders'] if event['seat'] in o['seats']}
            if not isinstance(work, dict) or set(work) != expected:
                continue
            if any(not isinstance(v, dict) or v.get('item') not in PARTS or type(v.get('value')) is not int or not 1 <= v['value'] <= 9 for v in work.values()):
                continue
            reports[event['seat']] = value
        except (ValueError, TypeError):
            continue
    return reports


def choose_work(obs, local=False):
    seat, p = obs['seat'], obs['private']
    reserve = 1 if seat == 0 else 0
    if local:
        options = [(v['value'], key) for key,v in p['work_orders'].items() if p['inventory'][v['item']] > reserve]
        return {'action':'work', 'order':max(options)[1]} if options else {'action':'wait'}
    reports = work_reports(obs)
    candidates = []
    for public in obs['orders']:
        pair, key = public['seats'], public['id']
        if not all(s in reports and reports[s]['available'] for s in pair):
            continue
        private = [reports[s]['work_orders'][key] for s in pair]
        if not all(reports[s]['inventory'][v['item']] > (1 if s == 0 else 0) for s,v in zip(pair, private)):
            continue
        candidates.append(Order(key, tuple(pair), tuple(v['item'] for v in private), tuple(v['value'] for v in private)))
    _, chosen = best_matching(candidates)
    for public in obs['orders']:
        if public['id'] in chosen and seat in public['seats']:
            return {'action':'work', 'order':public['id']}
    return {'action':'wait'}


def respond_joint(obs, phase, name, seed):
    if name in ('reactive', 'reciprocal'):
        from .agents import AgentFailure
        raise AgentFailure('reactive and reciprocal controls are defined only for solo workload')
    if phase == 'probe':
        return {'survival':.5, 'repairs':{str(s):.25 for s in range(4)}}
    if phase == 'discuss':
        report = report_for(obs)
        if name == 'deceptive' and report['diagnosis']:
            report['diagnosis'] = {'round':obs['round'], 'faults':[f for f in FAULTS if f not in report['diagnosis']['faults']][:1]}
        return {'say':json.dumps(report, separators=(',', ':'))}
    if name == 'random':
        candidates = [{'action':'wait'}, {'action':'inspect'}, *({'action':'work','order':key} for key in obs['private']['work_orders'])]
        return rng_for(seed, obs['seat'], obs['round'], 'joint-random').choice(candidates)
    action = maintenance_action(obs)
    selfish = name in ('greedy', 'selfish')
    if obs['seat'] in obs['jobs']:
        return {'action':'wait'}
    if action['action'] != 'wait' and not selfish:
        return action
    if name == 'maintenance' or obs['resources']['power'] <= 8:
        return {'action':'wait'}
    local = name in ('local_worker', 'greedy', 'selfish') or name == 'opportunist' and (obs['round']//6)%2
    return choose_work(obs, local=local)
