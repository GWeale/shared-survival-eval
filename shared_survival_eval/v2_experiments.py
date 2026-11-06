"""Bounded exact maintenance oracle and held-out checkpoint evaluation."""
from dataclasses import asdict, replace
import itertools
import json
from pathlib import Path

from .runner import atomic_json, run_batch, source_hash, validate_plan
from .v2 import FAULTS, PARTS, Config


def exact_repair_oracle(faults, inventory, recipes, delay, deadline):
    """Exact for one engineer's repair ordering, not a full-game optimal policy.

    Full information; parts already delivered; no other resource failure; no new
    faults or actions other than wait/repair. At most three unique faults.
    """
    if (not isinstance(faults,(list,tuple,set)) or len(faults)>3 or len(set(faults))!=len(faults)
        or any(f not in FAULTS for f in faults) or type(delay) is not int or not 1<=delay<=4
        or type(deadline) is not int or deadline<0):raise ValueError('invalid repair problem')
    if any(type(inventory.get(p)) is not int or inventory[p]<0 for p in PARTS):raise ValueError('invalid inventory')
    if set(recipes)!=set(FAULTS) or any(p not in PARTS for p in recipes.values()):raise ValueError('invalid recipes')
    best=()
    for length in range(len(faults)+1):
        for order in itertools.permutations(sorted(faults),length):
            required={p:sum(recipes[f]==p for f in order) for p in PARTS}
            if length*delay<=deadline and all(required[p]<=inventory[p] for p in PARTS) and len(order)>len(best):best=order
    return {'cleared':len(best),'all_feasible':len(best)==len(faults),'minimum_turns_for_all':len(faults)*delay
            if all(sum(recipes[f]==p for f in faults)<=inventory[p] for p in PARTS) else None,
            'schedule':[{'start':1+i*delay,'finish':(i+1)*delay,'fault':f} for i,f in enumerate(best)],
            'scope':'exact single-engineer repair subproblem; not full-game optimality'}


def learning_curve(checkpoints, out, *, seeds, difficulty='hard', modes=('shared','individual'), rotations=4,
                   max_calls=1000000, enable_external=False, resume=False, workload="solo"):
    """Evaluate supplied training checkpoints; this function never trains a model."""
    if not isinstance(checkpoints,list) or not checkpoints:raise ValueError('checkpoint list required')
    counts=[]
    for cp in checkpoints:
        if not isinstance(cp,dict) or set(cp)!={'training_episodes','plan'}:raise ValueError('checkpoint needs training_episodes and plan')
        n=cp['training_episodes']
        if type(n) is not int or n<0:raise ValueError('training_episodes must be nonnegative integer')
        counts.append(n);validate_plan(cp['plan'])
    if counts!=sorted(set(counts)):raise ValueError('checkpoint training counts must be unique and increasing')
    if type(max_calls) is not int or max_calls<len(checkpoints):raise ValueError('call budget too small')
    config=asdict(replace(Config.tier(difficulty),workload=workload))
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    manifest={'source_hash':source_hash(),'checkpoints':checkpoints,'seeds':seeds,'difficulty':difficulty,
              'config':config,'modes':list(modes),'rotations':rotations,'max_calls':max_calls,'enable_external':enable_external}
    saved=out/'curve-manifest.json'
    if saved.exists():
        if not resume or json.loads(saved.read_text())!=manifest:raise ValueError('curve manifest differs or resume not enabled')
    elif any(out.iterdir()):raise ValueError('curve directory must be empty')
    else:atomic_json(saved,manifest)
    rows=[]
    for cp in checkpoints:
        summary=run_batch(cp['plan'],out/f"checkpoint-{cp['training_episodes']}",seeds,split='test',rotations=rotations,
                          modes=modes,config=config,protocol='station-v2',difficulty=difficulty,max_calls=max_calls//len(checkpoints),
                          enable_external=enable_external,resume=resume)
        rows.append({'training_episodes':cp['training_episodes'],'rows':summary['rows'],'budget':summary['budget']})
    result={'protocol':'station-v2','rows':rows,'training':'Checkpoints supplied by caller; no training performed by evaluator.',
            'uncertainty':'Scenario-block bootstrap in each row; same held-out seeds and seat rotations at every checkpoint.'}
    atomic_json(out/'learning-curve.json',result)
    return result
