"""Locked JSONL storage and atomic single-file publication."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable, Iterator, Mapping, TextIO

from .errors import DurabilityError, InputError, LockError, StorageError
from .models import Transaction, parse_amount, parse_month, parse_name


FILES = ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl')


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'중복 JSON 키: {key}')
        result[key] = value
    return result


class Repository:
    """Use a session for an entire command, including interactive input."""

    def __init__(self, data_dir: str | Path = './data') -> None:
        self.directory = Path(data_dir)
        self.categories: set[str] = set()
        self.budgets: dict[str, int] = {}
        self._locked = False
        self._published = False

    @property
    def lock_path(self) -> Path:
        return self.directory / '.budget_app.lock'

    def path(self, filename: str) -> Path:
        return self.directory / filename

    @contextmanager
    def session(self) -> Iterator[Repository]:
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
        if not self._locked:
            raise RuntimeError('Repository operations require a session')

    def _records(self, filename: str) -> Iterator[dict[str, object]]:
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
        """Validate all existing files before creating or changing any file."""
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
            ids: set[str] = set()
            for record in self._records('transactions.jsonl'):
                transaction = Transaction.from_dict(record, stored=True)
                if transaction.id in ids:
                    raise InputError('중복 거래 id')
                if transaction.category not in categories:
                    raise InputError('미등록 category 참조')
                ids.add(transaction.id)
        except InputError as exc:
            raise StorageError(f'데이터 손상: {exc}', '원본을 보존하고 데이터 형식과 참조를 확인하세요.') from exc
        self.categories = categories
        self.budgets = budgets

    def iter_transactions(self) -> Iterator[Transaction]:
        self._require_lock()
        for record in self._records('transactions.jsonl'):
            try:
                yield Transaction.from_dict(record, stored=True)
            except InputError as exc:
                raise StorageError(f'거래 데이터 손상: {exc}', '원본 파일을 확인하세요.') from exc

    @staticmethod
    def _write_record(handle: TextIO, record: Mapping[str, object]) -> None:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')

    def write_transactions(self, transactions: Iterable[Transaction]) -> None:
        self._require_lock()
        def write(handle: TextIO) -> None:
            for transaction in transactions:
                self._write_record(handle, transaction.to_dict())
        self.atomic_write(self.path('transactions.jsonl'), write)

    def write_categories(self, categories: Iterable[str]) -> None:
        self._require_lock()
        def write(handle: TextIO) -> None:
            for name in sorted(categories):
                self._write_record(handle, {'name': name})
        self.atomic_write(self.path('categories.jsonl'), write)

    def write_budgets(self, budgets: Mapping[str, int]) -> None:
        self._require_lock()
        def write(handle: TextIO) -> None:
            for month, amount in sorted(budgets.items()):
                self._write_record(handle, {'month': month, 'amount': amount})
        self.atomic_write(self.path('budgets.jsonl'), write)

    def check_export_path(self, target: Path, overwrite: bool) -> None:
        self._require_lock()
        protected = [self.path(name) for name in FILES] + [self.lock_path]
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
        """Only the publication step changes the target; cleanup is unconditional."""
        self._require_lock()
        if export:
            self.check_export_path(target, overwrite)
        fd, tempname = tempfile.mkstemp(prefix='.budget-', suffix='.tmp', dir=target.parent)
        temporary = Path(tempname)
        published = False
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
                writer(handle)
                handle.flush()
                os.fsync(handle.fileno())
            if export:
                self.check_export_path(target, overwrite)
            if overwrite:
                os.replace(temporary, target)
            else:
                # An exclusive link publishes atomically without clobbering a race-created target.
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
        """An unlinked disk staging file, always cleaned when CSV validation fails."""
        self._require_lock()
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8', newline='', dir=self.directory) as handle:
            yield handle
