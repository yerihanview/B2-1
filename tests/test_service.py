"""Domain behavior checked without filesystem implementation assumptions."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile

from budget_app.cli import main
from budget_app.repository import Repository
from typing import get_type_hints
from unittest.mock import patch
from uuid import UUID

from budget_app.errors import InputError, StorageError
from budget_app.service import Service, allocate_id


class MemoryRepository:
    def __init__(self):
        self.categories = {"food", "salary", "transport"}
        self.budgets = {}
        self.rows = []
        self.fail = False

    def iter_transactions(self):
        yield from self.rows

    def write_transactions(self, rows):
        staged = list(rows)
        if self.fail:
            raise StorageError("test failure")
        self.rows = staged

    def write_categories(self, names):
        staged = set(names)
        if self.fail:
            raise StorageError("test failure")
        self.categories = staged

    def write_budgets(self, budgets):
        if self.fail:
            raise StorageError("test failure")
        self.budgets = dict(budgets)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryRepository()
        self.service = Service(self.repo)

    def add(self, **changes):
        fields = {"date": "2024-01-15", "type": "expense", "category": "food", "amount": "100", "memo": "점심", "tags": "meal"}
        fields.update(changes)
        return self.service.add(**fields)

    def test_add_validates_before_writing(self):
        for changes in [{"category": "missing"}, {"amount": "0"}, {"date": "2024-13-01"}, {"tags": "a,,b"}, {"id": "TX-custom"}]:
            with self.subTest(changes=changes), self.assertRaises(InputError):
                self.add(**changes)
            self.assertEqual(self.repo.rows, [])
        transaction = self.add(tags="meal,meal, work")
        self.assertEqual(transaction.tags, ("meal", "work"))
        self.assertEqual(self.repo.rows, [transaction])

    def test_latest_date_then_reverse_file_position(self):
        old = self.add(date="2023-12-31")
        first = self.add(date="2024-02-01", memo="first")
        last = self.add(date="2024-02-01", memo="last")
        self.assertEqual(self.service.select(limit=2), [last, first])
        self.assertNotIn(old, self.service.select(limit=2))
        for limit in [0, 1001, True]:
            with self.assertRaises(InputError):
                self.service.select(limit=limit)

    def test_search_and_boundaries_and_exact_tag(self):
        a = self.add(date="2024-01-01", tags="meal,weekday")
        self.add(date="2024-01-31", tags="meal")
        self.add(date="2024-02-01", tags="meal")
        self.add(date="2024-01-01", type="income", category="salary")
        self.assertEqual(self.service.select(from_date="2024-01-01", to_date="2024-01-31", category="food", type="expense", q="점", tag="weekday"), [a])
        self.assertEqual(self.service.select(tag="week"), [])
        self.assertEqual(self.service.select(category="unknown"), [])
        self.assertEqual(len(self.service.select(q="")), 4)
        with self.assertRaises(InputError):
            self.service.select(from_date="2024-02-01", to_date="2024-01-01")

    def test_update_keeps_position_and_id_and_clears_optional_fields(self):
        a = self.add()
        b = self.add()
        updated = self.service.update(a.id, amount="200", memo="", tags="")
        self.assertEqual(updated.id, a.id)
        self.assertEqual(self.repo.rows, [updated, b])
        self.assertEqual((updated.memo, updated.tags, updated.amount), ("", (), 200))
        snapshot = list(self.repo.rows)
        for id, changes in [(a.id, {}), (a.id, {"amount": "0"}), ("TX-missing", {"memo": "x"})]:
            with self.assertRaises(InputError):
                self.service.update(id, **changes)
            self.assertEqual(self.repo.rows, snapshot)

    def test_delete_missing_and_other_records_preserved(self):
        a, b = self.add(), self.add()
        self.service.delete(a.id)
        self.assertEqual(self.repo.rows, [b])
        with self.assertRaises(InputError):
            self.service.delete(a.id)
        self.assertEqual(self.repo.rows, [b])

    def test_used_category_cannot_be_removed_and_count_reported(self):
        self.add()
        self.add()
        with self.assertRaisesRegex(InputError, "2건"):
            self.service.remove_category("food")
        self.assertIn("food", self.repo.categories)
        self.service.add_category(" other ")
        self.service.remove_category("other")
        with self.assertRaises(InputError):
            self.service.add_category("food")

    def test_summary_only_expense_top_tie_and_budget(self):
        self.add(amount="100")
        self.add(category="transport", amount="100")
        self.add(category="salary", amount="300", type="income")
        self.service.set_budget("2024-01", "200")
        summary = self.service.summary("2024-01")
        self.assertEqual((summary["income"], summary["expense"], summary["balance"]), (300, 200, 100))
        self.assertEqual(summary["top"], [("food", 100), ("transport", 100)])
        self.assertEqual(summary["usage"], "100.0")
        self.assertFalse(summary["exceeded"])
        self.service.set_budget("2024-01", "199")
        self.assertTrue(self.service.summary("2024-01")["exceeded"])

    def test_empty_month_with_budget_and_round_half_up(self):
        self.service.set_budget("2024-02", "2000")
        empty = self.service.summary("2024-02")
        self.assertEqual((empty["count"], empty["usage"], empty["top"]), (0, "0.0", []))
        self.add(date="2024-02-01", amount="1")
        self.assertEqual(self.service.summary("2024-02")["usage"], "0.1")
        for top in [0, 101, True]:
            with self.assertRaises(InputError):
                self.service.summary("2024-02", top=top)

    def test_failed_writes_do_not_change_state(self):
        self.add()
        snapshot = list(self.repo.rows)
        self.repo.fail = True
        with self.assertRaises(StorageError):
            self.service.update(snapshot[0].id, memo="new")
        self.assertEqual(self.repo.rows, snapshot)
        with self.assertRaises(StorageError):
            self.service.add_category("new")
        self.assertNotIn("new", self.repo.categories)
        with self.assertRaises(StorageError):
            self.service.set_budget("2024-01", "100")
        self.assertEqual(self.repo.budgets, {})

    def test_public_type_hints_resolve(self):
        for method in (Service.__init__, Service.add, Service.update, Service.delete,
                       Service.select, Service.summary, Service.set_budget,
                       Service.add_category, Service.remove_category):
            with self.subTest(method=method.__name__):
                self.assertIn("return", get_type_hints(method))

    def test_add_regenerates_duplicate_uuid(self):
        first = UUID("00000000-0000-4000-8000-000000000001")
        second = UUID("00000000-0000-4000-8000-000000000002")
        with patch("budget_app.service.uuid4", return_value=first):
            original = self.add()
        with patch("budget_app.service.uuid4", side_effect=[first, second]) as generator:
            added = self.add()
        self.assertEqual(generator.call_count, 2)
        self.assertEqual(added.id, "TX-" + second.hex)
        self.assertEqual(self.repo.rows, [original, added])

    def test_uuid_exhaustion_preserves_transactions(self):
        fixed = UUID("00000000-0000-4000-8000-000000000001")
        with patch("budget_app.service.uuid4", return_value=fixed):
            original = self.add()
        with patch("budget_app.service.uuid4", return_value=fixed) as generator:
            with self.assertRaises(StorageError) as failure:
                self.add()
        self.assertEqual(failure.exception.code, 3)
        self.assertEqual(generator.call_count, 10)
        self.assertEqual(self.repo.rows, [original])

    def test_allocate_id_reserves_new_values_in_shared_set(self):
        fixed = UUID("00000000-0000-4000-8000-000000000001")
        used = set()
        with patch("budget_app.service.uuid4", return_value=fixed):
            generated = allocate_id(used)
            self.assertEqual(used, {generated})
            with self.assertRaises(StorageError):
                allocate_id(used)

    def test_large_summary_totals_preserve_exact_values_and_budget_usage(self):
        amount = '9' * 4300
        first = self.add(amount=amount)
        self.add(amount=amount)
        expected = first.amount * 2
        result = self.service.summary('2024-01')
        self.assertEqual(result['expense'], expected)
        self.service.set_budget('2024-01', amount)
        result = self.service.summary('2024-01')
        self.assertEqual(result['expense'], expected)
        self.assertEqual(result['usage'], '200.0')

    def test_large_cli_summary_outputs_exact_totals_and_top_without_digit_limit(self):
        amount = '9' * 4300
        doubled = '1' + '9' * 4299 + '8'
        quadrupled = '3' + '9' * 4299 + '6'
        with tempfile.TemporaryDirectory() as root:
            repo = Repository(Path(root) / 'data')
            with repo.session():
                service = Service(repo)
                service.add_category('food')
                for kind, count in [('expense', 2), ('income', 4)]:
                    for _ in range(count):
                        service.add(date='2024-01-15', type=kind, category='food', amount=amount)
            original = repo.path('transactions.jsonl').read_bytes()
            for budget in (False, True):
                with self.subTest(budget=budget):
                    if budget:
                        with repo.session():
                            Service(repo).set_budget('2024-01', amount)
                    output = StringIO()
                    with redirect_stdout(output):
                        result = main(['--data-dir', str(repo.directory), 'summary', '--month', '2024-01'])
                    self.assertEqual(result, 0)
                    self.assertIn('총 수입: ' + quadrupled + '원', output.getvalue())
                    self.assertIn('총 지출: ' + doubled + '원', output.getvalue())
                    self.assertIn('잔액: ' + doubled + '원', output.getvalue())
                    self.assertIn('1) food ' + doubled + '원', output.getvalue())
                    if budget:
                        self.assertIn('사용률 200.0%', output.getvalue())
                    self.assertEqual(repo.path('transactions.jsonl').read_bytes(), original)
                    self.assertFalse(repo.lock_path.exists())


if __name__ == "__main__":
    unittest.main()
