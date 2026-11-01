# B2-1 · 나만의 용돈 기입장 프로그램 만들기

> **진행 상태: 설계 완료 / 프로그램 미구현 / 테스트·캡처·로그 미수집**  
> 이 README는 **최종 제출물 목록과 증빙 준비의 기준 문서**다. 아래에 적힌 명령 및 출력은 *구현 예정 명세*이며 실제 실행·검증 완료를 의미하지 않는다.

## 1. 미션 개요와 공식 요구 산출물

Python 3.10+ 표준 라이브러리만 사용해 파일 기반 용돈 기입장 콘솔 애플리케이션 **1개**를 만든다. 아래 기능과 구성은 **B2-1 미션 원문의 필수 최종 결과물**이다.

| ID | 필수 기능 / 구성 | 미션에서 요구하는 결과 |
|---|---|---|
| F01 | 거래 추가 `add` | 날짜·타입·카테고리·금액·메모·태그 대화형 입력, 저장 성공 및 고유 거래 ID 표시 |
| F02 | 거래 목록 `list` | 최근순 목록, `--limit`, 제너레이터 스트리밍 |
| F03 | 거래 검색 `search` | 날짜 범위·카테고리·타입·메모 키워드·태그 필터, 최근순·스트리밍 |
| F04 | 월별 요약 `summary` | 월 수입·지출·잔액·카테고리별 지출 TOP N, 데이터 없음 처리 |
| F05 | 예산 `budget set` | 월 예산 저장, 요약에 예산 사용률·초과 경고 표시 |
| F06 | 카테고리 `category add/list/remove` | 생성·조회·삭제, 사용 중 카테고리의 안전한 삭제 처리 |
| F07 | 거래 수정 `update` | 거래 ID 기반 수정, 없는 ID 처리 |
| F08 | 거래 삭제 `delete` | ID 기반 삭제, 없는 ID 처리 |
| F09 | CSV `import/export` | 지정 스키마로 가져오기/내보내기, 건수 보고, 생성/반영 확인 |
| F10 | 파일 영속성 | 거래·카테고리·예산을 구분한 **3개 이상 저장 파일**, 종료/재실행 후 데이터 유지 |
| F11 | 필수 README | **실행 방법, 저장 파일 위치/형식, 주요 명령 예시, import/export CSV 스키마** 명시 |

다음은 미션의 **기술적 필수 요구**이며 F01~F11의 검수와 함께 확인한다: **클래스 2개 이상, 모듈 3개 이상, 데이터 모델(dataclass 등), 제너레이터, 실제 적용된 데코레이터 1개 이상, 타입 힌트, 원인+해결 힌트 오류 메시지 및 오류 시 0이 아닌 종료 코드, 모든 명령의 `--help`**. 파일 수정·삭제의 안전성, 저장 포맷 비교 및 10만 건 확장성 판단도 평가 대상이다.

**선택 보너스**인 백업, 반복 거래, 테이블 정렬은 필수 산출물에 포함하지 않는다. 파일 교체 안전성은 선택 보너스 설명에도 있지만 공식 평가표에서도 확인하므로 기본 설계에 포함했다.

## 2. 공식 평가 체크리스트와 제출 증빙의 연결

**중요:** 미션 원문은 스크린샷의 장수나 실행 로그의 제출 형식을 별도로 강제하지 않는다. 아래의 **증빙 파일은 공식 필수 제출물이 아니라 평가를 쉽게 하기 위해 우리가 정한 최소 준비 계획**이다.

| 평가 항목 | 검수할 내용 | 계획한 실제 증거 / 시연 | 상태 |
|---|---|---|---|
| **항목 1** | 8종 거래 기능, 카테고리, 예산, CSV, 재시작 후 3파일 유지, 오류 메시지·종료 코드 | `evidence/01-function-demo.txt` (명령·결과 요약), `evidence/02-persistence.txt` (재시작과 3파일 확인), `evidence/03-errors.txt` (의도한 실패+종료 코드), 실제 CLI 시연 | 미수집 |
| **항목 2** | 모듈 3+, 클래스 2+, 책임 경계, update/delete 파일 안전성 | `docs/design.md` 아키텍처 설명 및 안전한 파일 교체 근거, `evidence/04-tests.txt` 관련 테스트 출력 | 문서 초안 있음 / 실행 미검증 |
| **항목 3** | 제너레이터, 데코레이터, 타입 힌트의 구현·이유 | 최종 소스의 해당 부분과 `docs/learning-map.md`를 이용한 설명, `evidence/04-tests.txt` | 미검증 |
| **항목 4** | JSONL/CSV 장단점·선택 근거, 10만 건 병목, 깨진 CSV 행 처리 | `docs/design.md` ADR, `evidence/05-benchmark.txt` 실제 측정, `evidence/06-import-rollback.txt` 오류 행/롤백 검증 | 설계 기록 있음 / 측정 미실행 |

자세한 검수 식별자(A01~A16)와 기대값은 [docs/acceptance.md](docs/acceptance.md)에 있다. 이 표의 파일명은 *수집할 때 사용할 예약 이름*으로, 존재하거나 검증됐다는 의미가 아니다. 실제 필요한 증거만 생성하며 무의미한 중복 캡처는 만들지 않는다.

### 캡처·로그 수집 지침

- **우선순위 1:** 터미널에서 재현 가능한 명령과 결과, 실제 테스트 통과 로그.
- **우선순위 2:** 데모에 도움이 되는 화면 캡처 **2~3장 이내를 기본 목표**로 준비하되, 평가에 필요한 경우에만 늘린다. 예: 거래·요약 실행, 저장 파일 3종, CSV 오류/종료 코드.
- **원본 보호:** 실제 개인 가계 내역, API 키, 사용자 이름·절대 경로·민감 정보는 공개 저장소에 올리지 않는다. 증빙은 **가상의 테스트 데이터**로 생성한다.
- **증거의 정직성:** 실제 실행 결과에만 `검증 완료`를 표시한다. 실패·미실행 사항은 그대로 남기고, 로그의 실행 명령·Python 버전·Git 커밋을 함께 기록한다.
- 필요 없는 파일은 `evidence/`에 생성하지 않는다. 데이터 원본과 임시 파일은 Git에 커밋하지 않는다.

## 3. 실행 방법 — 구현 예정

```bash
# Python 3.10 이상 확인
python --version

# 도움말 (구현 후 실행 가능)
python -m budget_app --help

# 선택: 가상 데이터용 별도 폴더
python -m budget_app --data-dir ./data category add
```

- Python 3.10 이상, 별도 `pip install` 불필요.
- 기본 저장 위치: 실행 디렉터리 기준 `./data`.
- `--data-dir PATH`로 폴더 지정(전역 옵션은 하위 명령 **앞**에 작성).
- 모든 명령 `--help` 지원. 옵션은 기능 요구사항의 `--` 표기를 기준으로 한다. 원문 제약사항과의 표기 충돌·채택 이유는 [설계 결정서](docs/design.md)에 기록.

## 4. 주요 명령 예시 — 구현 예정

```bash
python -m budget_app category add
python -m budget_app category list
python -m budget_app add
python -m budget_app list --limit 20
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal
python -m budget_app summary --month 2024-01 --top 3
python -m budget_app budget set --month 2024-01 --amount 500000
python -m budget_app update --id TX_EXAMPLE --memo "점심 식사"
python -m budget_app delete --id TX_EXAMPLE
python -m budget_app category remove
python -m budget_app export --out export.csv --month 2024-01
python -m budget_app export --out export.csv --from 2024-01-01 --to 2024-01-31 --overwrite
python -m budget_app import --from import.csv
```

`category add`, `add`, `category remove`는 대화형 입력이다. `update`는 **옵션 방식**으로 고정했다. `TX_EXAMPLE`은 문법 설명용 자리표시자이며 실제 거래 ID가 아니다. `category add`로 카테고리를 등록해야 거래를 추가할 수 있다. 실행 전 세부 명령 계약은 [docs/spec.md](docs/spec.md)를 따른다.

## 5. 저장 위치와 포맷 — 구현 예정

| 저장 파일 | 형식 | 내용 |
|---|---|---|
| `./data/transactions.jsonl` | UTF-8 JSONL | 거래 ID·유형·날짜·금액·카테고리·메모·태그 |
| `./data/categories.jsonl` | UTF-8 JSONL | 카테고리 이름 |
| `./data/budgets.jsonl` | UTF-8 JSONL | 월별 예산 |

- JSONL은 한 줄마다 하나의 JSON 객체를 담는다.
- 프로그램을 다시 실행해도 데이터가 유지되어야 한다.
- 수정·삭제·추가는 동일 디렉터리 임시 파일을 작성하고 교체하는 안전성 정책을 사용한다. 단일 사용자용이며 동시에 여러 프로세스가 파일을 조작하는 사용은 지원하지 않는다.
- 내부 JSONL 선택 이유, 안전성의 한계와 대안은 [docs/design.md](docs/design.md) 참조.

## 6. CSV import/export 스키마 — 필수 README 내용

CSV 파일은 **UTF-8, 헤더 포함**, 다음 순서의 컬럼을 사용한다.

| 컬럼 | 필수 | 내용 |
|---|---|---|
| `date` | Y | `YYYY-MM-DD` |
| `type` | Y | `income` / `expense` |
| `category` | Y | 등록된 카테고리 |
| `amount` | Y | 양의 정수 |
| `memo` | N | 문자열 |
| `tags` | N | 쉼표로 구분한 문자열 |

```csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,15000,점심,"meal,weekday"
```

- `import --from PATH`: 모든 행 검증 후 일괄 반영. 하나라도 잘못되면 **전체를 반영하지 않고**, 행 번호와 이유를 보고한다(우리의 설계 선택).
- 기본 CSV에는 거래 ID가 없으므로 **같은 CSV를 다시 import하면 중복 거래로 추가될 수 있다**. 중복 방지는 보장하지 않는다.
- `export --out PATH`: `--month` 또는 `--from`/ `--to` 기간이 필수. 파일 덮어쓰기는 `--overwrite` 필요(설계 선택).
- 사용자 오류는 원인+해결 힌트를 보여주고 0이 아닌 종료 코드로 끝난다.

## 7. 최종 검수 방법 — 구현 후 실행

```bash
python -m unittest discover -s tests -v
```

검수 완료 시 실제 테스트 수/실패 여부, 실행 명령, Git 커밋, 관련 `evidence/` 자료를 아래 표에 기록한다.

| 항목 | 상태 | 근거 |
|---|---|---|
| 전체 기능 및 재시작 영속성 | 미실행 | — |
| 데이터 파일 3종 확인 | 미실행 | — |
| CSV 헤더·UTF-8·import/export | 미실행 | — |
| 오류 메시지·비영 종료 코드 | 미실행 | — |
| 파일 교체 실패 시 원본 보호 | 미실행 | — |
| 제너레이터·데코레이터·타입 힌트 | 미실행 | — |
| 10만 건 병목 측정 | 미실행 | — |
| 최종 실제 데모 | 미실행 | — |

## 8. 설계·검수·하네스 문서

- [미션 수행 전략](docs/mission-strategy.md)
- [아키텍처 및 ADR](docs/design.md)
- [상세 명세](docs/spec.md)
- [평가항목과 검수 게이트](docs/acceptance.md)
- [시연 시나리오](docs/demo.md)
- [개념 학습 지도](docs/learning-map.md)
- [AI 구현·검증 계획](docs/implementation-plan.md)
- [AI 작업 규칙](AGENTS.md)

## 9. 미션과 별도의 연구 목표

- **목표 A:** 공식 필수 기능·제약 및 평가항목 충족.
- **목표 B:** 명세/설계/검수 조건을 사람이 통제하고 AI가 구현·테스트·수정하도록 하는 **최소 개발 하네스**의 효과 검증. 목표 B는 **공식 평가항목이 아님**.
- 하네스 비용·실패·사람의 개입·재작업은 실제 관측 후 회고한다. 이를 위해 불필요한 스크린샷/로그 수집을 자동화하지 않는다.
