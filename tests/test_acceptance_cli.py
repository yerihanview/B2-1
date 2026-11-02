"""Independent black-box acceptance checks derived from docs/spec.md.

Only the public CLI is executed. Test data is synthetic and each test has its
own temporary data directory. Implementation modules are deliberately not imported.
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
HEADER = ['date', 'type', 'category', 'amount', 'memo', 'tags']
FILES = ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl')


class IndependentCLIAcceptance(unittest.TestCase):
    """T01-T15/T19-T25/T27: independent public-contract expectations."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix='b2-independent-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'

    def cli(self, *args: str, stdin: str = '', expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, '-m', 'budget_app', '--data-dir', str(self.data), *args],
            cwd=ROOT, input=stdin, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, expected,
                         f'args={args!r}\nstdout={result.stdout}\nstderr={result.stderr}')
        self.assertNotIn('Traceback', result.stdout + result.stderr)
        if expected:
            self.assertIn('[오류]', result.stderr)
            self.assertIn('[힌트]', result.stderr)
        return result

    def rows(self, filename: str = 'transactions.jsonl') -> list[dict]:
        return [json.loads(line) for line in (self.data / filename).read_text(encoding='utf-8').splitlines()]

    def snapshot(self) -> dict[str, bytes]:
        return {name: (self.data / name).read_bytes() for name in FILES if (self.data / name).exists()}

    def write_rows(self, filename: str, rows: list[dict]) -> None:
        self.data.mkdir(exist_ok=True)
        (self.data / filename).write_text(
            ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')

    def transaction(self, *, date: str = '2024-01-15', amount: int = 100,
                    category: str = 'food', kind: str = 'expense',
                    memo: str = '', tags: list[str] | None = None) -> dict:
        return {'id': 'TX-' + uuid.uuid4().hex, 'type': kind, 'date': date,
                'category': category, 'amount': amount, 'memo': memo, 'tags': tags or []}

    def seed(self, transactions: list[dict] | None = None,
             categories: tuple[str, ...] = ('food', 'salary', 'transport'),
             budgets: list[dict] | None = None) -> None:
        self.write_rows('categories.jsonl', [{'name': name} for name in categories])
        self.write_rows('budgets.jsonl', budgets or [])
        self.write_rows('transactions.jsonl', transactions or [])

    def csv_file(self, rows: list[list[str]], *, name: str = 'input.csv') -> Path:
        path = self.root / name
        with path.open('w', encoding='utf-8', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(HEADER)
            writer.writerows(rows)
        return path

    def listed_ids(self, text: str) -> list[str]:
        return re.findall(r'^\s*(TX-[0-9a-f]{32})\s*\|', text, re.MULTILINE)

    def assert_clean(self) -> None:
        self.assertFalse((self.data / '.budget_app.lock').exists())
        self.assertEqual({p.name for p in self.data.iterdir()}, set(FILES))

    def test_T21_all_help_and_parser_errors_do_not_create_data(self) -> None:
        commands = [(), ('add',), ('list',), ('search',), ('summary',),
                    ('update',), ('delete',), ('export',), ('import',),
                    ('budget',), ('budget', 'set'), ('category',),
                    ('category', 'add'), ('category', 'list'), ('category', 'remove')]
        for command in commands:
            with self.subTest(help=command):
                self.assertTrue(self.cli(*command, '--help').stdout.strip())
                self.assertFalse(self.data.exists())
        for args in [('unknown',), ('list', '--unknown'), ('summary',),
                     ('delete',), ('update',), ('budget', 'set'), ('import',), ()]:
            with self.subTest(invalid=args):
                self.cli(*args, expected=2)
                self.assertFalse(self.data.exists())

    def test_T21_help_ignores_corrupt_store_and_existing_lock(self) -> None:
        self.data.mkdir()
        (self.data/'transactions.jsonl').write_bytes(b'{broken}\n')
        lock = self.data/'.budget_app.lock'
        lock.write_text('other process')
        baseline = self.snapshot()
        self.cli('list', '--help')
        self.assertEqual(self.snapshot(), baseline)
        self.assertEqual(lock.read_text(), 'other process')
        self.cli('list', '--unknown', expected=2)
        self.assertEqual(self.snapshot(), baseline)
        self.assertEqual(lock.read_text(), 'other process')

    def test_T10_initialization_and_category_prerequisite(self) -> None:
        result = self.cli('category', 'list')
        self.assertTrue(result.stdout.strip())
        self.assertEqual(self.snapshot(), {name: b'' for name in FILES})
        self.cli('add', stdin='2024-01-15\nexpense\nfood\n100\n\n\n', expected=2)
        self.assertEqual(self.rows(), [])
        self.assert_clean()

    def test_T01_add_persistence_uuid_tags_and_memo(self) -> None:
        self.cli('category', 'add', stdin=' food \n')
        result = self.cli('add', stdin='2024-01-15\nexpense\n food \n15000\n 점심 식사 \n meal,weekday,meal \n')
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertRegex(row['id'], r'^TX-[0-9a-f]{32}$')
        self.assertIn(row['id'], result.stdout)
        self.assertEqual(row['category'], 'food')
        self.assertEqual(row['amount'], 15000)
        self.assertEqual(row['memo'], ' 점심 식사 ')
        self.assertEqual(row['tags'], ['meal', 'weekday'])
        self.assertIn(row['id'], self.cli('list').stdout)
        self.assertEqual(self.rows('categories.jsonl'), [{'name': 'food'}])
        self.assert_clean()

    def test_T01_invalid_interactive_values_preserve_files(self) -> None:
        self.seed()
        baseline = self.snapshot()
        values = [('2024-02-30', 'expense', 'food', '100', '', ''),
                  ('2024-1-01', 'expense', 'food', '100', '', ''),
                  ('2024-01-01', 'invalid', 'food', '100', '', ''),
                  ('2024-01-01', 'expense', 'absent', '100', '', ''),
                  ('2024-01-01', 'expense', 'food', '0', '', ''),
                  ('2024-01-01', 'expense', 'food', '-1', '', ''),
                  ('2024-01-01', 'expense', 'food', '1.2', '', ''),
                  ('2024-01-01', 'expense', 'food', '+1', '', ''),
                  ('2024-01-01', 'expense', 'food', ' 1', '', ''),
                  ('2024-01-01', 'expense', 'food', '１００', '', ''),
                  ('2024-01-01', 'expense', 'food', '100', '', 'a,,b'),
                  ('2024-01-01', 'expense', 'food', '100', 'x' * 501, '')]
        for fields in values:
            with self.subTest(fields=fields):
                self.cli('add', stdin='\n'.join(fields) + '\n', expected=2)
                self.assertEqual(self.snapshot(), baseline)
                self.assert_clean()

    def test_T02_latest_sort_ties_and_limit(self) -> None:
        a = self.transaction(date='2024-01-30', memo='first same day')
        b = self.transaction(date='2024-01-01')
        c = self.transaction(date='2024-01-30', memo='later same day')
        self.seed([a, b, c])
        self.assertEqual(self.listed_ids(self.cli('list').stdout), [c['id'], a['id'], b['id']])
        self.assertEqual(self.listed_ids(self.cli('list', '--limit', '1').stdout), [c['id']])
        self.assertEqual(len(self.listed_ids(self.cli('list', '--limit', '1000').stdout)), 3)
        for value in ['0', '1001', '-1', '1.5']:
            self.cli('list', '--limit', value, expected=2)

    def test_T02_default_limit_twenty(self) -> None:
        rows = [self.transaction(memo=str(i)) for i in range(25)]
        self.seed(rows)
        self.assertEqual(self.listed_ids(self.cli('list').stdout), [r['id'] for r in rows[-20:][::-1]])

    def test_T03_search_and_boundaries_case_and_tag(self) -> None:
        a = self.transaction(date='2024-01-01', memo='Lunch 점심', tags=['meal'])
        b = self.transaction(date='2024-01-31', memo='Lunch 점심', tags=['meal'])
        c = self.transaction(date='2024-02-01', memo='Lunch 점심', tags=['meal'])
        d = self.transaction(date='2024-01-20', memo='lunch 점심', tags=['meal'])
        e = self.transaction(date='2024-01-21', memo='Lunch 점심', tags=['meal2'])
        f = self.transaction(date='2024-01-22', memo='Lunch 점심', tags=['meal'], kind='income')
        self.seed([a,b,c,d,e,f])
        result = self.cli('search', '--from', '2024-01-01', '--to', '2024-01-31',
                          '--category', 'food', '--type', 'expense', '--q', 'Lunch', '--tag', 'meal')
        self.assertEqual(self.listed_ids(result.stdout), [b['id'], a['id']])
        self.assertEqual(self.listed_ids(self.cli('search', '--q', '').stdout),
                         self.listed_ids(self.cli('list').stdout))
        self.assertIn('[데이터 없음]', self.cli('search', '--category', 'unregistered').stdout)
        self.assertIn('[데이터 없음]', self.cli('search', '--tag', 'unregistered').stdout)
        self.cli('search', '--from', '2024-02-01', '--to', '2024-01-01', expected=2)
        self.cli('search', '--category', 'bad category', expected=2)

    def test_T04_summary_budget_rates_and_tie_order(self) -> None:
        self.seed([self.transaction(kind='income', category='salary', amount=3000000),
                   self.transaction(amount=45000),
                   self.transaction(category='transport', amount=20000)],
                  budgets=[{'month': '2024-01', 'amount': 500000}])
        result = self.cli('summary', '--month', '2024-01', '--top', '3')
        for number in ('3000000', '65000', '2935000', '13.0%'):
            self.assertIn(number, result.stdout)
        self.cli('budget', 'set', '--month', '2024-01', '--amount', '65000')
        self.assertIn('100.0%', self.cli('summary', '--month', '2024-01').stdout)
        self.assertNotRegex(self.cli('summary', '--month', '2024-01').stdout,
                            r'(?:초과\s*경고|\[경고\])')
        self.cli('budget', 'set', '--month', '2024-01', '--amount', '64000')
        self.assertIn('초과', self.cli('summary', '--month', '2024-01').stdout)
        self.assertEqual(self.rows('budgets.jsonl'), [{'month': '2024-01', 'amount': 64000}])
        for value in ('0', '101'):
            self.cli('summary', '--month', '2024-01', '--top', value, expected=2)

    def _assert_large_amount_summary(self, *, with_budget: bool) -> None:
        # The contract has no monetary maximum. Each input is accepted at the
        # CPython 3.12 default conversion boundary; their sum crosses it.
        # Build expected output as text so this independent oracle does not
        # reproduce the implementation's int-to-string conversion defect.
        self.seed()
        amount_text = '9' * 4300
        total_text = '1' + '9' * 4299 + '8'
        for memo in ('first large expense', 'second large expense'):
            self.cli('add', stdin='2024-01-15\nexpense\nfood\n' +
                     amount_text + '\n' + memo + '\n\n')
        if with_budget:
            self.cli('budget', 'set', '--month', '2024-01', '--amount', '1')
        before = self.snapshot()
        output = self.cli('summary', '--month', '2024-01').stdout
        self.assertIn('총 수입: 0원', output)
        self.assertIn('총 지출: ' + total_text + '원', output)
        self.assertIn('잔액: -' + total_text + '원', output)
        if with_budget:
            self.assertIn(total_text + '00.0%', output)
            self.assertIn('초과', output)
        self.assertEqual(self.snapshot(), before)
        self.assert_clean()

    def test_T04_large_accepted_amounts_summary_without_budget(self) -> None:
        self._assert_large_amount_summary(with_budget=False)

    def test_T12_large_accepted_amounts_summary_with_budget(self) -> None:
        self._assert_large_amount_summary(with_budget=True)

    def test_T04_category_top_ties_are_alphabetical_and_income_excluded(self) -> None:
        self.seed([self.transaction(category='transport', amount=10),
                   self.transaction(category='food', amount=10),
                   self.transaction(category='salary', kind='income', amount=10000)])
        output = self.cli('summary', '--month', '2024-01', '--top', '2').stdout
        self.assertLess(output.index('food'), output.index('transport'))
        self.assertNotIn('salary', output)

    def test_T12_budget_only_month_and_half_up(self) -> None:
        self.seed(budgets=[{'month': '2024-02', 'amount': 1000}])
        output = self.cli('summary', '--month', '2024-02').stdout
        self.assertIn('[데이터 없음]', output)
        self.assertIn('0.0%', output)
        self.seed([self.transaction(amount=1)], budgets=[{'month': '2024-01', 'amount': 80}])
        self.assertIn('1.3%', self.cli('summary', '--month', '2024-01').stdout)
        self.cli('budget', 'set', '--month', '2024-13', '--amount', '10', expected=2)
        self.cli('budget', 'set', '--month', '2024-01', '--amount', '0', expected=2)

    def test_T06_update_keeps_id_position_and_clears_optional_fields(self) -> None:
        a = self.transaction(memo='old', tags=['meal'])
        b = self.transaction(memo='other')
        self.seed([a,b])
        self.cli('update', '--id', a['id'], '--date', '2024-02-01', '--amount', '500',
                 '--category', 'transport', '--memo', '', '--tags', '')
        updated = self.rows()
        self.assertEqual([r['id'] for r in updated], [a['id'], b['id']])
        self.assertEqual(updated[0], dict(a, date='2024-02-01', amount=500,
                                          category='transport', memo='', tags=[]))
        self.assertEqual(updated[1], b)
        baseline = self.snapshot()
        self.cli('update', '--id', a['id'], expected=2)
        self.cli('update', '--id', a['id'], '--amount', '-1', expected=2)
        self.cli('update', '--id', 'TX-' + uuid.uuid4().hex, '--memo', 'x', expected=2)
        self.assertEqual(self.snapshot(), baseline)

    def test_T07_delete_without_prompt_and_absent_id(self) -> None:
        a,b = self.transaction(),self.transaction()
        self.seed([a,b])
        self.cli('delete', '--id', a['id'])
        self.assertEqual(self.rows(), [b])
        self.cli('delete', '--id', a['id'], expected=2)
        self.assertEqual(self.rows(), [b])

    def test_T11_category_sort_case_duplicate_referenced_and_unused(self) -> None:
        self.seed([self.transaction()], categories=('z', 'food', 'A'))
        output = self.cli('category', 'list').stdout
        self.assertLess(output.index('A'), output.index('food'))
        self.assertLess(output.index('food'), output.index('z'))
        baseline = self.snapshot()
        self.cli('category', 'add', stdin='food\n', expected=2)
        self.cli('category', 'remove', stdin='food\n', expected=2)
        self.cli('category', 'remove', stdin='missing\n', expected=2)
        self.assertEqual(self.snapshot(), baseline)
        self.cli('category', 'add', stdin='Food\n')
        self.cli('category', 'remove', stdin='Food\n')
        self.cli('category', 'remove', stdin='z\n')
        self.assertEqual({r['name'] for r in self.rows('categories.jsonl')}, {'food','A'})
        for value in ['한글', 'bad name', '', 'x'*51]:
            self.cli('category', 'add', stdin=value+'\n', expected=2)

    def test_T08_export_filters_file_order_schema_and_overwrite(self) -> None:
        a = self.transaction(date='2024-01-30', memo='점심,"quoted"', tags=['meal','weekday'])
        b = self.transaction(date='2024-01-01')
        c = self.transaction(date='2024-02-01')
        self.seed([a,b,c])
        output = self.root / 'export.csv'
        result = self.cli('export', '--out', str(output), '--month', '2024-01')
        self.assertIn('exported=2', result.stdout)
        with output.open(encoding='utf-8', newline='') as source:
            rows = list(csv.reader(source))
        self.assertEqual(rows[0], HEADER)
        self.assertEqual([r[0] for r in rows[1:]], ['2024-01-30','2024-01-01'])
        self.assertEqual(rows[1][4:], ['점심,"quoted"','meal,weekday'])
        baseline = output.read_bytes()
        self.cli('export', '--out', str(output), '--month', '2024-02', expected=2)
        self.assertEqual(output.read_bytes(), baseline)
        self.cli('export', '--out', str(output), '--month', '2024-02', '--overwrite')
        self.assertNotEqual(output.read_bytes(), baseline)
        self.cli('export', '--out', str(output), '--overwrite', expected=2)
        self.cli('export', '--out', str(output), '--from', '2024-01-01', expected=2)
        self.cli('export', '--out', str(output), '--month', '2024-01',
                 '--from', '2024-01-01', '--to', '2024-01-31', expected=2)

    def test_T08_export_zero_and_inclusive_range(self) -> None:
        self.seed([self.transaction(date='2024-01-01'),self.transaction(date='2024-01-31'),
                   self.transaction(date='2024-02-01')])
        output = self.root / 'range.csv'
        self.assertIn('exported=2', self.cli('export', '--out', str(output),
                      '--from','2024-01-01','--to','2024-01-31').stdout)
        output.unlink()
        self.assertIn('exported=0', self.cli('export', '--out', str(output), '--month','2023-01').stdout)
        with output.open(encoding='utf-8', newline='') as source:
            self.assertEqual(list(csv.reader(source)), [HEADER])

    def test_T09_import_unicode_quoting_nonidempotence(self) -> None:
        self.seed()
        source = self.csv_file([['2024-01-15','expense','food','15000','점심\n식사','meal,weekday']])
        result = self.cli('import', '--from', str(source))
        self.assertIn('imported=1, skipped=0', result.stdout)
        first = self.rows()[0]
        self.assertEqual(first['memo'], '점심\n식사')
        self.assertEqual(first['tags'], ['meal','weekday'])
        self.cli('import', '--from', str(source))
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual({k:v for k,v in rows[0].items() if k!='id'},
                         {k:v for k,v in rows[1].items() if k!='id'})
        self.assert_clean()

    def test_T09_valid_tags_are_not_limited_by_csv_default_field_size(self) -> None:
        # spec bounds each tag, not the number of tags or CSV record size.
        self.seed()
        tags = ['tag' + str(index) for index in range(20000)]
        source = self.csv_file([['2024-01-15','expense','food','1','',','.join(tags)]])
        self.assertIn('imported=1, skipped=0', self.cli('import','--from',str(source)).stdout)
        self.assertEqual(self.rows()[0]['tags'], tags)
        self.assert_clean()

    def test_T19_invalid_csv_rows_rollback_and_physical_line_number(self) -> None:
        self.seed([self.transaction()])
        baseline = self.snapshot()
        source = self.csv_file([['2024-01-15','expense','food','1','two\nlines',''],
                                ['2024-01-16','expense','food','0','','']])
        result = self.cli('import', '--from', str(source), expected=2)
        self.assertRegex(result.stderr, r'(?:행\s*4|4\s*행|line\s*4)')
        self.assertEqual(self.snapshot(), baseline)
        self.assert_clean()

    def test_T25_csv_error_variants_preserve_all_files(self) -> None:
        self.seed([self.transaction()])
        baseline = self.snapshot()
        header = ','.join(HEADER)+'\n'
        cases = [('',2), ('\ufeff'+header,2), ('date,type\n',2),
                 (header+'\n',2), (header+'2024-01-15,expense,food,1\n',2),
                 (header+'2024-01-15,expense,food,1,,,extra\n',2),
                 (header+'2024-01-15,expense,food,1,"unterminated\n',2),
                 (header+'2024-01-15,expense,absent,1,,\n',2),
                 (header+'2024-01-15,expense,food,1,,"a,,b"\n',2)]
        source = self.root/'bad.csv'
        for content,code in cases:
            with self.subTest(content=content):
                source.write_text(content,encoding='utf-8')
                self.cli('import','--from',str(source),expected=code)
                self.assertEqual(self.snapshot(),baseline)
                self.assert_clean()
        source.write_bytes(header.encode()+b'\xff')
        self.cli('import','--from',str(source),expected=3)
        self.assertEqual(self.snapshot(),baseline)
        self.cli('import','--from',str(self.root/'missing.csv'),expected=3)

    def test_T25_header_only_import_is_noop(self) -> None:
        self.seed([self.transaction()])
        source = self.csv_file([])
        baseline = self.snapshot()
        inode = (self.data/'transactions.jsonl').stat().st_ino
        self.assertIn('imported=0, skipped=0',self.cli('import','--from',str(source)).stdout)
        self.assertEqual(self.snapshot(),baseline)
        self.assertEqual((self.data/'transactions.jsonl').stat().st_ino,inode)

    def test_T25_first_twenty_validation_errors_only(self) -> None:
        self.seed()
        source = self.csv_file([['2024-01-15','expense','food','0','',''] for _ in range(25)])
        result = self.cli('import','--from',str(source),expected=2)
        self.assertRegex(result.stderr,r'(?:행\s*2\b|\b2\s*행|line\s*2\b)')
        self.assertRegex(result.stderr,r'(?:행\s*21\b|\b21\s*행|line\s*21\b)')
        self.assertNotRegex(result.stderr,r'(?:행\s*22\b|\b22\s*행|line\s*22\b)')
        self.assertEqual(self.rows(),[])

    def test_T24_export_protects_internal_files_and_aliases(self) -> None:
        self.seed([self.transaction()])
        baseline = self.snapshot()
        paths = [self.data/name for name in FILES] + [self.data/'.budget_app.lock']
        symlink = self.root/'alias.csv'
        symlink.symlink_to(self.data/'transactions.jsonl')
        hardlink = self.root/'hard.csv'
        os.link(self.data/'categories.jsonl',hardlink)
        paths.extend([symlink,hardlink,self.data/'..'/'data'/'transactions.jsonl'])
        for path in paths:
            for extra in [(),('--overwrite',)]:
                with self.subTest(path=path.name,overwrite=extra):
                    self.cli('export','--out',str(path),'--month','2024-01',*extra,expected=2)
                    self.assertEqual(self.snapshot(),baseline)
                    self.assert_clean()

    def test_T22_corruption_in_any_file_is_not_repaired(self) -> None:
        valid = self.transaction()
        transaction_variants = [
            b'\n', b'not json\n', b'\xff\n',
            (json.dumps(valid)+'\n'+json.dumps(valid)+'\n').encode(),
            (json.dumps(dict(valid,amount=True))+'\n').encode(),
            (json.dumps(dict(valid,category='missing'))+'\n').encode(),
            (json.dumps(dict(valid,extra=1))+'\n').encode(),
            (json.dumps(dict(valid,tags=['meal','meal']))+'\n').encode(),
            (json.dumps(dict(valid,category=' food'))+'\n').encode(),
            ('{"id":"'+valid['id']+'","id":"'+valid['id']+'"}\n').encode(),
        ]
        cases = [('transactions.jsonl',content) for content in transaction_variants]
        cases.extend([('categories.jsonl',b'{"name":"food"}\n{"name":"food"}\n'),
                      ('budgets.jsonl',b'{"month":"2024-01","amount":1}\n'*2),
                      ('budgets.jsonl',b'{"month":"2024-13","amount":1}\n')])
        for filename,content in cases:
            with self.subTest(filename=filename,content=content):
                self.seed([valid])
                (self.data/filename).write_bytes(content)
                baseline = self.snapshot()
                result = self.cli('list','--limit','1',expected=3)
                self.assertEqual(result.stdout,'')
                self.assertEqual(self.snapshot(),baseline)
                self.assert_clean()

    def test_T22_filter_does_not_hide_late_corruption(self) -> None:
        self.seed([self.transaction(date='2024-01-30')])
        with (self.data/'transactions.jsonl').open('a') as target:
            target.write('{bad late line}\n')
        baseline = self.snapshot()
        result = self.cli('search','--from','2025-01-01','--limit','1',expected=3)
        self.assertEqual(result.stdout,'')
        self.assertEqual(self.snapshot(),baseline)

    def test_T22_corrupt_and_missing_does_not_initialize_missing_file(self) -> None:
        self.data.mkdir()
        (self.data/'transactions.jsonl').write_bytes(b'{broken}\n')
        baseline = self.snapshot()
        self.cli('list',expected=3)
        self.assertEqual(self.snapshot(),baseline)
        self.assertEqual(set(self.snapshot()),{'transactions.jsonl'})
        self.assertFalse((self.data/'.budget_app.lock').exists())

    def test_T22_optional_fields_may_be_omitted(self) -> None:
        row = self.transaction()
        del row['memo']; del row['tags']
        self.seed([row])
        self.assertIn(row['id'],self.cli('list').stdout)

    def test_T23_stale_lock_is_preserved_and_reads_also_fail(self) -> None:
        self.seed()
        lock = self.data/'.budget_app.lock'
        lock.write_text('synthetic lock owner\n')
        baseline = self.snapshot()
        for args in [('list',),('category','list'),('budget','set','--month','2024-01','--amount','1')]:
            self.cli(*args,expected=4)
            self.assertEqual(lock.read_text(),'synthetic lock owner\n')
            self.assertEqual(self.snapshot(),baseline)
        lock.unlink()

    def test_T21_EOF_releases_owned_lock(self) -> None:
        self.seed()
        baseline = self.snapshot()
        self.cli('add',stdin='',expected=2)
        self.assertEqual(self.snapshot(),baseline)
        self.assert_clean()

    def test_T23_live_interactive_process_holds_lock_until_interrupted(self) -> None:
        self.seed()
        baseline = self.snapshot()
        process = subprocess.Popen(
            [sys.executable,'-m','budget_app','--data-dir',str(self.data),'add'],
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline = time.monotonic()+5
            while not (self.data/'.budget_app.lock').exists() and time.monotonic()<deadline:
                if process.poll() is not None:
                    break
                time.sleep(.02)
            self.assertTrue((self.data/'.budget_app.lock').exists(),'interactive command did not acquire lock')
            self.cli('list',expected=4)
            process.send_signal(signal.SIGINT)
            stdout,stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode,2,(stdout,stderr))
            self.assertNotIn('Traceback',stdout+stderr)
            self.assertIn('[오류]',stderr)
            self.assertIn('[힌트]',stderr)
            self.assertEqual(self.snapshot(),baseline)
            self.assert_clean()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
