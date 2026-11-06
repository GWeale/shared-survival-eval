import copy
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from shared_survival_eval.agents import AgentFailure, Baseline, CommandAgent, request_for
from shared_survival_eval.allocation import certificate, payoffs
from shared_survival_eval.runner import run_batch, run_episode, summarize
from shared_survival_eval.v2 import Config, StationEnv
from shared_survival_eval.v2_cli import create, envelope, restore, submit


def plan(name='allocation_objective'):
    return {'agents': {'a': {'type': 'baseline', 'name': name}}, 'crews': {'a': ['a']*4}}


def play(profile, mode='shared', enabled=True):
    env=StationEnv(mode, config=replace(Config.tier('intro'), workload='joint', allocation=enabled))
    env.reset(11); resources=[]
    while env.phase != 'terminal':
        decisions={s:Baseline('coordinator',0).respond(env.observe(s),env.phase).decision for s in range(4)}
        if env.phase=='act' and enabled:
            for s in range(4):decisions[s]['allocation']=profile[s]
        env.step(decisions)
        resources.append((env.oxygen,env.power,env.heat,env.coolant,env.integrity,copy.deepcopy(env.inventory)))
    return env, resources


class AllocationTests(unittest.TestCase):
    def test_all_profiles_certified_and_maintenance_independent(self):
        baseline, trajectory=play(['common']*4,enabled=False)
        self.assertEqual(certificate()['profiles_checked'],16)
        for profile in itertools.product(('common','private'),repeat=4):
            env, observed=play(profile)
            self.assertEqual(observed,trajectory)
            self.assertTrue(env.result()['survived'])
            self.assertEqual(env.allocation_opportunities,[6]*4)
            self.assertEqual(env.allocation_points,[6*v for v in payoffs(profile)])
            self.assertEqual(env.cargo,baseline.cargo)

    def test_every_visible_reward_instruction_uses_allocation_objective(self):
        env=StationEnv(config=replace(Config.tier('intro'),workload='joint',allocation=True))
        def reward_instructions(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key=='reward':yield item
                    else:yield from reward_instructions(item)
            elif isinstance(value,list):
                for item in value:yield from reward_instructions(item)
        for observation in env.reset().values():
            rewards=list(reward_instructions(observation))
            self.assertEqual(len(rewards),4)
            self.assertTrue(all(text==observation['reward'] for text in rewards))
            self.assertIn('allocation points',observation['reward'])

    def test_reward_mode_changes_only_rewards(self):
        shared,_=play(['private','common','common','common'])
        individual,_=play(['private','common','common','common'],'individual')
        self.assertEqual(shared.events,individual.events)
        self.assertEqual(shared.result()['rewards'],[.875]*4)
        self.assertEqual(individual.result()['rewards'],[1.,.6,.6,.6])

    def test_no_early_settlement_and_busy_engineer_eligible(self):
        env=StationEnv(config=replace(Config.tier('intro'),workload='joint',allocation=True));env.reset()
        env.step({s:{} for s in range(4)})
        self.assertEqual(env.allocation_points,[0]*4)
        env.jobs[0]={'target':'leak','remaining':2}
        obs=env.observe(0)
        self.assertEqual(obs['legal_actions'],['wait'])
        self.assertIn('allocation',request_for(obs,'act')['response_schema'])
        env.step({s:{'action':'wait','allocation':'common'} for s in range(4)})
        self.assertEqual(env.allocation_points,[8]*4)

    def test_invalid_fields_count_one_decision_and_burn_token(self):
        env=StationEnv(config=replace(Config.tier('intro'),workload='joint',allocation=True));env.reset()
        env.step({0:{'say':42,'private':{},'commit':42,'offer':{}},1:{},2:{},3:{}})
        self.assertEqual(env.invalid_count,1);self.assertEqual(env.invalid_events,4)
        env.step({s:{'action':'bad','allocation':'bad'} for s in range(4)})
        self.assertEqual(env.allocation_points,[0]*4)
        self.assertEqual(env.invalid_count,5);self.assertEqual(env.invalid_events,12)

    def test_objective_controls_oppose_without_survival_change(self):
        config=replace(Config.tier('intro'),workload='joint',allocation=True).__dict__
        records=[run_episode(plan(),'a',mode,7,protocol='station-v2',config=config) for mode in ('shared','individual')]
        self.assertTrue(all(r['result']['survived'] for r in records))
        self.assertEqual([r['result']['allocation_delivered_value'] for r in records],[192,96])
        self.assertEqual(records[0]['result']['cargo'],records[1]['result']['cargo'])
        contrasts={c['metric']:c for c in summarize(records)['paired_comparisons']}
        self.assertEqual(contrasts['shared_minus_individual_allocation_delivery']['mean'],96)


class ReliabilityTests(unittest.TestCase):
    def test_killed_lock_owner_releases_session_and_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';create(path,focal=0,workload='joint',allocation=True,background='allocation_common')
            state=json.loads(path.read_text());view=envelope(state,restore(state),0)
            reply={'decision_id':view['decision_id'],'decision':{}}
            code='import sys,time\nfrom shared_survival_eval.session_lock import locked\nwith locked(sys.argv[1]):\n print("ready",flush=True)\n time.sleep(60)'
            child=subprocess.Popen([sys.executable,'-c',code,str(path.with_suffix('.json.lock'))],stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),'ready')
                with self.assertRaisesRegex(ValueError,'locked'):submit(path,0,reply)
                child.kill();child.wait(timeout=5)
            finally:
                if child.poll() is None:child.kill();child.wait()
                child.stdout.close()
            first=submit(path,0,reply);self.assertEqual(submit(path,0,reply),first)
            self.assertEqual(len(json.loads(path.read_text())['turns']),1)
            with self.assertRaisesRegex(ValueError,'revise'):submit(path,0,{**reply,'decision':{'say':'changed'}})

    def test_concurrent_creates_have_one_winner(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json'
            def attempt(_):
                try:create(path);return True
                except ValueError:return False
            with ThreadPoolExecutor(4) as pool:self.assertEqual(sum(pool.map(attempt,range(4))),1)
            restore(json.loads(path.read_text()))

    def test_simultaneous_submissions_preserve_both_seats(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';create(path)
            state=json.loads(path.read_text());env=restore(state)
            replies=[{'decision_id':envelope(state,env,s)['decision_id'],'decision':{'say':str(s)}} for s in range(4)]
            def attempt(s):
                try:submit(path,s,replies[s])
                except ValueError as exc:self.assertIn('locked',str(exc))
            with ThreadPoolExecutor(4) as pool:list(pool.map(attempt,range(4)))
            for s in range(4):submit(path,s,replies[s])
            state=json.loads(path.read_text());self.assertEqual(len(state['turns']),1)
            self.assertEqual(state['turns'][0],{str(s):{'say':str(s)} for s in range(4)})

    def test_both_output_streams_are_bounded(self):
        obs=StationEnv().reset()[0]
        for stream in ('stdout','stderr'):
            command=[sys.executable,'-c',f'import sys;sys.{stream}.write("x"*2000000);sys.{stream}.flush()']
            with self.assertRaises(AgentFailure):CommandAgent(command,timeout=2).respond(obs,'act')


class SummaryTests(unittest.TestCase):
    def records(self):
        return [run_episode(plan('coordinator'),'a',m,0,protocol='station-v2',config=replace(Config.tier('intro'),workload='joint').__dict__) for m in ('shared','individual')]

    def test_delivery_pairing_and_missing_outcomes(self):
        records=self.records();records[0]['result']['cargo']=[10]*4;records[1]['result']['cargo']=[2]*4
        contrast=next(c for c in summarize(records)['paired_comparisons'] if c['metric']=='shared_minus_individual_delivered_value')
        self.assertEqual(contrast['mean'],32)
        records[0]['result']['survived']=False
        contrast=next(c for c in summarize(records)['paired_comparisons'] if c['metric']=='shared_minus_individual_delivered_value')
        self.assertEqual(contrast['mean'],-8)
        records[0]['status']='running';summary=summarize(records)
        self.assertEqual(sum(r['unfinished'] for r in summary['rows']),1)
        self.assertEqual(summary['paired_comparisons'][0]['unpaired_or_error'],1)

    def test_duplicate_incompatible_and_wrong_assignment_rejected(self):
        records=self.records()
        with self.assertRaisesRegex(ValueError,'duplicate'):summarize(records+[records[0]])
        for key,value in [('split','train'),('communication','none')]:
            bad=copy.deepcopy(records);bad[0][key]=value
            with self.assertRaisesRegex(ValueError,'mix'):summarize(bad)
        bad=copy.deepcopy(records);bad[0]['scenario']['config']['rounds']=9
        with self.assertRaisesRegex(ValueError,'mix'):summarize(bad)
        bad=copy.deepcopy(records);bad[0]['assignment'][0]='other'
        with self.assertRaisesRegex(ValueError,'assignments'):summarize(bad)

    def test_manifest_enumerates_crossplay_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'run';summary=run_batch(plan(),out,[0],rotations=4,repeats=2,protocol='station-v2',
                config=replace(Config.tier('intro'),workload='joint',allocation=True).__dict__,max_calls=8000)
            self.assertEqual(len(summary['manifest']['schedule']),16)
            self.assertEqual(sum(r['completed'] for r in summary['rows']),16)
            again=run_batch(plan(),out,[0],rotations=4,repeats=2,protocol='station-v2',
                config=replace(Config.tier('intro'),workload='joint',allocation=True).__dict__,max_calls=8000,resume=True)
            self.assertEqual(summary,again)
