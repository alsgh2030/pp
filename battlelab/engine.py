"""Turn-based singles sandbox. Full cartridge battle state is outside its scope."""
import random
from .models import Field, Move
from .mechanics import damage, first_actor, critical_probability, accuracy, supported, weather
from .ai import Action, choose, legal_moves, status_possible

SECONDARY={
 'FLAMETHROWER':('status','burn'), 'THUNDERBOLT':('status','paralysis'),
 'PSYCHIC':('stage','spdef'), 'SHADOW_BALL':('stage','spdef'), 'ENERGY_BALL':('stage','spdef'), 'CRUNCH':('stage','def'),
 'DARK_PULSE':('flinch',None), 'BITE':('flinch',None), 'AIR_SLASH':('flinch',None), 'ROCK_SLIDE':('flinch',None), 'IRON_HEAD':('flinch',None), 'WATERFALL':('flinch',None)
}
# Freeze and confusion require extra state: keep metadata/calculator support but reject them in battle.
BATTLE_EXCLUDED={'ICE_BEAM','WATER_PULSE','STRUGGLE'}
# Some abilities need passive or on-hit processes not modelled by this singles sandbox.
BATTLE_ABILITIES_EXCLUDED={'DRY_SKIN','SOLAR_POWER','SLOW_START'}

def add_stage(mon,stat,delta): mon.stages[stat]=max(-6,min(6,mon.stages.get(stat,0)+delta))

class Battle:
    def __init__(self,left,right,field=None,seed=32,potions=(0,0)):
        if not 1<=len(left)<=6 or not 1<=len(right)<=6: raise ValueError('Teams need 1..6 Pokemon')
        if any(all(p.hp==0 for p in team) for team in (left,right)): raise ValueError('Each team needs a live Pokemon')
        for p in left+right:
            if p.ability in BATTLE_ABILITIES_EXCLUDED: raise ValueError(f'{p.ability}: calculator only; battle passive not implemented')
            for m in p.moves:
                if not supported(m) or m.name in BATTLE_EXCLUDED: raise ValueError(f'{m.name}: not supported by battle simulator')
        self.teams=[left,right]; self.active=[next(i for i,p in enumerate(t) if p.hp>0) for t in self.teams]
        self.field=field or Field(); self.rng=random.Random(seed); self.turn=0; self.potions=list(potions)
        if len(self.potions)!=2 or any(n<0 for n in self.potions): raise ValueError('Invalid potion inventory')
    def mon(self,side): return self.teams[side][self.active[side]]
    def winner(self):
        alive=[any(p.hp>0 for p in t) for t in self.teams]
        return None if all(alive) else ('draw' if not any(alive) else (0 if alive[0] else 1))
    def decision(self,side): return choose(self.teams[side],self.active[side],self.mon(1-side),self.field,self.rng,self.potions[side],1-side)
    def validate(self,side,action):
        if action.kind=='move' and action.index in legal_moves(self.mon(side)): return
        if action.kind=='switch' and 0<=action.index<len(self.teams[side]) and action.index!=self.active[side] and self.teams[side][action.index].hp>0: return
        if action.kind=='potion' and self.potions[side]>0 and self.mon(side).hp<self.mon(side).max_hp: return
        if action.kind=='struggle' and not legal_moves(self.mon(side)): return
        raise ValueError(f'Illegal action: {action}')
    def switch(self,side,index,log):
        old=self.mon(side); old.stages.clear(); old.choice_lock=None; old.unburden=False; old.toxic_turns=1
        self.active[side]=index; log.append(f'{side}: 교체 → {self.mon(side).species}')
    def step(self,actions=None):
        if self.winner() is not None: raise ValueError('Battle already ended')
        acts=actions or [self.decision(s)[0] for s in (0,1)]
        if len(acts)!=2: raise ValueError('Two actions required')
        for s in (0,1): self.validate(s,acts[s])
        self.turn+=1; log=[f'턴 {self.turn}']; flinched=set()
        priorities={'switch':6,'potion':7}
        pa=priorities.get(acts[0].kind,-99); pb=priorities.get(acts[1].kind,-99)
        if pa!=pb: first=int(pb>pa)
        else:
            ma=self.mon(0).moves[acts[0].index] if acts[0].kind=='move' else Move.get('STRUGGLE')
            mb=self.mon(1).moves[acts[1].index] if acts[1].kind=='move' else Move.get('STRUGGLE')
            first=first_actor(self.mon(0),self.mon(1),ma,mb,self.field,self.rng)
        for side in (first,1-first):
            a=self.mon(side); b=self.mon(1-side); act=acts[side]
            if a.hp<=0: continue
            if act.kind=='switch': self.switch(side,act.index,log); continue
            if act.kind=='potion':
                gain=min(200,a.max_hp-a.hp); a.hp+=gain; self.potions[side]-=1; log.append(f'{side}: 회복 도구 +{gain} HP'); continue
            if side in flinched: log.append(f'{a.species}: 풀죽음'); continue
            if a.status=='paralysis' and self.rng.randrange(4)==0: log.append(f'{a.species}: 마비로 행동 불가'); continue
            if b.hp<=0: continue
            struggle=act.kind=='struggle'; m=Move.get('STRUGGLE') if struggle else a.moves[act.index]
            if not struggle:
                a.pp[act.index]-=1
                if a.item in {'CHOICE_BAND','CHOICE_SPECS','CHOICE_SCARF'}: a.choice_lock=act.index
            log.append(f'{a.species}: {m.name}')
            if not struggle and self.rng.randrange(100)>=accuracy(a,b,m): log.append('빗나감'); continue
            if m.category=='status':
                if not status_possible(a,b,m): log.append('효과 없음'); continue
                if m.name=='RECOVER': a.hp=min(a.max_hp,a.hp+max(1,a.max_hp//2))
                elif m.name in {'SWORDS_DANCE','AGILITY'}: add_stage(a,'atk' if m.name=='SWORDS_DANCE' else 'speed',2)
                elif m.name in {'GROWL','TAIL_WHIP'}: add_stage(b,'atk' if m.name=='GROWL' else 'def',-1)
                else: b.status={'THUNDER_WAVE':'paralysis','WILL_O_WISP':'burn','TOXIC':'toxic'}[m.name]; b.toxic_turns=1
                continue
            prob=critical_probability(a,b,m); crit=self.rng.randrange(prob.denominator)<prob.numerator
            if m.name in {'SEISMIC_TOSS','NIGHT_SHADE','SONIC_BOOM','DRAGON_RAGE'}: crit=False
            result=damage(a,b,m,self.field,self.rng.randint(85,100),crit,1-side)
            dealt=min(b.hp,result['damage']); b.hp-=dealt
            log.append(f'피해 {dealt}, {b.species} HP {b.hp}/{b.max_hp}'+(' (급소)' if crit else ''))
            if m.name=='BRICK_BREAK':
                r=list(self.field.reflect); l=list(self.field.light_screen); r[1-side]=l[1-side]=False; self.field.reflect=tuple(r); self.field.light_screen=tuple(l)
            if dealt and not struggle and m.name in SECONDARY and b.hp>0 and self.rng.randrange(100)<m.chance:
                kind,value=SECONDARY[m.name]
                if kind=='flinch': flinched.add(1-side)
                elif kind=='stage': add_stage(b,value,-1)
                elif b.status=='none' and not (value=='burn' and 'FIRE' in b.types): b.status=value
            if struggle: a.hp=max(0,a.hp-max(1,a.max_hp//4))
            elif dealt and a.item=='LIFE_ORB': a.hp=max(0,a.hp-max(1,a.max_hp//10))
        # Deliberately simplified residual ordering, documented; replacement occurs after residuals.
        w=weather(self.field,self.mon(0),self.mon(1))
        for side in (first,1-first):
            p=self.mon(side)
            if p.hp<=0: continue
            if (w=='sand' and not {'ROCK','STEEL','GROUND'}.intersection(p.types)) or (w=='hail' and 'ICE' not in p.types): p.hp=max(0,p.hp-max(1,p.max_hp//16))
            if p.hp and p.item=='LEFTOVERS': p.hp=min(p.max_hp,p.hp+max(1,p.max_hp//16))
            if p.hp and p.status in {'burn','poison'}: p.hp=max(0,p.hp-max(1,p.max_hp//(16 if p.status=='burn' and p.ability=='HEATPROOF' else 8)))
            if p.hp and p.status=='toxic': p.hp=max(0,p.hp-max(1,p.max_hp*p.toxic_turns//16)); p.toxic_turns=min(15,p.toxic_turns+1)
        for side in (0,1):
            if self.mon(side).hp==0:
                remaining=[i for i,p in enumerate(self.teams[side]) if p.hp>0]
                if remaining: self.switch(side,remaining[0],log)
        return log
