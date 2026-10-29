import unittest, random, copy
from battlelab.models import Pokemon,Move,Field,make_pokemon,data
from battlelab.mechanics import *
from battlelab.ai import *
from battlelab.engine import Battle

def mon(**kw):
    p=Pokemon('TEST',50,('NORMAL',),{'hp':200,'atk':100,'def':100,'speed':100,'spatk':100,'spdef':100},[Move.get('EARTHQUAKE')],200)
    for k,v in kw.items(): setattr(p,k,v)
    return p
class MechanicsTests(unittest.TestCase):
    def test_original_move_values(self):
        self.assertEqual(Move.get('THUNDERBOLT').power,95)
        self.assertEqual(Move.get('TACKLE').power,35)
        self.assertEqual(Move.get('QUICK_ATTACK').priority,1)
        self.assertEqual(len(data('moves')),468)
    def test_stats(self):
        p=make_pokemon('PIKACHU',['THUNDERBOLT'])
        self.assertEqual(p.stats,dict(hp=110,atk=75,**{'def':50},speed=110,spatk=70,spdef=60))
    def test_nature_ev(self):
        p=make_pokemon('PIKACHU',['THUNDERBOLT'],nature='TIMID',evs={'speed':252})
        self.assertEqual(p.stats['speed'],156); self.assertEqual(p.stats['atk'],67)
    def test_shedinja_hp(self): self.assertEqual(make_pokemon('SHEDINJA',['SHADOW_SNEAK']).hp,1)
    def test_ev_validation(self):
        with self.assertRaises(ValueError): make_pokemon('PIKACHU',['TACKLE'],evs={'atk':255,'speed':255,'hp':1})
    def test_unknown_ability(self):
        with self.assertRaises(ValueError): make_pokemon('PIKACHU',['TACKLE'],ability='MAGIC_GUARD')
    def test_stage(self):
        self.assertEqual([stage(100,n) for n in (-6,-2,0,2,6)], [25,50,100,200,400])
    def test_speed(self):
        self.assertEqual(effective_speed(mon(status='paralysis'),Field())[0],25)
        self.assertEqual(effective_speed(mon(status='paralysis',ability='QUICK_FEET'),Field())[0],150)
    def test_speed_weather(self):
        p=mon(ability='SWIFT_SWIM',item='CHOICE_SCARF',status='paralysis')
        self.assertEqual(effective_speed(p,Field(weather='rain'))[0],75)
        self.assertEqual(effective_speed(p,Field(weather='rain'),mon(ability='CLOUD_NINE'))[0],37)
    def test_speed_simple(self): self.assertEqual(effective_speed(mon(ability='SIMPLE',stages={'speed':2}),Field())[0],300)
    def test_tailwind(self): self.assertEqual(effective_speed(mon(tailwind=True),Field())[0],200)
    def test_priority_and_room(self):
        a=mon(); b=mon(); a.stats=dict(a.stats,speed=10)
        self.assertEqual(first_actor(a,b,Move.get('QUICK_ATTACK'),Move.get('EARTHQUAKE'),Field(),random.Random(1)),0)
        self.assertEqual(first_actor(a,b,a.moves[0],b.moves[0],Field(trick_room=True),random.Random(1)),0)
    def test_lagging_tail(self):
        self.assertEqual(first_actor(mon(item='LAGGING_TAIL'),mon(),Move.get('QUICK_ATTACK'),Move.get('EARTHQUAKE'),Field(),random.Random(1)),0)
    def test_tie_seed(self):
        values=[first_actor(mon(),mon(),Move.get('EARTHQUAKE'),Move.get('EARTHQUAKE'),Field(),random.Random(i)) for i in range(30)]
        self.assertEqual(set(values),{0,1})
    def test_base_damage(self): self.assertEqual(damage(mon(),mon(),Move.get('EARTHQUAKE'),Field())['damage'],46)
    def test_burn_before_plus_two(self): self.assertEqual(damage(mon(status='burn'),mon(),Move.get('EARTHQUAKE'),Field())['damage'],24)
    def test_reflect(self): self.assertEqual(damage(mon(),mon(),Move.get('EARTHQUAKE'),Field(reflect=(False,True)))['damage'],24)
    def test_crit_ignores_bad_stages_screen(self):
        self.assertEqual(damage(mon(stages={'atk':-6}),mon(stages={'def':6}),Move.get('EARTHQUAKE'),Field(reflect=(False,True)),critical=True)['damage'],92)
    def test_critical_keeps_good_stages(self):
        self.assertEqual(damage(mon(stages={'atk':2}),mon(),Move.get('EARTHQUAKE'),Field(),critical=True)['damage'],180)
    def test_rolls(self):
        r=damage_range(mon(),mon(),Move.get('EARTHQUAKE'),Field())
        self.assertEqual((r['min'],r['max'],len(r['rolls'])),(39,46,16))
    def test_stab(self): self.assertEqual(damage(mon(types=('GROUND',)),mon(),Move.get('EARTHQUAKE'),Field())['damage'],69)
    def test_immunity(self): self.assertEqual(damage(mon(),mon(types=('FLYING',)),Move.get('EARTHQUAKE'),Field())['damage'],0)
    def test_dual_type(self): self.assertEqual(matchup('ICE',mon(types=('DRAGON','FLYING'))),4)
    def test_gen4_steel_resists(self):
        self.assertEqual(matchup('GHOST',mon(types=('STEEL',))),Fraction(1,2)); self.assertEqual(matchup('DARK',mon(types=('STEEL',))),Fraction(1,2))
    def test_levitate_mold_breaker(self):
        self.assertEqual(damage(mon(),mon(ability='LEVITATE'),Move.get('EARTHQUAKE'),Field())['damage'],0)
        self.assertEqual(damage(mon(ability='MOLD_BREAKER'),mon(ability='LEVITATE'),Move.get('EARTHQUAKE'),Field())['damage'],46)
    def test_fixed_damage(self):
        self.assertEqual(damage(mon(),mon(),Move.get('SEISMIC_TOSS'),Field())['damage'],50)
        self.assertEqual(damage(mon(),mon(types=('GHOST',)),Move.get('SEISMIC_TOSS'),Field())['damage'],0)
    def test_crit_probability(self):
        self.assertEqual(critical_probability(mon(),mon(),Move.get('EARTHQUAKE')),Fraction(1,16))
        self.assertEqual(critical_probability(mon(),mon(ability='BATTLE_ARMOR'),Move.get('SLASH')),0)
    def test_unknown_move_effect_fails(self):
        with self.assertRaises(UnsupportedMove): damage(mon(),mon(),Move.get('METRONOME'),Field())
    def test_ai_immune_penalty(self):
        a=make_pokemon('PIKACHU',['THUNDERBOLT','QUICK_ATTACK']); b=make_pokemon('SANDSHREW',['TACKLE'])
        action,rows=choose([a],0,b,Field(),random.Random(32))
        self.assertEqual(action.index,1); self.assertEqual(rows[0]['damage']['max'],0)
    def test_ai_heal_item(self):
        a=mon(hp=20); action,_=choose([a],0,mon(),Field(),random.Random(1),potions=1)
        self.assertEqual(action.kind,'potion')
    def test_pp_fallback(self):
        a=mon(pp=[0]); self.assertEqual(choose([a],0,mon(),Field(),random.Random(1))[0].kind,'struggle')
    def test_choice_lock(self):
        a=make_pokemon('PIKACHU',['THUNDERBOLT','QUICK_ATTACK'],choice_lock=1)
        self.assertEqual(legal_moves(a),[1])
    def test_simulation_deterministic(self):
        from battlelab.__main__ import example
        def run():
            raw=example(); teams=[[make_pokemon(**p) for p in t] for t in raw['teams']]; b=Battle(*teams); log=[]
            for i in range(100):
                if b.winner() is not None: return log,b.winner()
                log+=b.step()
            self.fail('No completion')
        self.assertEqual(run(),run())
    def test_illegal_action_atomic(self):
        a=mon(); b=Battle([a],[mon()])
        with self.assertRaises(ValueError): b.step([Action('move',99),Action('move',0)])
        self.assertEqual(b.turn,0); self.assertEqual(a.pp,[10])
    def test_battle_rejects_freeze(self):
        with self.assertRaises(ValueError): Battle([make_pokemon('LAPRAS',['ICE_BEAM'])],[mon()])
    def test_struggle_typeless_and_no_technician(self):
        a=mon(ability='TECHNICIAN'); b=mon(types=('GHOST',),ability='WONDER_GUARD')
        self.assertEqual(damage(a,b,Move.get('STRUGGLE'),Field())['damage'],24)
    def test_struggle_battle_recoil(self):
        a=mon(pp=[0]); b=mon(pp=[0]); battle=Battle([a],[b],seed=32)
        battle.step([Action('struggle'),Action('struggle')])
        self.assertLessEqual(a.hp,150); self.assertLessEqual(b.hp,150)
    def test_original_ai_extraction(self):
        self.assertEqual(len(data('ai_commands')),109)
        self.assertEqual(data('ai_commands')[4]['name'],'AICmd_AddToMoveScore')
        self.assertEqual(data('ai_wordcode')['entries'][0],32)
        self.assertEqual(len(data('ai_wordcode')['entries']),32)
    def test_full_battle_many_seeds(self):
        from battlelab.__main__ import example
        for seed in range(50):
            raw=example(); teams=[[make_pokemon(**p) for p in t] for t in raw['teams']]; b=Battle(*teams,seed=seed)
            for _ in range(100):
                if b.winner() is not None: break
                b.step()
            self.assertIsNotNone(b.winner())
            for team in teams:
                for p in team:
                    self.assertTrue(0<=p.hp<=p.max_hp); self.assertTrue(all(v>=0 for v in p.pp))
if __name__=='__main__': unittest.main()
