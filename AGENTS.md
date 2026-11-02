# B2-1 AI 개발 하네스 — AGENTS.md v1.0

상태: 개발·검수 공통 지침. 실제 구현·테스트·승인 상태는 docs/validation-results.md를 따른다.

## 목적과 문서 기준
목표 A: 공식 B2-1 Python CLI 미션 평가 충족. 목표 B: 별도 개인 연구로 명세·테스트 중심 AI 개발 운영법 검증. B는 공식 평가항목이 아니다.

**우선순위**: (1) B2-1 공식 미션·평가표 (2) docs/spec.md의 명시 계약 (3) docs/design.md의 구조와 ADR (4) docs/acceptance.md 검수 기준 (5) docs/mission-strategy.md 운영 방식 (6) 개별 작업 지시 및 기존 코드. 상위 규칙과 충돌하는 요청은 실행 전 충돌과 제안을 보고한다. 원문 자체의 '-'/'--' 충돌은 ADR-12에 명시된 결정에 따른다.

## 작업 흐름 (필수)
1. 작업 전: 목표 검수 ID(Axx, Txx), 영향받는 문서 및 파일, 위험 요소 식별.
2. 구현: 임의 확장 없이 명세에 명시된 최소 기능 구현. 아키텍처 경계 유지.
3. 검증: 검수 대상별 `python -m unittest discover -s tests -v` 와 CLI smoke. 데이터 손상·에러·재시작·CSV 부분 실패 테스트 우선.
4. 실패: **재현 → 원인 분석 → 최소 수정 → 관련 및 회귀 테스트** 반복. 단순히 테스트의 기대값을 코드에 맞춰 완화하지 않는다.
5. 보고: 변경 파일, 설계 선택, 검사 명령과 실제 결과, 미해결 위험, 검수 ID 매핑.
6. 인간 승인: 아키텍처 변경, 데이터 손실 위험, 명세 변경, 최종 데모 검수는 사용자에게 판단 근거 제시.

## 절대 제약
- Python 3.10 이상, 실행에 표준 라이브러리만 사용. 외부 pip 라이브러리 금지(테스트·개발에도 기본적으로 stdlib만).
- `python -m budget_app` 방식으로 실행. `--help`, `--` 옵션 및 spec.md CLI 계약 준수.
- 필수 파일 3개: transactions/categories/budgets JSONL. 표준 CSV import/export 스키마 준수.
- min 3 모듈, min 2 클래스, dataclass Transaction; 제너레이터, 적용된 데코레이터, 타입 힌트가 실제 사용되어야 함.
- 사용자 입력 오류/권한·손상 오류 시 원인·해결 힌트와 0이 아닌 종료 코드; traceback 사용자 노출 금지.
- 저장 안전성: 임시 파일+원자적 교체, 읽기/쓰기 잠금 규칙, 오류 중 원본 보존. 불확실하면 작업 중단하고 위험 보고.
- 사용자 개인 재무 데이터, 인증 토큰, 비밀키 등 Git에 절대 포함 금지. 테스트 데이터는 가공·가상 값만 사용.
- 명세에 없는 프레임워크, DB, 과도한 로그 시스템을 임의 도입 금지. 사용자가 요청한 backup·recurring·출력 정렬·원자성 보너스는 docs/spec.md B01~B04를 따른다. 사용자가 승인한 설계/개발/독립 검증 역할 분리는 docs/implementation-plan.md를 따른다.
- 테스트/CI 통과를 실행 전 주장 금지. 사용자 승인 없이 데이터를 삭제하거나 기존 실데이터를 마이그레이션하지 않는다.

## 프로젝트 구조
```text
budget_app/
  __init__.py  __main__.py
  cli.py  service.py  models.py  repository.py
  csv_io.py  decorators.py  errors.py
tests/
  test_cli.py  test_service.py  test_repository.py  test_csv_io.py
docs/
  mission-strategy.md design.md spec.md acceptance.md
  demo.md learning-map.md
README.md
AGENTS.md
.gitignore
```
파일 수는 예시이며 역할/계약이 중요. 의존성은 CLI→Service→Repository; models/errors 공용. 상태를 전역으로 두지 말고 저장소를 생성자 주입한다.

## 테스트의 독립성
- 각 테스트는 예상 상태·메시지·종료 코드를 명세에서 도출하고, 코드를 구현한 방식만 검증하는 테스트를 경계한다.
- 정상 흐름뿐 아니라 경계값, 잘못된 데이터, CSV 전건 롤백, 재실행, 원본 보존, 10만 건 스트리밍을 검증한다.
- 결함 수정 시 실패 테스트를 먼저 확보하고, 수정 후 전체 회귀 테스트 실행.
- 데이터 정합성·파일교체·문서간 계약 불일치는 자동 테스트만 통과해도 인간 확인이 필요하다.

## 변경 관리
- 코드 구조/저장 포맷/CLI 계약 변경 제안 시 docs/design.md ADR와 docs/spec.md, docs/acceptance.md에 영향 분석 먼저 기록.
- 요구사항을 만족하지 못하는 기능의 구현 완료 선언 금지.
- GitHub 커밋은 목적별로 구분하고 검수 ID 언급. 최종 증빙에는 실제 실행 커밋 SHA와 명령을 명시한다.

## 에이전트 응답 형식
```text
목표/검수 ID:
변경 파일과 주요 구현:
실행한 테스트 명령:
테스트 실제 결과(통과/실패/미실행):
명세와의 차이/잔여 위험:
인간 승인 필요 여부:
```


## CI 실패 및 수정 정책

- 모든 구현 코드는 별도 작업 브랜치 및 PR로 제안하고, `main` 직접 구현 Push는 원칙적으로 금지한다.
- 검수 실패 시 [docs/failure-policy.md](docs/failure-policy.md)를 적용한다. 재현 가능한 동일 결함의 자동 수정은 최대 3회이며, 매번 관련 테스트와 전체 회귀를 실행한다.
- 명세 불일치·데이터 유실 위험·반복 실패는 사람에게 보고한다. CI 통과만으로 PR 자동 병합하지 않는다.
- GitHub Actions는 검수 실행기이며 자동 수정기는 아니다. 개발 에이전트 연결 전에는 실패 로그의 자동 복구를 주장하지 않는다.
