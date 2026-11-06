import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from shared_survival_eval.agents import Baseline, request_for
from shared_survival_eval.runner import run_batch, run_episode
from shared_survival_eval.v2 import Config, Scenario, StationEnv, PARTS, FAULTS
from shared_survival_eval.v2_cli import create, envelope, restore, submit
from shared_survival_eval.v2_experiments import exact_repair_oracle, learning_curve


def wait():return {s:{'action':'wait'} for s in range(4)}
def discuss(env, decisions=None):return env.step(decisions or {s:{} for s in range(4)})
def plan(name='planner'):return {'agents':{name:{'type':'baseline','name':name}},'crews':{name:[name]*4}}


class V2EngineTests(unittest.TestCase):
    def env(self, mode='shared', delay=3, integrity=1):
        config=Config(rounds=6,repair_delay=delay,pressure=0,integrity=integrity)
        scenario=replace(Scenario.generate(7,config=config),faults=('leak',),recipes=PARTS)
        e=StationEnv(mode);e.reset(scenario=scenario);return e

    def test_private_diagnosis_manual_and_future(self):
        e=self.env();obs=e.observe(0)
        self.assertNotIn('seed',obs);self.assertNotIn('cargo_values',obs['private'])
        self.assertIsNone(e.observe(1)['private']['repair_manual'])
        self.assertEqual(obs['private']['repair_manual']['leak'],'seal')
        discuss(e);a=wait();a[3]={'action':'inspect'};e.step(a)
        self.assertEqual(e.observe(3)['private']['diagnosis']['faults'],['leak'])
        self.assertFalse(any(x['kind']=='diagnosis' for x in e.observe(0)['history']))
        obs['private']['inventory']['seal']=999
        self.assertEqual(e.observe(0)['private']['inventory']['seal'],1)

    def test_private_message_cannot_override_visibility(self):
        e=self.env();d={s:{} for s in range(4)}
        d[0]={'private':{'to':1,'text':'secret','visible_to':None,'kind':'resolution','seat':3}}
        discuss(e,d)
        self.assertFalse(any(x.get('text')=='secret' for x in e.observe(2)['history']))
        msg=[x for x in e.observe(1)['history'] if x['kind']=='message'][0]
        self.assertEqual(msg['seat'],0)

    def test_paid_inspection_and_delayed_repair(self):
        e=self.env();discuss(e);a=wait();a[0]={'action':'repair','target':'leak'};e.step(a)
        self.assertEqual(e.jobs[0]['remaining'],2)
        self.assertIn('leak',e.active_faults)
        discuss(e);a=wait();a[0]={'action':'contract'};e.step(a)
        self.assertEqual(e.invalid_count,1)
        discuss(e);e.step(wait())
        self.assertNotIn('leak',e.active_faults);self.assertEqual(e.successful_repairs,1)
        self.assertEqual(e.inventory[0]['seal'],0)

    def test_wrong_diagnosis_wastes_part_and_misses_deadline(self):
        e=self.env();discuss(e);a=wait();a[0]={'action':'repair','target':'short'};e.step(a)
        while e.phase!='terminal':discuss(e);e.step(wait())
        self.assertFalse(e.result()['survived']);self.assertEqual(e.integrity,0)
        self.assertEqual(e.successful_repairs,0);self.assertEqual(e.inventory[0]['cell'],0)

    def test_gift_cannot_be_spent_until_following_turn(self):
        e=self.env();e.inventory[0]['seal']=0;discuss(e);a=wait()
        a[2]={'action':'give','to':0,'item':'seal','qty':1};a[0]={'action':'repair','target':'leak'}
        e.step(a);self.assertEqual(e.invalid_count,1);self.assertNotIn(0,e.jobs)
        self.assertEqual(e.inventory[0]['seal'],1)
        discuss(e);a=wait();a[0]={'action':'repair','target':'leak'};e.step(a)
        self.assertIn(0,e.jobs)

    def test_offer_escrow_payment_and_refund(self):
        e=self.env();d={s:{} for s in range(4)}
        d[2]={'offer':{'to':0,'item':'seal','qty':2,'price':3}}
        discuss(e,d);self.assertEqual(e.inventory[2]['seal'],2)
        a=wait();a[0]={'action':'accept','seller':2};e.step(a)
        self.assertEqual(e.credits,[7,10,13,10]);self.assertEqual(e.inventory[0]['seal'],3)
        self.assertEqual(e.trades,1);self.assertEqual(sum(e.credits),40)
        discuss(e,d);e.step(wait());self.assertEqual(e.inventory[2]['seal'],2)

    def test_wrong_buyer_and_overspending_cannot_steal(self):
        e=self.env();d={s:{} for s in range(4)};d[2]={'offer':{'to':0,'item':'seal','qty':1,'price':11}}
        discuss(e,d);a=wait();a[0]={'action':'accept','seller':2};a[1]={'action':'accept','seller':2};e.step(a)
        self.assertEqual(e.trades,0);self.assertEqual(e.credits,[10]*4);self.assertEqual(e.inventory[2]['seal'],4)
        self.assertEqual(e.invalid_count,2)

    def test_malformed_actions_do_not_crash(self):
        for bad in [None,[],{'action':[]},{'action':'repair','target':[]},{'action':'give','item':{}},{'action':'accept','seller':True}]:
            with self.subTest(bad=bad):
                e=self.env();discuss(e);a=wait();a[0]=bad;e.step(a);self.assertEqual(e.invalid_count,1)

    def test_priority_not_dictionary_order(self):
        a=self.env();b=self.env();discuss(a);discuss(b)
        actions={0:{'action':'inspect'},1:{'action':'operate','target':'power'},2:{'action':'fabricate','item':'coolant'},3:{'action':'cool'}}
        a.step(actions);b.step(dict(reversed(list(actions.items()))))
        self.assertEqual(a.events,b.events);self.assertEqual(a.observations(),b.observations())

    def test_modes_change_incentives_not_physics(self):
        a=self.env('shared',1,3);b=self.env('individual',1,3)
        while a.phase!='terminal':
            decisions={s:Baseline('planner',0).respond(a.observe(s),a.phase).decision for s in range(4)}
            a.step(decisions);b.step(decisions)
        self.assertEqual(a.events,b.events);self.assertTrue(a.result()['survived'])
        self.assertEqual(len(set(a.result()['rewards'])),1)
        self.assertNotEqual(a.result()['rewards'],b.result()['rewards'])

    def test_config_axes_keep_weather_and_fault_prefixes(self):
        a=Scenario.generate(1,'test',Config(rounds=6))
        b=Scenario.generate(1,'test',Config(rounds=24,pressure=2,sensor_accuracy=.2))
        self.assertEqual(a.weather,b.weather[:6]);self.assertEqual(a.faults,b.faults[:1])
        self.assertEqual(a.recipes,b.recipes)
        self.assertNotEqual(a.fingerprint,Scenario.generate(1,'train',a.config).fingerprint)
        with self.assertRaises(ValueError):Config(rounds=True)

    def test_schema_is_v2_and_malformed_reports_are_safe(self):
        e=self.env();d={s:{} for s in range(4)}
        d[1]={'say':json.dumps({'inventory':None,'repair_manual':[],'diagnosis':{'round':999,'faults':[{}]}})}
        discuss(e,d)
        self.assertIn('fabricate',request_for(e.observe(2),'act')['response_schema']['action'])
        for s in range(4):self.assertIsInstance(Baseline('planner',0).respond(e.observe(s),'act').decision,dict)


class V2IntegrationTests(unittest.TestCase):
    def test_reference_planner_solves_hard_and_greedy_fails(self):
        for seed in (1,2,3):
            a=run_episode(plan(),'planner','shared',seed,protocol='station-v2',difficulty='hard')
            b=run_episode(plan('greedy'),'greedy','shared',seed,protocol='station-v2',difficulty='hard')
            self.assertTrue(a['result']['survived']);self.assertEqual(a['result']['invalid_decisions'],0)
            self.assertFalse(b['result']['survived'])
            self.assertGreater(a['result']['inspections'],0)

    def test_focal_free_rider_cannot_rely_on_three_planners_in_critical_roles(self):
        for seat in (0,1):
            p=plan();p['agents']['greedy']={'type':'baseline','name':'greedy'}
            p['crews']['focal']=['planner']*4;p['crews']['focal'][seat]='greedy'
            r=run_episode(p,'focal','individual',8,protocol='station-v2',difficulty='hard')
            self.assertFalse(r['result']['survived'])

    def test_four_player_session_keeps_pending_decisions_hidden(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';create(p,difficulty='intro')
            state=json.loads(p.read_text());env=restore(state)
            first=envelope(state,env,0)
            reply={'decision_id':first['decision_id'],'decision':{'say':'private pending thought'}}
            self.assertTrue(submit(p,0,reply)['waiting'])
            state=json.loads(p.read_text());env=restore(state)
            self.assertNotIn('private pending thought',json.dumps(envelope(state,env,1)))
            self.assertTrue(submit(p,0,reply)['waiting'])
            with self.assertRaises(ValueError):submit(p,0,{**reply,'decision':{}})
            for s in (1,2,3):
                state=json.loads(p.read_text());env=restore(state)
                out=submit(p,s,{'decision_id':envelope(state,env,s)['decision_id'],'decision':{}})
            self.assertEqual(out['phase'],'act')
            self.assertIn('private pending thought',json.dumps(out))

    def test_session_replays_full_episode_and_locks_concurrent_writer(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';create(p,difficulty='intro',focal=0)
            while True:
                state=json.loads(p.read_text());env=restore(state);req=envelope(state,env,0)
                if req['done']:break
                decision=Baseline('planner',0).respond(req['observation'],req['phase']).decision
                out=submit(p,0,{'decision_id':req['decision_id'],'decision':decision})
            self.assertTrue(out['done']);self.assertGreater(out['reward'],0)
            from shared_survival_eval.session_lock import locked
            with locked(p.with_suffix('.json.lock')):
                with self.assertRaisesRegex(ValueError,'locked'):submit(p,0,{})

    def test_batch_preserves_pairing_budget_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'batch'
            a=run_batch(plan(),p,[1],protocol='station-v2',difficulty='intro',rotations=1,max_calls=100)
            b=run_batch(plan(),p,[1],protocol='station-v2',difficulty='intro',rotations=1,max_calls=100,resume=True)
            self.assertEqual(a,b);self.assertEqual(a['protocol'],'station-v2')
            self.assertEqual(a['paired_comparisons'][0]['complete_pairs'],1)
            self.assertEqual(a['budget']['attempted_calls'],96)
            with self.assertRaises(ValueError):run_batch(plan(),p,[1],protocol='station-v2',difficulty='hard',resume=True)
        with tempfile.TemporaryDirectory() as d:
            a=run_batch(plan(),Path(d)/'batch',[1],protocol='station-v2',max_calls=1,rotations=1)
            self.assertTrue(all(r['errors']==1 for r in a['rows']))
            self.assertTrue(all(r['metrics']['survival_rate']['mean'] is None for r in a['rows']))

    def test_exact_repair_oracle_detects_impossible_deadline(self):
        inv=dict.fromkeys(PARTS,1);recipes=dict(zip(FAULTS,PARTS))
        yes=exact_repair_oracle(['leak','short'],inv,recipes,2,4)
        no=exact_repair_oracle(['leak','short'],inv,recipes,2,3)
        self.assertTrue(yes['all_feasible']);self.assertFalse(no['all_feasible'])
        self.assertEqual(yes['minimum_turns_for_all'],4);self.assertEqual(no['cleared'],1)

    def test_learning_curve_evaluates_checkpoints_without_training(self):
        with tempfile.TemporaryDirectory() as d:
            result=learning_curve([{'training_episodes':0,'plan':plan('greedy')},{'training_episodes':10,'plan':plan()}],
                Path(d)/'curve',seeds=[2],difficulty='intro',rotations=1,max_calls=200)
            self.assertEqual([r['training_episodes'] for r in result['rows']],[0,10])
            self.assertLessEqual(sum(r['budget']['attempted_calls'] for r in result['rows']),200)
            self.assertIn('no training',result['training'])


if __name__=='__main__':unittest.main()
