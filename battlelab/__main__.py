import argparse, json, random
from pathlib import Path
from .models import make_pokemon, Move, Field, data
from .mechanics import damage, damage_range, effective_speed, supported, STATUS_MOVES, DIRECT_MOVES, FIXED_MOVES
from .ai import evaluate, Action
from .engine import Battle

def example():
    return {'seed':32,'field':{'weather':'none'},'teams':[
        [{'species':'TYPHLOSION','moves':['FLAMETHROWER','QUICK_ATTACK','EARTHQUAKE','WILL_O_WISP']}, {'species':'AMPHAROS','moves':['THUNDERBOLT','THUNDER_WAVE','TACKLE']}],
        [{'species':'FERALIGATR','moves':['WATERFALL','CRUNCH','SWORDS_DANCE','AQUA_JET']}, {'species':'MEGANIUM','moves':['ENERGY_BALL','TOXIC','TACKLE']}]]}

def load_scenario(path):
    raw=json.loads(Path(path).read_text(encoding='utf-8')) if path else example()
    return raw,[[make_pokemon(**p) for p in t] for t in raw['teams']],Field(**raw.get('field',{}))

def main():
    p=argparse.ArgumentParser(description='HGSS Battle Lab — Gen IV mechanics / experimental explainable AI')
    sub=p.add_subparsers(dest='cmd',required=True)
    for name in ('demo','play','analyze'):
        s=sub.add_parser(name); s.add_argument('--scenario'); s.add_argument('--seed',type=int); s.add_argument('--turns',type=int,default=50)
    s=sub.add_parser('move'); s.add_argument('name')
    s=sub.add_parser('supported')
    s=sub.add_parser('original-ai'); s.add_argument('--opcode',type=int)
    args=p.parse_args()
    if args.cmd=='move':
        m=Move.get(args.name); print(json.dumps(m.__dict__|{'calculator_supported':supported(m)},indent=2,ensure_ascii=False)); return
    if args.cmd=='supported':
        from .models import ABILITIES,ITEMS
        from .engine import BATTLE_EXCLUDED,BATTLE_ABILITIES_EXCLUDED
        print(json.dumps(dict(calculator_moves=sorted(STATUS_MOVES|DIRECT_MOVES|FIXED_MOVES),battle_excluded_moves=sorted(BATTLE_EXCLUDED),calculator_abilities=sorted(ABILITIES),battle_excluded_abilities=sorted(BATTLE_ABILITIES_EXCLUDED),items=sorted(ITEMS)),indent=2)); return
    if args.cmd=='original-ai':
        records=data('ai_commands'); raw=data('ai_wordcode')
        if args.opcode is None:
            print(json.dumps(dict(provenance=data('provenance'),entries=raw['entries'],commands=records),indent=2)); return
        if not 0<=args.opcode<len(records): p.error('opcode out of range')
        record=records[args.opcode]; print(json.dumps(record,indent=2))
        path=Path(__file__).resolve().parents[1]/'reference/src/battle/trainer_ai.c'
        if path.exists() and record['source_line']:
            lines=path.read_text().splitlines(); start=record['source_line']-1; depth=0
            for line in lines[start:]:
                print(line); depth+=line.count('{')-line.count('}')
                if depth==0: break
        return
    raw,teams,field=load_scenario(args.scenario); seed=args.seed if args.seed is not None else raw.get('seed',32)
    if args.cmd=='analyze':
        a,b=teams[0][0],teams[1][0]
        print(json.dumps(dict(attacker=a.species,defender=b.species,stats=a.stats,speed=effective_speed(a,field,b),opponent_speed=effective_speed(b,field,a),ai_policy='experimental; not HGSS script interpreter',scores=evaluate(a,b,field),damage_traces={m.name:damage(a,b,m,field) for m in a.moves if supported(m)}),indent=2,ensure_ascii=False)); return
    battle=Battle(*teams,field=field,seed=seed,potions=raw.get('potions',(0,0)))
    print('HGSS Battle Lab / 실험용 AI / 시드',seed)
    for _ in range(args.turns):
        if battle.winner() is not None: break
        actions=None
        if args.cmd=='play':
            a=battle.mon(0); b=battle.mon(1)
            print(f'나: {a.species} {a.hp}/{a.max_hp} | 상대: {b.species} {b.hp}/{b.max_hp}')
            print(' '.join(f'{i+1}:{m.name}(PP {a.pp[i]})' for i,m in enumerate(a.moves)))
            print('기술 번호 / s 번호(교체, 1부터) / item / auto / q')
            while True:
                try:
                    text=input('> ').strip()
                    if text=='q': return
                    if text=='auto': action=battle.decision(0)[0]
                    elif text=='item': action=Action('potion')
                    elif text.startswith('s '): action=Action('switch',int(text[2:])-1)
                    else: action=Action('move',int(text)-1)
                    battle.validate(0,action); actions=[action,battle.decision(1)[0]]; break
                except (ValueError,IndexError) as e: print('입력 오류:',e)
                except EOFError: return
        print('\n'.join(battle.step(actions)))
    winner=battle.winner()
    print('결과:',('턴 제한 도달 — 승패 미정' if winner is None else '무승부' if winner=='draw' else f'{winner}번 팀 승리'))

if __name__=='__main__':
    try: main()
    except (ValueError,KeyError) as e: raise SystemExit(f'오류: {e}')
