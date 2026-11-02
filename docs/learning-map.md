# B2-1 학습 개념 지도 v1.0

상태: 미션 학습 순서 계획. 문법별 튜토리얼 대신 구조·원리·설계 판단을 우선.

## 선수지식 기반 순서
1. **프로세스/CLI 실행:** Python 인터프리터, 모듈 로딩, `python -m`, 인자·표준입력·표준출력/표준에러, 종료 코드. 목표: 명령이 프로그램 어디로 진입해 종료되는지 설명.
2. **데이터 모델과 계약:** dataclass, 객체/클래스의 책임, 필드 불변조건, 타입 힌트와 런타임 검증의 차이. 목표: 어떤 데이터가 유효한 거래인지 설명.
3. **모듈 계층과 DI:** cli/service/repository 경계, 생성자 주입, 결합도와 테스트 용이성. 목표: 저장 포맷 변경이 서비스 규칙에 영향을 주지 않는 이유 설명.
4. **영구 저장과 장애:** 파일, JSONL/CSV, utf-8, flush/fsync, temp+replace, lock, 원자성 범위, 데이터 오염 방지. 목표: 수정/삭제 실패 때 원본이 왜 남는지 설명.
5. **제너레이터·메모리·정렬:** iterable/iterator/yield, 파일 순차 스캔, 최신순 정렬, bounded heap, 선택 알고리즘 O(N log K)/O(K), 중복 ID 검증 집합 O(N). 목표: 10만 건에서 무엇이 늘어나는지 설명.
6. **공통 관심사·오류:** 데코레이터와 `functools.wraps`, 예외 경계, 사용자 오류 코드. 목표: 정상 로직과 오류 처리를 왜 분리하는지 설명.
7. **검증 체계:** 단위/통합/CLI subprocess, tempfile, 주입 가능한 저장소, 경계값/장애 주입/회귀 테스트. 목표: 테스트 통과가 의미하는 범위와 의미하지 않는 범위를 설명.
8. **AI 개발 하네스:** 명세→작업 위임→자동 검수→실패 수정→위험 기반 인간 승인, 실제 비용/품질 회고. 목표: 품질을 코드 전수 검토 없이 어떻게 통제하는지 설명.

## 학습 운영
- 각 주제는 **전체 구조 → 핵심 개념 → 실제 코드에서 근거 확인 → 검수 가능 여부 설명** 순.
- 단순 Python 문법 암기, 전 함수 줄별 해석, 코드 수동 변경은 필수 활동으로 두지 않음.
- 공식 평가의 설명 항목은 이해를 확인하는 기준. AI 하네스는 별도의 개인 연구 성과.
- 이해가 불충분한 주제만 확장 학습하고, 정해진 주제 밖으로 무한 확장하지 않는다.

## 구현에서 확인할 위치

- 진입점·argparse·대화형 입력·출력: `budget_app/__main__.py`, `cli.py`.
- 불변 dataclass와 실제 입력/저장 모델 검증: `models.Transaction`, `from_dict`.
- 생성자 DI와 bounded heap, 요약의 정수 금액/십진 반올림: `service.Service`.
- 실제 yield와 전체 무결성 검증, session 잠금, publication 전후 실패: `repository.Repository`.
- CSV strict reader·디스크 staging·전건 롤백·고정 스키마: `csv_io.py`.
- 실제 적용된 `@user_errors`, `functools.wraps`, 오류 코드: `decorators.py`, `errors.py`, `cli.main`.
- 타입 힌트의 한계: 런타임 검증을 대신하지 않는다. 실제 get_type_hints 검수는 개발 테스트, 동작 계약 검수는 독립 CLI 테스트에서 확인한다.

이 위치의 코드를 따라 설명하고, validation-results.md의 실행 근거와 연결한다. AI의 자동 실행은 사람의 설명 가능성·최종 데모 승인을 대신하지 않는다.

보너스 학습 근거: backup.create_backup의 잠금 아래 스트리밍 ZIP·SHA-256, models.RecurringRule과 Transaction 출처 쌍, Service의 달력 보정·원자적 월 생성, formatting의 Unicode 폭·출력 이스케이프를 코드와 보너스 검수 로그로 설명한다.
