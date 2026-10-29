"""Editable educational scoring policy, NOT the original HGSS bytecode interpreter."""
from dataclasses import dataclass
from .mechanics import damage_range, accuracy, effective_speed, supported, matchup

@dataclass(frozen=True)
class Action:
    kind: str  # move, switch, potion
    index: int=0

def legal_moves(mon):
    return [i for i,m in enumerate(mon.moves) if supported(m) and mon.pp[i]>0 and (mon.choice_lock is None or mon.choice_lock==i)]

def status_possible(a,b,m):
    if m.name in {'RECOVER'}: return a.hp<a.max_hp
    if m.name in {'SWORDS_DANCE','AGILITY'}: return a.stages.get('atk' if m.name=='SWORDS_DANCE' else 'speed',0)<6
    if m.name in {'GROWL','TAIL_WHIP'}: return b.stages.get('atk' if m.name=='GROWL' else 'def',0)>-6
    if b.status!='none': return False
    if m.name=='THUNDER_WAVE': return matchup('ELECTRIC',b,a)>0
    if m.name=='WILL_O_WISP': return 'FIRE' not in b.types
    if m.name=='TOXIC': return not {'STEEL','POISON'}.intersection(b.types)
    return False

def evaluate(a,b,field,defender_side=1):
    rows=[]
    for i,m in enumerate(a.moves):
        reasons=['초기 100점']; score=100; span=None
        if i not in legal_moves(a):
            rows.append(dict(index=i,move=m.name,score=None,reasons=['PP/구애 고정/미지원으로 선택 불가'],damage=None)); continue
        if m.category!='status':
            span=damage_range(a,b,m,field,defender_side=defender_side)
            value=int(40*min(span['mean'],b.hp)/max(1,b.hp)*accuracy(a,b,m)/100)
            score+=value; reasons.append(f'명중률 반영 예상 피해 +{value}')
            if span['max']==0: score-=100; reasons.append('면역 -100')
            if span['min']>=b.hp: score+=20; reasons.append('비급소 명중 시 확정 KO +20')
            if m.priority>0 and span['min']>=b.hp: score+=10; reasons.append('선공기 KO +10')
        elif not status_possible(a,b,m): score-=100; reasons.append('효과 없음 -100')
        elif m.name=='RECOVER':
            value=35 if a.hp*3<=a.max_hp else -10; score+=value; reasons.append(f'현재 HP에 따른 회복 평가 {value:+}')
        elif m.name in {'SWORDS_DANCE','AGILITY'}:
            value=8 if a.hp*2>a.max_hp else -15; score+=value; reasons.append(f'강화 여유 {value:+}')
        else:
            value=8 if b.hp*2>b.max_hp else -10; score+=value; reasons.append(f'상태/능력 저하 효용 {value:+}')
        rows.append(dict(index=i,move=m.name,score=max(0,score),reasons=reasons,damage=span))
    return rows

def choose(team,active,opponent,field,rng,potions=0,defender_side=1):
    a=team[active]; rows=evaluate(a,opponent,field,defender_side)
    candidates=[r for r in rows if r['score'] is not None]
    # This policy has explicit, documented custom switching/item thresholds.
    alternatives=[]
    for i,p in enumerate(team):
        if i!=active and p.hp>0:
            scores=[r['score'] for r in evaluate(p,opponent,field,defender_side) if r['score'] is not None]
            if scores: alternatives.append((max(scores),i))
    if alternatives and (not candidates or max(r['score'] for r in candidates)<=0):
        return Action('switch',max(alternatives)[1]),rows
    if potions and a.hp*4<=a.max_hp: return Action('potion'),rows
    if not candidates: return Action('struggle'),rows
    best=max(r['score'] for r in candidates)
    return Action('move',rng.choice([r['index'] for r in candidates if r['score']==best])),rows
