import copy
import itertools
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from dataclasses import asdict,replace
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path

from shared_survival_eval.agents import AgentFailure,Baseline,CallBudget,ChatAgent,Reply,decode_decision
from shared_survival_eval.allocation import payoffs
from shared_survival_eval.harbor import Game,verify,export_task,strict_json
from shared_survival_eval.runner import run_batch,run_episode,parse_probe,summarize
from shared_survival_eval.v2 import Config,Scenario
from shared_survival_eval.v2_cli import create,envelope,restore,submit
from shared_survival_eval.v2_experiments import learning_curve

PLAN={'agents':{'a':{'type':'baseline','name':'coordinator'}},'crews':{'a':['a']*4}}
CONFIG=asdict(replace(Config.tier('intro'),workload='joint',allocation=True))
SPEC={'config':CONFIG,'mode':'shared','focal':2,'background':'allocation_common','seed':83,'split':'test'}

class HarborAuditTests(unittest.TestCase):
    def test_focal_play_replay_and_reject_forged_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'record.json';game=Game(SPEC,path)
            first=game.observe();foreign=Game(SPEC,Path(d)/'other.json').observe()
            self.assertNotEqual(first['decision_id'],foreign['decision_id'])
            with self.assertRaises(ValueError):game.submit({'decision_id':foreign['decision_id'],'decision':{}})
            while not game.observe()['done']:
                view=game.observe();obs=view['observation']
                self.assertNotIn('seed',obs);self.assertNotIn('scenario',obs)
                reply={'decision_id':view['decision_id'],'decision':Baseline('allocation_objective',0).respond(obs,obs['phase']).decision}
                result=game.submit(reply);self.assertEqual(game.submit(reply),result)
            record=json.loads(path.read_text());score=verify(record,SPEC)
            self.assertEqual(score['reward'],1)
            for field,value in [('result',{'rewards':[999]*4}),('done',False),('source_hash','bad')]:
                bad=copy.deepcopy(record);bad[field]=value
                with self.assertRaises(ValueError):verify(bad,SPEC)
            bad=copy.deepcopy(record);bad['turns'][0]['0']={'say':'forged'}
            with self.assertRaises(ValueError):verify(bad,SPEC)

    def test_incomplete_episode_has_no_reward_and_export_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game=Game(SPEC,root/'r.json')
            with self.assertRaisesRegex(ValueError,'transcript|incomplete'):verify(json.loads(game.path.read_text()),SPEC)
            out=export_task(root/'task',SPEC,'python:3.13-slim@sha256:'+'a'*64)
            self.assertFalse((out/'environment'/'spec.json').exists())
            self.assertFalse((out/'environment'/'shared_survival_eval').exists())
            self.assertIn('environment_mode = "separate"',(out/'task.toml').read_text())
            self.assertIn('service = "station"',(out/'task.toml').read_text())
            with self.assertRaises(ValueError):export_task(out,SPEC,'python:3.13-slim@sha256:'+'a'*64)

    def test_tokens_are_unique_and_focal_observation_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[Path(d)/f'{i}.json' for i in range(2)];views=[]
            for p in paths:
                create(p,focal=0,seed=83,workload='joint',background='coordinator')
                state=json.loads(p.read_text());env=restore(state);views.append(envelope(state,env,0))
                with self.assertRaisesRegex(ValueError,'focal'):envelope(state,env,1)
            self.assertNotEqual(views[0]['decision_id'],views[1]['decision_id'])
            with self.assertRaisesRegex(ValueError,'stale'):submit(paths[1],0,{'decision_id':views[0]['decision_id'],'decision':{}})

    def test_custom_scenarios_and_nonfinite_numbers_fail_at_boundary(self):
        s=Scenario.generate(1)
        for changes in ({'faults':()},{'values':((0,)*12,)*4},{'values':((float('inf'),)*12,)*4},{'recipes':('seal',)*3}):
            with self.assertRaises(ValueError):replace(s,**changes)
        self.assertIsNone(decode_decision('{"action":"wait","unused":1e309}'))
        with self.assertRaises(ValueError):strict_json('{"unused":1e309}')
        self.assertIsNone(parse_probe({'survival':10**400,'repairs':{str(s):0 for s in range(4)}}))
        for profile in itertools.product(('common','private','burn'),repeat=4):
            values=payoffs(profile);self.assertLessEqual(max(values),10);self.assertLessEqual(sum(values),32)

    def test_curve_can_use_allocation_and_freezes_config(self):
        plan={'agents':{'a':{'type':'baseline','name':'allocation_common'}},'crews':{'a':['a']*4}}
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'curve';cp=[{'training_episodes':0,'plan':plan}]
            result=learning_curve(cp,out,seeds=[1],rotations=1,max_calls=1000,config=CONFIG)
            self.assertEqual(sum(r['errors'] for r in result['rows'][0]['rows']),0)
            with self.assertRaises(ValueError):learning_curve(cp,out,seeds=[1],rotations=1,max_calls=1000,config={**CONFIG,'allocation':False},resume=True)

    def test_resume_checks_results_budget_and_command_artifacts(self):
        for corruption in ('reward','budget','assignment','missing_usage','erased_calls'):
            with tempfile.TemporaryDirectory() as d:
                out=Path(d)/'run';run_batch(PLAN,out,[0,1],modes=('shared',),rotations=1,max_calls=1000,protocol='station-v2',config={**CONFIG,'allocation':False})
                p=next((out/'episodes').glob('*s0--*.json'));record=json.loads(p.read_text())
                next((out/'episodes').glob('*s1--*.json')).unlink()
                if corruption=='reward':record['result']['rewards']=[999]*4;p.write_text(json.dumps(record))
                elif corruption=='assignment':record['assignment']=['fake']*4;p.write_text(json.dumps(record))
                elif corruption=='missing_usage':del record['calls'][0]['input_tokens'];p.write_text(json.dumps(record))
                elif corruption=='erased_calls':record['calls']=[];record['attempted_calls']=0;p.write_text(json.dumps(record));(out/'budget.json').write_text('{"attempted_calls":0}')
                else:(out/'budget.json').write_text('{"attempted_calls":0}')
                with patch('shared_survival_eval.runner.run_episode',side_effect=AssertionError('must validate before new calls')) as run:
                    with self.assertRaises(ValueError):run_batch(PLAN,out,[0,1],modes=('shared',),rotations=1,max_calls=1000,protocol='station-v2',config={**CONFIG,'allocation':False},resume=True)
                    run.assert_not_called()
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run';script=Path(d)/'policy.py';script.write_text('print("{}")')
            plan={'agents':{'a':{'type':'command','argv':[sys.executable,str(script)]}},'crews':{'a':['a']*4}}
            run_batch(plan,out,[0],rotations=1,max_calls=1,enable_external=True)
            script.write_text('print("{\\"action\\":\\"wait\\"}")')
            with self.assertRaisesRegex(ValueError,'manifest'):run_batch(plan,out,[0],rotations=1,max_calls=1,enable_external=True,resume=True)

    def test_summary_uses_schedule_for_missing_pairs(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run';summary=run_batch(PLAN,out,[0,1],rotations=1,max_calls=1000,protocol='station-v2',config={**CONFIG,'allocation':False})
            records=[json.loads(p.read_text()) for p in (out/'episodes').glob('*s0--*.json')]
            partial=summarize(records,summary['manifest'])
            self.assertTrue(all(row['completion_fraction']==.5 for row in partial['rows']))
            self.assertTrue(all(row['unpaired_or_error']==1 for row in partial['paired_comparisons']))

    def test_budget_requires_integer_and_huge_usage_stays_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            for value in (1.1,True):
                with self.assertRaises(ValueError):run_batch(PLAN,Path(d)/'run',[0],max_calls=value)
        class Huge:
            def respond(self,*args):return Reply({},10**1000,1)
        _,usage=CallBudget(1).call(Huge(),{'type':'chat','input_usd_per_million':1.,'output_usd_per_million':1.},{},'act')
        self.assertIsNone(usage['input_tokens']);self.assertIsNone(usage['estimated_usd'])

    def test_http_deadline_and_truncated_chunks_become_agent_failures(self):
        for mode in ('dribble','truncated'):
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    try:
                        if mode=='truncated':
                            self.wfile.write(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nab');self.wfile.flush();self.close_connection=True
                        else:
                            self.send_response(200);self.send_header('Content-Length','100');self.end_headers()
                            for _ in range(100):self.wfile.write(b' ');self.wfile.flush();time.sleep(.02)
                    except (BrokenPipeError,ConnectionResetError):pass
            server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                start=time.monotonic()
                with self.assertRaises(AgentFailure):ChatAgent({'model':'fixture','base_url':f'http://127.0.0.1:{server.server_port}/v1','timeout':.3}).respond({},'act')
                self.assertLess(time.monotonic()-start,1.5)
            finally:server.shutdown();server.server_close();thread.join()

    def test_failed_messages_are_counted_and_conventions_disclosed(self):
        from shared_survival_eval.agents import request_for
        from shared_survival_eval.engine import StationEnv as V1
        from shared_survival_eval.v2 import StationEnv as V2
        plan={'agents':{'a':{'type':'baseline','name':'cooperative'}},'crews':{'a':['a']*4}}
        record=run_episode(plan,'a','shared',0,budget=CallBudget(8))
        self.assertEqual(record['status'],'error')
        self.assertEqual(summarize([record])['rows'][0]['message_characters'],sum(len(e['text']) for e in record['events'] if e['kind']=='message'))
        self.assertGreater(summarize([record])['rows'][0]['message_characters'],0)
        for env in (V1(),V2()):self.assertIn('scripted_partner_protocol',request_for(env.reset()[0],'discuss'))

    def test_curve_lock_rejects_second_writer_without_outputs(self):
        from shared_survival_eval.session_lock import locked
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'curve'
            with locked(Path(d)/'curve.curve.lock'):
                with self.assertRaisesRegex(ValueError,'locked'):learning_curve([],out,seeds=[0])
            self.assertFalse(out.exists())

    def test_interrupted_initial_manifest_preserves_orphan_and_recovers(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run';out.mkdir();(out/'.writing-fixture').write_text('interrupted bytes')
            result=run_batch(PLAN,out,[0],rotations=1,max_calls=1000,protocol='station-v2',config={**CONFIG,'allocation':False},resume=True)
            self.assertEqual(sum(row['completed'] for row in result['rows']),2)
            recovered=list(Path(d).glob('run.recovered-*/.writing-fixture'))
            self.assertEqual(len(recovered),1);self.assertEqual(recovered[0].read_text(),'interrupted bytes')
