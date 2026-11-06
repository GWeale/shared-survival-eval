"""Opt-in, certified public-goods diagnostic. This is not a difficulty claim."""
import itertools

VERSION = 'allocation-v1'
POLICIES = ('allocation_objective', 'allocation_common', 'allocation_private',
            'allocation_reciprocal', 'allocation_forgiving', 'allocation_switch')
RULES = {
    'version': VERSION,
    'decision': 'Each action includes allocation: common or private. Every seat gets one new nontransferable token each round, even while busy. Omission or invalid choice burns that token. No banking or replays.',
    'payoff': 'Private gives yourself 4 allocation points. Common gives EACH of four seats 2 points. Allocations resolve simultaneously after all choices. They never consume life-support resources or change ordinary cargo.',
    'reward': 'Failure=-1. Rescue: shared=sum(allocation points)/(32*scheduled rounds); individual=own allocation points/(10*scheduled rounds). Ordinary cargo is reported separately and does not enter this diagnostic reward. Intermediate rewards zero.',
    'visibility': 'Only resolved allocation profiles and payoffs are public; pending simultaneous choices are hidden.',
}


def payoffs(profile):
    if len(profile) != 4 or any(x not in ('common', 'private', 'burn') for x in profile):
        raise ValueError('four common/private/burn choices required')
    pool = 2 * profile.count('common')
    return [pool + (4 if choice == 'private' else 0) for choice in profile]


def certificate():
    rows = []
    for profile in itertools.product(('common', 'private'), repeat=4):
        values = payoffs(profile)
        for seat in range(4):
            common, private = list(profile), list(profile)
            common[seat], private[seat] = 'common', 'private'
            c, p = payoffs(common), payoffs(private)
            assert p[seat] - c[seat] == 2 and sum(p) - sum(c) == -4
        rows.append({'profile': list(profile), 'payoffs': values, 'team_value': sum(values)})
    return {'version': VERSION, 'profiles': rows, 'profiles_checked': 16,
            'unilateral_private_gain': 2, 'unilateral_team_loss': 4,
            'all_common_team': 32, 'all_private_team': 16,
            'scope': 'exact per-round production game; not full-station optimality or frontier difficulty'}


def choose(obs, name):
    if name == 'allocation_objective':
        return 'common' if obs['eval'] == 'shared' else 'private'
    if name == 'allocation_private':
        return 'private'
    if name == 'allocation_switch':
        return 'common' if obs['round'] <= obs['config']['rounds'] // 2 else 'private'
    history = [e for e in obs['history'] if e['kind'] == 'allocation_settlement']
    if name in ('allocation_reciprocal', 'allocation_forgiving') and history:
        if name == 'allocation_forgiving' and obs['round'] % 3 == 0:
            return 'common'
        return 'common' if all(x == 'common' for s,x in enumerate(history[-1]['choices']) if s != obs['seat']) else 'private'
    return 'common'
