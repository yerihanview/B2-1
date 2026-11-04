# 보너스 4가지 독립 시연 (B01~B04)

저장소 루트의 Bash 터미널에서 아래 블록을 순서대로 복사한다. Python 3.10 이상, 외부 패키지 불필요. 기본 데모의 `DEMO_DIR`를 사용하지 않는다. 전체 자동 리허설은 `bash demos/bonus/commands.sh`로 실행한다.

## 0. 별도 데이터 준비

```bash
BONUS_DIR="$(python scripts/prepare_bonus_demo.py)"
export BONUS_DIR
printf '보너스 전용 데이터: %s\n' "$BONUS_DIR"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
```

매번 `data/bonus-demo-고유문자열/`을 새로 만든다. 원본 가상 데이터는 기본 데모와 같은 6건을 복사하지만 실행 폴더는 완전히 분리된다. 이전 데모나 실제 데이터는 변경·삭제하지 않는다. 모든 블록은 같은 터미널에서 실행한다. 처음부터 다시 연습하려면 0번부터 실행한다.

## 1. 반복 내역 등록·생성 (B02)

```bash
python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 31 --type income --category 용돈 --amount 300000 --memo '가상 월급' --tags '정기'
python -m budget_app --data-dir "$BONUS_DIR" recurring list
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" search --from 2026-11-01 --to 2026-11-30 --q '가상 월급'
```

예상: 규칙 `RR-...` 등록 → 첫 적용 `generated=1, skipped=0` → 재적용 `generated=0, skipped=1`. 11월에는 31일이 없어 11월 30일로 보정된다. 특정 월의 자동 생성은 `apply` 실행으로 시작하며 백그라운드 스케줄러는 없다. `recurring.jsonl`이 추가된다.

잘못된 날짜도 거부한다. 이 오류는 의도된 시연이다.

```bash
if python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 32 --type expense --category 식비 --amount 10000; then
    echo 'FAIL: 잘못된 날짜를 허용함'; exit 1
else
    CODE=$?
    test "$CODE" -eq 2 || exit 1
    echo 'PASS: day 32 거부, 종료 코드 2'
fi
```

## 2. 외부 라이브러리 없는 표 정렬 (B03)

```bash
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR" search --type expense --limit 20
```

관찰: 한글 메모·카테고리의 길이가 달라도 `|` 열 경계가 맞고 금액은 오른쪽 정렬된다. 고정폭 글꼴의 터미널에서 확인한다. `budget_app/formatting.py`가 표준 라이브러리 `unicodedata`로 표시 폭을 계산한다. 복합 이모지는 터미널·폰트에 따라 폭 차이가 있을 수 있다.

## 3. 타임스탬프 백업·내용 검증·복원 확인 (B01)

```bash
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
```

예상: `backup-UTC타임스탬프-UUID.zip` 두 개. 필수 3파일과 반복 규칙 파일, 크기·SHA-256 목록이 포함된다. 잠금 파일과 기존 백업은 포함되지 않는다. 새 폴더에 수동 복원 후 규칙 조회와 요약에 성공한다. 11월 수입 600,000 / 지출 100,000 / 잔액 500,000원. 앱 자체에 자동 복원 명령은 없다.

## 4. 저장 원자성: update/delete 실패 시 원본 보존 (B04)

```bash
python -m scripts.demo_atomicity "$BONUS_DIR"
```

이 도구는 보너스 데이터를 **또 다른 임시 폴더에 복사**한 뒤, 실행 중에만 `os.replace`가 실패하도록 모의 처리한다. 소스 파일·원래 보너스 데이터는 수정하지 않는다. 실제 디스크 고장이나 강제 종료를 유발하지 않는다.

예상: update/delete 각각 종료 코드 3, 오류·힌트 출력, 전후 SHA-256 동일, 임시 파일·잠금 정리 `PASS`. 정상 저장은 임시 파일 기록 → flush/fsync → `os.replace`로 반영한다. 교체 후 동기화 실패는 별도 내구성 오류이며, 이번 시연은 교체 전 실패의 원본 보존을 확인한다. 다중 파일 트랜잭션·전원 장애 완전 내구성 보장은 아니다.

## 시연 종료

데이터와 백업은 출력된 `BONUS_DIR`에 유지된다. 기본 미션 데모와 순서·실행 상태를 공유하지 않으며, 기본 데모를 먼저 실행할 필요가 없다. 기능별 확인 대상은 B01(백업), B02(반복), B03(표 정렬), B04/T16(원자적 교체)이다. 발표자가 화면을 보고 설명하는 최종 검수는 별도로 진행한다.
