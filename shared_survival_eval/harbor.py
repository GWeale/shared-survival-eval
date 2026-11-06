"""Harbor focal-seat task export, isolated game service, and replay verifier.

One Harbor agent controls one seat; the other three are scripted partners.
This transport is not a four-model orchestration or a training algorithm.
"""
from __future__ import annotations

import argparse
import copy
import json
import secrets
import re
import tempfile
import shutil
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .agents import Baseline, request_for, finite_float
from .runner import atomic_json, source_hash
from .v2 import Config, StationEnv

HARBOR_REVISION = 'ff2a1ef48070a8df374669138e4d4db79b77f013'
MAX_REQUEST_BYTES = 16384


def strict_json(text):
    def reject(value):raise ValueError('nonfinite JSON')
    return json.loads(text,parse_constant=reject,parse_float=finite_float)


def validate_spec(spec):
    if set(spec) != {'mode','seed','split','focal','background','config'}:
        raise ValueError('invalid task specification')
    if type(spec['focal']) is not int or spec['focal'] not in range(4):
        raise ValueError('invalid focal seat')
    if spec['background'] not in ('allocation_common','allocation_private','allocation_reciprocal','allocation_forgiving','allocation_switch','allocation_objective','coordinator'):
        raise ValueError('unsupported background')
    config=Config(**spec['config'])
    if config.workload!='joint':raise ValueError('Harbor tasks require joint workload')
    if not config.allocation and spec['background'].startswith('allocation_'):
        raise ValueError('allocation partner requires allocation mode')
    env=StationEnv(spec['mode'],config=config);env.reset(spec['seed'],spec['split'])
    return env


class Game:
    def __init__(self,spec,record_path):
        self.spec=copy.deepcopy(spec);self.env=validate_spec(spec)
        self.path=Path(record_path);self.turns=[];self.accepted={}
        self.token=secrets.token_hex(24);self.persist()

    def persist(self):
        atomic_json(self.path,{'format':'harbor-focal-v1','source_hash':source_hash(),
                    'spec':self.spec,'turns':self.turns,'done':self.env.phase=='terminal',
                    'result':self.env.result() if self.env.phase=='terminal' else None})

    def observe(self):
        seat=self.spec['focal']
        if self.env.phase=='terminal':
            return {'done':True,'reward':self.env.result()['rewards'][seat]}
        return {'done':False,'decision_id':self.token,**request_for(self.env.observe(seat),self.env.phase)}

    def submit(self,reply):
        if not isinstance(reply,dict) or set(reply)!={'decision_id','decision'} or not isinstance(reply['decision'],dict):
            raise ValueError('expected decision_id and decision object')
        token=reply['decision_id']
        if not isinstance(token,str):raise ValueError('invalid decision_id')
        if token in self.accepted:
            if self.accepted[token]!=reply['decision']:raise ValueError('cannot revise accepted input')
            return self.observe()
        if self.env.phase=='terminal' or not secrets.compare_digest(token,self.token):
            raise ValueError('stale or foreign decision_id')
        decisions={s:copy.deepcopy(reply['decision']) if s==self.spec['focal'] else Baseline(self.spec['background'],0).respond(self.env.observe(s),self.env.phase).decision for s in range(4)}
        next_env=copy.deepcopy(self.env);next_env.step(decisions)
        self.env=next_env;self.turns.append(decisions)
        self.accepted[token]=copy.deepcopy(reply['decision']);self.token=secrets.token_hex(24)
        self.persist();return self.observe()


def verify(record,spec):
    """Replay trusted sidecar evidence; never accept an agent-supplied score."""
    if record.get('format')!='harbor-focal-v1' or record.get('source_hash')!=source_hash() or record.get('spec')!=spec:
        raise ValueError('evidence identity differs')
    env=validate_spec(spec);turns=record.get('turns')
    if not isinstance(turns,list) or not 1<=len(turns)<=2*env.config.rounds:
        raise ValueError('invalid transcript length')
    for frame in turns:
        if not isinstance(frame,dict) or set(map(str,frame))!={'0','1','2','3'} or env.phase=='terminal':
            raise ValueError('invalid transcript frame')
        decisions={int(s):d for s,d in frame.items()}
        for seat in range(4):
            if seat!=spec['focal']:
                expected=Baseline(spec['background'],0).respond(env.observe(seat),env.phase).decision
                if decisions[seat]!=expected:raise ValueError('background decision mismatch')
        env.step(decisions)
    if env.phase!='terminal' or record.get('done') is not True:
        raise ValueError('incomplete episode: no terminal reward')
    result=env.result()
    if result!=record.get('result'):raise ValueError('claimed result differs from replay')
    return {'reward':result['rewards'][spec['focal']],'survived':int(result['survived']),
            'station_delivery':sum(result['cargo']) if result['survived'] else 0,
            'allocation_delivery':result['allocation_delivered_value'],
            'invalid_decisions':result['invalid_decisions']}


def serve(spec,path,host='0.0.0.0',port=8080):
    game=Game(spec,path)
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(3)
        def log_message(self,*args):pass
        def respond(self,code,value):
            body=json.dumps(value,allow_nan=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path=='/health':self.respond(200,{'ready':True})
            elif self.path=='/observation':self.respond(200,game.observe())
            else:self.respond(404,{'error':'unknown endpoint'})
        def do_POST(self):
            if self.path!='/submit':self.respond(404,{'error':'unknown endpoint'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_REQUEST_BYTES or self.headers.get('Transfer-Encoding'):
                    raise ValueError('invalid request size')
                raw=self.rfile.read(length)
                if len(raw)!=length:raise ValueError('incomplete request')
                reply=strict_json(raw);response=game.submit(reply)
            except (ValueError,TypeError,KeyError,TimeoutError):
                self.respond(400,{'error':'invalid request or decision'});return
            self.respond(200,response)
    # One serialized game owner; partial requests time out instead of occupying it forever.
    with HTTPServer((host,port),Handler) as server:server.serve_forever()


CLIENT = '''import json,sys,urllib.request
base="http://station:8080"
if sys.argv[1:]==["observe"]:request=urllib.request.Request(base+"/observation")
elif sys.argv[1:]==["submit"]:request=urllib.request.Request(base+"/submit",data=sys.stdin.buffer.read(16385),headers={"Content-Type":"application/json"})
else:raise SystemExit("usage: station observe | station submit < reply.json")
with urllib.request.urlopen(request,timeout=15) as response:print(response.read().decode())
'''


def _write_task(out,spec,base_image):
    validate_spec(spec);out=Path(out)
    if out.exists():raise ValueError('export destination must not exist')
    if not isinstance(base_image,str) or not re.fullmatch(r'python:3\.13[.a-zA-Z0-9_-]*@sha256:[0-9a-f]{64}',base_image):
        raise ValueError('supply a digest-pinned python:3.13 image')
    out.mkdir(parents=True)
    package=__package__;src=Path(__file__).parent
    def put(name,text):
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    for folder in ('environment/station','tests'):
        for p in src.iterdir():
            if p.suffix in ('.py','.html'):
                target=out/folder/package/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        put(folder+'/spec.json',json.dumps(spec,sort_keys=True)+'\n')
    put('environment/Dockerfile',f'FROM {base_image}\nRUN useradd -m -u 1000 agent\nCOPY client.py /usr/local/lib/station-client.py\nRUN printf \'#!/bin/sh\\nexec python /usr/local/lib/station-client.py "$@"\\n\' > /usr/local/bin/station && chmod 755 /usr/local/bin/station\nWORKDIR /workspace\nRUN mkdir -p /workspace && chown agent:agent /workspace\nUSER agent\n')
    put('environment/client.py',CLIENT)
    put('environment/station/Dockerfile',f'FROM {base_image}\nWORKDIR /opt/station\nCOPY . .\nRUN mkdir /evidence\nCMD ["python", "-m", "{package}.harbor", "serve", "--spec", "spec.json", "--record", "/evidence/record.json"]\n')
    put('environment/docker-compose.yaml','services:\n  main:\n    depends_on:\n      station:\n        condition: service_healthy\n  station:\n    build:\n      context: ${CONTEXT_DIR}/station\n    expose: ["8080"]\n    healthcheck:\n      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen(\'http://localhost:8080/health\',timeout=2)"]\n      interval: 2s\n      timeout: 3s\n      retries: 15\n')
    put('tests/Dockerfile',f'FROM {base_image}\nWORKDIR /tests\nCOPY . /tests/\n')
    put('tests/test.sh',f'#!/bin/sh\nset -eu\ncd /tests\npython -m {package}.harbor verify --spec /tests/spec.json --record /evidence/record.json --reward /logs/verifier/reward.json\n')
    put('task.toml','''schema_version = "1.4"
[[artifacts]]
source = "/evidence/record.json"
service = "station"
[metadata]
category = "multi-agent-cooperation"
protocol = "harbor-focal-v1"
[agent]
timeout_sec = 1800
user = "agent"
[verifier]
timeout_sec = 120
environment_mode = "separate"
[verifier.environment]
network_mode = "no-network"
cpus = 1
memory_mb = 1024
[environment]
cpus = 1
memory_mb = 1024
storage_mb = 2048
''')
    put('instruction.md',f'''<!-- harbor-canary: survival-focal-v1-7f941bde -->
Play one space-station episode as focal seat {spec['focal']} under {spec['mode']} reward.
Three other seats are independent scripted {spec['background']} policies, not model instances.
Run `station observe` for your private observation, action schema and full game rules.
Submit one JSON object with the returned decision_id and your decision using `station submit < reply.json`.
Repeat until done is true. A rejected request does not advance the game; an identical accepted retry is idempotent.
Use only this interface for game facts and actions. Every response concerns your fixed seat; there is no reset or seat-switch API.
The stated terminal reward is the objective. You do not submit a score or solution file.
The evaluator collects the station service's transcript and independently replays it in a separate verifier.
''')
    put('solution/solve.sh',f'''#!/bin/sh
set -eu
python /solution/oracle.py
''')
    # A reference policy uses only the focal RPC; no seed or evaluator-state access.
    for p in src.iterdir():
        if p.suffix in ('.py','.html'):
            target=out/'solution'/package/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    put('solution/oracle.py',f'''import json,urllib.request
from {package}.agents import Baseline
base="http://station:8080"
policy=Baseline("allocation_objective" if {validate_spec(spec).config.allocation!r} else "coordinator",0)
with urllib.request.urlopen(base+"/observation") as r:view=json.load(r)
while not view["done"]:
    obs=view["observation"];decision=policy.respond(obs,obs["phase"]).decision
    request=urllib.request.Request(base+"/submit",data=json.dumps({{"decision_id":view["decision_id"],"decision":decision}}).encode(),headers={{"Content-Type":"application/json"}})
    with urllib.request.urlopen(request) as r:view=json.load(r)
''')
    put('provenance.json',json.dumps({'harbor_revision':HARBOR_REVISION,'source_hash':source_hash(),'spec':spec,'base_image':base_image,'scope':'one focal agent plus three scripted partners; development task'},indent=2)+'\n')
    return out


def export_task(out,spec,base_image):
    from .session_lock import locked
    target=Path(out).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    with locked(target.parent/(target.name+'.export.lock')):
        if target.exists():raise ValueError('export destination must not exist')
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='.harbor-export-') as temporary:
            built=_write_task(Path(temporary)/'task',spec,base_image)
            if target.exists():raise ValueError('export destination appeared during build')
            built.rename(target)
    return target


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['export','serve','verify'])
    p.add_argument('--spec',type=Path,required=True);p.add_argument('--out',type=Path)
    p.add_argument('--base-image');p.add_argument('--record',type=Path);p.add_argument('--reward',type=Path)
    a=p.parse_args();spec=strict_json(a.spec.read_text())
    if a.command=='export':print(export_task(a.out,spec,a.base_image))
    elif a.command=='serve':serve(spec,a.record)
    else:
        # Harbor removes stale rewards; direct invocation must do so too.
        a.reward.unlink(missing_ok=True)
        if a.record.stat().st_size>4_000_000:raise ValueError('oversize evidence')
        result=verify(strict_json(a.record.read_text()),spec);atomic_json(a.reward,result)

if __name__=='__main__':main()
