"""Extract reproducible metadata and AI research sources from a local checkout."""
import argparse, hashlib, json, re, shutil, struct, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def export(repo):
    data = ROOT / 'battlelab/data'
    def dump(name, obj):
        (data/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    def constants(path, prefix):
        return {int(n): key for key,n in re.findall(r'^#define '+prefix+r'(\w+)\s+(\d+)\s*$', (repo/path).read_text(), re.M)}
    names = constants('include/constants/moves.h', 'MOVE_')
    types = constants('include/constants/pokemon.h', 'TYPE_')
    blob = (repo/'files/poketool/waza/waza_tbl.narc').read_bytes()
    pos = 16; members = []; image = b''
    while pos < len(blob):
        tag, size = struct.unpack_from('<4sI', blob, pos)
        if tag == b'BTAF':
            count = struct.unpack_from('<H', blob, pos+8)[0]
            members = [struct.unpack_from('<II', blob, pos+12+i*8) for i in range(count)]
        if tag == b'GMIF': image = blob[pos+8:pos+size]
        pos += size
    payload = b''.join(image[a:b] for a,b in members)
    assert len(payload) % 16 == 0
    moves = {}
    for i in range(len(payload)//16):
        if i not in names: continue  # Alignment/padding records beyond MOVE_SHADOW_FORCE.
        effect,cat,power,typ,accuracy,pp,chance,target,priority,flags = struct.unpack_from('<H6BHbB',payload,i*16)
        moves[names.get(i,str(i))] = dict(id=i,effect=effect,category=('physical','special','status')[cat],power=power,type=types[typ],accuracy=accuracy,pp=pp,chance=chance,target=target,priority=priority,flags=flags)
    dump('moves.json',moves)
    raw=json.loads((repo/'files/poketool/personal/personal.json').read_text())['baseStats']
    dump('species.json',{x['species']:dict(stats={k:x[k] for k in ('hp','atk','def','speed','spatk','spdef')},types=list(dict.fromkeys(t.removeprefix('TYPE_') for t in x['types'])),abilities=[a.removeprefix('ABILITY_') for a in x['abilities']]) for x in raw if x['hp']})
    util=(repo/'src/battle/battle_util.c').read_text()
    section=util.split('static const u8 sTypeEffectiveness[][3] = {')[1].split('};')[0]
    factors={'NOT_EFFECTIVE':0.5,'SUPER_EFFECTIVE':2,'NO_EFFECT':0}
    dump('types.json',[dict(attack=a,defend=d,factor=factors[f]) for a,d,f in re.findall(r'\{ TYPE_(\w+),\s+TYPE_(\w+),\s+TYPE_MUL_(\w+)',section) if a not in ('FORESIGHT','ENDTABLE')])
    asm=(repo/'asm/trainer_ai_data.s').read_text()
    segment=asm.split('gTrainerAITable:')[1].split('sAICommandTable:')[0]
    # Only the consecutive .byte directives directly under gTrainerAITable.
    values=[]
    for line in segment.splitlines():
        if line.strip().startswith('.byte'):
            values.extend(int(x,16) for x in re.findall(r'0x[0-9A-Fa-f]+',line))
        elif values and line.strip(): break
    words=list(struct.unpack('<'+'I'*(len(values)//4),bytes(values)))
    dump('ai_wordcode.json',dict(entries=words[:32],words=words))
    commands=re.findall(r'\.word (AICmd_\w+)',asm.split('sAICommandTable:')[1])
    c=(repo/'src/battle/trainer_ai.c').read_text()
    commands_info=[]
    for i,name in enumerate(commands):
        match=re.search(r'void '+name+r'\([^;]*?\) \{',c)
        body=''
        if match:
            start=match.end(); depth=1; end=start
            while depth:
                if c[end]=='{': depth+=1
                if c[end]=='}': depth-=1
                end+=1
            body=c[start:end-1]
        commands_info.append(dict(opcode=i,name=name,reads=len(re.findall(r'AIScript_Read\(ctx\)',body)),source_line=c[:match.start()].count('\n')+1 if match else None))
    dump('ai_commands.json',commands_info)
    paths=['src/battle/trainer_ai.c','asm/trainer_ai_data.s','src/battle/battle_util.c','src/battle/battle_command.c','src/battle/battle_controller_opponent.c','include/battle/trainer_ai.h','include/constants/battle/trainer_ai.h','include/move.h','include/constants/moves.h']
    hashes={}
    for p in paths:
        dest=ROOT/'reference'/p; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(repo/p,dest)
        hashes[p]=hashlib.sha256((repo/p).read_bytes()).hexdigest()
    dump('provenance.json',dict(repository='https://github.com/ctrl-cheeb-del/pokeheartgold',commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),sha256=hashes,move_count=len(moves),species_count=len(raw)))
    print(f'Extracted {len(moves)} moves, {len(raw)} personal records, {len(commands)} AI commands, {len(words)} words')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('repo',type=Path); export(p.parse_args().repo.resolve())
