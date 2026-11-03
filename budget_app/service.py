"""생성자로 전달받은 저장소를 이용해 가계부 업무 규칙을 처리한다."""

from __future__ import annotations

import heapq
import calendar
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, localcontext
from itertools import chain
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import InputError, StorageError
from .models import RecurringRule, Transaction, parse_amount, parse_date, parse_month, parse_name
from .repository import Repository


def allocate_id(used: set[str], prefix: str = "TX-") -> str:
    """기존 거래와 추가 예정 거래에 없는 UUID 식별자를 할당한다."""
    for _ in range(10):
        identifier = prefix + uuid4().hex

        if identifier not in used:
            used.add(identifier)

            return identifier

    raise StorageError(
        "거래 id 생성이 반복 충돌했습니다. 전체 미반영.",
        "기존 데이터를 보존하고 UUID 생성 환경을 확인하세요.",
    )


class Service:
    """잠금과 검증을 마친 저장소 위에서 가계부 업무 규칙을 수행한다."""

    def __init__(self, repo: Repository) -> None:
        """업무 처리에 사용할 저장소를 주입받는다."""
        self.repo = repo

    def _registered(self, name: str) -> str:
        """카테고리를 정규화하고 등록 여부를 확인한다."""
        normalized = parse_name(name)

        if normalized not in self.repo.categories:
            raise InputError(f"등록되지 않은 카테고리입니다: {normalized}", "category add로 먼저 등록하세요.")

        return normalized

    def add(self, **fields: Any) -> Transaction:
        """입력 전체를 검증한 뒤 새 거래를 한 번의 원자적 저장으로 추가한다."""
        if fields.keys() - {"date", "type", "category", "amount", "memo", "tags"}:
            raise InputError("추가할 거래에 미정의 필드가 있습니다.")

        used = {row.id for row in self.repo.iter_transactions()}
        record = {"id": allocate_id(used), **fields}
        record["category"] = self._registered(fields.get("category", ""))
        transaction = Transaction.from_dict(record)
        self.repo.write_transactions(chain(self.repo.iter_transactions(), (transaction,)))

        return transaction

    def update(self, id: str, **fields: Any) -> Transaction:
        """식별자와 원본 순서를 유지하면서 지정한 거래 필드만 수정한다."""
        allowed = {"date", "type", "category", "amount", "memo", "tags"}

        if not fields or fields.keys() - allowed:
            raise InputError("변경할 필드를 한 개 이상 지정해야 합니다.")

        original = next((row for row in self.repo.iter_transactions() if row.id == id), None)

        if original is None:
            raise InputError(f"없는 거래 id입니다: {id}", "list로 거래 id를 확인하세요.")

        merged = original.to_dict()
        merged.update(fields)
        merged["category"] = self._registered(merged["category"])
        updated = Transaction.from_dict(merged)
        self.repo.write_transactions(updated if row.id == id else row for row in self.repo.iter_transactions())

        return updated

    def delete(self, id: str) -> None:
        """지정한 거래를 삭제하고 다른 거래는 그대로 유지한다."""
        if not any(row.id == id for row in self.repo.iter_transactions()):
            raise InputError(f"없는 거래 id입니다: {id}", "list로 거래 id를 확인하세요.")

        self.repo.write_transactions(row for row in self.repo.iter_transactions() if row.id != id)

    def add_category(self, name: str) -> str:
        """중복 없는 정규화된 카테고리를 등록한다."""
        name = parse_name(name)

        if name in self.repo.categories:
            raise InputError(f"이미 있는 카테고리입니다: {name}")

        categories = self.repo.categories | {name}
        self.repo.write_categories(sorted(categories))
        self.repo.categories = categories

        return name

    def remove_category(self, name: str) -> None:
        """거래나 반복 규칙이 참조하지 않는 카테고리만 삭제한다."""
        name = self._registered(name)
        count = sum(1 for row in self.repo.iter_transactions() if row.category == name)
        rule_count = sum(1 for rule in getattr(self.repo, "recurring", {}).values() if rule.category == name)

        if count or rule_count:
            raise InputError(f"사용 중인 카테고리입니다: {name} (거래 {count}건, 반복 규칙 {rule_count}건)",
                             "해당 거래와 반복 규칙을 수정하거나 삭제한 후 다시 시도하세요.")

        categories = self.repo.categories - {name}
        self.repo.write_categories(sorted(categories))
        self.repo.categories = categories

    def set_budget(self, month: str, amount: str | int) -> None:
        """해당 월의 양의 정수 예산을 등록하거나 갱신한다."""
        month = parse_month(month)
        budgets = dict(self.repo.budgets)
        budgets[month] = parse_amount(amount)
        self.repo.write_budgets(budgets)
        self.repo.budgets = budgets

    def add_recurring(self, day: str | int, type: str, category: str,
                      amount: str | int, memo: str = "", tags: str = "") -> RecurringRule:
        """거래를 자동 생성하지 않고 월별 반복 규칙만 등록한다."""
        category = self._registered(category)
        used = set(self.repo.recurring)
        used.update(row.recurring_id for row in self.repo.iter_transactions() if row.recurring_id is not None)
        rule = RecurringRule.from_dict({
            "id": allocate_id(used, prefix="RR-"), "day": day, "type": type,
            "category": category, "amount": amount, "memo": memo, "tags": tags,
        })
        rules = dict(self.repo.recurring)
        rules[rule.id] = rule
        self.repo.write_recurring(rules.values())
        self.repo.recurring = rules

        return rule

    def list_recurring(self) -> list[RecurringRule]:
        """반복 규칙을 식별자순으로 반환한다."""
        return sorted(self.repo.recurring.values(), key=lambda rule: rule.id)

    def remove_recurring(self, id: str) -> None:
        """과거 거래는 보존하고 반복 규칙만 삭제한다."""
        if id not in self.repo.recurring:
            raise InputError(f"없는 반복 규칙 id입니다: {id}", "recurring list로 규칙 id를 확인하세요.")

        rules = dict(self.repo.recurring)
        del rules[id]
        self.repo.write_recurring(rules.values())
        self.repo.recurring = rules

    def apply_recurring(self, month: str) -> tuple[int, int]:
        """아직 생성되지 않은 규칙·월 조합을 검증한 뒤 한 번에 저장한다."""
        month = parse_month(month)

        if not self.repo.recurring:
            return 0, 0

        year, month_number = map(int, month.split("-"))
        last_day = calendar.monthrange(year, month_number)[1]
        used: set[str] = set()
        applied: set[tuple[str, str]] = set()

        for row in self.repo.iter_transactions():
            used.add(row.id)

            if row.recurring_id is not None and row.recurring_month is not None:
                applied.add((row.recurring_id, row.recurring_month))

        generated: list[Transaction] = []
        skipped = 0

        for rule in self.list_recurring():
            pair = (rule.id, month)

            if pair in applied:
                skipped += 1
                continue

            self._registered(rule.category)
            generated.append(Transaction(
                id=allocate_id(used), date=parse_date(month + f"-{min(rule.day, last_day):02d}"),
                type=rule.type, category=rule.category, amount=rule.amount,
                memo=rule.memo, tags=rule.tags, recurring_id=rule.id, recurring_month=month,
            ))
            applied.add(pair)

        if generated:
            self.repo.write_transactions(chain(self.repo.iter_transactions(), generated))

        return len(generated), skipped

    def select(
        self, limit: int = 20, from_date: str | None = None,
        to_date: str | None = None, category: str | None = None,
        type: str | None = None, q: str | None = None, tag: str | None = None,
    ) -> list[Transaction]:
        """전체 목록을 메모리에 올리지 않고 제한된 힙으로 최신 거래를 선별한다."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise InputError("limit은 1~1000이어야 합니다.")

        start = parse_date(from_date) if from_date is not None else None
        end = parse_date(to_date) if to_date is not None else None

        if start is not None and end is not None and start > end:
            raise InputError("시작 날짜가 종료 날짜보다 늦습니다.")

        category = parse_name(category) if category is not None else None
        tag = parse_name(tag, tag=True) if tag is not None else None

        if type is not None and type not in ("income", "expense"):
            raise InputError("타입은 income 또는 expense여야 합니다.")

        heap: list[tuple[Any, int, Transaction]] = []

        for position, row in enumerate(self.repo.iter_transactions()):
            if start is not None and row.date < start or end is not None and row.date > end:
                continue

            if category is not None and row.category != category or type is not None and row.type != type:
                continue

            if q is not None and q not in row.memo or tag is not None and tag not in row.tags:
                continue

            item = (row.date, position, row)

            if len(heap) < limit:
                heapq.heappush(heap, item)
            elif item[:2] > heap[0][:2]:
                heapq.heapreplace(heap, item)

        return [item[2] for item in sorted(heap, reverse=True)]

    def summary(self, month: str, top: int = 3) -> dict[str, Any]:
        """월별 수입·지출과 카테고리 합계, 소수 첫째 자리 예산 사용률을 계산한다."""
        month = parse_month(month)

        if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= 100:
            raise InputError("top은 1~100이어야 합니다.")

        income = expense = count = 0
        categories: dict[str, int] = defaultdict(int)

        for row in self.repo.iter_transactions():
            if row.date.isoformat()[:7] != month:
                continue

            count += 1

            if row.type == "income":
                income += row.amount
            else:
                expense += row.amount
                categories[row.category] += row.amount

        budget = self.repo.budgets.get(month)
        usage = None

        if budget is not None:
            with localcontext() as context:
                context.prec = max(Decimal(expense).adjusted(), Decimal(budget).adjusted()) + 21
                usage = str((Decimal(expense) * 100 / Decimal(budget)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

        return {
            "income": income, "expense": expense, "balance": income - expense,
            "top": sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:top],
            "count": count, "budget": budget, "usage": usage,
            "exceeded": budget is not None and expense > budget,
        }

    def import_csv(self, source: str | Path) -> int:
        """CSV 전건을 임시 파일에 검증한 뒤 거래 파일에 한 번만 반영한다."""
        from .csv_io import import_csv

        return import_csv(self.repo, source)

    def export_csv(self, destination: str | Path, *, from_date: str,
                   to_date: str, overwrite: bool = False) -> int:
        """선택한 기간의 거래를 원본 순서와 고정 헤더로 내보낸다."""
        from .csv_io import export_csv
        start = parse_date(from_date).isoformat()
        end = parse_date(to_date).isoformat()

        if start > end:
            raise InputError("시작 날짜가 종료 날짜보다 늦습니다.")

        return export_csv(self.repo, destination, from_date=start, to_date=end,
                          overwrite=overwrite)

    def backup(self, out_dir: str | Path | None = None) -> Path:
        """CLI에 파일 처리를 노출하지 않고 검증된 저장소의 백업을 요청한다."""
        from .backup import create_backup

        return create_backup(self.repo, out_dir)
