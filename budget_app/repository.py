"""JSONL 파일 잠금과 검증, 원자적 저장을 담당한다."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import tempfile
from typing import Any, BinaryIO, Callable, Iterable, Iterator, Mapping, TextIO

from .errors import DurabilityError, InputError, LockError, StorageError
from .models import RecurringRule, Transaction, parse_amount, parse_month, parse_name


FILES = ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl')
OPTIONAL_FILES = ('recurring.jsonl',)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """중복 JSON 키를 거부하며 키·값 쌍을 사전으로 변환한다."""
    result: dict[str, object] = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f'중복 JSON 키: {key}')

        result[key] = value

    return result


class Repository:
    """명령 전체에 걸쳐 파일 잠금과 검증된 저장 상태를 관리한다."""

    def __init__(self, data_dir: str | Path = './data') -> None:
        """데이터 경로와 세션에서 사용할 상태를 초기화한다."""
        self.directory = Path(data_dir)
        self.categories: set[str] = set()
        self.budgets: dict[str, int] = {}
        self.recurring: dict[str, RecurringRule] = {}
        self._locked = False
        self._published = False

    @property
    def lock_path(self) -> Path:
        """데이터 폴더의 잠금 파일 경로를 반환한다."""
        return self.directory / '.budget_app.lock'

    def path(self, filename: str) -> Path:
        """데이터 폴더 안의 파일 경로를 반환한다."""
        return self.directory / filename

    @contextmanager
    def session(self) -> Iterator[Repository]:
        """잠금 획득과 전건 검증 후 명령을 실행하고 자신이 만든 잠금만 해제한다."""
        self.directory.mkdir(parents=True, exist_ok=True)

        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LockError('다른 명령의 잠금이 존재합니다.',
                            '실행 중인 프로세스를 확인하세요. stale lock은 확인 후 수동 처리하세요.') from exc

        identity = os.fstat(fd)
        self._locked = True
        self._published = False

        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(str(os.getpid()) + '\n')

            self.validate()

            for filename in FILES:
                target = self.path(filename)

                if not target.exists():
                    self.atomic_write(target, lambda handle: None, overwrite=False)

            yield self
        finally:
            self._locked = False

            try:
                current = self.lock_path.lstat()

                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    self.lock_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                if self._published:
                    raise DurabilityError('변경 반영됨, 잠금 정리 실패',
                                          '잠금과 데이터를 확인하세요. 자동 재실행하지 마세요.') from exc

                raise StorageError('잠금 정리 실패', '실행 상태를 확인한 후 잠금을 수동 확인하세요.') from exc

    def _require_lock(self) -> None:
        """저장소 작업에 필요한 잠금 세션이 활성화됐는지 확인한다."""
        if not self._locked:
            raise RuntimeError('Repository operations require a session')

    def _records(self, filename: str) -> Iterator[dict[str, object]]:
        """JSONL을 한 행씩 읽고 구문·인코딩 오류에 파일과 행 번호를 덧붙인다."""
        target = self.path(filename)

        if not target.exists():
            return

        try:
            with target.open(encoding='utf-8') as handle:
                for number, line in enumerate(handle, 1):
                    try:
                        record = json.loads(line, object_pairs_hook=_unique_object)

                        if not isinstance(record, dict):
                            raise ValueError('JSON 객체가 아닙니다.')
                    except (ValueError, TypeError, RecursionError) as exc:
                        raise StorageError(f'{filename} {number}행 손상: {exc}',
                                           '원본을 보존하고 올바른 JSONL 데이터를 확인하세요.') from exc

                    yield record
        except UnicodeError as exc:
            raise StorageError(f'{filename} UTF-8 오류', '파일 인코딩을 확인하세요.') from exc

    def validate(self) -> None:
        """파일을 생성하거나 변경하기 전에 기존 데이터 전체의 정합성을 검증한다."""
        self._require_lock()
        categories: set[str] = set()
        budgets: dict[str, int] = {}

        try:
            for record in self._records('categories.jsonl'):
                if set(record) != {'name'}:
                    raise InputError('category 필드 불일치')

                name = record['name']

                if not isinstance(name, str) or parse_name(name) != name or name in categories:
                    raise InputError('중복 또는 비정규 category')

                categories.add(name)

            for record in self._records('budgets.jsonl'):
                if set(record) != {'month', 'amount'}:
                    raise InputError('budget 필드 불일치')

                month = parse_month(record['month'])
                amount = record['amount']

                if type(amount) is not int or month in budgets:
                    raise InputError('중복 month 또는 잘못된 budget amount')

                budgets[month] = parse_amount(amount)

            recurring: dict[str, RecurringRule] = {}

            for record in self._records('recurring.jsonl'):
                rule = RecurringRule.from_dict(record, stored=True)

                if rule.id in recurring:
                    raise InputError('중복 반복 규칙 id')

                if rule.category not in categories:
                    raise InputError('반복 규칙의 미등록 category 참조')

                recurring[rule.id] = rule

            ids: set[str] = set()
            sources: set[tuple[str, str]] = set()

            for record in self._records('transactions.jsonl'):
                transaction = Transaction.from_dict(record, stored=True)

                if transaction.id in ids:
                    raise InputError('중복 거래 id')

                if transaction.category not in categories:
                    raise InputError('미등록 category 참조')

                ids.add(transaction.id)

                if transaction.recurring_id is not None:
                    source = (transaction.recurring_id, parse_month(transaction.recurring_month))

                    if source in sources:
                        raise InputError('중복 반복 거래 출처')

                    sources.add(source)
        except InputError as exc:
            raise StorageError(f'데이터 손상: {exc}', '원본을 보존하고 데이터 형식과 참조를 확인하세요.') from exc

        self.categories = categories
        self.budgets = budgets
        self.recurring = recurring

    def iter_transactions(self) -> Iterator[Transaction]:
        """잠금 세션에서 저장된 거래를 한 건씩 검증하며 반환한다."""
        self._require_lock()

        for record in self._records('transactions.jsonl'):
            try:
                yield Transaction.from_dict(record, stored=True)
            except InputError as exc:
                raise StorageError(f'거래 데이터 손상: {exc}', '원본 파일을 확인하세요.') from exc

    @staticmethod
    def _write_record(handle: TextIO, record: Mapping[str, object]) -> None:
        """사전 한 개를 UTF-8 JSONL 한 행으로 기록한다."""
        handle.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')

    def write_transactions(self, transactions: Iterable[Transaction]) -> None:
        """거래 목록을 원자적으로 저장한다."""
        self._require_lock()

        def write(handle: TextIO) -> None:
            """검증된 항목을 JSONL 형식으로 임시 출력에 기록한다."""
            for transaction in transactions:
                self._write_record(handle, transaction.to_dict())

        self.atomic_write(self.path('transactions.jsonl'), write)

    def write_categories(self, categories: Iterable[str]) -> None:
        """카테고리를 이름순으로 원자적으로 저장한다."""
        self._require_lock()

        def write(handle: TextIO) -> None:
            """검증된 항목을 JSONL 형식으로 임시 출력에 기록한다."""
            for name in sorted(categories):
                self._write_record(handle, {'name': name})

        self.atomic_write(self.path('categories.jsonl'), write)

    def write_budgets(self, budgets: Mapping[str, int]) -> None:
        """월별 예산을 월순으로 원자적으로 저장한다."""
        self._require_lock()

        def write(handle: TextIO) -> None:
            """검증된 항목을 JSONL 형식으로 임시 출력에 기록한다."""
            for month, amount in sorted(budgets.items()):
                self._write_record(handle, {'month': month, 'amount': amount})

        self.atomic_write(self.path('budgets.jsonl'), write)

    def write_recurring(self, rules: Iterable[RecurringRule]) -> None:
        """반복 규칙 목록을 원자적으로 저장한다."""
        self._require_lock()

        def write(handle: TextIO) -> None:
            """검증된 항목을 JSONL 형식으로 임시 출력에 기록한다."""
            for rule in rules:
                self._write_record(handle, rule.to_dict())

        self.atomic_write(self.path('recurring.jsonl'), write)

    def storage_filenames(self) -> tuple[str, ...]:
        """필수 파일과 현재 존재하는 선택 저장 파일의 이름을 반환한다."""
        self._require_lock()

        return FILES + tuple(name for name in OPTIONAL_FILES if self.path(name).exists())

    def check_export_path(self, target: Path, overwrite: bool) -> None:
        """내부 데이터의 덮어쓰기와 경로 별칭, 기존 출력 파일 충돌을 차단한다."""
        self._require_lock()
        protected = [self.path(name) for name in FILES + OPTIONAL_FILES] + [self.lock_path]

        try:
            resolved = target.resolve()
            protected_resolved = [internal.resolve() for internal in protected]
        except RuntimeError as exc:
            raise StorageError('경로의 symlink 순환을 해석할 수 없습니다.', '순환 없는 출력 경로를 지정하세요.') from exc

        for internal, internal_resolved in zip(protected, protected_resolved):
            if resolved == internal_resolved:
                raise InputError('내부 데이터/잠금 파일로 export할 수 없습니다.', '별도의 CSV 경로를 지정하세요.')

            if target.exists() and internal.exists() and os.path.samefile(target, internal):
                raise InputError('내부 파일과 같은 inode입니다.', '별도의 CSV 경로를 지정하세요.')

        if not target.parent.is_dir():
            raise InputError('출력 부모 디렉터리가 없습니다.', '기존 디렉터리에 CSV를 저장하세요.')

        if (target.exists() or target.is_symlink()) and not overwrite:
            raise InputError('출력 파일이 이미 존재합니다.', '새 경로 또는 --overwrite를 사용하세요.')

    def _sync_directory(self, directory: Path) -> None:
        """파일 반영 후 디렉터리 변경의 내구성을 확인하고 파일 기술자를 닫는다."""
        fd = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))

        try:
            try:
                os.fsync(fd)
            except OSError as exc:
                if exc.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP):
                    raise
        finally:
            os.close(fd)

    def atomic_write(self, target: Path, writer: Callable[[TextIO], None], *,
                     overwrite: bool = True, export: bool = False) -> None:
        """텍스트 작성 콜백의 결과를 임시 파일을 거쳐 원자적으로 반영한다."""
        self._atomic_write(target, writer, overwrite=overwrite, export=export)

    def atomic_binary_write(self, target: Path, writer: Callable[[BinaryIO], None], *,
                            overwrite: bool = False) -> None:
        """바이너리 작성 콜백의 결과를 외부 출력 경로에 원자적으로 반영한다."""
        self._atomic_write(target, writer, overwrite=overwrite, export=True, binary=True)

    def _atomic_write(self, target: Path, writer: Callable[[Any], None], *,
                      overwrite: bool = True, export: bool = False, binary: bool = False) -> None:
        """임시 파일 기록·동기화·발행을 수행하고 실패 시 반영 여부를 구분한다."""
        self._require_lock()

        if export:
            self.check_export_path(target, overwrite)

        fd, tempname = tempfile.mkstemp(prefix='.budget-', suffix='.tmp', dir=target.parent)
        temporary = Path(tempname)
        published = False

        try:
            handle = (os.fdopen(fd, 'w+b') if binary else
                      os.fdopen(fd, 'w', encoding='utf-8', newline=''))

            with handle:
                writer(handle)
                handle.flush()
                os.fsync(handle.fileno())

            if export:
                self.check_export_path(target, overwrite)

            if overwrite:
                os.replace(temporary, target)
            else:
                # 배타적 링크로 발행해 다른 프로세스가 먼저 만든 출력 파일을 덮어쓰지 않는다.
                try:
                    os.link(temporary, target)
                except FileExistsError as exc:
                    raise InputError('출력 파일이 이미 존재합니다.', '새 경로를 지정하세요.') from exc

                published = True
                self._published = True
                temporary.unlink()

            published = True
            self._published = True
            self._sync_directory(target.parent)
        except OSError as exc:
            if published:
                raise DurabilityError('변경 반영됨, 내구성 확인 실패',
                                      '파일을 확인하세요. 자동 재실행하지 마세요.') from exc

            raise
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                if published:
                    raise DurabilityError('변경 반영됨, 임시 파일 정리 실패',
                                          '출력과 임시 파일을 확인하세요. 자동 재실행하지 마세요.') from exc

                raise

    @contextmanager
    def staging(self) -> Iterator[TextIO]:
        """CSV 전건 검증에 사용할 디스크 임시 파일을 만들고 항상 정리한다."""
        self._require_lock()

        with tempfile.TemporaryFile(mode='w+', encoding='utf-8', newline='', dir=self.directory) as handle:
            yield handle
