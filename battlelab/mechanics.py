"""Selected Generation IV singles mechanics. See docs/MECHANICS.md for scope."""
from fractions import Fraction
from .models import data

class UnsupportedMove(ValueError): pass
STATUS_MOVES={'SWORDS_DANCE','AGILITY','GROWL','TAIL_WHIP','RECOVER','THUNDER_WAVE','WILL_O_WISP','TOXIC'}
# Only explicitly supported effects may enter the simulator. Metadata != full support.
DIRECT_MOVES=set('STRUGGLE POUND SCRATCH TACKLE QUICK_ATTACK EXTREME_SPEED AQUA_JET MACH_PUNCH BULLET_PUNCH ICE_SHARD SHADOW_SNEAK WING_ATTACK AERIAL_ACE SWIFT EARTHQUAKE SURF FLAMETHROWER THUNDERBOLT ICE_BEAM PSYCHIC SHADOW_BALL ENERGY_BALL DARK_PULSE WATER_PULSE DRAGON_PULSE DRAGON_CLAW SLASH NIGHT_SLASH LEAF_BLADE AIR_SLASH ROCK_SLIDE CRUNCH BITE IRON_HEAD WATERFALL BRICK_BREAK'.split())
FIXED_MOVES={'SEISMIC_TOSS','NIGHT_SHADE','SONIC_BOOM','DRAGON_RAGE'}
HIGH_CRIT={'SLASH','NIGHT_SLASH','LEAF_BLADE'}

def supported(move): return move.name in STATUS_MOVES|DIRECT_MOVES|FIXED_MOVES

def stage(value, n):
    n=max(-6,min(6,n))
    return value*(2+max(0,n))//(2+max(0,-n))

def weather(field, *mons):
    return 'none' if any(p.ability in {'CLOUD_NINE','AIR_LOCK'} and p.hp>0 for p in mons) else field.weather

def effective_speed(mon, field, opponent=None):
    trace=[]; n=mon.stages.get('speed',0)*(2 if mon.ability=='SIMPLE' else 1)
    v=stage(mon.stats['speed'],n); trace.append(('stage',v))
    w=weather(field,mon,*([opponent] if opponent else []))
    if (mon.ability=='SWIFT_SWIM' and w=='rain') or (mon.ability=='CHLOROPHYLL' and w=='sun'): v*=2; trace.append(('weather ability',v))
    if mon.item in {'IRON_BALL','MACHO_BRACE'}: v//=2; trace.append(('halving item',v))
    if mon.item=='CHOICE_SCARF': v=v*15//10; trace.append(('Choice Scarf',v))
    if mon.item=='QUICK_POWDER' and mon.species=='DITTO': v*=2; trace.append(('Quick Powder',v))
    if mon.ability=='QUICK_FEET' and mon.status!='none': v=v*15//10; trace.append(('Quick Feet',v))
    elif mon.status=='paralysis': v//=4; trace.append(('Gen IV paralysis',v))
    if mon.ability=='SLOW_START' and mon.slow_start: v//=2; trace.append(('Slow Start',v))
    if mon.ability=='UNBURDEN' and mon.unburden and mon.item=='NONE': v*=2; trace.append(('Unburden',v))
    if mon.tailwind: v*=2; trace.append(('Tailwind',v))
    return v,trace

def first_actor(a,b,move_a,move_b,field,rng):
    if move_a.priority!=move_b.priority: return int(move_b.priority>move_a.priority)
    sa=effective_speed(a,field,b)[0]; sb=effective_speed(b,field,a)[0]
    la=a.item in {'LAGGING_TAIL','FULL_INCENSE'}; lb=b.item in {'LAGGING_TAIL','FULL_INCENSE'}
    if la!=lb: return int(la)
    if not la:
        la=a.ability=='STALL'; lb=b.ability=='STALL'
        if la!=lb: return int(la)
    if sa==sb: return rng.randrange(2)
    reverse=bool(la and lb) or field.trick_room
    return int(sa>sb) if reverse else int(sa<sb)

def matchup(move_type, defender, attacker=None):
    result=Fraction(1)
    for r in data('types'):
        if r['attack']==move_type and r['defend'] in defender.types:
            if move_type=='GROUND' and r['defend']=='FLYING' and defender.item=='IRON_BALL': continue
            if move_type in {'NORMAL','FIGHTING'} and r['defend']=='GHOST' and attacker and attacker.ability=='SCRAPPY': continue
            result*=Fraction(str(r['factor']))
    if attacker is None or attacker.ability!='MOLD_BREAKER':
        if move_type=='GROUND' and defender.ability=='LEVITATE' and defender.item!='IRON_BALL': return Fraction(0)
    return result

def critical_probability(a,b,move):
    if a.ability!='MOLD_BREAKER' and b.ability in {'BATTLE_ARMOR','SHELL_ARMOR'}: return Fraction(0)
    level=int(move.name in HIGH_CRIT)+int(a.ability=='SUPER_LUCK')+int(a.item in {'SCOPE_LENS','RAZOR_CLAW'})
    return Fraction(1,(16,8,4,3,2)[min(level,4)])

def accuracy(a,b,move):
    if move.accuracy==0: return 100
    n=max(-6,min(6,a.stages.get('accuracy',0)-b.stages.get('evasion',0)))
    return min(100,move.accuracy*(3+max(0,n))//(3+max(0,-n)))

def damage(a,b,move,field,roll=100,critical=False,defender_side=1):
    if not supported(move): raise UnsupportedMove(f'{move.name}: metadata available, effect not implemented')
    if not 85<=roll<=100: raise ValueError('Damage roll must be 85..100')
    if defender_side not in (0,1): raise ValueError('defender_side must be 0 or 1')
    trace=[]
    if move.category=='status': return {'damage':0,'effectiveness':1.0,'trace':[('status move',0)]}
    typ="TYPELESS" if move.name=="STRUGGLE" else move.type; factor=matchup(typ,b,a); defensive=b.ability if a.ability!='MOLD_BREAKER' else 'NONE'
    if factor==0 or (move.name!='STRUGGLE' and defensive=='WONDER_GUARD' and factor<=1): return {'damage':0,'effectiveness':0.0,'trace':[('immune',0)]}
    if defensive=='DRY_SKIN' and typ=='WATER': return {'damage':0,'effectiveness':0.0,'trace':[('Dry Skin absorbs',0)]}
    if move.name in FIXED_MOVES:
        value={'SONIC_BOOM':20,'DRAGON_RAGE':40}.get(move.name,a.level)
        return {'damage':value,'effectiveness':float(factor),'trace':[('fixed damage; type immunity only',value)]}
    physical=move.category=='physical'; ak='atk' if physical else 'spatk'; dk='def' if physical else 'spdef'
    at=a.stats[ak]; de=b.stats[dk]; power=move.power; w=weather(field,a,b)
    if a.ability=='TECHNICIAN' and power<=60 and move.name!='STRUGGLE': power=power*15//10
    if physical and a.ability in {'HUGE_POWER','PURE_POWER'}: at*=2
    if physical and a.ability=='SLOW_START' and a.slow_start: at//=2
    if (physical and a.item=='CHOICE_BAND') or (not physical and a.item=='CHOICE_SPECS'): at=at*15//10
    if defensive=='THICK_FAT' and typ in {'FIRE','ICE'}: power//=2
    if physical and a.ability=='GUTS' and a.status!='none': at=at*15//10
    if physical and defensive=='MARVEL_SCALE' and b.status!='none': de=de*15//10
    if a.hp<=a.max_hp//3 and (a.ability,typ) in {('BLAZE','FIRE'),('TORRENT','WATER'),('OVERGROW','GRASS'),('SWARM','BUG')}: power=power*15//10
    if defensive=='HEATPROOF' and typ=='FIRE': power//=2
    if defensive=='DRY_SKIN' and typ=='FIRE': power=power*125//100
    sa=a.stages.get(ak,0)*(2 if a.ability=='SIMPLE' else 1); sd=b.stages.get(dk,0)*(2 if defensive=='SIMPLE' else 1)
    if defensive=='UNAWARE': sa=0
    if a.ability=='UNAWARE': sd=0
    if critical: sa=max(0,sa); sd=min(0,sd)
    if not physical and a.ability=='SOLAR_POWER' and w=='sun': at=at*15//10
    if not physical and 'ROCK' in b.types and w=='sand': de=de*15//10
    at=stage(at,sa); de=max(1,stage(de,sd)); trace.extend([('power',power),('attack',at),('defense',de)])
    v=(2*a.level//5+2)*power*at//de//50; trace.append(('base before +2',v))
    if physical and a.status=='burn' and a.ability!='GUTS': v//=2; trace.append(('burn',v))
    screen=(field.reflect if physical else field.light_screen)[defender_side]
    if screen and not critical and move.name!='BRICK_BREAK': v//=2; trace.append(('screen',v))
    if (w=='rain' and typ=='WATER') or (w=='sun' and typ=='FIRE'): v=v*15//10; trace.append(('weather boost',v))
    if (w=='rain' and typ=='FIRE') or (w=='sun' and typ=='WATER'): v//=2; trace.append(('weather reduction',v))
    if a.flash_fire and typ=='FIRE': v=v*15//10
    v+=2; trace.append(('+2',v))
    if critical: v*=3 if a.ability=='SNIPER' else 2; trace.append(('critical',v))
    if a.item=='LIFE_ORB': v=v*130//100; trace.append(('Life Orb',v))
    v=max(1,v*roll//100); trace.append(('damage roll',v))
    if typ in a.types: v=v*2 if a.ability=='ADAPTABILITY' else v*15//10; trace.append(('STAB',v))
    # Preserve the original type table iteration order and per-step truncation.
    for r in data('types'):
        if r['attack']!=typ or r['defend'] not in b.types: continue
        if typ=='GROUND' and r['defend']=='FLYING' and b.item=='IRON_BALL': continue
        if typ in {'NORMAL','FIGHTING'} and r['defend']=='GHOST' and a.ability=='SCRAPPY': continue
        f=Fraction(str(r['factor'])); v=max(1,v*f.numerator//f.denominator); trace.append(('type '+r['defend'],v))
    if factor>1:
        if defensive in {'FILTER','SOLID_ROCK'}: v=max(1,v*3//4)
        if a.item=='EXPERT_BELT': v=v*120//100
    if factor<1 and a.ability=='TINTED_LENS': v*=2
    return {'damage':v,'effectiveness':float(factor),'trace':trace}

def damage_range(a,b,move,field,critical=False,defender_side=1):
    rolls=[damage(a,b,move,field,r,critical,defender_side)['damage'] for r in range(85,101)]
    return {'min':min(rolls),'max':max(rolls),'mean':sum(rolls)/16,'rolls':rolls,'ko_probability_on_hit':sum(v>=b.hp for v in rolls)/16}
