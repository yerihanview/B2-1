# B2-1 상세 명세 v1.0

상태: 구현 기준 · 아직 구현 및 테스트 미실행. 설계 선택과 이유는 docs/design.md ADR 참조. 공식 미션 요구사항 충돌 시 공식 문서 우선.

## 실행 계약
- Python 3.10+, 표준 라이브러리만. `python -m budget_app [--data-dir PATH] <command> [options]`.
- 모든 명령과 서브명령 `--help` 지원. 옵션 표기는 `--`로 통일(원문 기능 요구와 예시 우선; 제약 문구 '-'와 충돌은 ADR-12로 추적).
- `--data-dir`은 명령 앞에 둔다. 기본 `./data`는 현재 작업 디렉터리 기준.
- 정상 종료 0, 입력/요구사항 위반 2, 저장·파일/데이터 손상 오류 3, 잠금 충돌 4. 사용자 오류는 `[오류] ... [힌트] ...`를 stderr에 출력하고 traceback은 출력하지 않는다. 도움말은 0.
- 모든 정상 명령은 세 JSONL 파일이 없으면 생성한다. 존재하지만 손상된 파일은 재생성하지 않는다.

## 데이터 계약
- transactions.jsonl: `{"id":"TX-<uuid4hex>","type":"expense","date":"2024-01-15","category":"food","amount":15000,"memo":"점심","tags":["meal"]}`.
- categories.jsonl: `{"name":"food"}`; budgets.jsonl: `{"month":"2024-01","amount":500000}`.
- 세 파일은 UTF-8 JSONL. JSONL의 비어 있는 행/유효하지 않은 JSON/중복 id/중복 category/중복 month/형식 불일치는 데이터 손상 오류로 다룬다.
- 거래 필수: id(유일), type income|expense, date 유효한 YYYY-MM-DD, amount 양의 정수(bool 거부), category 등록된 이름. memo/tags는 선택이고 기본 빈 값.
- category: trim 후 1~50자, 공백 없는 영문·숫자·밑줄·하이픈 (`^[A-Za-z0-9_-]{1,50}$`), 대소문자 구별; 거래·CSV 양쪽 동일 정책. 태그: trim 후 같은 문자 규칙, 각 1~30자, 중복 제거 후 원래 순서 유지. memo: UTF-8 텍스트 0~500자.
- 날짜 범위 경계는 양 끝 포함; from > to면 오류. month는 YYYY-MM 형식이며 실제 유효월.
- 거래 id 새로 생성: TX- + uuid4 hex 32자. 삭제된 id 재사용 금지(실질적으로 UUID 확률에 의존); 기존 레코드 수정 시 id 유지.

## 명령별 세부 동작
### add (대화형 필수)
`python -m budget_app add`: date,type,category,amount,memo,tags 순서대로 표준입력에서 수집. 검증 오류 시 사용자 메시지+비영 종료(재입력 루프는 구현하지 않음: 원문 '재입력 또는 오류' 만족). 빈 memo/tags 허용. 존재하는 category만 허용. 성공 시 `[저장 완료] id=<id>`.

### list
`list [--limit N]`: 기본 20, 1~1000; 날짜 내림차순, 동률은 저장 파일에서 뒤쪽 거래가 먼저. 각 행 `id | date | type | category | amount | memo`. 빈 결과 `[데이터 없음]`. transactions.jsonl generator 순회 및 bounded heap만 허용.

### search
`search [--from DATE] [--to DATE] [--category NAME] [--type income|expense] [--q TEXT] [--tag TAG] [--limit N]`: 입력한 조건 모두 AND. `--q`는 memo 대소문자 구별 부분 문자열 검색, `--tag`는 완전 일치. 다른 조건 없이 search도 허용(전체 list와 동일). 정렬·limit·빈 결과는 list와 동일.

### summary
`summary --month YYYY-MM [--top N]`: --top 기본 3, 1~100. 해당 월 전체 거래를 스트리밍 순회. 총수입, 총지출, 잔액(수입-지출), 카테고리별 **지출** 상위 N(합계 내림차순, 동일 합계는 category 문자열 오름차순) 출력. 거래가 없으면 `[데이터 없음] YYYY-MM`를 출력하되 예산 설정이 있으면 예산/사용률 0%도 표시. 예산 사용률 = (월 지출/예산)*100, 소수 첫째 자리; 지출 > 예산인 경우에만 초과 경고(같으면 초과 아님).

### budget
`budget set --month YYYY-MM --amount POSITIVE_INT`: 같은 월이 존재하면 덮어쓰기(업서트). `budget --help`와 `budget set --help` 지원. 성공 월/금액 출력. 예산은 양의 정수.

### category
`category add`: 대화형으로 이름을 입력하고 새 category 추가. 기존 name 중복이면 오류.
`category list`: 이름 사전순 출력. 없으면 안내.
`category remove`: 대화형으로 이름 입력. 현재 어떤 거래라도 해당 category를 사용하면 삭제 거부하고 해당 거래 수와 해결 힌트 안내. 존재하지 않는 이름은 오류.
카테고리 파일 초기값은 비어 있으며 add 전에 category add를 먼저 수행해야 한다.

### update
`update --id ID [--date DATE] [--type TYPE] [--category NAME] [--amount POSITIVE_INT] [--memo TEXT] [--tags CSV_TAGS]`: 옵션 방식만 지원; id 필수, 변경 필드 한 개 이상 필수. 지정하지 않은 속성은 그대로 유지. `--memo ""`는 비우기, `--tags ""`는 모든 태그 제거. 존재하지 않는 id는 오류+힌트; 변경 결과가 model 제약 위반 시 파일 변경 없음. 원래 파일 줄 위치 유지.

### delete
`delete --id ID`: 해당 id 1개 삭제. 없는 id는 오류+힌트. 확인 프롬프트 없이 실행(스크립트 재현성 우선), README에 비가역적 변경 경고.

### export
`export --out PATH [--month YYYY-MM | --from DATE --to DATE]`: 기간 지정은 --month 또는 --from/--to 쌍 중 반드시 하나. 섞어 사용 불가. 같은 이름 파일이 이미 있으면 명시적 `--overwrite`가 있어야 교체. 성공 `exported=<N>`와 경로 출력. CSV 정렬은 list와 동일 최신순이며 메모리 상한 문제를 피하기 위해 **날짜순 전체 정렬 대신 순차 스캔 순서로 내보냄**(미션은 export 순서 지정 없음). 헤더 포함, 데이터가 없어도 헤더 생성.

### import
`import --from PATH`: 전체 CSV 행을 읽고 모두 검증한 후에만 반영한다. CSV header가 정확히 `date,type,category,amount,memo,tags` 순서로 있어야 한다. 빈 필수 값, 미등록 category, 잘못된 amount/date/type/tag, 중복 헤더/예상 외 컬럼, UTF-8 오류가 있으면 전체 롤백. 같은 내용의 거래도 **새 거래**로 추가됨(기본 CSV에는 id 없어 중복 판별 불가); 사용자 문서에 비멱등성 명시. 기존 거래 수정 없음. 성공 `imported=N, skipped=0`; 실패 시 전체 미반영과 처음 20개 행 번호 및 원인. 최대 CSV 파일 크기·행수 미제한이나 디스크 여유/시간은 사전 운영 조건. CSV를 한 줄씩 읽고 staging temp 파일에 임시 저장한 뒤 정상 검증 시 transactions 단일 파일로 원자적 교체.

## CSV 스키마
헤더 순서: `date,type,category,amount,memo,tags` (UTF-8, csv 표준 quoting, newline=''). date: YYYY-MM-DD, type: income|expense, category: 기존 category, amount: 양의 정수 십진 숫자, memo: 선택, tags: 쉼표 구분 문자열(필드 자체는 CSV quote가 적용됨). 거래 id는 CSV에 포함하지 않는다.

## 저장/잠금/안전성 계약
- 파일 변경은 동일 디렉터리 temp+flush+fsync+os.replace. 치환 이전 오류에서 원본 동일성 검증. 디렉터리 fsync는 플랫폼에서 지원되면 수행.
- 단일 사용자 프로세스. 데이터 접근 명령 시작 시 `.budget_app.lock`을 배타 생성해 명령 종료 시 정리. 이미 있으면 오류 코드 4; stale lock은 사용자 수동 확인을 안내하되 프로그램이 자동 제거하지 않음.
- 파일 손상이나 파싱 오류 시 데이터 자동 복구/초기화 금지. 사용자 데이터 보호를 위해 즉시 종료.
- 단일 파일 원자적 교체이며 크로스파일 트랜잭션, 시스템 크래시 전원 차단을 포함한 완전 내구성은 비보장.

## 확장성 및 범위
100,000건의 list/search는 O(N log K), 메모리 O(K); update/delete/add/import는 파일 전체 재작성 O(N). 실제 10만 건 데이터로 재현 가능한 벤치마크 작성 및 설계상 대안을 설명하되 성능 절대 수치는 선결정하지 않는다.
보너스 backup, 반복 내역, 출력 정렬 강화는 구현 범위 밖.
