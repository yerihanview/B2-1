# 구현·검수 결과

현재는 사용자 승인 후 PR #1이 main에 병합된 상태다. [최종 제출물 점검](submission-check.md)과 [평가 대비 설명](evaluation-guide.md)을 추가했다. 아래는 단계별 당시 기록이며, 과거의 승인 대기·원격 미확인 표현과 현재 상태를 구분한다.

최신 상태: 최종 PR 검토 중 발견한 큰 합계 오류를 수정했다. 최신 전체 회귀와 CI·승인 대상은 [final-review.md](final-review.md)를 따른다. 아래 71개·113개 결과는 각각 당시 고정 소스의 실행 기록이다.

기준 소스 커밋: `823779645ec28ed202d06f34c20c0737b83fcf9d`의 전체 SHA는 아래 실행 로그에 기록한다. 이 기본 단계 기록은 보너스 추가 전 소스의 결과다. 이후 보너스 통합 결과와 구분한다. 2026-11-02.

## 구현 범위

표준 라이브러리만으로 `python -m budget_app` 진입점, 거래 CRUD, 최신순 list/search, 월 요약, category, budget, JSONL 세 파일, CSV import/export를 구현했다. Transaction은 불변 dataclass이며 Service에 Repository를 생성자 주입한다. CLI는 Service로 흐름을 전달하고 CSV 변환은 csv_io, 잠금·파일 검증·발행은 Repository가 담당한다.

## 실행 결과와 근거

| 검사 | 결과 | 근거 |
|---|---|---|
| Python 3.12.14 전체 회귀 | 71개, 실패·오류·스킵 0 | [로그](../evidence/04-tests-python312.txt) |
| Python 3.10.22 전체 회귀 | 71개, 실패·오류·스킵 0 | [로그](../evidence/04-tests-python310.txt) |
| 독립 CLI 검수 | 위 각 71개 중 30개. 명세에서 먼저 작성, 구현 import/수정 없이 subprocess 검수 | [테스트](../tests/test_acceptance_cli.py) |
| 개발 모델·서비스·장애 검수 | 위 각 71개 중 41개 | tests/test_models.py, test_service.py, test_repository.py, test_csv_io.py |
| 실제 CLI 데모 | 정상·오류·혼합 CSV 롤백·별도 프로세스 재실행 통과 | [실행 로그](../evidence/01-cli-demo.txt), scripts/smoke.py |
| 10만 건 측정·출력 검수 | 별도 측정 결과 아래 기록 | [원시 결과](../evidence/05-benchmark.jsonl), scripts/benchmark.py |
| GitHub Actions | 원격 실행 미확인 | PR·수동 트리거 유지. 로컬 실행 결과를 원격 CI 성공으로 간주하지 않음 |
| 사람의 최종 데모·병합 | 승인 대기 | docs/demo.md, acceptance.md G2 |

양 버전 테스트는 같은 고정 소스에서 실행했다. 증거 커밋은 실행 로그를 추가하기 때문에 실행 대상 소스 커밋과 구분한다. 자동 시연은 사람이 프로그램 구조와 설계 선택을 설명할 수 있는지를 보증하지 않는다.

## 재현

저장소 루트에서 외부 패키지 없이 실행한다.

```bash
python -m unittest discover -s tests -v
python scripts/smoke.py
python scripts/benchmark.py --repeat 1
```

환경에 준비된 최소 버전 인터프리터는 `/workspace/.runtimes/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10`이다. 다른 환경에서는 자체 Python 3.10+를 사용한다. 원격 Actions는 Python 3.10으로 설정되어 있다.

## 검수 ID 대응

- A01~A07: 독립 CLI 정상·경계·지속성·오류·종료 코드, 실제 smoke 흐름.
- A08/A09/A12/A13: 구조·dataclass·DI·실제 decorator 적용/wraps·타입 힌트·stdlib imports 개발 검수와 design/learning-map의 설명 근거. 사람의 설명 평가는 대기.
- A10: T16/T26 단계별 write/flush/fsync/replace 실패 주입, 모든 변경 대상 원본 보존, 교체 후 fsync/정리 실패의 반영 상태 구분.
- A11: 실제 generator 순회, bounded heap 최신 K 선택, 10만 건 list/search 출력 건수 및 메모리 측정.
- A14: design ADR-01에 JSONL/CSV 장단점과 선택 근거. 사람의 설명 평가는 대기.
- A15: P01 고정 seed·N/K 변화·list/search/add/update 측정과 아래 병목 분석. 사람의 설명 평가는 대기.
- A16: 잘못된 CSV 레코드/UTF-8/quoting·행 번호·오류 20건 상한, staging 전건 미반영과 정상 import 확인.
- F11: README 실행·저장 위치/형식·주요 명령·CSV 스키마·삭제 경고를 정리하고 smoke에서 대표 예시를 실행했다. 모든 문구 조합을 전수 실행했다는 의미는 아니다.

## 남는 한계

- 단일 파일 발행이며 다중 파일 트랜잭션·전원 장애 완전 내구성·자동 복구는 제공하지 않는다. 교체 이후 오류는 미반영으로 간주하지 않는다.
- 명령 실행 중에는 읽기도 잠근다. 강제 종료 후 stale lock은 사람의 확인이 필요하다.
- 정확한 중복 ID 검출 집합 때문에 전체 메모리는 O(N)이다. 전체 거래 객체는 적재하지 않으며 조회 선택 힙만 O(K)다.
- CSV에는 ID가 없어 재수입은 중복 추가다. 이 기본 단계 이후 사용자 요청으로 보너스 백업·반복 거래·정렬·원자성 전체를 추가했다.
- 공식 원문·평가표는 첨부 텍스트 대조 완료이며 사용자 요청에 따라 GitHub에 포함하지 않았다. 삽입 이미지는 대조 범위 밖이다.
- 테스트 통과는 모든 입력·플랫폼에서의 무결성을 보증하지 않는다. 실제 Linux 검증 범위와 mock 장애 주입을 구분한다.

## P01 측정 결과

Python 3.12.14, Linux, seed 20261102, 각 1회. 시작 import와 데이터 생성은 제외하고 CLI 전체 검증·파일 I/O·fsync·tracemalloc 비용은 포함했다. 최대 메모리는 Python 할당 추적값이며 프로세스 RSS와 다르다.

| 명령 | N | K | 시간(초) | 최대 Python 할당(MiB) | 동작 확인 |
|---|---:|---:|---:|---:|---|
| list | 10000 | 20 | 1.139 | 1.47 | 출력 20건 |
| list | 100000 | 20 | 11.533 | 11.93 | 출력 20건 |
| list | 100000 | 1000 | 11.431 | 11.94 | 출력 1000건 |
| search | 100000 | 20 | 11.688 | 11.94 | 출력 20건 |
| add | 100000 | — | 20.501 | 11.94 | 저장된 추가/수정 내용 확인 |
| update | 100000 | — | 13.485 | 11.93 | 저장된 추가/수정 내용 확인 |

N이 커지면 전체 무결성 검사와 조회 스캔 비용이 증가한다. N=10만에서 K=20/1000의 전체 최대 메모리가 비슷한 것은 ID 집합 검증 단계가 peak를 지배하기 때문이다. 이 수치만으로 조회 힙 O(K)를 증명하지 않으며 bounded heap 구현·정렬/건수 검수와 함께 판단한다. add는 유일 ID 검사와 기존 파일 재작성, update도 탐색과 재작성 때문에 여러 번 순회한다.

개선 대안은 디스크 기반 중복 검증, 날짜/검색 인덱스, SQLite 트랜잭션이다. 현재 미션에서는 외부 저장 구조를 추가하지 않고 비용과 한계를 설명한다. 1회 측정이므로 통계적 성능 보장이나 임의 합격 시간 상한으로 사용하지 않는다.

## 보너스 통합 검수 B01~B04

사용자가 보너스 4개 전체를 필수 범위로 지정하여 구현했다. 기존 데이터 세 파일은 그대로 읽으며 recurring.jsonl은 첫 규칙 저장 때만 추가한다. 생성 거래에 선택 출처 쌍을 보존하고 기존 기록을 자동 마이그레이션하지 않는다.

최종 앱·테스트·시연 소스 SHA: `5af81cf787d57a25769d18f1a8147b80e85e0eb7`. 아래 로그는 같은 소스에서 실행했다. 이후 문서·증거 정리 커밋은 앱·테스트·스크립트 소스를 변경하지 않는다.

| 검사 | 결과 | 근거 |
|---|---|---|
| Python 3.10.22 전체 회귀 | 113개 통과, 실패·오류·스킵 0 | [전체 로그](../evidence/bonus-tests-python310.txt) |
| Python 3.12.14 전체 회귀 | 113개 통과, 실패·오류·스킵 0 | [전체 로그](../evidence/bonus-tests-python312.txt) |
| 독립 CLI | 기존 30개 + 보너스 18개, 위 전체 회귀에 포함 | test_acceptance_cli.py, test_bonus_acceptance.py |
| 개발 단위·장애 | 기존 41개 + 보너스 24개, 위 전체 회귀에 포함 | test_bonus.py, test_bonus_service.py, test_bonus_formatting.py 및 기존 테스트 |
| 기본 CLI 실제 시연 | 보너스 추가 후에도 통과 | [로그](../evidence/bonus-core-demo.txt) |
| 보너스 CLI 실제 시연 | 월말·중복 방지·정렬·백업·가상 복구·과거 거래 보존 통과 | [로그](../evidence/bonus-demo.txt) |
| 최신 10만 건 검사 | 결과·분석은 아래 최신 측정 절 참조 | [원시 결과](../evidence/bonus-benchmark.jsonl) |

- B01: 원본 바이트와 SHA-256/크기 manifest, 정확한 ZIP 구성·기타 파일 제외, 기존 백업 보존, 별도 폴더에서 CLI 복구 검증. 발행 전 오류는 원본 보존과 산출물 정리, 발행 후 디렉터리 fsync 오류는 완성 ZIP 보존과 반영됨 안내를 확인했다.
- B02: 윤년·비윤년·30일 월말, 출처 멱등성, 수정 후 skip, 거래 삭제 후 새 ID 생성, 규칙 삭제 후 과거 거래 보존, 규칙 참조 카테고리 삭제 거부, 손상/중복 출처, apply 원자 교체와 무변경 skip 검수.
- B03: 한글·Unicode Mn/Me·결합 문자 표시 폭, 금액 오른쪽 정렬, 마지막 메모 열까지 표시 폭 정렬, newline/tab/제어문자 escape, 원본 메모 보존 확인.
- B04: 기존 T16/T26과 신규 규칙/거래/ZIP 발행 경로의 장애 주입 검수.

실제 테스트는 Linux와 두 Python 버전에서 실행했다. 복합 이모지의 글자 폭은 터미널·폰트에 따라 다를 수 있다. 백업은 제공하지만 자동 복구 명령·백그라운드 월별 스케줄러는 제공하지 않는다. `recurring apply --month`가 명시적인 생성 시점이다. 이 실행 당시 원격 Actions 결과는 별도로 남겼으며, 이후 확인한 CI와 최신 검토 상태는 final-review.md를 따른다. 사람의 최종 데모·병합 승인은 여전히 별도다.

## 보너스 통합 버전 P01 최신 측정

동일 seed·Python 3.12.14·각 1회·tracemalloc 포함 조건이다. 반복 규칙이 없는 10만 건 거래 fixture로 기존 list/search/add/update 회귀 비용을 측정했다. 백업·반복 내역 자체의 동작은 별도 보너스 CLI/장애 검수로 확인했으며 이 표가 10만 개 반복 규칙의 성능을 뜻하지는 않는다.

| 명령 | N | K | 시간(초) | 최대 Python 할당(MiB) |
|---|---:|---:|---:|---:|
| list | 10000 | 20 | 1.224 | 1.50 |
| list | 100000 | 20 | 11.102 | 11.96 |
| list | 100000 | 1000 | 11.883 | 11.96 |
| search | 100000 | 20 | 11.784 | 11.97 |
| add | 100000 | — | 19.757 | 11.97 |
| update | 100000 | — | 14.805 | 11.96 |

조회 출력 20/1000건과 추가·수정 저장 내용을 확인했다. 전체 ID 검증 집합과 전체 파일 순회/재작성 병목은 유지되며, 성능 절대값을 합격 상한이나 전체 O(K)의 증명으로 사용하지 않는다.
