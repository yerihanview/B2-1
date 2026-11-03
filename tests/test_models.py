"""Input and persisted-model boundary cases derived from spec.md."""

import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from datetime import date
from uuid import uuid4
from typing import get_type_hints

from budget_app.errors import InputError
from budget_app.models import (
    Transaction, parse_amount, parse_date, parse_month, parse_name,
    parse_tags, validate_memo,
)


class ModelTests(unittest.TestCase):
    def record(self, **changes):
        return {"id": "TX-" + uuid4().hex, "type": "expense", "date": "2024-02-29", "category": "food", "amount": 15000, **changes}

    def test_model_roundtrip_and_frozen_dataclass(self):
        transaction = Transaction.from_dict(self.record(tags=["meal"], memo=" 점심 "), stored=True)
        self.assertTrue(is_dataclass(transaction))
        self.assertEqual(transaction.date, date(2024, 2, 29))
        self.assertEqual(transaction.memo, " 점심 ")
        self.assertEqual(Transaction.from_dict(transaction.to_dict(), stored=True), transaction)
        with self.assertRaises(FrozenInstanceError):
            setattr(transaction, 'amount', 3)

    def test_optional_fields_default(self):
        row = Transaction.from_dict(self.record(), stored=True)
        self.assertEqual((row.memo, row.tags), ("", ()))

    def test_dates_reject_noncanonical_and_invalid_calendar(self):
        for value in ["2024-2-29", "2023-02-29", "２０２４-01-01", "2024-01-01 ", "0000-01-01", None]:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_date(value)
        self.assertEqual(parse_month("2024-02"), "2024-02")
        for value in ["2024-2", "2024-13", "2024-00"]:
            with self.assertRaises(InputError):
                parse_month(value)

    def test_amount_rejects_bool_zero_float_sign_and_whitespace(self):
        self.assertEqual(parse_amount("0010"), 10)
        for value in [True, False, 0, -1, 1.5, " 1", "1 ", "+1", "-1", "1e2", "１", "", None]:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_amount(value)

    def test_names_and_tags_normalize_input(self):
        self.assertEqual(parse_name(" food "), "food")
        self.assertEqual(parse_tags("meal, work,meal"), ("meal", "work"))
        self.assertEqual(parse_tags(""), ())
        for value in ["a,,b", " ", "a,", ",a", "한글!"]:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_tags(value)

    def test_hangul_names_tags_and_length_boundaries(self):
        for value in ["식비", "교통비", "월급", "식비_food-1", "가", "힣", "가" * 50]:
            with self.subTest(value=value):
                self.assertEqual(parse_name(" " + value + " "), value)
        self.assertEqual(parse_tags("점심, 외식,정기지출,점심"), ("점심", "외식", "정기지출"))
        self.assertEqual(parse_name("힣" * 30, tag=True), "힣" * 30)

    def test_hangul_rejects_specials_jamo_and_excess_length(self):
        for tag, maximum in [(False, 50), (True, 30)]:
            for value in ["가" * (maximum + 1), "한글!", "식 비", "ㄱ", "가", "食費", "é", "외식🙂"]:
                with self.subTest(tag=tag, value=value):
                    with self.assertRaises(InputError) as error:
                        parse_name(value, tag=tag)
                    self.assertIn("한글(가-힣)", error.exception.hint)
                    self.assertIn(f"1~{maximum}자", error.exception.hint)

    def test_stored_fields_are_strict_and_never_normalized(self):
        for changes in [
            {"category": " food"}, {"tags": ["meal", "meal"]},
            {"tags": [" meal"]}, {"tags": "meal"}, {"amount": "15000"},
            {"amount": True}, {"extra": 1}, {"memo": None},
            {"type": "EXPENSE"}, {"id": "TX-123"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(InputError):
                Transaction.from_dict(self.record(**changes), stored=True)

    def test_memo_length_and_utf8(self):
        self.assertEqual(validate_memo("가" * 500), "가" * 500)
        for value in ["가" * 501, "\ud800"]:
            with self.assertRaises(InputError):
                validate_memo(value)

    def test_model_public_type_hints_resolve(self):
        self.assertEqual(get_type_hints(Transaction)["date"], date)
        self.assertEqual(get_type_hints(parse_amount)["return"], int)


if __name__ == "__main__":
    unittest.main()
