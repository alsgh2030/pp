from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import json

@lru_cache(None)
def data(name):
    return json.loads((Path(__file__).parent/'data'/f'{name}.json').read_text(encoding='utf-8'))

def key(value): return value.upper().replace(' ', '_').replace('-', '_')

@dataclass(frozen=True)
class Move:
    name: str
    id: int
    effect: int
    category: str
    power: int
    type: str
    accuracy: int
    pp: int
    chance: int
    target: int
    priority: int
    flags: int
    @classmethod
    def get(cls, name):
        name=key(name)
        if name not in data('moves'): raise ValueError(f'Unknown move: {name}')
        return cls(name=name, **data('moves')[name])

# Supported mechanics are explicit: unknown abilities/items never silently do nothing.
ABILITIES=set('NONE SIMPLE SWIFT_SWIM CHLOROPHYLL QUICK_FEET SLOW_START UNBURDEN CLOUD_NINE AIR_LOCK HUGE_POWER PURE_POWER GUTS TECHNICIAN THICK_FAT MARVEL_SCALE OVERGROW BLAZE TORRENT SWARM HEATPROOF DRY_SKIN UNAWARE SOLAR_POWER ADAPTABILITY LEVITATE MOLD_BREAKER WONDER_GUARD FILTER SOLID_ROCK TINTED_LENS SNIPER SUPER_LUCK BATTLE_ARMOR SHELL_ARMOR SCRAPPY STALL'.split())
ITEMS=set('NONE CHOICE_SCARF CHOICE_BAND CHOICE_SPECS IRON_BALL MACHO_BRACE QUICK_POWDER LAGGING_TAIL FULL_INCENSE LIFE_ORB EXPERT_BELT LEFTOVERS SCOPE_LENS RAZOR_CLAW'.split())
STAT_NAMES=('hp','atk','def','speed','spatk','spdef')
NATURES=['HARDY','LONELY','BRAVE','ADAMANT','NAUGHTY','BOLD','DOCILE','RELAXED','IMPISH','LAX','TIMID','HASTY','SERIOUS','JOLLY','NAIVE','MODEST','MILD','QUIET','BASHFUL','RASH','CALM','GENTLE','SASSY','CAREFUL','QUIRKY']

@dataclass
class Pokemon:
    species: str
    level: int
    types: tuple
    stats: dict
    moves: list
    hp: int
    ability: str='NONE'
    item: str='NONE'
    status: str='none'
    stages: dict=field(default_factory=dict)
    pp: list=field(default_factory=list)
    tailwind: bool=False
    unburden: bool=False
    slow_start: bool=False
    flash_fire: bool=False  # External calculation flag, not automatic ability activation.
    choice_lock: int | None=None
    toxic_turns: int=1
    def __post_init__(self):
        if self.ability not in ABILITIES: raise ValueError(f'Unsupported ability: {self.ability}')
        if self.item not in ITEMS: raise ValueError(f'Unsupported item: {self.item}')
        if self.status not in {'none','burn','paralysis','poison','toxic'}: raise ValueError('Supported statuses: none, burn, paralysis, poison, toxic')
        if not 0 <= self.hp <= self.stats['hp']: raise ValueError('HP outside valid range')
        if not 1 <= len(self.moves) <= 4: raise ValueError('Choose 1 to 4 moves')
        if any(k not in STAT_NAMES+('accuracy','evasion') or not -6<=v<=6 for k,v in self.stages.items()): raise ValueError('Invalid stat stage')
        if not self.pp: self.pp=[m.pp for m in self.moves]
        if len(self.pp)!=len(self.moves) or any(not 0<=n<=m.pp for n,m in zip(self.pp,self.moves)): raise ValueError('Invalid PP')
    @property
    def max_hp(self): return self.stats['hp']

@dataclass
class Field:
    weather: str='none'
    trick_room: bool=False
    reflect: tuple=(False,False)
    light_screen: tuple=(False,False)
    def __post_init__(self):
        if self.weather not in {'none','sun','rain','sand','hail'}: raise ValueError('Invalid weather')
        if len(self.reflect)!=2 or len(self.light_screen)!=2: raise ValueError('Screens need two sides')

def make_pokemon(species, moves, level=50, nature='HARDY', ivs=None, evs=None, **state):
    species=key(species); nature=key(nature)
    if species not in data('species'): raise ValueError(f'Unknown species: {species}')
    if not 1<=level<=100: raise ValueError('Level must be 1..100')
    if nature not in NATURES: raise ValueError('Unknown nature')
    ivs={k:31 for k in STAT_NAMES}|(ivs or {}); evs={k:0 for k in STAT_NAMES}|(evs or {})
    if set(ivs)!=set(STAT_NAMES) or set(evs)!=set(STAT_NAMES): raise ValueError('Unknown stat name')
    if any(not 0<=v<=31 for v in ivs.values()) or any(not 0<=v<=255 for v in evs.values()) or sum(evs.values())>510: raise ValueError('Invalid IV/EV budget')
    record=data('species')[species]; stats={}; plus,minus=divmod(NATURES.index(nature),5)
    nature_stats=('atk','def','speed','spatk','spdef')
    for k,base in record['stats'].items():
        value=(2*base+ivs[k]+evs[k]//4)*level//100
        if k=='hp': value=1 if species=='SHEDINJA' else value+level+10
        else:
            value+=5
            if plus!=minus:
                if k==nature_stats[plus]: value=value*110//100
                if k==nature_stats[minus]: value=value*90//100
        stats[k]=value
    state={**state}; state['ability']=key(state.get('ability','NONE')); state['item']=key(state.get('item','NONE'))
    return Pokemon(species,level,tuple(record['types']),stats,[Move.get(m) for m in moves],state.pop('hp',stats['hp']),**state)
