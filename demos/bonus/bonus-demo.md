# 보너스 4가지 독립 시연 (B01~B04)

저장소 루트의 Bash 터미널에서 아래 블록을 순서대로 복사한다. Python 3.10 이상, 외부 패키지 불필요. 기본 데모의 `DEMO_DIR`를 사용하지 않는다. 이 문서는 직접 결과를 읽으며 연습하는 수동 시연 안내다. `commands.sh`는 별도의 기존 자동 검증 방식이며, 이 문서의 수동 명령과는 다르다.

## 0. 별도 데이터 준비

```bash
BONUS_DIR="$(python scripts/prepare_bonus_demo.py)"
export BONUS_DIR
printf '보너스 전용 데이터: %s\n' "$BONUS_DIR"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
```

매번 `data/bonus-demo-고유문자열/`을 새로 만든다. 원본 가상 데이터는 기본 데모와 같은 6건을 복사하지만 실행 폴더는 완전히 분리된다. 이전 데모나 실제 데이터는 변경·삭제하지 않는다. 모든 블록은 같은 터미널에서 실행한다. 처음부터 다시 연습하려면 0번부터 실행한다.

## 1. 반복 내역 등록·생성 (B02)

### 1-1. 규칙 등록 후 저장 내용 확인

```bash
python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 31 --type income --category 용돈 --amount 300000 --memo '가상 월급' --tags '정기'
python -m budget_app --data-dir "$BONUS_DIR" recurring list
cat "$BONUS_DIR/recurring.jsonl"
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
```

확인: 규칙 1개가 표시되고 JSONL에 day 31, income, 용돈, amount 300000, 메모 가상 월급, 태그 정기가 저장돼 있다. 거래는 기존 6건뿐이며 가상 월급은 아직 없다. 규칙 등록과 거래 생성은 별개다.

### 1-2. 해당 월의 거래 생성 후 조회

```bash
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" search --q '가상 월급'
cat "$BONUS_DIR/transactions.jsonl"
```

확인: `generated=1, skipped=0`. 가상 월급 300,000원 거래 1건이 보인다. 11월에는 31일이 없으므로 날짜는 2026-11-30이다. JSONL의 `recurring_id`는 규칙 ID, `recurring_month`는 2026-11이다. 전체 거래는 7건이다.

### 1-3. 같은 월에 다시 적용해 중복 여부 확인

```bash
python -m budget_app --data-dir "$BONUS_DIR" recurring apply --month 2026-11
python -m budget_app --data-dir "$BONUS_DIR" search --q '가상 월급'
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
```

확인: `generated=0, skipped=1`. 가상 월급은 여전히 1건, 전체 거래도 7건이다. 특정 월의 자동 생성은 `apply`를 실행할 때 시작하며 백그라운드 스케줄러는 없다.

### 1-4. 잘못된 규칙 등록 거부 확인

```bash
python -m budget_app --data-dir "$BONUS_DIR" recurring add --day 32 --type expense --category 식비 --amount 10000
printf '종료 코드: %s (예상 2)\n' "$?"
python -m budget_app --data-dir "$BONUS_DIR" recurring list
cat "$BONUS_DIR/recurring.jsonl"
```

확인: day 32는 오류와 해결 힌트를 출력하며 거부된다. 이 오류는 의도된 시연이다. 규칙 목록과 파일에는 기존 가상 월급 규칙 1개만 남는다. 종료 코드는 실패 명령 바로 다음에 확인해야 한다.

## 2. 외부 라이브러리 없는 표 정렬 (B03)

```bash
python -m budget_app --data-dir "$BONUS_DIR" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR" search --type expense --limit 20
cat "$BONUS_DIR/transactions.jsonl"
```

확인: 전체 목록은 7건, 지출 검색은 5건이다. 한글 메모·카테고리의 길이가 달라도 `|` 열 경계가 맞고 금액은 오른쪽 정렬된다. 파일의 원래 값은 그대로이며 표에 맞춘 공백은 화면 출력에만 사용한다.

고정폭 글꼴의 터미널에서 확인한다. `budget_app/formatting.py`가 표준 라이브러리 `unicodedata`로 표시 폭을 계산한다. 복합 이모지는 터미널·폰트에 따라 폭 차이가 있을 수 있다. 이 단계는 눈으로 확인하는 시연이며 자동 정렬 테스트를 실행하지 않는다.

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

## 4. 저장 원자성: 저장 코드와 수정·삭제 결과 확인 (B04)

### 4-1. 저장 순서 설명

[F7 파일 저장의 안전성 그림](../../docs/diagrams/F7-illustrated.png)을 보며 아래 소스 파일을 편집기로 연다.

```bash
cat budget_app/repository.py
```

`_atomic_write()`에서 다음 순서를 찾는다.

1. `tempfile.mkstemp`: 원본과 같은 폴더에 임시 파일 생성
2. `writer(handle)`: 변경 내용을 임시 파일에 기록
3. `handle.flush()`와 `os.fsync()`: 기록을 밀어내고 동기화
4. `os.replace(temporary, target)`: 완성된 임시 파일로 원본 교체

교체 전까지 원본을 직접 수정하지 않는 구조임을 설명한다. 교체 후 동기화 실패는 변경이 이미 반영된 상태일 수 있으며, 무조건 재실행하면 안 된다.

### 4-2. 전용 복사본에서 정상 수정·삭제 확인

```bash
mkdir "$BONUS_DIR/atomic-practice" && cp "$BONUS_DIR/"*.jsonl "$BONUS_DIR/atomic-practice/"
PRACTICE_DIR="$BONUS_DIR/atomic-practice"
python -m budget_app --data-dir "$PRACTICE_DIR" list --limit 20
python -m budget_app --data-dir "$PRACTICE_DIR" update --id TX-00000000000340008000000000000001 --memo '원자적 저장 연습'
python -m budget_app --data-dir "$PRACTICE_DIR" search --q '원자적 저장 연습'
cat "$PRACTICE_DIR/transactions.jsonl"
python -m budget_app --data-dir "$PRACTICE_DIR" delete --id TX-00000000000340008000000000000001
python -m budget_app --data-dir "$PRACTICE_DIR" list --limit 20
python -m budget_app --data-dir "$BONUS_DIR" search --q '학교 점심'
```

확인: 복사본에서 학교 점심의 메모가 변경되고, 같은 ID를 삭제하면 목록에서 사라진다. 복사본 거래는 7건에서 6건이 된다. 마지막 명령은 원래 보너스 폴더의 학교 점심이 여전히 남아 있음을 보여준다. 연습 폴더가 이미 있으면 덮어쓰지 말고 0번부터 새 폴더로 시작한다.

**이 단계는 저장 코드 설명과 정상 동작 시연이다. 교체 실패를 실제로 발생시켜 원본 보존을 입증하는 검증은 포함하지 않는다.** 실패 주입 스크립트나 자동 검증 테스트는 실행하지 않는다. 다중 파일 트랜잭션·전원 장애 완전 내구성을 보장한다는 의미도 아니다.

## 시연 종료

데이터와 백업은 출력된 `BONUS_DIR`에 유지된다. 기본 미션 데모와 순서·실행 상태를 공유하지 않으며, 기본 데모를 먼저 실행할 필요가 없다. 기능별 확인 대상은 B01(백업), B02(반복), B03(표 정렬), B04(저장 구조 설명·정상 수정/삭제)이다. T16의 교체 실패 검증은 이 수동 시연에 포함되지 않는다. 발표자가 화면을 보고 설명하는 최종 검수는 별도로 진행한다.
