# GitHub 최종 제출물 점검

2026-11-02. 교육기관 최종 제출은 GitHub에 산출물을 올리는 것으로 사용자와 확인했다. 별도 업로드 포털·압축 제출·추가 스크린샷 요건을 임의로 만들지 않는다.

**결과:** 기본·보너스 산출물과 검수 증거는 공개 저장소의 main에 반영됐고, 제출물 점검과 평가 설명 자료 정리를 완료했다. 사용자의 설명 능력이나 교육기관의 실제 평가 통과를 대신 선언하지 않는다.

- 저장소: https://github.com/yerihanview/B2-1
- 기본 브랜치: main, 공개 범위 public, archived 아님(API 읽기 확인).
- 구현 승인·병합: [PR #1](https://github.com/yerihanview/B2-1/pull/1), 병합 커밋 `b6e36138de804ee1424553ec178249f895e58c91`.
- 앱·테스트 최종 소스: `0505fbf218b9605e95ad7657d9978e4ca79f7afe`. 이후 PR 보고서·병합·제출 문서 정리는 앱·테스트·개발 스크립트를 바꾸지 않았다.

## 제출 항목 확인

| 항목 | 확인 결과 | 위치 |
|---|---|---|
| 실행 가능한 Python CLI | 기본 기능과 보너스 포함, 외부 패키지 설치 불필요 | budget_app/ |
| 필수 README | 실행·저장 위치/형식·명령 예시·CSV 스키마·삭제/재수입 주의 포함 | [README](../../README.md) |
| 기능·데이터 계약 | 기본 명령, 오류 코드, 무결성·잠금, B01~B04 정의 | [spec](../spec.md) |
| 모듈·클래스·저장 설계 | 책임 경계와 ADR, 원자성의 한계 | [design](../design.md) |
| 평가 대응 | A01~A16, T01~T27, B01~B04, P01 및 제출 README 대응 | [acceptance](../acceptance.md) |
| 자동 검수 | Python 3.10/3.12 각각 117개 통과, 독립 CLI 50개 포함 | [최종 검증 요약](../../evidence/toomuch/final-verification.txt) |
| 원격 CI | PR #1 마지막 구현·보고서 head의 Python 3.10 check SUCCESS | [Actions](https://github.com/yerihanview/B2-1/actions/runs/41401251160/job/125133345229) |
| CLI·파일·CSV 증거 | 새 프로세스 재시작·오류·혼합 CSV 롤백 포함 | [최종 검토](final-review.md), evidence/ |
| 보너스 증거 | 백업 원본/manifest/가상 복구, 월말·중복 방지, 정렬, 장애 주입 | [보너스 실행](../../evidence/toomuch/bonus-demo.txt), tests/ |
| 10만 건 | 소스 SHA·seed·N/K·시간·메모리와 동작 검증 기록 | [측정 원본](../../evidence/toomuch/bonus-benchmark.jsonl), [분석](validation-results.md) |
| 평가 설명 | 실제 코드 위치·동작·선택 이유·한계·연습 질문 | [evaluation-guide](../evaluation-guide.md) |
| 저장소 내용 | 실사용 data/·ZIP 백업·첨부 공식 원문 파일을 추적하지 않음 | git ls-files 점검 |
| 문서 연결 | 추적된 Markdown의 로컬 파일 링크 대상을 확인 | [제출물 점검 로그](../../evidence/toomuch/submission-audit.txt) |

## 깨끗한 제출 파일로 실행 확인

병합된 main `b6e3613`을 git archive로 내보내 별도 임시 폴더에 풀었다. Git 메타데이터나 기존 작업 폴더의 파일을 복사하지 않았다. Python `-E`로 PYTHON 환경변수의 영향을 제외하고, budget_app이 해당 임시 폴더에서 로드됐음을 확인했다. 앱 실행에는 Git이 필요 없으며, SHA를 기록하는 개발용 smoke/benchmark 스크립트는 Git 체크아웃에서 사용한다.

Python 3.10.22와 3.12.14 각각에서 도움말의 저장소 무접근, 카테고리 선등록, 거래 추가, 예산·요약 경고, CSV export, 반복 규칙 등록·윤년 적용·재실행 skip, ZIP 원본/manifest 대조, 입력 오류의 원본 보존을 확인했다. 외부 pip 설치는 하지 않았다. 실제 명령과 종료 코드는 [로그](../../evidence/toomuch/submission-audit.txt)에 있다.

이는 이미 통과한 전체 117개를 새로 실행한 것으로 표기하지 않는다. 제출 파일만으로 동작하는지 확인하는 별도 대표 검증이다. 앱·테스트 소스가 바뀌지 않아 기존 회귀·성능 측정을 불필요하게 반복하지 않았다.

## 제출과 별개인 사항

- 환경 게시 오류는 사용자가 신고 완료했다. 현재 제공 정보로 게시 성공·원인 해결은 확인하지 못했다. GitHub의 코드·증거 보존과는 별개다.
- main 보호 규칙 조회는 integration 권한 제한으로 확인하지 못했고 설정을 변경하지 않았다. 필수 CI·PR 승인 강제는 추가 운영 보강 사항이다.
- 평가에서 직접 설명하는 것은 사용자의 학습 확인 영역이다. 이 자료 준비나 자동 테스트 통과를 이해도 평가 통과로 바꾸지 않는다.
- 추가 개발·제출 단계는 현재 사용자와 확인한 미션 범위에서 필요하지 않다. 새 요구사항이나 실제 결함이 발견되면 별도 작업으로 기록한다.
