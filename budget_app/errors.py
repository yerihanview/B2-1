"""사용자에게 표시할 오류와 CLI 종료 코드를 정의한다."""


class AppError(Exception):
    """트레이스백 없이 사용자에게 원인과 힌트를 표시할 수 있는 오류."""

    code = 2

    def __init__(
        self,
        message: str,
        hint: str = "입력과 도움말(--help)을 확인하세요.",
        code: int | None = None,
    ) -> None:
        """오류 메시지와 해결 힌트를 저장하고 필요하면 종료 코드를 지정한다."""
        super().__init__(message)
        self.message = message
        self.hint = hint

        if code is not None:
            self.code = code


class InputError(AppError):
    """입력이 명령의 요구 조건을 만족하지 않을 때 발생하는 오류."""

    code = 2


class StorageError(AppError):
    """파일 접근 실패나 저장 데이터 손상을 나타내는 오류."""

    code = 3


class LockError(AppError):
    """다른 명령이 데이터 폴더의 잠금을 보유하고 있음을 나타내는 오류."""

    code = 4


class DurabilityError(StorageError):
    """변경은 반영됐지만 내구성 또는 정리 작업을 확인하지 못한 오류."""
