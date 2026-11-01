# B2-1 전체 설계서 v1.0

상태: 구현 기준 설계(아직 구현·검증 전). 기준: B2-1 미션 원문 및 평가항목. 2026-11-02.

## 아키텍처
```text
python -m budget_app
  → cli.py (argparse / 대화형 입력 / 사용자 메시지 / exit code)
  → service.py (검증 / 거래·카테고리·예산 규칙 / 요약)
  → repository.py (JSONL 스트리밍 / 파일 안전 교체)
  → data/{transactions,categories,budgets}.jsonl
models.py (dataclass 및 계약) / csv_io.py (CSV 입출력 변환)
errors.py (오류 분류) / decorators.py (공통 오류 매핑)
```
CLI는 파일을 직접 만지지 않는다. Repository는 입출력 UI나 도메인 정책을 갖지 않는다. Service는 Repository를 생성자로 전달받는 DI를 사용한다. Transaction/Repository/Service 등 클래스 2개 이상, 모듈 3개 이상을 만족한다.

## 모델
- Transaction: id: str, type: income|expense, date: date, category: str, amount: int (>0), memo: str, tags: tuple[str,...].
- Category(name: str), Budget(month: YYYY-MM, amount: int > 0).
- 거래 id는 `TX-` + uuid4 hex 32자리; 재사용·수정 불가. import 시 새 id 부여.
- 카테고리는 대소문자 구별, trim 후 비어 있지 않은 문자열. 이미 참조된 카테고리는 삭제 금지.
- 금액은 원 단위 양의 정수. 부동소수점은 사용하지 않는다.

## 영속성
- 저장 포맷: JSONL (한 줄에 UTF-8 JSON 객체 하나). CSV는 외부 교환 전용.
- 파일 3종: transactions.jsonl, categories.jsonl, budgets.jsonl; 기본 ./data, 옵션 --data-dir.
- 첫 실행에서 세 파일 생성. 카테고리 초기값은 빈 목록으로 시작하고 add 전에 category add를 안내한다.
- 모든 데이터 변경은 동일 폴더의 임시 파일에 완전한 결과를 기록하고 flush/fsync 후 os.replace. 실패 시 원본 유지, 임시 파일 청소. **add도 파일 전체 재작성**해 append 도중 데이터 손상 위험을 회피한다. O(N) 쓰기 비용은 수용한다.
- 단일 사용자 프로세스 전제. 동시 writer는 지원하지 않으며 배타적 lock file로 중복 변경을 차단한다. 비정상 종료로 잠금 파일이 남으면 자동 삭제하지 않고 해결 안내를 출력한다. 모든 읽기/쓰기 명령이 같은 lock 규칙에 따른다.
- 한 파일의 교체는 전체 다중 파일 트랜잭션이 아니다. import는 기존 category만 허용하여 transactions 파일만 변경한다.
- 깨진 JSONL/권한 오류 시 자동 초기화·원본 덮어쓰기 금지.

## 조회 전략
- '최신순' = 거래 날짜 내림차순, 동일 날짜면 원본 파일 내 뒤에 기록된 거래 우선.
- list/search는 파일 전체를 로드하지 않고 generator로 순차 처리. 기본 --limit 20, 1~1000 허용.
- 날짜와 파일상 순서를 기준으로 **최신 K건 bounded heap**을 유지하고 결과 K건만 정렬. 시간 O(N log K), 메모리 O(K). search도 같은 처리. 검색조건 모두 만족한 거래만 heap에 넣는다.
- summary는 generator로 월간 거래를 순회해 총수입·총지출·카테고리 합계를 누적한다. 예산 사용률 = 지출/월 예산*100, 초과는 지출 > 예산.

## CSV 안전성
- CSV 최소 스키마 date,type,category,amount,memo,tags; UTF-8 헤더 필수, 쉼표 구분 tags는 CSV quoting 사용.
- import는 **전건 검증 후 전건 반영**. 실패 행이 있으면 전부 롤백하며 파일을 교체하지 않는다. 사용자에게 최초 20건의 행 번호+원인을 알린다.
- export는 임시 파일 작성 후 원자 교체하며 범위/월 필터를 필수로 한다.
- import 중복 감지는 명시된 규칙에 따라 처리(상세 명세 참조).

## 설계 결정 기록 (ADR)
| ID | 채택한 방식 | 대안 | 이유와 대가 |
|---|---|---|---|
| 01 | 내부 JSONL, 교환 CSV | 내부 CSV | 객체/태그를 자연스럽게 표현; 직접 표 편집은 불편 |
| 02 | category 선등록 | 자동 기본 카테고리 | 초기 상태가 명확하고 category 시연 가능; 편의성 감소 |
| 03 | 양의 정수 금액 | float/Decimal | 원 단위의 정확한 합계 및 CSV 정수 계약 |
| 04 | UUID 기반 id | 순차 번호 | counter 파일 불필요, 충돌 위험 극소; id가 길다 |
| 05 | 날짜순+같은 날짜 입력순 | 파일만 역순 | 날짜가 뒤섞여도 의미 있는 최신순 |
| 06 | bounded heap + limit 최대 1000 | 무제한 결과 | 스트리밍 메모리 상한; 전체 결과 한 번에 보기 제한 |
| 07 | 모든 변경 시 temp+replace | 직접 append/수정 | 실패 시 원본 보호; 변경 성능 O(N) |
| 08 | import 전건 롤백 | 부분 성공 | 오염된 데이터의 부분 유입 방지; 모든 행 유효해야 함 |
| 09 | 사용 중 category 삭제 거부 | 거래 자동 변경 | 거래 기록의 무단 변경 방지 |
| 10 | update 옵션 기반 | 대화형 | 재현·자동화·테스트에 적합 |
| 11 | 표준 라이브러리만 사용 | 외부 프레임워크 | 공식 제약 준수 |
| 12 | 옵션 -- 사용 | 단일 - | 기능 요구사항이 명시적이고 예시와 일치. 제약사항의 단일 '-'과 충돌은 위험으로 기록 |
| 13 | 단일 사용자 및 잠금 파일 | 동시 writer | 파일 안전성을 우선하며 구현 범위 통제 |
| 14 | 생성자 DI | 전역 저장소 | 테스트 용이성과 모듈 책임 분리 |
| 15 | 사용자 오류 메시지와 비영 종료 코드 | traceback 노출 | 평가 규칙 준수 |

## 한계 및 검증
10만 건에서 목록/검색 전체 스캔과 쓰기 전체 재작성은 병목. 벤치마크로 관찰하고 SQLite 전환, 인덱스, DB 트랜잭션을 개선책으로 설명한다(구현 범위 밖). os.replace는 단일 파일의 교체 안정성을 높이지만 플랫폼·파일시스템·전원 장애에 대한 절대적 안전성을 보장하지 않는다. 데모·테스트 기준은 acceptance.md 참조.
