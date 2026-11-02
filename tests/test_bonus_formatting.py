"""B03 Unicode table layout and storage-independent display escaping."""
from datetime import date
import unittest
import uuid

from budget_app.formatting import display_width, escape_text, format_transactions
from budget_app.models import Transaction


class BonusFormattingTests(unittest.TestCase):
    def row(self, *, kind='expense', category='food', amount=1, memo=''):
        return Transaction('TX-' + uuid.uuid4().hex, kind, date(2024, 1, 15),
                           category, amount, memo)

    def test_B03_width_accounts_for_korean_fullwidth_and_combining(self):
        self.assertEqual(display_width('abc'), 3)
        self.assertEqual(display_width('한글'), 4)
        self.assertEqual(display_width('Ａ'), 2)
        self.assertEqual(display_width('e\u0301'), 1)
        self.assertEqual(display_width('가e\u0301Ａ'), 5)

    def test_B03_columns_align_and_amounts_are_right_aligned(self):
        rows = [self.row(kind='income', category='salary', amount=900000, memo='월급'),
                self.row(category='x', amount=7, memo='e\u0301'),
                self.row(category='transport', amount=1234, memo='기차')]
        rendered = format_transactions(rows)
        parts = [line.split(' | ') for line in rendered]
        self.assertTrue(all(len(row) == 6 for row in parts))
        positions = [[display_width(' | '.join(row[:i])) for i in range(1, 6)] for row in parts]
        self.assertEqual(positions[0], positions[1])
        self.assertEqual(positions[1], positions[2])
        self.assertEqual(parts[0][4], '900000')
        self.assertEqual(parts[1][4], '     7')
        self.assertEqual(parts[2][4], '  1234')
        self.assertEqual([part[0].strip() for part in parts], [row.id for row in rows])

    def test_B03_control_escaping_is_single_line_and_preserves_model(self):
        memo = '점심\n저녁\t메모\r\x1b[31m\x00\x85\u2028\u2029\u200b'
        transaction = self.row(memo=memo)
        rendered = format_transactions([transaction])[0]
        self.assertEqual(len(rendered.splitlines()), 1)
        self.assertIn(r'점심\n저녁\t메모\r\x1b[31m\x00\x85\u2028\u2029\u200b', rendered)
        self.assertEqual(transaction.memo, memo)
        self.assertEqual(escape_text('plain 한글 e\u0301'), 'plain 한글 e\u0301')

    def test_B03_empty_rows_keep_existing_message(self):
        self.assertEqual(format_transactions([]), ['[데이터 없음]'])

    def test_B03_class_zero_nonspacing_and_enclosing_marks_have_zero_width(self):
        self.assertEqual(display_width('\ufe0f'), 0)
        self.assertEqual(display_width('\u20dd'), 0)
        self.assertEqual(display_width('A\ufe0f\u20dd'), 1)
