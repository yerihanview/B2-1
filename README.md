# B2-1 · 나만의 용돈 기입장

Python 3.10+ 표준 라이브러리만 사용하는 파일 기반 CLI 가계부다. 거래·카테고리·예산을 JSONL 세 파일로 저장하고 CSV로 가져오기/내보내기한다. 백업·월별 반복 내역·한글 테이블 정렬·저장 원자성 보너스도 필수 범위에 포함한다. 외부 패키지 설치는 필요 없다.

**제출 상태:** 사용자 승인 후 PR #1을 main에 병합했다. [제출물 점검](docs/submission-check.md), [평가 대비 설명](docs/evaluation-guide.md), [최종 검토](docs/final-review.md), [단계별 검수 기록](docs/validation-results.md)을 확인할 수 있다. 로컬 검증, 원격 GitHub Actions, 사람의 최종 데모 승인을 구분한다. 공식 미션·평가표는 첨부 원문으로 대조했으며 사용자 요청에 따라 저장소에 포함하지 않는다.

## 실행

처음 받는 경우 Git으로 내려받고 저장소 루트에서 실행한다. GitHub ZIP으로 받은 경우에도 프로그램 실행에는 Git이 필요 없지만, SHA를 기록하는 개발용 smoke/benchmark 스크립트는 Git 체크아웃에서 사용한다.

```bash
git clone https://github.com/yerihanview/B2-1.git
cd B2-1
python --version  # 3.10 이상
python -m budget_app --help
python -m budget_app --data-dir ./data category add
python -m budget_app --data-dir ./data add
python -m budget_app --data-dir ./data list --limit 20
```

기본 저장 폴더는 현재 작업 디렉터리의 `./data`다. `--data-dir PATH`는 하위 명령 앞에 작성한다. 모든 명령과 서브명령은 `--help`를 지원한다.

`category add`에서 `food`를 먼저 등록한다. `add`는 날짜·타입·카테고리·금액·메모·태그 순서로 대화형 입력한다. 예: `2024-01-15`, `expense`, `food`, `15000`, `점심`, `meal,weekday`. 메모와 태그는 빈 입력을 허용한다. 금액은 양의 정수, 날짜는 실제 유효한 `YYYY-MM-DD`다. 입력 오류 시 재입력하지 않고 원인·해결 힌트와 비영 종료 코드로 끝난다.

카테고리는 영문·숫자·밑줄·하이픈 1~50자, 태그는 같은 문자 1~30자이며 대소문자를 구별한다. 태그는 쉼표로 구분하고 중복을 제거한다. 메모는 UTF-8 500자 이하이며 공백을 보존한다.

## 주요 명령

```bash
python -m budget_app category add
python -m budget_app category list
python -m budget_app category remove
python -m budget_app add
python -m budget_app list --limit 20
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal
python -m budget_app summary --month 2024-01 --top 3
python -m budget_app budget set --month 2024-01 --amount 500000
python -m budget_app update --id TX_EXAMPLE --memo "점심 식사" --tags ""
python -m budget_app delete --id TX_EXAMPLE
python -m budget_app export --out export.csv --month 2024-01
python -m budget_app export --out export.csv --from 2024-01-01 --to 2024-01-31 --overwrite
python -m budget_app import --from import.csv
```

`TX_EXAMPLE`은 설명용이며 `add`가 출력한 실제 `TX-` + UUID4 ID로 바꿔야 한다. `update`는 옵션 방식이고 지정한 필드만 바꾼다. `--memo ""`는 메모를, `--tags ""`는 태그를 비운다. **`delete`는 확인 프롬프트 없이 삭제하며 자동 복구를 제공하지 않는다.** 사용 중인 카테고리 삭제는 거래 수와 함께 거부한다.

list/search는 거래 날짜 내림차순, 같은 날짜면 원본 파일 뒤쪽 거래 우선이다. 기본 limit은 20, 범위는 1~1000이다. search 조건은 AND로 결합하고 기간은 양 끝을 포함한다. summary는 수입·지출·잔액·카테고리별 지출 TOP을 표시하며 예산이 있으면 소수 첫째 자리 사용률과 초과 경고를 표시한다.

## 저장 위치와 안전성

| 파일 | UTF-8 JSONL 한 줄 예시 |
|---|---|
| `data/transactions.jsonl` | `{"id":"TX-00000000000040008000000000000001","type":"expense","date":"2024-01-15","category":"food","amount":15000,"memo":"점심","tags":["meal"]}` |
| `data/categories.jsonl` | `{"name":"food"}` |
| `data/budgets.jsonl` | `{"month":"2024-01","amount":500000}` |

첫 데이터 명령은 기존 파일 전체를 검증한 뒤 누락 파일을 생성한다. 카테고리 초기값은 비어 있다. 손상 파일은 자동 초기화하지 않는다. 실제 금융 데이터는 Git에 추가하지 않는다. 기본 `/data/`와 Python 캐시는 `.gitignore`로 제외하지만 다른 `--data-dir`을 사용하면 별도로 추적 여부를 확인해야 한다.

모든 데이터 명령은 `.budget_app.lock`을 배타 생성한다. 다른 명령이 잠금을 갖고 있으면 읽기도 거부한다. 비정상 강제 종료로 잠금이 남으면 실행 중인 프로세스와 데이터 상태를 확인한 뒤 수동 처리한다. 프로그램은 다른 프로세스의 잠금을 자동 삭제하지 않는다.

변경은 같은 디렉터리의 임시 파일에 쓰고 flush/fsync 뒤 원자적으로 발행한다. 기존 파일 교체에는 `os.replace`, 새 export의 비덮어쓰기 발행에는 배타적인 hard link를 사용한다. 교체 전 실패는 기존 원본을 보존한다. 교체 후 디렉터리 fsync 실패는 **반영됨·내구성 확인 실패**로 보고하므로 무조건 재실행하지 않는다. 다중 파일 트랜잭션·전원 장애 완전 내구성·자동 복구는 제공하지 않는다.

| 종료 코드 | 뜻 |
|---|---|
| 0 | 성공 또는 도움말 |
| 2 | 입력/요구사항 위반·입력 중단 |
| 3 | 파일/손상/내구성 오류 |
| 4 | 잠금 충돌 |

사용자 오류는 stderr에 `[오류]`와 `[힌트]`를 출력하며 traceback을 노출하지 않는다.

## CSV 스키마

UTF-8(BOM 없음), 헤더 포함, 컬럼 순서는 다음과 같다.

```csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,15000,점심,"meal,weekday"
```

| 컬럼 | 조건 |
|---|---|
| date | 실제 유효한 `YYYY-MM-DD` |
| type | `income` 또는 `expense` |
| category | 등록된 카테고리 |
| amount | 양의 ASCII 십진 정수 |
| memo | 빈 값 허용, UTF-8 500자 이하 |
| tags | 빈 값 또는 쉼표 구분 태그; CSV quoting 적용 |

import는 전건 검증 후 한 번만 반영한다. 잘못된 행이 있으면 전부 미반영하고 최초 20개 오류를 물리적 시작 줄 번호와 함께 안내한다. 헤더만 있으면 0건 성공, 빈 파일은 오류다. **CSV에 ID가 없어 같은 파일을 다시 import하면 새 거래로 중복 추가된다.**

export는 월 또는 시작/종료 날짜 쌍 중 하나가 필수다. list와 달리 원본 파일 순서로 출력한다. 기존 출력 파일은 `--overwrite` 없이 교체하지 않으며 내부 데이터·잠금 파일 및 경로 별칭으로의 출력은 거부한다.

## 보너스 기능

```bash
python -m budget_app backup
python -m budget_app backup --out-dir ./my-backups
python -m budget_app recurring add --day 31 --type income --category salary --amount 3000000 --memo "월급" --tags monthly
python -m budget_app recurring list
python -m budget_app recurring apply --month 2024-02
python -m budget_app recurring remove --id RR_EXAMPLE
```

반복 규칙의 카테고리도 먼저 등록해야 한다. `RR_EXAMPLE`은 등록 시 출력된 `RR-` + UUID4 ID로 바꾼다. 모든 새 명령과 하위 명령도 `--help`를 지원한다.

백업은 같은 데이터 잠금 아래 기본 3파일과 존재하는 `recurring.jsonl`을 원본 바이트 그대로 ZIP에 담는다. 기본 출력은 `<data-dir>/backups`이며 UTC 타임스탬프와 UUID가 있는 새 파일을 만든다. `manifest.json`의 파일별 크기·SHA-256으로 내용을 대조할 수 있다. 잠금·기존 백업·기타 파일은 넣지 않고 기존 아카이브는 덮어쓰지 않는다. 사용자 지정 백업 폴더에는 실제 금융 데이터가 포함될 수 있으므로 Git에 추가하지 않는다. 자동 복구 명령은 제공하지 않는다.

반복 규칙은 첫 등록 때 선택 파일 `recurring.jsonl`에 저장한다. 기존 세 파일을 자동 변환하지 않는다. 지정한 월에 존재하지 않는 날짜는 말일로 보정한다. 예: 31일 규칙은 2024년 2월 29일, 2025년 2월 28일 거래를 만든다. `apply` 실행 없이 백그라운드에서 자동 생성하지 않는다.

생성 거래는 `recurring_id`와 `recurring_month` 출처 쌍을 가진다. 같은 출처 쌍이 현재 거래에 있으면 건너뛰며, 날짜·금액을 수정해도 출처를 유지한다. 생성 거래를 삭제하고 다시 apply하면 새로운 ID로 재생성한다. 규칙 삭제는 과거 거래를 삭제하지 않는다. 사용 중인 규칙이 있는 카테고리도 삭제할 수 없다. CSV는 기존 6컬럼을 유지하며 출처는 내보내지 않는다.

list/search는 한글 등 표시 폭에 맞춰 열을 정렬하고 금액을 오른쪽 정렬한다. 메모의 줄바꿈·탭·제어문자는 화면에서 이스케이프해 거래당 한 행으로 표시하며 저장된 메모는 유지한다. 복합 이모지의 폭은 터미널·폰트에 따라 다를 수 있다.

## 개발·검수

```bash
python -m unittest discover -s tests -v
python scripts/smoke.py
python scripts/bonus_smoke.py
python scripts/benchmark.py --repeat 1
```

검수와 데모는 임시 디렉터리·가상 데이터만 사용한다. benchmark는 고정 seed로 1만/10만 건과 limit 20/1000을 비교하고 list/search/add/update의 시간·최대 Python 할당 메모리를 측정한다. tracemalloc 비용이 포함되므로 일상 실행 속도와 구분한다.

독립 검수는 `tests/test_acceptance_cli.py`와 `tests/test_bonus_acceptance.py`, 개발 단위·장애 검수는 나머지 테스트 파일에 둔다. GitHub Actions는 Python 3.10에서 두 종류를 실행하며 0건·전체 스킵 성공을 차단한다. 실제 실행 결과를 확인하기 전 원격 CI 통과를 주장하지 않는다. PR 자동 병합은 하지 않는다.

## 설계·평가·학습 자료

- [아키텍처와 ADR](docs/design.md), [상세 명세](docs/spec.md), [평가항목과 검수 기준](docs/acceptance.md)
- [구현·역할 분담 계획](docs/implementation-plan.md), [실패 처리 정책](docs/failure-policy.md), [에이전트 지침](AGENTS.md)
- [미션 수행 전략](docs/mission-strategy.md), [학습 개념 지도](docs/learning-map.md), [데모](docs/demo.md)
- [인수인계 검토 기록](docs/handover-review.md), [검수 결과와 증거](docs/validation-results.md)
- [GitHub 제출 점검표](docs/submission-check.md), [평가 대비 설명과 연습 질문](docs/evaluation-guide.md)
- [과잉 운영 검토 원문](docs/overengineering-review.md), [원인·재발 방지 지침·소스 재검토 설명](docs/overengineering-followup.md)

공식 미션 달성과 별도로 명세 중심 AI 개발 운영법을 연구한다. 이 개인 연구는 공식 평가항목이 아니며 불필요한 하네스·로그 수집보다 실제 기능·안전성 검수를 우선한다.
