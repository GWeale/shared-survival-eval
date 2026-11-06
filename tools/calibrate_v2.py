import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shared_survival_eval.v2 import Config,StationEnv
from shared_survival_eval.agents import Baseline
from shared_survival_eval.runner import atomic_json,source_hash,interval_by_seed
parser=argparse.ArgumentParser(description='Calibrate scripted strategies; this does not evaluate LLMs or train models.')
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--seeds',type=int,default=100)
parser.add_argument('--seed-start',type=int,default=10000)
parser.add_argument('--split',choices=['train','validation','test'],default='test')
args=parser.parse_args()
if args.seeds<1 or args.seed_start<0:parser.error('invalid seed range')
out=args.out
if out.exists() and any(out.iterdir()):parser.error('output directory must be empty')
out.mkdir(parents=True,exist_ok=True)
rows=[];failures=[]
for tier in ['intro','standard','hard','extreme']:
 for policy in ['planner','reactive','greedy']:
  cases=[]
  for seed in range(args.seed_start,args.seed_start+args.seeds):
   env=StationEnv('shared',config=Config.tier(tier));env.reset(seed,args.split)
   actors=[Baseline(policy,seed+s) for s in range(4)]
   while env.phase!='terminal':
    obs=env.observations();env.step({s:actors[s].respond(obs[s],env.phase).decision for s in range(4)})
   r=env.result();cases.append({'seed':seed,'survived':r['survived'],'reward':r['rewards'][0],'invalid':r['invalid_decisions'],'repairs':r['successful_repairs']})
   if policy=='planner' and not r['survived']:failures.append({'tier':tier,'seed':seed,'resources':env.observe(0)['resources'],'faults':sorted(env.active_faults)})
  row={'tier':tier,'policy':policy,'scenarios':len(cases),'survived':sum(c['survived'] for c in cases),
       'invalid':sum(c['invalid'] for c in cases),'survival_ci95':interval_by_seed({c['seed']:[float(c['survived'])] for c in cases})}
  rows.append(row);print(json.dumps(row),flush=True)
  atomic_json(out/f'{tier}-{policy}.json',{'cases':cases})
atomic_json(out/'summary.json',{'protocol':'station-v2','source_hash':source_hash(),'split':args.split,'seeds':[args.seed_start,args.seed_start+args.seeds-1],
 'note':'Scripted policy calibration; no LLMs or training. Homogeneous teams; rotations would repeat the identical policy assignment. No model ranking is inferred. Report development/calibration/test provenance separately for each use.',
 'rows':rows,'reference_failures':failures})
