# Pyright 정적 검사 증빙 (A13)

- 실행일: 2026-11-03 (UTC)
- 수정 전 main 커밋: `d1acba759ac38804144af6954abd1a7dc635d7a9`
- 수정 후 검사 대상 커밋: `920356d69e475ca9e448a8fe59e45c12775d1d57`
- 도구: Pyright 1.1.414, Python 3.12.14
- 작업 디렉터리: `/workspace/B2-1`
- 명령: `pyright --outputjson budget_app tests scripts`
- 별도 Pyright 설정 없이 기본 검사. 도구는 저장소 밖 `/tmp/b2-pyright`에 설치.

| 결과 | 파일 수 | 오류 | 경고 | 종료 코드 |
|---|---:|---:|---:|---:|
| [수정 전](before.json) | 23 | 24 | 0 | 1 |
| [수정 후](after.json) | 23 | 0 | 0 | 0 |

JSON의 진단 줄·열 번호는 0부터 시작한다. 파일 경로만 저장소 기준 상대 경로로 정규화했다.

보완 내용: 반환 타입, Optional 값 확인, fdopen 인자 타입 추론, 테스트 대역·콜백 타입 계약을 정리했다. 읽기 전용 필드 예외 검증은 유지했다. 전체 unittest 120개와 기본·보너스 CLI smoke도 통과했다.

Pyright 통과는 정적 타입 검사 결과이며 실행 동작 전체의 보증은 아니다. 미션 A13의 공개 API 타입 힌트 검수를 보조하며, 미션 최종 인간 검수를 대체하지 않는다.
