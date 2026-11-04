#!/usr/bin/env bash
# demos/bonus/bonus-demo.md의 Bash 블록을 순서대로 실행한다.
# 기본 데모와 별도의 새 데이터 폴더를 사용한다.
set -euo pipefail

BONUS_DIR="$(python scripts/prepare_bonus_demo.py)"
export BONUS_DIR
printf '보너스 전용 데이터: %s\n' "$BONUS_DIR"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20

python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 31 --type income --category 용돈 --amount 300000 --memo '가상 월급' --tags '정기'
python -m budget_app --data-dir "$BONUS_DIR" recurring list
python - "$BONUS_DIR" <<'PYTHON'
import json
from pathlib import Path
import sys

folder = Path(sys.argv[1])
rules = [json.loads(line) for line in (folder / 'recurring.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(rules) == 1
rule = rules[0]
assert (rule['day'], rule['type'], rule['category'], rule['amount'], rule['memo'], rule['tags']) == (31, 'income', '용돈', 300000, '가상 월급', ['정기'])
print('저장된 규칙:', json.dumps(rule, ensure_ascii=False))
assert len((folder / 'transactions.jsonl').read_text(encoding='utf-8').splitlines()) == 6
print('PASS: 반복 규칙 저장 확인·등록만으로 거래가 생성되지 않음')
PYTHON
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" search --q '가상 월급'
python - "$BONUS_DIR" <<'PYTHON'
import json
from pathlib import Path
import sys

folder = Path(sys.argv[1])
rows = [json.loads(line) for line in (folder / 'transactions.jsonl').read_text(encoding='utf-8').splitlines()]
rule = json.loads((folder / 'recurring.jsonl').read_text(encoding='utf-8'))
generated = [row for row in rows if row.get('recurring_id') == rule['id']]
assert len(rows) == 7 and len(generated) == 1
row = generated[0]
assert (row['date'], row['type'], row['category'], row['amount'], row['memo'], row['tags'], row['recurring_month']) == ('2026-11-30', 'income', '용돈', 300000, '가상 월급', ['정기'], '2026-11')
print('생성된 거래:', json.dumps(row, ensure_ascii=False))
print('PASS: 말일 보정·생성 거래 1건·규칙과 월 출처 확인')
PYTHON
REPEAT_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
REPEAT_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$REPEAT_BEFORE" = "$REPEAT_AFTER" || exit 1
echo 'PASS: 재적용 후 거래·규칙·카테고리·예산 파일 모두 동일'
python -m budget_app --data-dir "$BONUS_DIR" search --from 2026-11-01 --to 2026-11-30 --q '가상 월급'

INVALID_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
if python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 32 --type expense --category 식비 --amount 10000; then
    echo 'FAIL: 잘못된 날짜를 허용함'; exit 1
else
    CODE=$?
    test "$CODE" -eq 2 || exit 1
    echo 'PASS: day 32 거부, 종료 코드 2'
fi
INVALID_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$INVALID_BEFORE" = "$INVALID_AFTER" || exit 1
echo 'PASS: 잘못된 규칙 등록 거부 후 모든 저장 파일 유지'

FORMAT_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR" search --type expense --limit 20
FORMAT_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$FORMAT_BEFORE" = "$FORMAT_AFTER" || exit 1
echo 'PASS: 표 출력 전후 저장 데이터 동일'
python -m unittest discover -s tests -p 'test_bonus_formatting.py' -v

BACKUP_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
python -m budget_app --data-dir "$BONUS_DIR" backup
FIRST_BACKUP_HASH="$(python -c 'import hashlib,os,pathlib; files=list((pathlib.Path(os.environ["BONUS_DIR"])/"backups").glob("*.zip")); assert len(files)==1; print(hashlib.sha256(files[0].read_bytes()).hexdigest())')"
echo "첫 백업 SHA-256: $FIRST_BACKUP_HASH"
python -m budget_app --data-dir "$BONUS_DIR" backup
python - "$BONUS_DIR" "$FIRST_BACKUP_HASH" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

folder = Path(sys.argv[1])
archives = sorted((folder / 'backups').glob('*.zip'))
assert len(archives) == 2
assert hashlib.sha256(archives[0].read_bytes()).hexdigest() == sys.argv[2]
print('PASS: 두 번째 백업 후 첫 백업 파일 보존')
restored = folder / 'restored'
restored.mkdir()  # 기존 복원 폴더가 있으면 덮어쓰지 않고 중단한다.
for path in archives:
    print('백업 파일:', path.name)
    assert re.fullmatch(r'backup-\d{8}T\d{12}Z-[0-9a-f]{32}\.zip', path.name)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['format'] == 'budget_app_backup' and manifest['version'] == 1
        assert set(manifest['files']) == {'transactions.jsonl', 'categories.jsonl', 'budgets.jsonl', 'recurring.jsonl'}
        assert set(archive.namelist()) == set(manifest['files']) | {'manifest.json'}
        for name, info in manifest['files'].items():
            raw = archive.read(name)
            assert raw == (folder / name).read_bytes()
            assert len(raw) == info['size']
            assert hashlib.sha256(raw).hexdigest() == info['sha256']
            print('검증:', name, info['sha256'])
            if path == archives[-1]:
                (restored / name).write_bytes(raw)
print('PASS: 서로 다른 백업 2개·원본 바이트·해시 일치·새 폴더 복원')
PY
python -m budget_app --data-dir "$BONUS_DIR/restored" recurring list
python -m budget_app --data-dir "$BONUS_DIR/restored" summary --month 2026-11 --top 3
BACKUP_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$BACKUP_BEFORE" = "$BACKUP_AFTER" || exit 1
echo 'PASS: 백업·복원 확인 후 원본 저장 파일 모두 유지'

ATOMIC_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
python -m scripts.demo_atomicity "$BONUS_DIR"
ATOMIC_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$ATOMIC_BEFORE" = "$ATOMIC_AFTER" || exit 1
echo 'PASS: 실패 주입 시연 후 보너스 원본 데이터도 그대로 유지'
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
