#!/usr/bin/env bash
# demos/mission/mission-demo.md의 Bash 블록을 순서대로 실행하는 전체 리허설 명령 모음.
# 저장소 루트에서 bash demos/mission/commands.sh 로 실행한다.
# 오류 시연 명령의 종료 코드 2는 예상된 결과다.
# 매 실행마다 새 가상 데이터 폴더를 생성하고 기존 데이터는 변경하지 않는다.

python --version
python -m budget_app --help
DEMO_DIR="$(python scripts/prepare_demo.py)"
export DEMO_DIR
printf '시연 폴더: %s\n' "$DEMO_DIR"
LUNCH_ID=TX-00000000000340008000000000000001
BOOK_ID=TX-00000000000640008000000000000001
MISSING_ID=TX-ffffffffffff4fff8fffffffffffffff

python -m budget_app --data-dir "$DEMO_DIR" add <<'INPUT'
2026-11-04
expense
식비
20000
시연 점심
식사,학교
INPUT

# 추가 직후 별도 프로세스로 저장된 거래를 조회한다.
python -m budget_app --data-dir "$DEMO_DIR" search --from 2026-11-04 --to 2026-11-04 --category 식비 --type expense --q '시연 점심' --tag 학교

python -m budget_app --data-dir "$DEMO_DIR" list --limit 3

python -m budget_app --data-dir "$DEMO_DIR" search --from 2026-11-01 --to 2026-11-30 --category 식비 --type expense --q 점심 --tag 학교 --limit 20

python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3

python -m budget_app --data-dir "$DEMO_DIR" budget set --month 2026-11 --amount 150000
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3
python -m budget_app --data-dir "$DEMO_DIR" budget set --month 2026-11 --amount 100000
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3

printf '임시분류\n' | python -m budget_app --data-dir "$DEMO_DIR" category add
python -m budget_app --data-dir "$DEMO_DIR" category list
printf '임시분류\n' | python -m budget_app --data-dir "$DEMO_DIR" category remove
printf '식비\n' | python -m budget_app --data-dir "$DEMO_DIR" category remove
CATEGORY_EXIT=$?
printf '사용 중 카테고리 삭제 종료 코드: %s (예상 2)\n' "$CATEGORY_EXIT"
test "$CATEGORY_EXIT" -eq 2

python -m budget_app --data-dir "$DEMO_DIR" update --id "$LUNCH_ID" --memo '수정된 학교 점심' --tags '식사,학교,수정'
python -m budget_app --data-dir "$DEMO_DIR" search --q '수정된 학교 점심'
python -m budget_app --data-dir "$DEMO_DIR" update --id "$MISSING_ID" --memo '없는 거래'
UPDATE_EXIT=$?
printf '없는 ID 수정 종료 코드: %s (예상 2)\n' "$UPDATE_EXIT"
test "$UPDATE_EXIT" -eq 2

python -m budget_app --data-dir "$DEMO_DIR" delete --id "$BOOK_ID"
python -m budget_app --data-dir "$DEMO_DIR" delete --id "$BOOK_ID"
DELETE_EXIT=$?
printf '없는 ID 삭제 종료 코드: %s (예상 2)\n' "$DELETE_EXIT"
test "$DELETE_EXIT" -eq 2
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3

python -m budget_app --data-dir "$DEMO_DIR" import --from demos/mission/import.csv
python -m budget_app --data-dir "$DEMO_DIR" summary --month 2026-11 --top 3

BEFORE_HASH="$(python -c 'import hashlib,os,pathlib; print(hashlib.sha256((pathlib.Path(os.environ["DEMO_DIR"])/"transactions.jsonl").read_bytes()).hexdigest())')"
python -m budget_app --data-dir "$DEMO_DIR" import --from demos/mission/invalid.csv
IMPORT_EXIT=$?
printf '잘못된 CSV 종료 코드: %s (예상 2)\n' "$IMPORT_EXIT"
test "$IMPORT_EXIT" -eq 2
AFTER_HASH="$(python -c 'import hashlib,os,pathlib; print(hashlib.sha256((pathlib.Path(os.environ["DEMO_DIR"])/"transactions.jsonl").read_bytes()).hexdigest())')"
test "$BEFORE_HASH" = "$AFTER_HASH" && echo 'PASS: CSV 오류 시 원본 바이트 보존'

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
