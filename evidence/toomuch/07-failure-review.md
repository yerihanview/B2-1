# 개발 중 결함·재검증 요약

최종 재검증 소스 SHA는 `04-tests-python312.txt`, `04-tests-python310.txt`에 기록한다. 임시 가상 데이터로 재현했다. 동일 결함 자동 수정 3회 상한을 넘긴 사례는 없으며 아래 재현 결함은 첫 수정 후 재검증을 통과했다. 원본 첨부 자료·실제 재무 데이터는 포함하지 않는다.

| 재현 결함 | 수정·회귀 근거 |
|---|---|
| UUID4 고정 주입 시 중복 ID가 유입되어 다음 읽기가 손상 오류 | 기존/배치 ID 집합과 최대 10회 재생성, 고갈 시 코드 3 및 원본 보존. test_service의 duplicate_uuid/uuid_exhaustion, test_csv_io의 배치 충돌 검수 |
| 새 export link 발행 후 temp unlink 실패를 교체 전 오류처럼 처리 | 발행 직후 상태 기록. test_T26_post_exclusive_link_cleanup_failure_is_committed |
| 깊은 JSON에 RecursionError traceback | 손상 코드 3. test_T22_excessively_nested_json_is_storage_error_without_traceback |
| 순환 symlink export 대상에서 RuntimeError traceback | 경로 확인 실패를 파일 오류 3으로 변환. test_T24_export_symlink_loop_is_storage_error |
| 131072자 초과 유효 태그 CSV가 파서 기본 상한에 걸림 | 파싱 동안 field_size_limit을 플랫폼 한계로 확장하고 finally 복원. 독립 test_T09_valid_tags_are_not_limited_by_csv_default_field_size를 실패→수정→통과로 검수 |
| 반영 뒤 lock cleanup 실패의 반영 상태가 불분명 | 반영됨과 정리 실패를 함께 안내. test_T26_lock_cleanup_after_commit_reports_change |

독립 검증자는 명세에서 CLI 입력·기대값을 먼저 작성하고 구현을 수정하지 않았다. 별도 읽기 전용 안전성 검토자가 결함을 재현하고 수정 후 직접 재검증했다. 통합 담당은 최종 SHA에서 양 Python 버전 전체 회귀와 실제 CLI demo를 다시 실행했다. 원격 Actions 통과나 사람의 최종 승인을 대신하지 않는다.

## 최종 PR 검토 추가 회귀

4300자리 지출 2건의 합계 summary가 정수 문자열 변환 제한으로 traceback을 내는 P2를 예산 유무 양쪽에서 독립 CLI로 재현했다. 입력상한 신설/전역 제한 해제 없이 Decimal의 정확한 출력·자리수 계산으로 1차 수정했다. 최신 양버전 117개 회귀와 별도 읽기 전용 재검증은 final-verification.txt 및 docs/toomuch/final-review.md에 기록한다.
