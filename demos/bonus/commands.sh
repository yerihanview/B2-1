#!/usr/bin/env bash
# 저장소 루트에서 실행하는 보너스 전용 리허설. 기본 데모와 데이터 분리.
set -euo pipefail

BONUS_DIR="$(python scripts/prepare_bonus_demo.py)"
export BONUS_DIR
printf '보너스 전용 데이터: %s\n' "$BONUS_DIR"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20

python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 31 --type income --category 용돈 --amount 300000 --memo '가상 월급' --tags '정기'
python -m budget_app --data-dir "$BONUS_DIR" recurring list
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" search --from 2026-11-01 --to 2026-11-30 --q '가상 월급'

if python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 32 --type expense --category 식비 --amount 10000; then
    echo 'FAIL: 잘못된 날짜를 허용함'; exit 1
else
    CODE=$?
    test "$CODE" -eq 2 || exit 1
    echo 'PASS: day 32 거부, 종료 코드 2'
fi

python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR" search --type expense --limit 20

python -m budget_app --data-dir "$BONUS_DIR" backup
python -m budget_app --data-dir "$BONUS_DIR" backup
python - "$BONUS_DIR" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

folder = Path(sys.argv[1])
archives = sorted((folder / 'backups').glob('*.zip'))
assert len(archives) == 2
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

python -m scripts.demo_atomicity "$BONUS_DIR"
