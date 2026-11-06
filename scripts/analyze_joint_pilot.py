"""Recompute pilot statistics from sanitized outcomes, using the standard library."""
import argparse
import json
from collections import Counter
from math import ceil
from pathlib import Path
from statistics import mean, stdev


def paired_summary(differences):
    """Exact empirical-bootstrap percentiles by integer-sum convolution."""
    n = len(differences)
    assert n and all(type(x) is int for x in differences)
    distribution = Counter({0: 1})
    weights = Counter(differences)
    for _ in range(n):
        next_distribution = Counter()
        for total, count in distribution.items():
            for value, weight in weights.items():
                next_distribution[total + value] += count * weight
        distribution = next_distribution
    draws = n ** n
    assert sum(distribution.values()) == draws

    def quantile(numerator):
        rank = ceil(draws * numerator / 1000)
        cumulative = 0
        for total, count in sorted(distribution.items()):
            cumulative += count
            if cumulative >= rank:
                return total / n
        raise AssertionError('Missing bootstrap quantile')

    return {'n_scenarios': n, 'differences': differences, 'mean': mean(differences),
            'sd': stdev(differences) if n > 1 else None,
            'ci95': [quantile(25), quantile(975)], 'bootstrap_samples': draws}


def summarize(data):
    games, controls = data['games'], data['controls']
    assert len(games) == 32 and len(controls) == 144
    assert len({(g['scenario'], g['role'], g['mode']) for g in games}) == 32
    assert all(g['completed'] and g['source_manifest_and_replay_passed'] and g['tool_boundary_passed'] for g in games)
    assert all(g['interface_decision_attempts'] == 72 for g in games)
    output = {'model': data['model'], 'roles': {}, 'controls': []}
    coordinator = {r['scenario']: r['team_delivered_value'] for r in controls if r['control'] == 'coordinator' and r['mode'] == 'shared'}
    for role in data['design']['roles']:
        role_games = [g for g in games if g['role'] == role]
        pairs = [{g['mode']: g for g in role_games if g['scenario'] == scenario} for scenario in range(1, 9)]
        diffs = [p['shared']['team_delivered_value'] - p['individual']['team_delivered_value'] for p in pairs]
        role_result = {'primary_shared_minus_individual': paired_summary(diffs), 'cells': {}}
        clean = [p for p in pairs if all(g['infrastructure_clean'] for g in p.values())]
        role_result['post_hoc_clean_pairs'] = paired_summary([p['shared']['team_delivered_value'] - p['individual']['team_delivered_value'] for p in clean])
        role_result['post_hoc_clean_pairs']['scenarios'] = [p['shared']['scenario'] for p in clean]
        # Planning approximation only: two-sided normal test, 80% power, delta=5.
        sd = role_result['primary_shared_minus_individual']['sd']
        role_result['rough_worlds_for_five_point_effect'] = ceil(((1.96 + 0.84) * sd / 5) ** 2)
        for mode in data['design']['reward_modes']:
            cell = sorted((g for g in role_games if g['mode'] == mode), key=lambda g: g['scenario'])
            actions, counts, messages = Counter(), Counter(), Counter()
            for game in cell:
                actions.update(game['actions']); counts.update(game['counts']); messages.update(game['message_fields'])
            role_result['cells'][mode] = {
                'n': len(cell), 'delivery': [g['team_delivered_value'] for g in cell],
                'mean_delivery': mean(g['team_delivered_value'] for g in cell),
                'mean_delivery_given_survival': mean(g['team_delivered_value'] for g in cell if g['survived']),
                'survived': sum(g['survived'] for g in cell),
                'mean_focal_reward': mean(g['focal_reward'] for g in cell),
                'mean_own_cargo': mean(g['own_cargo'] for g in cell),
                'mean_completed_orders': mean(g['completed_orders'] for g in cell),
                'mean_team_failed_work_actions': mean(g['team_failed_work_actions'] for g in cell),
                'actions': dict(actions), 'counts': dict(counts), 'message_fields': dict(messages),
                'exploratory_gain_over_coordinator': paired_summary([g['team_delivered_value'] - coordinator[g['scenario']] for g in cell]),
            }
        output['roles'][role] = role_result
    for kind, role in sorted({(c['control'], c['focal_role']) for c in controls}, key=str):
        group = sorted((c for c in controls if c['control'] == kind and c['focal_role'] == role and c['mode'] == 'shared'), key=lambda c: c['scenario'])
        output['controls'].append({'control': kind, 'focal_role': role, 'n_per_mode': len(group),
                                   'delivery': [c['team_delivered_value'] for c in group],
                                   'mean_delivery': mean(c['team_delivered_value'] for c in group),
                                   'survived': sum(c['survived'] for c in group),
                                   'mean_failed_work_actions': mean(c['failed_work_actions'] for c in group)})
    output['execution'] = {
        'scheduled': len(games), 'completed': sum(g['completed'] for g in games),
        'survived': sum(g['survived'] for g in games), 'incomplete': sum(not g['completed'] for g in games),
        'infrastructure_clean': sum(g['infrastructure_clean'] for g in games),
        'clean_fraction': mean(g['infrastructure_clean'] for g in games),
        'meets_90_percent_clean_target': mean(g['infrastructure_clean'] for g in games) >= 0.9,
        'network_error_episodes': sum(g['recorded_network_error'] for g in games),
        'application_restart_episodes': sum(g['recorded_application_restart'] for g in games),
        'interface_decision_attempts': sum(g['interface_decision_attempts'] for g in games),
        'submit_command_attempts': sum(g['submit_command_attempts'] for g in games),
        'strict_submit_attempt_cap_breaches': sum(not g['strict_submit_attempt_cap_met'] for g in games),
        'invalid_game_decisions': sum(g['counts']['focal_invalid_decisions'] for g in games),
        'explicit_silence': sum(g['counts']['explicit_silence'] for g in games),
        'maintenance_reports_parsed': sum(g['counts']['maintenance_report_parsed'] for g in games),
        'work_reports_parsed': sum(g['counts']['work_report_parsed'] for g in games),
        'discussion_decisions': sum(g['counts']['discussions'] for g in games),
        'provider_usage': None,
    }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[1] / 'docs/joint-pilot-data.json'
    parser.add_argument('--input', type=Path, default=default)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rendered = json.dumps(summarize(json.loads(args.input.read_text())), indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
