# B2-1 상세 명세 v1.0

상태: 구현 계약. 실제 구현·검증 결과는 validation-results.md 참조. 설계 선택과 이유는 docs/design.md ADR 참조. 공식 미션 요구사항 충돌 시 공식 문서 우선.

## 실행 계약
- Python 3.10+, 표준 라이브러리만. `python -m budget_app [--data-dir PATH] <command> [options]`.
- 모든 명령과 서브명령 `--help` 지원. 옵션 표기는 `--`로 통일(원문 기능 요구와 예시 우선; 제약 문구 '-'와 충돌은 ADR-12로 추적).
- `--data-dir`은 명령 앞에 둔다. 기본 `./data`는 현재 작업 디렉터리 기준.
- 정상 종료 0, 입력/요구사항 위반 2, 저장·파일/데이터 손상 오류 3, 잠금 충돌 4. 사용자 오류는 `[오류] ... [힌트] ...`를 stderr에 출력하고 traceback은 출력하지 않는다. 도움말은 0.
- 도움말과 인자 파싱 실패는 저장소에 접근하지 않는다. 데이터 명령은 잠금 확보 후 기존 세 파일 전체의 무결성을 확인하고 누락 파일만 생성한다. 손상 발견 시 누락 파일도 생성하지 않는다. 최초 초기화의 빈 파일 생성은 다중 파일 원자성이 없으며, 실패 시 기존 파일은 보존하고 생성된 빈 파일은 남을 수 있다.
- 알 수 없는 명령/옵션, 누락 인자, 대화형 EOF·사용자 입력 중단은 원인과 힌트를 출력하고 코드 2로 종료한다. 대화형 입력 검증 완료 전에는 초기화 외 데이터 변경을 하지 않는다.

## 데이터 계약
- transactions.jsonl: `{"id":"TX-<uuid4hex>","type":"expense","date":"2024-01-15","category":"food","amount":15000,"memo":"점심","tags":["meal"]}`.
- categories.jsonl: `{"name":"food"}`; budgets.jsonl: `{"month":"2024-01","amount":500000}`.
- 세 파일은 UTF-8 JSONL. JSONL의 비어 있는 행/유효하지 않은 JSON/중복 id/중복 category/중복 month/형식 불일치는 데이터 손상 오류로 다룬다.
- 거래 필수: id(유일), type income|expense, date 유효한 YYYY-MM-DD, amount 양의 정수(bool 거부), category 등록된 이름. memo/tags는 선택이고 기본 빈 값.
- category: trim 후 1~50자, 공백 없는 영문·숫자·밑줄·하이픈 (`^[A-Za-z0-9_-]{1,50}$`), 대소문자 구별; 거래·CSV 양쪽 동일 정책. 태그: trim 후 같은 문자 규칙, 각 1~30자, 중복 제거 후 원래 순서 유지. memo: UTF-8 텍스트 0~500자.
- 날짜 범위 경계는 양 끝 포함; from > to면 오류. month는 YYYY-MM 형식이며 실제 유효월.
- 거래 id 새로 생성: TX- + uuid4 hex 32자. 삭제된 id 재사용 금지(실질적으로 UUID 확률에 의존); 기존 레코드 수정 시 id 유지.
- JSON 객체의 중복 키·미정의 키·잘못된 값 타입은 손상 오류다. 거래의 memo/tags 생략은 각각 빈 문자열/빈 목록으로 읽는다. 저장된 category/tag는 이미 정규형이어야 하며 trim·중복 제거로 손상을 자동 수정하지 않는다. 거래의 미등록 category 참조도 손상 오류다. 모든 데이터 명령은 검색조건·limit과 관계없이 세 파일 전체를 검증하고, 검증 완료 전 성공 결과를 출력하거나 기존 파일을 변경하지 않는다.
- 입력의 정규화는 category/tag trim 및 태그 중복 제거만 한다. 빈 태그 문자열은 태그 없음, `a,,b` 또는 공백만 있는 토큰은 입력 오류다. 날짜는 ASCII `YYYY-MM-DD`, 월은 ASCII `YYYY-MM` 고정 길이, 금액은 ASCII `[0-9]+`의 양수다. 부호·소수점·지수·숫자 안팎 공백은 허용하지 않는다. memo 공백은 보존한다.
- summary 사용률은 정수 금액으로 계산하고 십진 ROUND_HALF_UP 방식으로 소수 첫째 자리까지 표시한다. 금액 자체는 float로 변환하지 않는다.

## 명령별 세부 동작
### add (대화형 필수)
`python -m budget_app add`: date,type,category,amount,memo,tags 순서대로 표준입력에서 수집. 검증 오류 시 사용자 메시지+비영 종료(재입력 루프는 구현하지 않음: 원문 '재입력 또는 오류' 만족). 빈 memo/tags 허용. 존재하는 category만 허용. 성공 시 `[저장 완료] id=<id>`.

### list
`list [--limit N]`: 기본 20, 1~1000; 날짜 내림차순, 동률은 저장 파일에서 뒤쪽 거래가 먼저. 각 행 `id | date | type | category | amount | memo`. 빈 결과 `[데이터 없음]`. transactions.jsonl generator 순회 및 bounded heap만 허용.

### search
`search [--from DATE] [--to DATE] [--category NAME] [--type income|expense] [--q TEXT] [--tag TAG] [--limit N]`: 입력한 조건 모두 AND. `--q`는 memo 대소문자 구별 부분 문자열 검색, `--tag`는 완전 일치. 다른 조건 없이 search도 허용(전체 list와 동일). 정렬·limit·빈 결과는 list와 동일.

검색 category/tag는 문자 형식을 검증하되 등록 여부를 요구하지 않는다. 유효한 형식의 미등록 이름은 빈 검색 결과다. 빈 `--q`는 모든 memo와 일치한다.

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
`export --out PATH [--month YYYY-MM | --from DATE --to DATE] [--overwrite]`: 기간 지정은 --month 또는 --from/--to 쌍 중 반드시 하나. 섞어 사용 불가. 같은 이름 파일이 이미 있으면 명시적 `--overwrite`가 있어야 교체. 성공 `exported=<N>`와 경로 출력. CSV는 **transactions 파일의 순차 스캔 순서**로 내보내며 최신순 정렬하지 않는다. 헤더 포함, 데이터가 없어도 헤더 생성. 첨부 공식 원문 대조 결과 export 정렬 순서는 지정되지 않았으며, 파일 순서는 프로젝트의 설계 선택이다.

출력 대상의 정규화된 실제 경로가 내부 세 JSONL 파일·잠금 파일과 같거나, 기존 파일의 동일 inode 별칭(hard link 포함)이면 `--overwrite` 유무와 관계없이 입력 오류 2로 거부한다. 보호 파일로 향하는 symlink도 거부한다. 출력 부모 디렉터리는 기존 디렉터리여야 한다. 교체 직전에도 보호 경로를 재확인하고, 비덮어쓰기 모드에서는 기존 출력 파일을 치환하지 않는다. 외부 프로세스의 악의적 경로 변경까지 방어하는 보안 경계는 범위 밖이다.

### import
`import --from PATH`: 전체 CSV 행을 읽고 모두 검증한 후에만 반영한다. CSV header가 정확히 `date,type,category,amount,memo,tags` 순서로 있어야 한다. 빈 필수 값, 미등록 category, 잘못된 amount/date/type/tag, 중복 헤더/예상 외 컬럼, UTF-8 오류가 있으면 전체 롤백. 같은 내용의 거래도 **새 거래**로 추가됨(기본 CSV에는 id 없어 중복 판별 불가); 사용자 문서에 비멱등성 명시. 기존 거래 수정 없음. 성공 `imported=N, skipped=0`; 검증 또는 교체 전 실패 시 전체 미반영과 처음 20개 행 번호 및 원인을 안내한다. 교체 후 실패는 저장/잠금/안전성 계약을 따른다. 최대 CSV 파일 크기·행수 미제한이나 디스크 여유/시간은 사전 운영 조건. CSV를 한 줄씩 읽고 staging temp 파일에 임시 저장한 뒤 정상 검증 시 transactions 단일 파일로 원자적 교체.

## CSV 스키마
헤더 순서: `date,type,category,amount,memo,tags` (UTF-8, csv 표준 quoting, newline=''). date: YYYY-MM-DD, type: income|expense, category: 기존 category, amount: 양의 정수 십진 숫자, memo: 선택, tags: 쉼표 구분 문자열(필드 자체는 CSV quote가 적용됨). 거래 id는 CSV에 포함하지 않는다.

UTF-8 BOM은 허용하지 않는다. 빈 파일은 헤더 누락 오류, 헤더만 있으면 `imported=0, skipped=0` 성공이며 거래 파일을 교체하지 않는다. 빈 레코드·열 부족/초과·닫히지 않은 quote 등 csv strict 파싱 오류는 입력 오류 2다. 잘못된 UTF-8·읽기 실패는 파일 오류 3이며 부분 반영하지 않는다. 행 번호는 헤더를 1행으로 센 물리적 시작 줄 번호다. 여러 줄 memo는 한 레코드로 처리한다. 복구 가능한 레코드 검증 오류는 최초 20건까지 보고하고, 파싱/디코딩을 계속할 수 없으면 해당 지점에서 종료한다.

## 저장/잠금/안전성 계약
- 파일 변경은 동일 디렉터리 temp+flush+fsync+os.replace. 치환 이전 오류에서 원본 동일성 검증. 디렉터리 fsync는 플랫폼에서 지원되면 수행.
- 단일 사용자 프로세스. 데이터 접근 명령 시작 시 `.budget_app.lock`을 배타 생성해 명령 종료 시 정리. 이미 있으면 오류 코드 4; stale lock은 사용자 수동 확인을 안내하되 프로그램이 자동 제거하지 않음.
- 파일 손상이나 파싱 오류 시 데이터 자동 복구/초기화 금지. 사용자 데이터 보호를 위해 즉시 종료.
- 단일 파일 원자적 교체이며 크로스파일 트랜잭션, 시스템 크래시 전원 차단을 포함한 완전 내구성은 비보장.
- 교체 성공 이후 디렉터리 fsync 실패는 코드 3과 함께 '변경 반영됨, 내구성 확인 실패'를 안내한다. 미반영·롤백 성공으로 보고하거나 자동 재실행하지 않는다. 지원되지 않는 디렉터리 fsync는 플랫폼 한계로 구분한다.
- 잠금은 입력 수집을 포함한 데이터 명령 전체에 유지한다. 정상/오류/입력 중단 시 자신이 획득한 잠금만 정리하며 다른 프로세스의 잠금은 삭제하지 않는다. 강제 종료 후 stale lock은 수동 확인 대상이다.

## 확장성 및 범위
N은 거래 수, K는 limit이다. list/search의 거래 선택은 generator와 bounded heap으로 시간 O(N log K), 추가 메모리 O(K)다. 정확한 전체 중복 ID 검출에는 ID 집합 O(N)을 사용한다. 따라서 전체 명령을 O(K) 메모리라고 주장하지 않는다. 카테고리·월 집합 비용도 별도 기록한다. 전체 거래 객체를 목록으로 적재하는 것은 허용하지 않는다. add/update/delete/import는 기존 N건과 입력 M건에 대해 O(N+M) 재작성하며 무결성 검증 집합 비용을 포함한다. 실제 10만 건 데이터로 재현 가능한 벤치마크를 작성한다. 첨부 공식 원문은 제너레이터 기반 스트리밍과 전체 파일 일괄 적재 금지를 요구하며 전체 명령 O(K)는 요구하지 않는다. 원문은 사용자 요청에 따라 저장소에 포함하지 않는다.
보너스 backup, 반복 내역, 출력 정렬 강화는 사용자 요청으로 아래 B01~B04 필수 범위에 포함한다.

## 보너스 필수 범위 (사용자 요청, 2026-11-02)

보너스 4개를 모두 프로젝트 필수 범위에 포함한다. B01 백업, B02 반복 내역, B03 테이블 정렬, B04 저장 원자성 강화다. 기존 원자성 계약은 B04에도 적용한다. 외부 패키지·백그라운드 스케줄러·실데이터 자동 마이그레이션은 추가하지 않는다.

### B01 backup

`backup [--out-dir PATH]`: 같은 데이터 잠금을 보유하고 전체 무결성 검증을 마친 뒤 저장 파일들의 일관된 스냅샷을 ZIP으로 만든다. 기본 출력 폴더는 `<data-dir>/backups`이며 없으면 생성한다. `backup-<UTC YYYYMMDDTHHMMSSffffffZ>-<uuid4hex>.zip` 이름으로 생성하고 기존 아카이브는 덮어쓰지 않는다. 성공 시 생성된 경로를 출력한다. ZIP에는 세 기본 JSONL과 존재하는 경우 recurring.jsonl, manifest.json만 넣는다. 잠금·이전 백업·절대 경로·기타 파일은 포함하지 않는다. manifest는 `format="budget_app_backup"`, `version=1`, UTC `created_at`, 각 파일 이름에 대한 `size`(바이트)·`sha256`을 포함하는 `files` 객체다. 저장 파일은 원본 바이트 그대로 백업한다. 생성 파일은 같은 출력 폴더의 임시 파일에 스트리밍 작성·flush/fsync 후 배타적으로 발행하고 디렉터리 fsync를 수행한다. 발행 전 실패는 완성 ZIP을 남기지 않으며 데이터 원본을 보존한다. 발행 후 오류는 반영됨/정리 또는 내구성 확인 실패로 보고한다. 자동 복구 명령은 추가하지 않는다. 검수에서는 ZIP 해시와 가상 복구 디렉터리에서의 CLI 실행을 확인한다.

### B02 recurring

- `recurring add --day N --type income|expense --category NAME --amount POSITIVE_INT [--memo TEXT] [--tags CSV_TAGS]`: 매월 반복 규칙을 등록한다. day는 1~31의 ASCII 양의 정수, 나머지 검증·정규화는 거래와 같다. ID는 `RR-` + uuid4 hex 32자이며 유일하다. 성공 시 ID를 출력한다.
- `recurring list`: 규칙을 ID 오름차순으로 출력한다. 없으면 `[데이터 없음]`을 표시한다.
- `recurring remove --id ID`: 규칙만 삭제한다. 이미 생성된 거래는 보존하며 없는 ID는 코드 2다.
- `recurring apply --month YYYY-MM`: 모든 현재 규칙을 해당 월 거래로 한 번에 생성한다. 해당 월에 day가 없으면 마지막 날을 사용한다(예: 31일 규칙→2024-02-29). 생성 거래 ID는 새로운 UUID4다. `generated=N, skipped=M`을 출력한다. 입력/저장 오류 시 전건 미반영이며 transactions.jsonl만 한 번 원자 교체한다.
- 규칙은 선택 파일 `recurring.jsonl`에 `{id,day,type,category,amount,memo,tags}`로 저장한다. memo/tags는 생략 시 기본 빈 값이다. 기존 3파일은 그대로 읽으며 일괄 변환하지 않는다. recurring 파일이 없으면 빈 규칙 집합이고, 첫 규칙 저장 때 생성한다. 존재하면 모든 데이터 명령의 전체 손상 검증과 export 출력 보호 대상이다. 규칙 ID 중복·미정의/중복 키·비정규 값·미등록 category 참조는 손상 오류다. 등록된 반복 규칙이 사용하는 category도 삭제를 거부하고 참조 수를 안내한다.
- 생성 거래에는 선택 필드 `recurring_id`, `recurring_month`를 함께 저장한다. 두 값은 각각 유효한 RR UUID4 ID와 YYYY-MM이며 반드시 쌍으로 존재한다. 같은 (규칙 ID, 생성 월) 쌍의 중복 거래는 손상 오류다. 과거 거래를 보존하기 위해 이미 삭제한 규칙의 ID도 출처로 허용한다. `update`는 이 출처 필드를 변경하지 않는다. CSV 최소 스키마는 유지하며 출처 필드는 CSV에 포함하지 않는다.
- apply는 현재 거래에 같은 출처 쌍이 있으면 건너뛴다. 거래의 날짜/금액/태그를 수정해도 출처는 유지되므로 재생성하지 않는다. 생성 거래를 직접 삭제한 뒤 apply하면 새 ID로 다시 생성한다. 규칙을 삭제하고 새로 등록하면 별도 규칙으로 처리한다. 명령 실행 없이 자동으로 월별 거래를 만들지는 않는다.

### B03 테이블 정렬

list/search는 기존 여섯 열과 최신순·limit 계약을 유지하며 열마다 표시 폭을 맞춘다. 열 사이는 ` | `, 금액은 오른쪽 정렬하고 나머지는 왼쪽 정렬한다. 한글 등 East Asian Width W/F는 2칸, 결합 문자는 0칸, 나머지는 1칸으로 계산한다. 메모의 줄바꿈/탭/제어문자는 화면에서 이스케이프해 한 거래가 한 물리적 줄을 차지하게 한다. 저장된 메모는 변경하지 않는다. 빈 결과는 기존 안내를 유지한다. 터미널/폰트에 따른 복합 이모지 폭의 완전한 일치는 보장하지 않는다.
