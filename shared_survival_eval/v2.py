"""Station V2: partially observed maintenance, coupled resources, and trade."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .engine import SEATS, rng_for

PROTOCOL = 'station-v2'
ROLES = ('engineer', 'operator', 'quartermaster', 'scout')
PARTS = ('seal', 'cell', 'filter')
FAULTS = ('leak', 'short', 'clog')
PART_FOR = dict(zip(FAULTS, PARTS))
TIERS = {
    'intro': dict(rounds=6, repair_delay=1, pressure=0, sensor_accuracy=1.0, integrity=3),
    'standard': dict(rounds=12, repair_delay=2, pressure=0, sensor_accuracy=.8, integrity=3),
    'hard': dict(rounds=24, repair_delay=3, pressure=1, sensor_accuracy=.65, integrity=2),
    'extreme': dict(rounds=36, repair_delay=3, pressure=2, sensor_accuracy=.5, integrity=1),
}
SCHEMAS = {
    'discuss': {'say': 'public text <=600 chars', 'private': {'to': 'other seat', 'text': '<=400 chars'},
                'commit': 'optional action name', 'offer': {'to': 'other seat', 'item': 'seal/cell/filter', 'qty': 'integer 1..3', 'price': 'integer total credits 0..40'}},
    'act': {'action': 'wait/inspect/repair/operate/cool/fabricate/give/accept/contract',
            'target': 'repair: leak/short/clog; operate: oxygen/power', 'item': 'fabricate/give: seal/cell/filter; fabricate also coolant',
            'to': 'give: other seat', 'qty': 'give: integer 1..3', 'seller': 'accept: offering seat'},
    'probe': {'survival': 'probability 0..1', 'repairs': {str(s): 'probability 0..1' for s in SEATS}},
}
RULES = {
    'roles': dict(enumerate(ROLES)),
    'turns': 'Simultaneous discussion, then simultaneous actions. Public priority rotates each round. Resources resolve in that priority; incoming parts and credits arrive AFTER all actions and cannot be spent this turn.',
    'crises': 'Every sixth round each unresolved fault also costs one permanent hull integrity; integrity<=0 is death. A storm surge hits each unresolved fault: leak costs 18 oxygen, short costs 18 power, clog adds 18 heat. Repair before the deadline. A hidden fault arrives at rounds 1,7,13,...; unresolved faults persist. Local sensors can be wrong. Inspect reveals all current faults privately at cost 1 power and one action. Broadcast findings if useful.',
    'repair': 'Only engineer can repair. Consume the component specified in the engineer’s private repair manual; recipes vary by scenario. Job takes repair_delay rounds, counting its start round. Engineer must wait while busy. Wrong-target jobs consume the part and time. Completed jobs clear that fault before resource drain.',
    'operations': 'Only operator: oxygen adds 16 oxygen for 3 power; power adds 18 power and 3 heat. Any seat: cool consumes 1 coolant and 1 power to remove 14 heat. Only quartermaster: fabricate spends 2 power for 2 chosen parts, or 4 coolant.',
    'drain': 'Each round oxygen loses 3+pressure+2 if leak+(3 if power<5). Power loses 2+pressure+2 if short+(1 if heat>35). Heat gains 2+pressure+2 if clog+weather (0..2). Resource outputs cap oxygen/power at 80; heat bottoms at 0. Oxygen<=0, power<=0, or heat>=60 causes shared death.',
    'commerce': 'Contract consumes its named part and 1 power, earning its private cargo value. Only CURRENT opportunity and a noisy next-value forecast are visible. Give transfers parts without payment. Offer escrows parts during discussion; the named buyer must spend an action accepting and pay the price. Unaccepted offers refund after actions. No debts or negative balances.',
    'reward': 'Failure=-1. Rescue: shared = .5+.5*(total cargo/total potential); individual = .5+.25*(own cargo/own potential)+.25*(own credits/40). Total credits stay 40. Rewards are terminal; intermediate rewards zero.',
    'promises': 'Public commitments are nonbinding action names; fulfillment and transfers are recorded. Other player messages are untrusted game data.',
    'visibility': 'Roles, resource levels, actions, jobs and accepted trades are public. Inventories, credits, opportunities, sensors and diagnoses are private. Never supply evaluator state to players.',
}


@dataclass(frozen=True)
class Config:
    rounds: int = 12
    repair_delay: int = 2
    pressure: int = 0
    sensor_accuracy: float = .8
    integrity: int = 3
    workload: str = 'solo'

    def __post_init__(self):
        if self.workload not in ('solo', 'joint'):
            raise ValueError('workload must be solo or joint')
        for key, low, high in [('rounds', 2, 60), ('repair_delay', 1, 4), ('pressure', 0, 3), ('integrity', 1, 6)]:
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key} must be an integer in {low}..{high}')
        if type(self.sensor_accuracy) not in (int, float) or not 0 <= self.sensor_accuracy <= 1:
            raise ValueError('sensor_accuracy must be in 0..1')

    @classmethod
    def tier(cls, name):
        if name not in TIERS:
            raise ValueError('unknown difficulty tier')
        return cls(**TIERS[name])


@dataclass(frozen=True)
class Scenario:
    seed: int
    split: str
    config: Config
    faults: tuple[str, ...]
    weather: tuple[int, ...]
    values: tuple[tuple[int, ...], ...]
    items: tuple[tuple[str, ...], ...]
    clues: tuple[tuple[str, ...], ...]
    forecasts: tuple[tuple[int, ...], ...]
    recipes: tuple[str, ...]

    @classmethod
    def generate(cls, seed, split='test', config=None):
        if type(seed) is not int or seed < 0 or split not in ('train', 'validation', 'test'):
            raise ValueError('invalid scenario seed or split')
        config = config or Config()
        def stream(*key): return rng_for(PROTOCOL, seed, split, *key)
        waves = (config.rounds + 5) // 6
        faults = tuple(stream('fault',w).choice(FAULTS) for w in range(waves))
        weather = tuple(stream('weather',r).randrange(3) for r in range(config.rounds))
        values = tuple(tuple(stream('value',s,r).randint(1,9) for r in range(config.rounds)) for s in SEATS)
        items = tuple(tuple(stream('item',s,r).choice(PARTS) for r in range(config.rounds)) for s in SEATS)
        clues = tuple(tuple(f if stream('clue',s,w).random()<config.sensor_accuracy else
                            stream('wrong-clue',s,w).choice([x for x in FAULTS if x!=f])
                            for w,f in enumerate(faults)) for s in SEATS)
        forecasts = tuple(tuple(max(1,min(9,stream('value',s,r+1).randint(1,9)+stream('forecast',s,r).choice((-2,-1,0,1,2))))
                                for r in range(config.rounds)) for s in SEATS)
        recipes=list(PARTS); stream('recipes').shuffle(recipes)
        return cls(seed, split, config, faults, weather, values, items, clues, forecasts, tuple(recipes))

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


class StationEnv:
    def __init__(self, mode='shared', communication='full', config=None):
        if mode not in ('shared','individual') or communication not in ('full','public','none'):
            raise ValueError('invalid mode or communication')
        self.mode, self.communication = mode, communication
        self.config = config or Config()
        self.scenario = None

    def reset(self, seed=0, split='test', *, scenario=None):
        self.scenario = scenario or Scenario.generate(seed, split, self.config)
        self.config = self.scenario.config
        self.round, self.phase = 1, 'discuss'
        self.oxygen, self.power, self.heat, self.coolant = 60, 55, 8, 12
        self.inventory = [{p: (4 if s == 2 else 1) for p in PARTS} for s in SEATS]
        self.integrity=self.config.integrity
        self.work_submissions = {}
        self.completed_orders = self.failed_work_actions = 0
        self.credits, self.cargo = [10]*4, [0]*4
        self.active_faults = {self.scenario.faults[0]}
        self.diagnoses = [None]*4
        self.jobs, self.offers, self.commitments = {}, {}, {}
        self.events = []
        self.invalid_count = self.commitment_count = self.fulfilled = 0
        self.repairs = self.successful_repairs = self.contracts = self.inspections = 0
        self.trades = self.gifts = self.fabrications = 0
        self._event('alarm', {'wave': 1})
        return self.observations()

    def _event(self, kind, data, visible_to=None):
        self.events.append({'round': self.round, 'phase': self.phase, 'kind': kind,
                            'visible_to': visible_to, **copy.deepcopy(data)})

    def _invalid(self, seat, reason):
        self.invalid_count += 1
        self._event('invalid', {'seat': seat, 'reason': reason}, [seat])

    def observe(self, seat):
        if self.scenario is None or type(seat) is not int or seat not in SEATS:
            raise ValueError('reset first; seat must be 0..3')
        r = min(self.round-1, self.config.rounds-1)
        actions = ['wait','inspect','cool','give','accept','contract']
        actions += {0:['repair'],1:['operate'],2:['fabricate'],3:[]}[seat]
        if seat in self.jobs:
            actions = ['wait']
        observation = copy.deepcopy({'protocol': PROTOCOL, 'eval': self.mode, 'communication': self.communication,
            'seat': seat, 'role': ROLES[seat], 'round': self.round, 'phase': self.phase,
            'config': asdict(self.config), 'rules': RULES,
            'reward': RULES['reward'], 'legal_actions': actions,
            'resources': {'oxygen': self.oxygen, 'power': self.power, 'heat': self.heat, 'coolant': self.coolant, 'integrity': self.integrity},
            'priority': [(self.round-1+i)%4 for i in SEATS], 'jobs': self.jobs,
            'offers': self.offers, 'private': {'inventory': self.inventory[seat], 'credits': self.credits[seat],
                'cargo': self.cargo[seat], 'repair_manual': dict(zip(FAULTS,self.scenario.recipes)) if seat==0 else None, 'opportunity': {'item': self.scenario.items[seat][r], 'value': self.scenario.values[seat][r]},
                'next_value_forecast': self.scenario.forecasts[seat][r] if self.round < self.config.rounds else None,
                'sensor': self.scenario.clues[seat][r//6], 'diagnosis': self.diagnoses[seat]},
            'history': [e for e in self.events if e['visible_to'] is None or seat in e['visible_to']]})
        if self.config.workload == 'joint':
            from .work_orders import orders_for, WORK_RULES
            orders = orders_for(self.scenario.seed, self.scenario.split, r + 1)
            observation['rules']['joint_work'] = WORK_RULES
            observation['rules']['reward'] = observation['reward'] = WORK_RULES['reward']
            observation['orders'] = [{'id':o.id, 'seats':list(o.seats)} for o in orders]
            observation['private']['work_orders'] = {o.id: {'item':o.items[o.seats.index(seat)], 'value':o.values[o.seats.index(seat)]}
                                                    for o in orders if seat in o.seats}
            observation['private']['opportunity'] = None
            observation['private']['next_value_forecast'] = None
            observation['legal_actions'] = ['work' if a == 'contract' else a for a in actions]
        return observation

    def observations(self):
        return {s:self.observe(s) for s in SEATS}

    @staticmethod
    def _seat(value):
        return type(value) is int and value in SEATS

    @staticmethod
    def _qty(value):
        return type(value) is int and 1 <= value <= 3

    def _discuss(self, decisions):
        self.commitments, self.offers = {}, {}
        for seat in SEATS:
            d = decisions[seat]
            if not isinstance(d, dict):
                self._invalid(seat, 'discussion must be an object'); continue
            if self.communication == 'none':
                continue
            say = d.get('say', '')
            if not isinstance(say, str):
                self._invalid(seat, 'say must be text')
            elif say:
                self._event('message', {'seat':seat, 'text':say[:600], 'channel':'public'})
            p = d.get('private')
            if p is not None and self.communication == 'full':
                if isinstance(p,dict) and self._seat(p.get('to')) and p['to'] != seat and isinstance(p.get('text'),str):
                    self._event('message', {'seat':seat, 'to':p['to'], 'text':p['text'][:400], 'channel':'private'}, [seat,p['to']])
                else: self._invalid(seat, 'invalid private message')
            commit = d.get('commit')
            if commit is not None:
                if isinstance(commit,str) and commit in (*SCHEMAS['act']['action'].split('/'), 'work'):
                    self.commitments[seat] = commit; self.commitment_count += 1
                    self._event('commitment', {'seat':seat, 'action':commit})
                else: self._invalid(seat,'invalid commitment')
            offer = d.get('offer')
            if offer is not None:
                if (isinstance(offer,dict) and set(offer)=={'to','item','qty','price'} and self._seat(offer['to'])
                    and offer['to'] != seat and isinstance(offer['item'],str) and offer['item'] in PARTS
                    and self._qty(offer['qty']) and type(offer['price']) is int and 0<=offer['price']<=40
                    and self.inventory[seat][offer['item']] >= offer['qty']):
                    self.inventory[seat][offer['item']] -= offer['qty']
                    self.offers[seat] = copy.deepcopy(offer)
                    self._event('offer', {'seat':seat, **offer})
                else: self._invalid(seat,'invalid or unfunded offer')
        self.phase = 'act'

    def _act(self, seat, d, incoming, payments, accepted):
        if not isinstance(d,dict) or not isinstance(d.get('action'),str):
            raise ValueError('action must be an object with action text')
        action = d['action']
        if seat in self.jobs and action != 'wait':
            raise ValueError('busy repairing; must wait')
        target, item = d.get('target'), d.get('item')
        inv = self.inventory[seat]
        if action == 'wait': return action
        if action == 'inspect':
            if self.power < 1: raise ValueError('insufficient power')
            self.power -= 1; self.inspections += 1
            self.diagnoses[seat] = {'round':self.round, 'faults':sorted(self.active_faults)}
            self._event('diagnosis', {'seat':seat, **self.diagnoses[seat]}, [seat])
        elif action == 'repair':
            if seat != 0 or not isinstance(target,str) or target not in FAULTS:
                raise ValueError('engineer and valid fault target required')
            part = dict(zip(FAULTS,self.scenario.recipes))[target]
            if inv[part] < 1: raise ValueError('missing repair component')
            inv[part] -= 1
            self.jobs[seat] = {'target':target, 'remaining':self.config.repair_delay}
            self.repairs += 1
        elif action == 'operate':
            if seat != 1 or target not in ('oxygen','power'): raise ValueError('operator and oxygen/power target required')
            if target == 'oxygen':
                if self.power < 3: raise ValueError('insufficient power')
                self.power -= 3; self.oxygen = min(80,self.oxygen+16)
            else:
                self.power = min(80,self.power+18); self.heat += 3
        elif action == 'cool':
            if self.coolant < 1 or self.power < 1: raise ValueError('coolant and power required')
            self.coolant -= 1; self.power -= 1; self.heat = max(0,self.heat-14)
        elif action == 'fabricate':
            if seat != 2 or not isinstance(item,str) or item not in (*PARTS,'coolant'):
                raise ValueError('quartermaster and valid item required')
            if self.power < 2: raise ValueError('insufficient power')
            self.power -= 2; self.fabrications += 1
            if item == 'coolant': self.coolant += 4
            else: inv[item] += 2
        elif action == 'give':
            to, qty = d.get('to'), d.get('qty',1)
            if not self._seat(to) or to==seat or not isinstance(item,str) or item not in PARTS or not self._qty(qty) or inv[item]<qty:
                raise ValueError('invalid or unfunded gift')
            inv[item] -= qty; incoming[to][item] += qty; self.gifts += 1
            self._event('transfer', {'seat':seat,'to':to,'item':item,'qty':qty,'price':0})
        elif action == 'accept':
            seller=d.get('seller')
            if not self._seat(seller) or seller not in self.offers or seller in accepted:
                raise ValueError('no available offer')
            offer=self.offers[seller]
            if offer['to']!=seat or self.credits[seat]<offer['price']: raise ValueError('wrong buyer or insufficient credits')
            self.credits[seat]-=offer['price']; payments[seller]+=offer['price']
            incoming[seat][offer['item']]+=offer['qty']; accepted.add(seller); self.trades+=1
            self._event('transfer',{'seat':seller, **offer})
        elif action == 'work':
            if self.config.workload != 'joint': raise ValueError('work requires joint workload')
            from .work_orders import orders_for
            order = next((o for o in orders_for(self.scenario.seed, self.scenario.split, self.round) if o.id == d.get('order')), None)
            if order is None or seat not in order.seats: raise ValueError('order requires this seat')
            item = order.items[order.seats.index(seat)]
            if inv[item] < 1 or self.power < 1: raise ValueError('work needs component and power')
            inv[item] -= 1; self.power -= 1
            self.work_submissions[seat] = order.id
            self._event('work_attempt', {'seat':seat, 'order':order.id})
        elif action == 'contract':
            if self.config.workload == 'joint': raise ValueError('joint workload requires work, not solo contracts')
            item=self.scenario.items[seat][self.round-1]
            if inv[item]<1 or self.power<1: raise ValueError('contract needs component and power')
            inv[item]-=1; self.power-=1; self.cargo[seat]+=self.scenario.values[seat][self.round-1]; self.contracts+=1
        else: raise ValueError('unknown action')
        return action

    def step(self, decisions: dict[int,Any]):
        if self.scenario is None or self.phase=='terminal': raise ValueError('reset before stepping')
        if not isinstance(decisions,dict) or set(decisions)!=set(SEATS) or any(type(s) is not int for s in decisions):
            raise ValueError('exactly four integer seats required')
        if self.phase=='discuss':
            self._discuss(decisions)
            return self.observations(),dict.fromkeys(SEATS,0.),False,{}
        incoming=[dict.fromkeys(PARTS,0) for _ in SEATS]; payments=[0]*4; accepted=set(); executed={}
        for seat in [(self.round-1+i)%4 for i in SEATS]:
            try: executed[seat]=self._act(seat,decisions[seat],incoming,payments,accepted)
            except ValueError as exc:
                self._invalid(seat,str(exc)); executed[seat]='wait'
            if self.commitments.get(seat)==executed[seat]: self.fulfilled+=1
        if self.config.workload == 'joint':
            from .work_orders import orders_for
            completed_seats = set()
            for order in orders_for(self.scenario.seed, self.scenario.split, self.round):
                if all(self.work_submissions.get(s) == order.id for s in order.seats):
                    for seat, value in zip(order.seats, order.values): self.cargo[seat] += value
                    completed_seats.update(order.seats); self.completed_orders += 1
                    self._event('work_complete', {'order':order.id, 'seats':list(order.seats), 'value':sum(order.values)})
            self.failed_work_actions += len(set(self.work_submissions) - completed_seats)
            self.work_submissions = {}
        for seller,offer in self.offers.items():
            if seller not in accepted: incoming[seller][offer['item']]+=offer['qty']
        self.offers={}
        for s in SEATS:
            self.credits[s]+=payments[s]
            for p in PARTS: self.inventory[s][p]+=incoming[s][p]
        for s,job in list(self.jobs.items()):
            job['remaining']-=1
            if job['remaining']==0:
                success=job['target'] in self.active_faults
                self.active_faults.discard(job['target']); self.successful_repairs+=int(success)
                self._event('repair_complete',{'seat':s,'target':job['target'],'success':success})
                del self.jobs[s]
        low_power=self.power<5; hot=self.heat>35
        self.oxygen=max(0,self.oxygen-3-self.config.pressure-2*('leak' in self.active_faults)-3*low_power)
        self.power=max(0,self.power-2-self.config.pressure-2*('short' in self.active_faults)-int(hot))
        self.heat+=2+self.config.pressure+2*('clog' in self.active_faults)+self.scenario.weather[self.round-1]
        if self.round%6==0:
            self.integrity=max(0,self.integrity-len(self.active_faults))
            self.oxygen=max(0,self.oxygen-18*('leak' in self.active_faults))
            self.power=max(0,self.power-18*('short' in self.active_faults))
            self.heat+=18*('clog' in self.active_faults)
        self._event('resolution',{'actions':executed,'resources':{'oxygen':self.oxygen,'power':self.power,'heat':self.heat,'coolant':self.coolant,'integrity':self.integrity},'weather':self.scenario.weather[self.round-1]})
        dead=self.oxygen<=0 or self.power<=0 or self.heat>=60 or self.integrity<=0
        if dead or self.round==self.config.rounds:
            self.phase='terminal'; result=self.result()
            return self.observations(),dict(enumerate(result['rewards'])),True,result
        self.round+=1; self.phase='discuss'
        if (self.round-1)%6==0:
            self.active_faults.add(self.scenario.faults[(self.round-1)//6])
            self._event('alarm',{'wave':(self.round-1)//6+1})
        return self.observations(),dict.fromkeys(SEATS,0.),False,{}

    def result(self):
        if self.phase!='terminal': raise ValueError('result only at termination')
        survived=self.oxygen>0 and self.power>0 and self.heat<60 and self.integrity>0
        potentials=[sum(row) for row in self.scenario.values]
        team_potential = sum(potentials)
        if self.config.workload == 'joint':
            from .work_orders import orders_for, best_matching
            rounds = [orders_for(self.scenario.seed, self.scenario.split, r) for r in range(1, self.config.rounds+1)]
            potentials = [sum(max(o.values[o.seats.index(s)] for o in orders if s in o.seats) for orders in rounds) for s in SEATS]
            team_potential = sum(best_matching(orders)[0] for orders in rounds)
        completion=[self.cargo[s]/potentials[s] for s in SEATS]
        team=sum(self.cargo)/team_potential
        rewards=[(-1. if not survived else .5+.5*team if self.mode=='shared' else .5+.25*completion[s]+.25*self.credits[s]/40) for s in SEATS]
        if self.config.workload == 'joint':
            rewards = [-1. if not survived else team if self.mode == 'shared' else .75*completion[s]+.25*self.credits[s]/40 for s in SEATS]
        return {'survived':survived,'rounds':self.round,'reason':'rescued' if survived else 'resource_failure',
            'rewards':rewards,'cargo':self.cargo.copy(),'objective_completion':completion,'team_completion':team,
            'realized_team_completion':team if survived else 0.,'credits':self.credits.copy(),
            'commitments':self.commitment_count,'fulfilled':self.fulfilled,'invalid_decisions':self.invalid_count,
            'repairs':self.repairs,'successful_repairs':self.successful_repairs,'inspections':self.inspections,
            'trades':self.trades,'gifts':self.gifts,'fabrications':self.fabrications,
            'contracts':self.contracts, 'delivered_value':sum(self.cargo) if survived else 0,
            'completed_orders':self.completed_orders, 'failed_work_actions':self.failed_work_actions,
            'opportunity_upper_bound':team_potential}
