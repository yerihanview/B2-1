# 미션 기능 시연: 복사해서 실행하는 명령어

Python 3.10 이상, 외부 패키지 불필요. Bash 터미널에서 저장소 루트로 이동한 뒤 **아래 순서대로 같은 터미널에서** 실행한다. PowerShell에서는 Bash 터미널을 사용한다. 실제 옵션은 `--limit`, `--from`, `--month`처럼 하이픈 두 개다. `--data-dir`는 하위 명령 앞에 둔다.

전체를 자동으로 연습하려면 저장소 루트에서 `bash demos/mission/commands.sh`를 실행한다. 아래 블록은 발표용 단계별 복사본이다.

## 0. 준비 — 기존 데이터와 분리

```bash
python --version
python -m budget_app --help
DEMO_DIR="$(python scripts/prepare_demo.py)"
export DEMO_DIR
printf '시연 폴더: %s\n' "$DEMO_DIR"
LUNCH_ID=TX-00000000000340008000000000000001
BOOK_ID=TX-00000000000640008000000000000001
MISSING_ID=TX-ffffffffffff4fff8fffffffffffffff
```

준비 스크립트는 매번 `data/mission-demo-고유문자열/`을 새로 만든다. 기존 폴더를 삭제하거나 덮어쓰지 않는다. 다시 시작하려면 이 준비 블록부터 실행한다. 이전 터미널을 닫았다면 출력됐던 경로를 `DEMO_DIR`에 다시 지정하면 데이터가 유지된다.

모든 예시는 가상 데이터다. 원본은 `demos/mission/data/`에 있고 실행용 복사본만 변경한다.

| 날짜 | 타입 | 카테고리 | 금액 | 메모 |
|---|---|---|---:|---|
| 10/31 | 지출 | 식비 | 9,000 | 지난달 식사 |
| 11/01 | 수입 | 용돈 | 300,000 | 11월 가상 용돈 |
| 11/02 | 지출 | 식비 | 15,000 | 학교 점심 |
| 11/02 | 지출 | 식비 | 45,000 | 친구와 저녁 |
| 11/03 | 지출 | 교통 | 10,000 | 교통카드 충전 |
| 11/03 | 지출 | 도서 | 30,000 | 파이썬 책 |

11월 초기 합계는 수입 300,000원 / 지출 100,000원 / 잔액 200,000원이다. 같은 날짜의 거래는 나중에 저장된 거래가 먼저 표시된다.

## 1. 거래 추가(add) — A01 / T01

발표에서는 아래 명령을 입력하고 날짜·타입·카테고리·금액·메모·태그를 차례대로 입력한다.

```text
python -m budget_app --data-dir "$DEMO_DIR" add
2026-11-04
expense
식비
20000
시연 점심
식사,학교
```

자동 입력으로 재현하려면 **위 수동 입력 대신** 다음 블록을 한 번 실행한다. 둘 다 실행하면 2건이 추가된다.

```bash
python -m budget_app --data-dir "$DEMO_DIR" add <<'INPUT'
2026-11-04
expense
식비
20000
시연 점심
식사,학교
INPUT
```

예상: `[저장 완료] id=TX-...` 출력. ID는 매번 새로 생성된다. 전체 7건, 11월 지출 120,000원.

### 추가 직후 저장 결과 확인

수동 입력 또는 자동 입력 중 하나를 마친 뒤, 아래 명령을 실행한다. 별도 Python 프로세스가 저장 파일을 다시 읽어 방금 추가한 거래를 보여준다.

```bash
python -m budget_app --data-dir "$DEMO_DIR" search --from 2026-11-04 --to 2026-11-04 --category 식비 --type expense --q '시연 점심' --tag 학교
```

예상: `2026-11-04 / expense / 식비 / 20000 / 시연 점심` 거래 **1건**이 표시된다. 행의 ID가 위 `[저장 완료]` 메시지의 ID와 같은지 확인한다. 태그 `식사,학교`는 추가 입력값이며 표에는 별도 태그 열이 없지만, `--tag 학교` 검색으로 해당 태그의 저장도 확인한다.

이후 2번에서는 다른 거래와 함께 최신순 목록을, 마지막 단계에서는 JSONL 파일 전체와 CSV를 확인한다. 추가 성공 확인을 마지막까지 미루지 않는다.

## 2. 거래 목록(list) — A01,A11 / T02,T17

```bash
python -m budget_app --data-dir "$DEMO_DIR" list --limit 3
```

예상: 시연 점심 → 파이썬 책 → 교통카드 충전 순서로 3건. 화면에서는 최신순·limit을 확인한다. 스트리밍 구현 자체는 `repository.py`의 `iter_transactions()`와 `service.py`의 제한된 힙 처리로 설명한다. 이 소규모 시연만으로 10만 건 성능을 입증하지는 않는다.

## 3. 거래 검색(search) — A01 / T03

```bash
python -m budget_app --data-dir "$DEMO_DIR" search --from 2026-11-01 --to 2026-11-30 --category 식비 --type expense --q 점심 --tag 학교 --limit 20
```

예상: 조건은 AND로 결합되어 시연 점심과 학교 점심 2건만 최신순으로 표시된다.

## 4. 월별 요약(summary) — A01,A04 / T04

```bash
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
```

예상: 수입 300,000 / 지출 120,000 / 잔액 180,000원. TOP 3은 식비 80,000 → 도서 30,000 → 교통 10,000원. 지난달 9,000원은 제외된다.

## 5. 예산 설정·조회(budget) — A04 / T05,T12

```bash
python -m budget_app --data-dir "$DEMO_DIR" budget set --month 2026-11 --amount 150000
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
python -m budget_app --data-dir "$DEMO_DIR" budget set --month 2026-11 --amount 100000
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
```

예상: 저장 성공 → 사용률 80.0%, 초과 경고 없음 → 예산 갱신 → 사용률 120.0%, `[경고] 예산 초과`. 별도 budget 조회 명령 대신 summary에서 조회한다.

## 6. 카테고리 관리(category) — A03,A06,A07 / T11

```bash
printf '임시분류\n' | python -m budget_app --data-dir "$DEMO_DIR" category add
python -m budget_app --data-dir "$DEMO_DIR" category list
printf '임시분류\n' | python -m budget_app --data-dir "$DEMO_DIR" category remove
python -m budget_app --data-dir "$DEMO_DIR" category list
printf '식비\n' | python -m budget_app --data-dir "$DEMO_DIR" category remove
CATEGORY_EXIT=$?
printf '사용 중 카테고리 삭제 종료 코드: %s (예상 2)\n' "$CATEGORY_EXIT"
test "$CATEGORY_EXIT" -eq 2
python -m budget_app --data-dir "$DEMO_DIR" category list
python - "$DEMO_DIR" <<'PYTHON'
import json
from pathlib import Path
import sys

names = {json.loads(line)['name'] for line in (Path(sys.argv[1]) / 'categories.jsonl').read_text(encoding='utf-8').splitlines()}
assert '임시분류' not in names and '식비' in names
assert names == {'용돈', '식비', '교통', '도서'}
print('PASS: 임시분류 삭제 확인·삭제 거부된 식비와 나머지 분류 유지')
PYTHON
```

예상: 미사용 카테고리는 추가·삭제 성공. 삭제 직후 목록에서 임시분류가 사라지고, 식비 삭제 거부 후에는 식비가 그대로 남아 있음을 확인한다. 식비는 참조 거래 4건 때문에 삭제 거부. 오류 원인·해결 힌트가 나오고 traceback은 없다. 대화형으로 보여주려면 `printf ... |` 부분을 빼고 프롬프트에 카테고리를 입력한다.

## 7. 거래 수정(update) — A01,A06,A07 / T06

```bash
python -m budget_app --data-dir "$DEMO_DIR" search --q '학교 점심'
python -m budget_app --data-dir "$DEMO_DIR" update --id "$LUNCH_ID" --memo '수정된 학교 점심' --tags '식사,학교,수정'
python -m budget_app --data-dir "$DEMO_DIR" search --q '수정된 학교 점심' --tag 수정
python - "$DEMO_DIR" "$LUNCH_ID" <<'PYTHON'
import json
from pathlib import Path
import sys

identifier = sys.argv[2]
def find(path):
    return next(row for row in map(json.loads, path.read_text(encoding='utf-8').splitlines()) if row['id'] == identifier)

before = find(Path('demos/mission/data/transactions.jsonl'))
after = find(Path(sys.argv[1]) / 'transactions.jsonl')
print('수정 전:', json.dumps(before, ensure_ascii=False))
print('수정 후:', json.dumps(after, ensure_ascii=False))
expected = dict(before, memo='수정된 학교 점심', tags=['식사', '학교', '수정'])
assert after == expected
print('PASS: 메모·태그만 변경, ID·날짜·타입·카테고리·금액 유지')
PYTHON
python -m budget_app --data-dir "$DEMO_DIR" update --id "$MISSING_ID" --memo '없는 거래'
UPDATE_EXIT=$?
printf '없는 ID 수정 종료 코드: %s (예상 2)\n' "$UPDATE_EXIT"
test "$UPDATE_EXIT" -eq 2
```

예상: 수정 전·후 검색 결과와 저장 레코드를 표시한다. 원래 학교 점심의 ID·날짜·타입·카테고리·금액은 유지되고 메모·태그만 변경된다. 표에 없는 태그도 JSON과 `--tag 수정` 검색으로 확인한다. 없는 ID는 실패. 수정 방식은 옵션 방식으로 고정되어 있다.

## 8. 거래 삭제(delete) — A01,A06,A07 / T07

```bash
python -m budget_app --data-dir "$DEMO_DIR" delete --id "$BOOK_ID"
python -m budget_app --data-dir "$DEMO_DIR" list --limit 20
python - "$DEMO_DIR" "$BOOK_ID" <<'PYTHON'
import json
from pathlib import Path
import sys

folder = Path(sys.argv[1])
rows = [json.loads(line) for line in (folder / 'transactions.jsonl').read_text(encoding='utf-8').splitlines()]
seed = [json.loads(line) for line in Path('demos/mission/data/transactions.jsonl').read_text(encoding='utf-8').splitlines()]
remaining = {row['id'] for row in rows}
assert sys.argv[2] not in remaining
assert {row['id'] for row in seed if row['id'] != sys.argv[2]} <= remaining
assert len(rows) == 6 and sum(row['memo'] == '시연 점심' for row in rows) == 1
print('PASS: 삭제 ID 없음·나머지 거래 유지·전체 6건')
PYTHON
python -m budget_app --data-dir "$DEMO_DIR" delete --id "$BOOK_ID"
DELETE_EXIT=$?
printf '없는 ID 삭제 종료 코드: %s (예상 2)\n' "$DELETE_EXIT"
test "$DELETE_EXIT" -eq 2
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
```

시연용 파이썬 책 1건을 삭제한다. 바로 목록 전체를 출력해 해당 ID가 없고, 원래의 다른 거래 5건과 추가한 시연 점심 1건이 남아 있는지 확인한다. 확인 프롬프트는 없다. 두 번째 삭제는 없는 ID 오류. 11월 지출 90,000원 / 잔액 210,000원 / 예산 사용률 90.0%로 변경된다.

## 9. 가져오기(import) — A05,A16 / T09,T13,T19

```bash
python -m budget_app --data-dir "$DEMO_DIR" import --from demos/mission/import.csv
python -m budget_app --data-dir "$DEMO_DIR" search --from 2026-11-04 --to 2026-11-04 --q 가상
python - "$DEMO_DIR" <<'PYTHON'
import json
from pathlib import Path
import sys

rows = [json.loads(line) for line in (Path(sys.argv[1]) / 'transactions.jsonl').read_text(encoding='utf-8').splitlines()]
imported = [row for row in rows if row['memo'] in ('가상 간식', '가상 버스')]
assert len(imported) == 2
assert {(row['date'], row['type'], row['category'], row['amount'], row['memo'], tuple(row['tags'])) for row in imported} == {
    ('2026-11-04', 'expense', '식비', 5000, '가상 간식', ('식사', '학교')),
    ('2026-11-04', 'expense', '교통', 7000, '가상 버스', ('통학',)),
}
for row in imported:
    print('가져온 거래:', json.dumps(row, ensure_ascii=False))
print('PASS: 가져온 2건의 날짜·타입·카테고리·금액·메모·태그 확인')
PYTHON
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
```

예상: `imported=2, skipped=0`. 이어지는 검색에서 가상 버스 → 가상 간식 순서로 2건이 표시되며 저장된 각 필드도 검증한다. 간식 5,000원과 버스 7,000원 추가. 11월 지출 102,000원 / 잔액 198,000원 / 사용률 102.0%와 초과 경고. 같은 CSV를 다시 가져오면 새 ID로 중복 추가되므로 한 번만 실행한다.

정상 행과 오류 행이 섞인 CSV의 전체 미반영도 확인한다.

```bash
BEFORE_HASH="$(python -c 'import hashlib,os,pathlib; print(hashlib.sha256((pathlib.Path(os.environ["DEMO_DIR"])/"transactions.jsonl").read_bytes()).hexdigest())')"
python -m budget_app --data-dir "$DEMO_DIR" import --from demos/mission/invalid.csv
IMPORT_EXIT=$?
printf '잘못된 CSV 종료 코드: %s (예상 2)\n' "$IMPORT_EXIT"
test "$IMPORT_EXIT" -eq 2
AFTER_HASH="$(python -c 'import hashlib,os,pathlib; print(hashlib.sha256((pathlib.Path(os.environ["DEMO_DIR"])/"transactions.jsonl").read_bytes()).hexdigest())')"
test "$BEFORE_HASH" = "$AFTER_HASH" && echo 'PASS: CSV 오류 시 원본 바이트 보존'
```

예상: 3행의 음수 금액 오류와 전체 미반영 안내. 정상 행도 추가되지 않고 거래 파일 해시가 동일하다.

## 10. 내보내기(export) 및 영구 저장 — A02,A05 / T08,T10,T13

```bash
python -m budget_app --data-dir "$DEMO_DIR" export --out "$DEMO_DIR/november.csv" --month 2026-11
python -m budget_app --data-dir "$DEMO_DIR" export --out "$DEMO_DIR/november-range.csv" --from 2026-11-01 --to 2026-11-30
python - "$DEMO_DIR" <<'PY'
import csv
import json
from pathlib import Path
import sys

folder = Path(sys.argv[1])
for name in ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl'):
    path = folder / name
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    print(f'{path.name}: {len(rows)}건')
    print(path.read_text(encoding='utf-8'))
    assert len(rows) == {'transactions.jsonl': 8, 'categories.jsonl': 4, 'budgets.jsonl': 1}[name]

for name in ('november.csv', 'november-range.csv'):
    path = folder / name
    print(path.read_text(encoding='utf-8'))
    with path.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ['date', 'type', 'category', 'amount', 'memo', 'tags']
    assert len(rows) == 8  # 헤더 1행과 11월 거래 7건.
print('PASS: 3파일 영구 저장·CSV 7건')
PY
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
```

예상: `exported=7`, CSV 두 파일 생성. JSONL은 전체 거래 8건(10월 1건 포함)·카테고리 4건·예산 1건이다. 명령마다 Python 프로세스가 종료되고 다음 명령이 파일을 다시 읽으므로 마지막 summary에서 동일한 잔액 198,000원을 확인하는 것이 재시작 후 영속성 시연이다.

내보내기는 목록 표시와 달리 원본 파일 순서다. 파일이 이미 있으면 덮어쓰기를 거부한다. 반복 시연은 준비부터 새 폴더로 시작한다.

## 최종 결과물 설명

- 필수 영구 저장 파일: `transactions.jsonl`, `categories.jsonl`, `budgets.jsonl` — UTF-8, 한 줄에 JSON 객체 하나.
- CSV: UTF-8(BOM 없음), 헤더 `date,type,category,amount,memo,tags`. 태그의 쉼표는 CSV quoting으로 보존한다. ID는 CSV에 없고 import 시 새로 할당한다.
- `README.md`의 실행·저장 위치와 안전성·주요 명령·CSV 스키마 절에서 필수 문서 구성을 확인할 수 있다.
- 목표 검수: A01~A07,A11,A16 및 T01~T15,T19. 스트리밍의 대용량 검증은 기존 T17과 benchmark를 별도로 사용한다.
- 위 시연의 자동 실행 확인은 발표자의 실제 최종 데모 검수를 대신하지 않는다.
