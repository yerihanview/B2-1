"""명령 경계의 예외를 사용자 안내와 일관된 종료 코드로 변환한다."""
from __future__ import annotations

from functools import wraps
import sys
from typing import Callable, ParamSpec

from .errors import AppError

P = ParamSpec('P')


def user_errors(function: Callable[P, int]) -> Callable[P, int]:
    """함수 메타데이터를 유지하면서 사용자용 예외 처리를 적용한다."""
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> int:
        """업무·입출력·입력 중단 예외를 안내 메시지와 종료 코드로 변환한다."""
        try:
            return function(*args, **kwargs)
        except AppError as exc:
            print(f'[오류] {exc}\n[힌트] {exc.hint}', file=sys.stderr)

            return exc.code
        except (EOFError, KeyboardInterrupt):
            print('[오류] 입력이 중단되었습니다.\n[힌트] 필수 입력을 확인하고 다시 실행하세요.', file=sys.stderr)

            return 2
        except (OSError, UnicodeError) as exc:
            print(f'[오류] 파일 처리 실패: {exc}\n[힌트] 경로·권한·인코딩·디스크 여유를 확인하세요.', file=sys.stderr)

            return 3

    return wrapped
