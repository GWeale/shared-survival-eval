import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from shared_survival_eval.agents import Baseline, request_for
from shared_survival_eval.v2 import Config, StationEnv
from shared_survival_eval.work_orders import Order, orders_for, best_matching
from shared_survival_eval.v2_cli import create, restore


class JointWorkTests(unittest.TestCase):
    def env(self, mode='shared'):
        e = StationEnv(mode, config=replace(Config.tier('intro'), workload='joint'))
        e.reset(3, 'validation')
        return e

    def act(self, e, decisions):
        e.step({s:{} for s in range(4)})
        return e.step({s:decisions.get(s, {'action':'wait'}) for s in range(4)})

    def test_matching_handles_greedy_trap(self):
        orders = [Order('a',(0,1),('seal','seal'),(9,9)), Order('b',(2,3),('seal','seal'),(1,1)),
                  Order('c',(0,2),('seal','seal'),(8,8)), Order('d',(1,3),('seal','seal'),(8,8))]
        self.assertEqual(best_matching(orders), (32, ('c','d')))
        self.assertEqual(best_matching([]), (0, ()))

    def test_observation_metadata_cannot_mutate_other_players_rules(self):
        from shared_survival_eval.work_orders import WORK_RULES
        e=self.env()
        original=WORK_RULES['production']
        try:
            e.observe(0)['rules']['joint_work']['production']='mutated by player'
            self.assertEqual(e.observe(1)['rules']['joint_work']['production'],original)
        finally:
            WORK_RULES['production']=original

    def test_generation_reproducible_and_split_separate(self):
        self.assertEqual(orders_for(1,'test',1), orders_for(1,'test',1))
        self.assertNotEqual(orders_for(1,'test',1), orders_for(1,'train',1))
        self.assertEqual(len(orders_for(1,'test',1)), 6)

    def test_private_work_values_and_schema(self):
        e = self.env(); obs = e.observe(0)
        self.assertEqual(len(obs['private']['work_orders']), 3)
        self.assertTrue(all(set(o) == {'id','seats'} for o in obs['orders']))
        self.assertNotIn('seed', obs)
        self.assertIsNone(obs['private']['opportunity'])
        self.assertIn('work', obs['legal_actions']); self.assertNotIn('contract', obs['legal_actions'])
        self.assertNotIn('contract', request_for(obs,'act')['response_schema']['action'])
        self.assertNotIn('r2-', json.dumps(obs))

    def test_pair_required_and_unmatched_work_consumes_input(self):
        e = self.env(); order = orders_for(3,'validation',1)[0]
        before = e.inventory[0][order.items[0]]
        self.act(e, {0:{'action':'work','order':order.id}})
        self.assertEqual(e.cargo, [0]*4)
        self.assertEqual(e.inventory[0][order.items[0]], before-1)
        self.assertEqual(e.failed_work_actions, 1)
        self.assertEqual(e.completed_orders, 0)

    def test_two_pairs_complete_and_credit_their_own_values(self):
        e = self.env(); orders = orders_for(3,'validation',1)
        pairs = [orders[0], orders[-1]]
        self.act(e, {s:{'action':'work','order':o.id} for o in pairs for s in o.seats})
        self.assertEqual(e.completed_orders, 2)
        self.assertEqual(e.failed_work_actions, 0)
        for o in pairs:
            for seat,value in zip(o.seats,o.values): self.assertEqual(e.cargo[seat],value)

    def test_wrong_seat_expired_order_and_solo_action_rejected(self):
        e = self.env()
        self.act(e, {3:{'action':'work','order':'r1-0'}, 0:{'action':'contract'}})
        self.assertEqual(e.invalid_count, 2)
        self.act(e, {0:{'action':'work','order':'r1-0'}})
        self.assertEqual(e.invalid_count, 3)

    def test_death_zeroes_delivery_and_no_work_means_zero_shared_reward(self):
        e = self.env()
        while e.phase != 'terminal':
            e.step({s:Baseline('maintenance',0).respond(e.observe(s),e.phase).decision for s in range(4)})
        self.assertTrue(e.result()['survived'])
        self.assertEqual(e.result()['rewards'], [0]*4)
        e.oxygen = 0
        self.assertEqual(e.result()['delivered_value'], 0)
        self.assertEqual(e.result()['rewards'], [-1]*4)

    def test_modes_share_physics_but_change_rewards(self):
        a,b = self.env(),self.env('individual')
        while a.phase != 'terminal':
            actions = {s:Baseline('coordinator',0).respond(a.observe(s),a.phase).decision for s in range(4)}
            a.step(actions); b.step(actions)
        self.assertEqual(a.events,b.events)
        self.assertEqual(a.result()['delivered_value'],b.result()['delivered_value'])
        self.assertNotEqual(a.result()['rewards'],b.result()['rewards'])
        self.assertLessEqual(sum(a.cargo), a.result()['opportunity_upper_bound'])

    def test_session_preserves_workload_and_report_fits_budget(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.json'
            create(p,workload='joint',background='coordinator')
            env=restore(json.loads(p.read_text()))
            self.assertEqual(env.config.workload, 'joint')
            for s in range(4):
                report=Baseline('coordinator',0).respond(env.observe(s),'discuss').decision
                self.assertLessEqual(len(report['say']),600)
                json.loads(report['say'])

    def test_research_selection_requires_delivery_not_survival(self):
        from shared_survival_eval.v2_research import select_candidate, paired_gain
        good={'config':{'rounds':12},'reference':{'survived':1,'positive_delivery_rate':1,'invalid':0},'paired_gain':{'ci95':[1,4]}}
        bad={**good,'config':{'rounds':36},'reference':{**good['reference'],'positive_delivery_rate':0}}
        self.assertEqual(select_candidate([good,bad]),good)
        self.assertIsNone(select_candidate([bad]))
        gain=paired_gain([{'seed':1,'delivered_value':4},{'seed':2,'delivered_value':6}],
                         [{'seed':1,'delivered_value':1},{'seed':2,'delivered_value':3}])
        self.assertEqual(gain,{'mean':3,'ci95':[3,3]})

    def test_joint_request_discloses_scripted_convention_without_private_data(self):
        e=self.env(); obs=e.observe(0)
        req=request_for(obs,'discuss')
        convention=req['scripted_partner_protocol']
        self.assertEqual(set(convention['fields']),{'inventory','diagnosis','repair_manual','work_orders','available'})
        self.assertIn('ignore',convention['scope'])
        self.assertNotIn('r1-',json.dumps(convention))
        self.assertNotIn('Contract consumes',obs['rules']['commerce'])
        solo=StationEnv();solo.reset()
        self.assertNotIn('scripted_partner_protocol',request_for(solo.observe(0),'discuss'))

    def test_solo_baseline_results_and_action_space_are_preserved(self):
        e=StationEnv();e.reset()
        self.assertNotIn('orders',e.observe(0))
        self.assertIn('contract',e.observe(0)['legal_actions'])
        with self.assertRaises(ValueError): Config(workload='typo')

if __name__ == '__main__': unittest.main()
