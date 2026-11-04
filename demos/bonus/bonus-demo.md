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
```

예상: 규칙 `RR-...` 등록 → 첫 적용 `generated=1, skipped=0` → 재적용 `generated=0, skipped=1`. 11월에는 31일이 없어 11월 30일로 보정된다. 특정 월의 자동 생성은 `apply` 실행으로 시작하며 백그라운드 스케줄러는 없다. `recurring.jsonl`이 추가된다.

등록 직후에는 규칙 필드와 거래 미생성을, 첫 적용 직후에는 실제 거래의 날짜·금액·태그·출처를 확인한다. 재적용 전후에는 네 저장 파일 해시가 같은지 비교해 중복 추가가 없음을 확인한다.

잘못된 날짜도 거부한다. 이 오류는 의도된 시연이다.

```bash
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
```

## 2. 외부 라이브러리 없는 표 정렬 (B03)

```bash
FORMAT_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR" search --type expense --limit 20
FORMAT_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$FORMAT_BEFORE" = "$FORMAT_AFTER" || exit 1
echo 'PASS: 표 출력 전후 저장 데이터 동일'
python -m unittest discover -s tests -p 'test_bonus_formatting.py' -v
```

조회 전후 저장 파일 해시를 비교해 표시 과정이 원본을 바꾸지 않았음을 확인한다. 이어지는 포맷터 테스트는 열 경계·금액 오른쪽 정렬·제어문자 이스케이프를 검증한다.

관찰: 한글 메모·카테고리의 길이가 달라도 `|` 열 경계가 맞고 금액은 오른쪽 정렬된다. 고정폭 글꼴의 터미널에서 확인한다. `budget_app/formatting.py`가 표준 라이브러리 `unicodedata`로 표시 폭을 계산한다. 복합 이모지는 터미널·폰트에 따라 폭 차이가 있을 수 있다.

## 3. 백업·내용 검증·복원 확인 (B01)

한 명령씩 실행하면서 **ZIP 생성 → 압축 해제 → 파일 4개 확인 → 복원 폴더로 프로그램 실행** 순서로 확인한다. 여기서는 해시 비교 대신 파일 내용과 복원 후 실행 결과를 직접 확인한다. `commands.sh`는 기존의 자동 해시 검증 방식을 유지한다.

### 3-1. ZIP 생성

```bash
python -m budget_app --data-dir "$BONUS_DIR" backup --out-dir "$BONUS_DIR/demo-backup"
ls "$BONUS_DIR/demo-backup/"*.zip
```

예상: 생성 시각과 고유 ID가 들어간 `backup-날짜시간-UUID.zip` 파일 1개가 보인다. 이 단계는 새로 준비한 보너스 폴더에서 한 번 실행한다. 기본 백업 폴더와 구분하기 위해 이번 시연은 `--out-dir`로 `demo-backup` 폴더를 지정한다.

### 3-2. 압축 해제

```bash
for BACKUP_ZIP in "$BONUS_DIR/demo-backup/"*.zip; do
    printf '압축을 풀 백업: %s\n' "$BACKUP_ZIP"
done
mkdir "$BONUS_DIR/restored" && python -m zipfile -e "$BACKUP_ZIP" "$BONUS_DIR/restored"
```

위에서 만든 ZIP을 새 `restored` 폴더에 푼다. 외부 압축 도구 없이 Python 표준 라이브러리를 사용한다. 복원 폴더가 이미 있으면 `mkdir`가 실패하고 압축 해제를 실행하지 않는다. 다시 연습하려면 0번부터 새 보너스 폴더를 준비한다.

### 3-3. 파일 4개와 내용 확인

```bash
ls "$BONUS_DIR/restored/"*.jsonl
for NAME in transactions.jsonl categories.jsonl budgets.jsonl recurring.jsonl; do
    printf '\n=== %s ===\n' "$NAME"
    cat "$BONUS_DIR/restored/$NAME"
done
```

다음 네 파일을 확인한다.

| 파일 | 예상 내용 |
|---|---|
| `transactions.jsonl` | 기존 거래 6건 + 생성된 가상 월급 1건, 총 7건 |
| `categories.jsonl` | 용돈·식비·교통·도서, 총 4개 |
| `budgets.jsonl` | 예산을 등록하지 않았으므로 빈 파일 |
| `recurring.jsonl` | 매월 31일 가상 월급 300,000원 규칙 1건 |

ZIP에는 위 네 데이터 파일 외에 파일 크기·해시 목록인 `manifest.json`도 있다. 따라서 압축 해제 폴더의 전체 파일 수는 5개다. 위 `ls`는 JSONL 데이터 파일 4개만 보여준다. 이번 수동 시연에서는 해시 목록을 계산·비교하지 않는다.

### 3-4. 복원 폴더로 프로그램 실행

```bash
python -m budget_app --data-dir "$BONUS_DIR/restored" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR/restored" recurring list
python -m budget_app --data-dir "$BONUS_DIR/restored" summary --month 2026-11 --top 3
```

예상: 복원한 거래 7건과 반복 규칙 1건이 조회된다. 11월 수입 600,000 / 지출 100,000 / 잔액 500,000원이다. 10월 거래 1건은 목록에는 보이지만 11월 요약에서는 제외된다.

이 과정은 백업 파일을 별도 폴더에 직접 풀어 앱에서 재사용할 수 있음을 보여준다. 원래 보너스 데이터는 그대로 두고 `--data-dir`만 복원 폴더로 바꾼다. 앱 자체에 자동 복원 명령은 없다.

## 4. 저장 원자성: update/delete 실패 시 원본 보존 (B04)

```bash
ATOMIC_BEFORE="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
python -m scripts.demo_atomicity "$BONUS_DIR"
ATOMIC_AFTER="$(python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["BONUS_DIR"]); print([(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.glob("*.jsonl"))])')"
test "$ATOMIC_BEFORE" = "$ATOMIC_AFTER" || exit 1
echo 'PASS: 실패 주입 시연 후 보너스 원본 데이터도 그대로 유지'
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
```

이 도구는 보너스 데이터를 **또 다른 임시 폴더에 복사**한 뒤, 실행 중에만 `os.replace`가 실패하도록 모의 처리한다. 소스 파일·원래 보너스 데이터는 수정하지 않는다. 실제 디스크 고장이나 강제 종료를 유발하지 않는다.

예상: update/delete 각각 종료 코드 3, 오류·힌트 출력, 전후 SHA-256 동일, 임시 파일·잠금 정리 `PASS`. 정상 저장은 임시 파일 기록 → flush/fsync → `os.replace`로 반영한다. 교체 후 동기화 실패는 별도 내구성 오류이며, 이번 시연은 교체 전 실패의 원본 보존을 확인한다. 다중 파일 트랜잭션·전원 장애 완전 내구성 보장은 아니다.

## 시연 종료

데이터와 백업은 출력된 `BONUS_DIR`에 유지된다. 기본 미션 데모와 순서·실행 상태를 공유하지 않으며, 기본 데모를 먼저 실행할 필요가 없다. 기능별 확인 대상은 B01(백업), B02(반복), B03(표 정렬), B04/T16(원자적 교체)이다. 발표자가 화면을 보고 설명하는 최종 검수는 별도로 진행한다.
