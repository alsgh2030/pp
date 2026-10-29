# HGSS Battle Lab

하트골드·소울실버 소스를 분석해 만든 **Python 전투 메커니즘 계산기 + 설명 가능한 실험 AI + 싱글 배틀 실습 프로젝트**입니다. ROM과 DS SDK 없이 실행됩니다.

원작 AI 소스와 109개 명령·판단 워드코드를 연구 자료로 추출했습니다. Python AI는 점수제 구조를 활용한 **새 실험 정책**이며 원작 AI 전체의 완전 이식은 아닙니다. 상세 분석과 지원/미지원 범위는 [docs/MECHANICS.md](docs/MECHANICS.md)를 읽어 주세요.

## 실행 — Windows PowerShell 기준

ZIP을 풀고 이 README가 있는 폴더를 VS Code로 여세요. Python 3.10 이상이면 외부 패키지 설치가 필요 없습니다. Anaconda 환경도 가능합니다.

```powershell
python --version
python -m battlelab demo
python -m battlelab play
python -m battlelab analyze --scenario examples/johto.json
python -m unittest discover -s tests -v
```

`run_demo.bat`을 더블클릭해도 자동 배틀이 실행됩니다. `play`에서는 기술 번호(1부터), `s 2`(두 번째 포켓몬 교체), `item`, `auto`, `q`를 입력합니다. 회복 도구는 기본 0개이며 JSON에서 `"potions": [2, 2]`로 지정할 수 있습니다. 예제 배틀은 최대 50턴 후 중단되며, 미종료를 승리로 처리하지 않습니다.

## 주요 기능

- IV/EV/성격/레벨 기반 실능력치 계산.
- 스피드 랭크, 마비 1/4, 구애스카프, 순풍, 날씨 특성, 트릭룸·우선도 비교.
- 물리/특수 대미지, 85~100 난수 16종, 자속, 4세대 타입 상성, 급소, 화상, 벽, 날씨 및 명시된 특성·도구.
- AI 기술 점수와 선택 이유, 예상 피해와 조건부 KO 확률 출력.
- 자동/수동 싱글 배틀, PP·교체·회복·주요 상태·일부 부가효과.
- 원본 기술 467개(+NONE), 포켓몬/폼 데이터, 원본 AI C 코드 탐색.

```powershell
python -m battlelab move THUNDERBOLT
python -m battlelab supported
python -m battlelab original-ai --opcode 4
python -m battlelab original-ai > original_ai_index.json
python -m battlelab analyze > analysis.json
python -m battlelab demo --seed 32 --turns 100
```

기술·포켓몬 이름은 영문 상수명을 사용합니다. 예: `TYPHLOSION`, `FERALIGATR`, `FLAMETHROWER`. 출력 데이터 설명과 문서는 한국어입니다. 기본 특성은 의도적으로 `NONE`이므로 실제 특성을 적용하려면 JSON에 명시하세요. 모든 기술·특성을 지원하는 것은 아니며 지원하지 않는 효과는 오류로 알려줍니다.

## Python에서 직접 사용

```python
from battlelab.models import make_pokemon, Move, Field
from battlelab.mechanics import damage, damage_range, effective_speed
from battlelab.ai import evaluate

a = make_pokemon('TYPHLOSION', ['FLAMETHROWER'], ability='BLAZE')
b = make_pokemon('MEGANIUM', ['ENERGY_BALL'])
field = Field(weather='sun')
print(effective_speed(a, field, b))
print(damage_range(a, b, Move.get('FLAMETHROWER'), field))
print(damage(a, b, Move.get('FLAMETHROWER'), field)['trace'])
print(evaluate(a, b, field))
```

`examples/johto.json`에서 `level`, `nature`, `ivs`, `evs`, `ability`, `item`, `status`, `stages`, `hp`를 변경할 수 있습니다. 예: `"nature": "TIMID"`, `"evs": {"speed":252,"spatk":252,"hp":4}`, `"stages": {"speed": 1}`, `"status":"paralysis"`. 성격/종/기술/특성/도구는 영어 이름이며 스탯 키는 `hp, atk, def, speed, spatk, spdef`입니다.

## 구조

| 경로 | 역할 |
|---|---|
| `battlelab/models.py` | 데이터 로딩, 포켓몬·기술·필드, 실능력치 |
| `battlelab/mechanics.py` | 스피드·순서·명중·급소·피해 계산 |
| `battlelab/ai.py` | 수정 가능한 점수 정책과 설명 |
| `battlelab/engine.py` | 싱글 턴제 진행 |
| `battlelab/__main__.py` | 자동 배틀·수동 배틀·분석 CLI |
| `battlelab/data/` | 원본에서 추출한 JSON과 출처 해시 |
| `reference/` | 원본 AI·전투 계산 연구 코드 |
| `tools/extract_reference.py` | 지정 저장소에서 데이터 재추출 |
| `tests/` | 계산 기준값·경계·배틀 검증 |
| `docs/MECHANICS.md` | 원본 분석과 구현 범위 설명 |

원본 재추출은 기존 저장소를 소유한 경우 `python tools/extract_reference.py ../pokeheartgold`로 실행합니다. 지정 커밋을 체크아웃해 재현하세요. `pip install -e .`는 선택 사항이며 기본 실행에는 필요 없습니다. 원본 소스 표시 명령은 ZIP 전체를 유지한 작업 폴더에서 사용하세요.
