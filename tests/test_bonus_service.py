"""B02 recurring rules and backward-compatible transaction provenance."""

from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from budget_app.errors import InputError, StorageError
from budget_app.models import RecurringRule, Transaction
from budget_app.repository import Repository
from budget_app.service import Service


class RecurringModelTests(unittest.TestCase):
    def rule_record(self, **changes):
        return {"id": "RR-" + uuid4().hex, "day": 31, "type": "expense", "category": "food", "amount": 100, **changes}

    def transaction_record(self, **changes):
        return {"id": "TX-" + uuid4().hex, "date": "2024-01-01", "type": "expense", "category": "food", "amount": 100, **changes}

    def test_old_transactions_omit_provenance_and_new_pair_roundtrips(self):
        old = Transaction.from_dict(self.transaction_record(), stored=True)
        self.assertNotIn("recurring_id", old.to_dict())
        self.assertNotIn("recurring_month", old.to_dict())
        record = self.transaction_record(recurring_id="RR-" + uuid4().hex, recurring_month="2024-02")
        transaction = Transaction.from_dict(record, stored=True)
        self.assertEqual(transaction.to_dict()["recurring_id"], record["recurring_id"])
        self.assertEqual(Transaction.from_dict(transaction.to_dict(), stored=True), transaction)

    def test_provenance_must_be_valid_pair_and_may_differ_from_updated_date(self):
        rule_id = "RR-" + uuid4().hex
        for fields in [{"recurring_id": rule_id}, {"recurring_month": "2024-01"},
                       {"recurring_id": None, "recurring_month": None},
                       {"recurring_id": rule_id, "recurring_month": "2024-13"},
                       {"recurring_id": "RR-no", "recurring_month": "2024-01"}]:
            with self.subTest(fields=fields), self.assertRaises(InputError):
                Transaction.from_dict(self.transaction_record(**fields), stored=True)
        transaction = Transaction.from_dict(self.transaction_record(recurring_id=rule_id, recurring_month="2023-12"), stored=True)
        self.assertEqual(transaction.date, date(2024, 1, 1))

    def test_rule_defaults_roundtrip_and_normalized_input(self):
        rule = RecurringRule.from_dict(self.rule_record(), stored=True)
        self.assertEqual((rule.memo, rule.tags), ("", ()))
        self.assertEqual(RecurringRule.from_dict(rule.to_dict(), stored=True), rule)
        raw = RecurringRule.from_dict(self.rule_record(day="01", category=" food ", tags="a,a, b"))
        self.assertEqual((raw.day, raw.category, raw.tags), (1, "food", ("a", "b")))

    def test_rule_strict_day_fields_id_and_values(self):
        for fields in [{"day": 0}, {"day": 32}, {"day": True}, {"day": "31"},
                       {"amount": "100"}, {"extra": 1}, {"category": " food"},
                       {"tags": ["a", "a"]}, {"id": "TX-" + uuid4().hex}]:
            with self.subTest(fields=fields), self.assertRaises(InputError):
                RecurringRule.from_dict(self.rule_record(**fields), stored=True)
        for day in [" 1", "+1", "１", "32", "0"]:
            with self.subTest(day=day), self.assertRaises(InputError):
                RecurringRule.from_dict(self.rule_record(day=day))


class RecurringServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="b2-recurring-service-")
        self.addCleanup(self.temporary.cleanup)
        self.repository = Repository(Path(self.temporary.name) / "data")
        self.context = self.repository.session()
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.service = Service(self.repository)
        self.service.add_category("food")

    def rule(self, **changes):
        fields = {"day": "31", "type": "expense", "category": "food", "amount": "100", "memo": "반복 식비", "tags": "monthly"}
        fields.update(changes)
        return self.service.add_recurring(**fields)

    def rows(self):
        return list(self.repository.iter_transactions())

    def test_rule_crud_sorted_and_optional_file_created_only_when_needed(self):
        self.assertFalse(self.repository.path("recurring.jsonl").exists())
        self.assertEqual(self.service.list_recurring(), [])
        first, second = self.rule(), self.rule(day="1")
        self.assertTrue(self.repository.path("recurring.jsonl").exists())
        self.assertEqual([rule.id for rule in self.service.list_recurring()], sorted([first.id, second.id]))
        self.service.remove_recurring(first.id)
        self.assertEqual(self.service.list_recurring(), [second])
        with self.assertRaises(InputError):
            self.service.remove_recurring(first.id)

    def test_category_rule_references_reject_removal_even_without_transactions(self):
        rule = self.rule()
        with self.assertRaisesRegex(InputError, "반복 규칙 1건"):
            self.service.remove_category("food")
        self.service.remove_recurring(rule.id)
        self.service.remove_category("food")
        self.assertEqual(self.repository.categories, set())

    def test_apply_last_day_leap_year_idempotence_and_no_rewrite_when_skipped(self):
        first = self.rule()
        second = self.rule(day="1", type="income")
        with patch.object(self.repository, "write_transactions", wraps=self.repository.write_transactions) as write:
            self.assertEqual(self.service.apply_recurring("2024-02"), (2, 0))
            self.assertEqual(write.call_count, 1)
        by_rule = {row.recurring_id: row for row in self.rows()}
        self.assertEqual(by_rule[first.id].date, date(2024, 2, 29))
        self.assertEqual(by_rule[second.id].date, date(2024, 2, 1))
        self.assertEqual({row.recurring_month for row in self.rows()}, {"2024-02"})
        with patch.object(self.repository, "write_transactions") as write:
            self.assertEqual(self.service.apply_recurring("2024-02"), (0, 2))
            write.assert_not_called()
        self.assertEqual(self.service.apply_recurring("2023-02"), (2, 0))
        self.assertIn(date(2023, 2, 28), [row.date for row in self.rows()])

    def test_update_preserves_provenance_delete_regenerates_and_remove_keeps_history(self):
        rule = self.rule()
        self.service.apply_recurring("2024-02")
        original = self.rows()[0]
        updated = self.service.update(original.id, date="2025-01-01", amount="250", tags="new")
        self.assertEqual((updated.recurring_id, updated.recurring_month), (rule.id, "2024-02"))
        self.assertEqual(self.service.apply_recurring("2024-02"), (0, 1))
        self.service.delete(original.id)
        self.assertEqual(self.service.apply_recurring("2024-02"), (1, 0))
        self.assertNotEqual(self.rows()[0].id, original.id)
        self.service.remove_recurring(rule.id)
        self.assertEqual(len(self.rows()), 1)
        self.repository.validate()

    def test_empty_apply_and_invalid_month_never_rewrite(self):
        with patch.object(self.repository, "write_transactions") as write:
            self.assertEqual(self.service.apply_recurring("2024-01"), (0, 0))
            with self.assertRaises(InputError):
                self.service.apply_recurring("2024-13")
            write.assert_not_called()

    def test_invalid_rules_and_storage_failure_do_not_update_cached_rules(self):
        for fields in [{"day": "32"}, {"amount": "0"}, {"category": "missing"}]:
            with self.subTest(fields=fields), self.assertRaises(InputError):
                self.rule(**fields)
        self.assertEqual(self.repository.recurring, {})
        self.assertFalse(self.repository.path("recurring.jsonl").exists())
        with patch.object(self.repository, "write_recurring", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                self.rule()
        self.assertEqual(self.repository.recurring, {})

    def test_apply_collision_exhaustion_before_write_is_all_or_nothing(self):
        self.rule()
        self.rule(day="1")
        before = self.repository.path("transactions.jsonl").read_bytes()
        fixed = UUID("00000000-0000-4000-8000-000000000001")
        with patch("budget_app.service.uuid4", return_value=fixed):
            with self.assertRaises(StorageError):
                self.service.apply_recurring("2024-02")
        self.assertEqual(self.repository.path("transactions.jsonl").read_bytes(), before)

    def test_new_rule_never_reuses_retired_source_identifier(self):
        fixed = UUID("00000000-0000-4000-8000-000000000001")
        next_uuid = UUID("00000000-0000-4000-8000-000000000002")
        with patch("budget_app.service.uuid4", return_value=fixed):
            rule = self.rule()
        self.service.apply_recurring("2024-02")
        self.service.remove_recurring(rule.id)
        with patch("budget_app.service.uuid4", side_effect=[fixed, next_uuid]):
            fresh = self.rule()
        self.assertNotEqual(fresh.id, rule.id)
        self.assertEqual(fresh.id, "RR-" + next_uuid.hex)


if __name__ == "__main__":
    unittest.main()
