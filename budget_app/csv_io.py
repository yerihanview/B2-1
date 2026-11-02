"""CSV conversion; Repository owns publication and staging files."""
from __future__ import annotations

import csv
from contextlib import contextmanager
from itertools import chain
import json
from pathlib import Path
import sys
from typing import Iterator, TextIO

from .errors import InputError, StorageError
from .models import Transaction
from .repository import Repository
from .service import allocate_id

HEADER = ['date', 'type', 'category', 'amount', 'memo', 'tags']


@contextmanager
def _csv_field_limit() -> Iterator[None]:
    previous = csv.field_size_limit()
    try:
        csv.field_size_limit(sys.maxsize)
        yield
    finally:
        csv.field_size_limit(previous)


def import_csv(repository: Repository, source: str | Path) -> int:
    """Validate all rows to disk and publish the transaction file once."""
    errors: list[str] = []
    count = 0
    used_ids = {transaction.id for transaction in repository.iter_transactions()}
    with repository.staging() as stage, _csv_field_limit():
        try:
            with Path(source).open(encoding='utf-8', newline='') as handle:
                reader = csv.reader(handle, strict=True)
                try:
                    header = next(reader)
                except StopIteration as exc:
                    raise InputError('1행: CSV 헤더가 없습니다.', '정해진 헤더를 추가하세요.') from exc
                except csv.Error as exc:
                    raise InputError(f'1행: CSV 구문 오류: {exc}', 'CSV quoting을 확인하세요.') from exc
                if header != HEADER:
                    raise InputError('1행: CSV 헤더가 스키마와 다릅니다.', ','.join(HEADER))
                while True:
                    line = reader.line_num + 1
                    try:
                        row = next(reader)
                    except StopIteration:
                        break
                    except csv.Error as exc:
                        errors.append(f'{line}행: CSV 구문 오류: {exc}')
                        break
                    try:
                        if len(row) != len(HEADER):
                            raise InputError('컬럼 수가 6개가 아닙니다.')
                        record = dict(zip(HEADER, row))
                        record['id'] = allocate_id(used_ids)
                        transaction = Transaction.from_dict(record)
                        if transaction.category not in repository.categories:
                            raise InputError('미등록 category')
                        stage.write(json.dumps(transaction.to_dict(), ensure_ascii=False) + '\n')
                        count += 1
                    except InputError as exc:
                        if len(errors) < 20:
                            errors.append(f'{line}행: {exc}')
        except UnicodeError as exc:
            raise StorageError('CSV UTF-8 오류: 전체 미반영', 'UTF-8(BOM 없음) 파일을 사용하세요.') from exc
        if errors:
            raise InputError('CSV 전체 미반영\n' + '\n'.join(errors[:20]), '오류 행을 수정한 뒤 다시 가져오세요.')
        if count:
            stage.seek(0)
            staged = (Transaction.from_dict(json.loads(line), stored=True) for line in stage)
            repository.write_transactions(chain(repository.iter_transactions(), staged))
    return count


def export_csv(repository: Repository, destination: str | Path, *,
               from_date: str, to_date: str, overwrite: bool = False) -> int:
    """Export the selected range in original file order with a fixed header."""
    count = 0
    def write(handle: TextIO) -> None:
        nonlocal count
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for transaction in repository.iter_transactions():
            day = transaction.date.isoformat()
            if from_date <= day <= to_date:
                writer.writerow([day, transaction.type, transaction.category,
                                 transaction.amount, transaction.memo, ','.join(transaction.tags)])
                count += 1
    repository.atomic_write(Path(destination), write, overwrite=overwrite, export=True)
    return count
