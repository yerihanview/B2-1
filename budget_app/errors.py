"""User-facing errors and stable CLI exit codes."""


class AppError(Exception):
    """A failure that can be shown without a Python traceback."""

    code = 2

    def __init__(
        self,
        message: str,
        hint: str = "입력과 도움말(--help)을 확인하세요.",
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        if code is not None:
            self.code = code


class InputError(AppError):
    """Input does not satisfy the command contract."""

    code = 2


class StorageError(AppError):
    """A file is inaccessible or its stored contents are corrupt."""

    code = 3


class LockError(AppError):
    """Another command owns the data-directory lock."""

    code = 4


class DurabilityError(StorageError):
    """Replacement committed, but directory durability could not be confirmed."""
