# B2-1 최종 데모 및 증빙 설계 v1.0

상태: 시연 시나리오. 가상 데이터 CLI 자동 시연은 scripts/smoke.py로 재현하며 실행 결과는 evidence/toomuch/01-cli-demo.txt 참조. 사람의 최종 데모 승인은 별도다. **15분은 사용자 제안 목표이며 공식 평가 시간 제한이 아니다.**

## 준비
- Python 버전과 git commit 기록. 테스트용 임시 data-dir 사용, 개인정보 제외.
- 데모용 가상 파일: category food/transport/salary, 거래 4~6건, budget 2024-01 = 500000, 정상 CSV와 잘못된 CSV 각 하나.
- CLI 실행 화면, 데이터 파일 3종, docs/design.md 계층 그림, docs/acceptance.md 추적표를 준비.
- 데모 전 테스트 통과를 실제 확인하고 실패는 숨기지 않는다.

## 시연 1: 정상 동작·영속성 (6분)
1. `category add`로 food/salary 등록, category list.
2. `add`로 income/expense 입력하여 생성 id 확인.
3. list 최신순, search 기간/category/tag로 검색.
4. update --id ... --memo ..., delete --id ... 후 list 비교.
5. budget set --month 2024-01 --amount 500000 → summary --month 2024-01 --top 3, 지출/사용률/초과 경고 설명.
6. export --out ... --month 2024-01 → CSV 헤더/UTF-8 확인. import --from ... 정상 건수 확인.
7. 프로그램을 별도 프로세스로 재실행하고 category/budget/transaction 영속성 확인, data 폴더 3개 파일 확인.
8. 의도적 잘못된 날짜/CSV 행을 이용해 원인+힌트와 비영 종료 코드 확인. CSV 실패 시 거래 건수 그대로 유지되는지 확인.

## 시연 2: 전체 구조 (3분)
- CLI → Service → Repository → JSONL 데이터 흐름.
- 모델의 dataclass, 최소 2 클래스·3 모듈의 책임 경계.
- 임시 파일+flush/fsync+os.replace 및 중단 시 원본 보존이라는 장점과 한계.

## 시연 3: 핵심 기술 (3분)
- 제너레이터 yield와 K개 bounded heap: 거래 객체 전체를 적재하지 않는 이유와 중복 ID 집합 O(N)의 별도 비용.
- 공통 오류 매핑 decorator 적용 위치와 책임 분리.
- type hint로 드러나는 호출/반환 계약과 실제 사례.

## 시연 4: 선택과 대안 (3분)
- 왜 내부 JSONL/외부 CSV인가? 두 포맷 비교.
- 10만 건에서 전체 파일 스캔과 재작성의 병목, SQLite/인덱싱 대안.
- 깨진 CSV 처리의 전체 롤백 정책, 오류 행 번호와 사용자 신뢰.

## 최소 증거 패키지
- 기능/영속성 시연 메모 또는 실제 실행 출력
- 테스트 한 번의 전체 결과와 실행한 커밋 ID
- 의도된 오류 메시지/exit code 및 혼합 CSV 롤백의 실제 실행 결과
- 아키텍처 그림 1장(README 또는 docs/design.md 기반)
- **실제로 확인한 증거만 사용**. 전 과정 캡처·중복 로그 축적 금지.

## 평가 매핑
공식 항목 1→시연1 / 항목 2→시연2 / 항목 3→시연3 / 항목 4→시연4. 상세 세부 매핑과 검수 상태는 docs/acceptance.md.

## 보너스 시연

`scripts/bonus_smoke.py`로 가상 데이터에서 반복 규칙 등록·윤년 말일 거래 생성·같은 월 skip·정렬 출력·백업 manifest/원본 바이트 대조·별도 폴더 복구 후 CLI·규칙 삭제 후 과거 거래 보존·백업 반복 생성까지 실행한다. B04 교체 전후 장애는 단위 장애 주입 로그로 설명한다. 이 자동 시연과 사람의 최종 설명/데모 승인은 별도다.
