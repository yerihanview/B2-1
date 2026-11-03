"""Independent bonus acceptance: public CLI and documented data formats only."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FILES = ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl')


class IndependentBonusAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix='b2-bonus-independent-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root/'data'

    def cli(self, *args: str, stdin: str = '', expected: int = 0,
            data: Path | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, '-m', 'budget_app', '--data-dir', str(data or self.data), *args],
            cwd=ROOT, input=stdin, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, expected,
                         f'{args!r}\nstdout={result.stdout}\nstderr={result.stderr}')
        self.assertNotIn('Traceback', result.stdout+result.stderr)
        if expected:
            self.assertIn('[오류]',result.stderr)
            self.assertIn('[힌트]',result.stderr)
        return result

    def seed(self, transactions: list[dict] | None = None) -> None:
        self.data.mkdir(exist_ok=True)
        self.write_rows('transactions.jsonl',transactions or [])
        self.write_rows('categories.jsonl',[{'name':'food'},{'name':'salary'},{'name':'transport'}])
        self.write_rows('budgets.jsonl',[{'month':'2024-01','amount':500000}])

    def write_rows(self, filename: str, rows: list[dict]) -> None:
        (self.data/filename).write_text(
            ''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')

    def rows(self, filename: str = 'transactions.jsonl') -> list[dict]:
        return [json.loads(line) for line in (self.data/filename).read_text(encoding='utf-8').splitlines()]

    def snapshot(self) -> dict[str,bytes]:
        return {p.name:p.read_bytes() for p in self.data.glob('*.jsonl')}

    def transaction(self, **changes) -> dict:
        return dict({'id':'TX-'+uuid.uuid4().hex,'date':'2024-01-15','type':'expense',
                     'category':'food','amount':100,'memo':'','tags':[]},**changes)

    def add_rule(self, *, day: str = '31', kind: str = 'expense', category: str = 'food',
                 amount: str = '100', memo: str = '월별 거래', tags: str = 'monthly') -> dict:
        result = self.cli('recurring','add','--day',day,'--type',kind,'--category',category,
                          '--amount',amount,'--memo',memo,'--tags',tags)
        rules = self.rows('recurring.jsonl')
        match = re.search(r'RR-[0-9a-f]{32}', result.stdout)
        self.assertIsNotNone(match)
        assert match is not None
        rule = next(row for row in rules if row['id'] == match.group(0))
        self.assertRegex(rule['id'],r'^RR-[0-9a-f]{32}$')
        self.assertEqual(uuid.UUID(hex=rule['id'][3:]).version,4)
        self.assertIn(rule['id'],result.stdout)
        return rule

    @staticmethod
    def display_width(value: str) -> int:
        return sum(0 if unicodedata.category(char) in ('Mn', 'Me') or unicodedata.combining(char) else
                   2 if unicodedata.east_asian_width(char) in 'WF' else 1 for char in value)

    def test_B01_B02_all_help_and_parser_errors_without_store_access(self) -> None:
        for args in [('backup',),('recurring',),('recurring','add'),('recurring','list'),
                     ('recurring','remove'),('recurring','apply')]:
            with self.subTest(args=args):
                self.assertTrue(self.cli(*args,'--help').stdout.strip())
                self.assertFalse(self.data.exists())
        for args in [('backup','--unknown'),('recurring',),('recurring','add'),
                     ('recurring','remove'),('recurring','apply')]:
            with self.subTest(args=args):
                self.cli(*args,expected=2)
                self.assertFalse(self.data.exists())

    def test_B01_backup_bytes_manifest_exclusions_and_repeated_preservation(self) -> None:
        self.seed([self.transaction(memo='한글 원본')])
        # Arbitrary whitespace is valid JSONL and must survive byte-for-byte.
        (self.data/'transactions.jsonl').write_text(
            json.dumps(self.rows()[0],ensure_ascii=False,indent=None)+'  \n',encoding='utf-8')
        (self.data/'not-finance.txt').write_text('must not be included')
        before = self.snapshot()
        self.cli('backup')
        archives = sorted((self.data/'backups').glob('*.zip'))
        self.assertEqual(len(archives),1)
        first = archives[0]
        self.assertRegex(first.name,r'^backup-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{32}\.zip$')
        first_bytes = first.read_bytes()
        with zipfile.ZipFile(first) as archive:
            self.assertEqual(set(archive.namelist()),set(FILES)|{'manifest.json'})
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['format'],'budget_app_backup')
            self.assertEqual(manifest['version'],1)
            stamp = datetime.fromisoformat(manifest['created_at'].replace('Z','+00:00'))
            offset = stamp.utcoffset()
            self.assertIsNotNone(offset)
            assert offset is not None
            self.assertEqual(offset.total_seconds(),0)
            self.assertEqual(set(manifest['files']),set(FILES))
            for filename,raw in before.items():
                self.assertEqual(archive.read(filename),raw)
                self.assertEqual(manifest['files'][filename]['size'],len(raw))
                self.assertEqual(manifest['files'][filename]['sha256'],hashlib.sha256(raw).hexdigest())
        self.cli('backup')
        self.assertEqual(len(list((self.data/'backups').glob('*.zip'))),2)
        self.assertEqual(first.read_bytes(),first_bytes)
        self.assertEqual(self.snapshot(),before)
        self.assertFalse((self.data/'.budget_app.lock').exists())

    def test_B01_backup_optional_rules_and_restore_in_new_directory(self) -> None:
        self.seed([self.transaction(memo='보존할 거래')])
        self.add_rule()
        self.cli('recurring','apply','--month','2024-02')
        before = self.snapshot()
        target = self.root/'custom'/'archives'
        self.cli('backup','--out-dir',str(target))
        archives = list(target.glob('*.zip'))
        self.assertEqual(len(archives),1)
        restored = self.root/'restored'
        restored.mkdir()
        with zipfile.ZipFile(archives[0]) as archive:
            self.assertEqual(set(archive.namelist()),set(FILES)|{'recurring.jsonl','manifest.json'})
            manifest = json.loads(archive.read('manifest.json'))
            for name,raw in before.items():
                self.assertEqual(archive.read(name),raw)
                self.assertEqual(manifest['files'][name]['sha256'],hashlib.sha256(raw).hexdigest())
                (restored/name).write_bytes(archive.read(name))
        self.assertEqual(self.cli('list').stdout,self.cli('list',data=restored).stdout)
        self.assertEqual(self.cli('recurring','list').stdout,
                         self.cli('recurring','list',data=restored).stdout)
        self.assertEqual(self.cli('summary','--month','2024-02').stdout,
                         self.cli('summary','--month','2024-02',data=restored).stdout)
        self.assertIn('generated=0, skipped=1',
                      self.cli('recurring','apply','--month','2024-02',data=restored).stdout)

    def test_B01_backup_rejects_corruption_and_lock_without_archive(self) -> None:
        self.seed()
        target = self.root/'backups'
        (self.data/'transactions.jsonl').write_bytes(b'{broken}\n')
        before = self.snapshot()
        self.cli('backup','--out-dir',str(target),expected=3)
        self.assertEqual(self.snapshot(),before)
        self.assertFalse(any(target.glob('*.zip')))
        self.seed()
        lock = self.data/'.budget_app.lock'
        lock.write_text('another process')
        self.cli('backup','--out-dir',str(target),expected=4)
        self.assertEqual(lock.read_text(),'another process')
        self.assertFalse(any(target.glob('*.zip')))

    def test_B02_optional_rule_file_is_lazy_and_empty_apply_is_noop(self) -> None:
        self.seed()
        before = self.snapshot()
        inode = (self.data/'transactions.jsonl').stat().st_ino
        self.assertIn('[데이터 없음]',self.cli('recurring','list').stdout)
        self.assertIn('generated=0, skipped=0',self.cli('recurring','apply','--month','2024-01').stdout)
        self.assertFalse((self.data/'recurring.jsonl').exists())
        self.assertEqual(self.snapshot(),before)
        self.assertEqual((self.data/'transactions.jsonl').stat().st_ino,inode)

    def test_B02_rule_add_list_sort_and_validation(self) -> None:
        self.seed()
        first = self.add_rule(day='15',memo=' 급여 ',tags=' monthly,monthly,pay ')
        self.add_rule(day='1',kind='income',category='salary',amount='3000000')
        rules = self.rows('recurring.jsonl')
        self.assertEqual(first['memo'],' 급여 ')
        self.assertEqual(first['tags'],['monthly','pay'])
        output = self.cli('recurring','list').stdout
        ids = re.findall(r'RR-[0-9a-f]{32}',output)
        self.assertEqual(ids,sorted(row['id'] for row in rules))
        baseline = self.snapshot()
        for day in ('0','32','1.5','+1',' 1','１'):
            self.cli('recurring','add','--day',day,'--type','expense','--category','food',
                     '--amount','1',expected=2)
        for args in [('--type','invalid','--category','food','--amount','1'),
                     ('--type','expense','--category','missing','--amount','1'),
                     ('--type','expense','--category','food','--amount','0'),
                     ('--type','expense','--category','food','--amount','1','--tags','a,,b')]:
            self.cli('recurring','add','--day','1',*args,expected=2)
        self.assertEqual(self.snapshot(),baseline)

    def test_B02_stored_optional_rule_fields_default_and_invalid_apply_is_noop(self) -> None:
        self.seed()
        rule = self.add_rule()
        del rule['memo']; del rule['tags']
        self.write_rows('recurring.jsonl',[rule])
        before=self.snapshot()
        self.cli('recurring','apply','--month','2024-13',expected=2)
        self.cli('recurring','apply','--month','2024-1',expected=2)
        self.assertEqual(self.snapshot(),before)
        self.cli('recurring','apply','--month','2024-01')
        generated=self.rows()[0]
        self.assertEqual(generated['memo'],'')
        self.assertEqual(generated['tags'],[])

    def test_B02_month_end_clamping_and_different_months(self) -> None:
        self.seed()
        rule = self.add_rule(day='31')
        for month,expected_date in [('2024-02','2024-02-29'),('2023-02','2023-02-28'),
                                    ('2024-04','2024-04-30'),('2024-01','2024-01-31')]:
            output = self.cli('recurring','apply','--month',month).stdout
            self.assertIn('generated=1, skipped=0',output)
            rows = self.rows()
            target = [row for row in rows if row.get('recurring_month')==month]
            self.assertEqual(len(target),1)
            self.assertEqual(target[0]['date'],expected_date)
            self.assertEqual(target[0]['recurring_id'],rule['id'])
            self.assertNotEqual(target[0]['id'][3:],rule['id'][3:])
        ids = [row['id'] for row in self.rows()]
        self.assertEqual(len(ids),len(set(ids)))

    def test_B02_apply_idempotence_update_provenance_and_delete_regeneration(self) -> None:
        self.seed()
        rule = self.add_rule()
        self.cli('recurring','apply','--month','2024-02')
        original = self.rows()[0]
        before = self.snapshot()
        inode = (self.data/'transactions.jsonl').stat().st_ino
        self.assertIn('generated=0, skipped=1',self.cli('recurring','apply','--month','2024-02').stdout)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual((self.data/'transactions.jsonl').stat().st_ino,inode)
        self.cli('update','--id',original['id'],'--date','2024-03-01','--amount','777',
                 '--memo','수정한 거래','--tags','changed')
        edited = self.rows()[0]
        self.assertEqual(edited['recurring_id'],rule['id'])
        self.assertEqual(edited['recurring_month'],'2024-02')
        self.assertIn('generated=0, skipped=1',self.cli('recurring','apply','--month','2024-02').stdout)
        self.assertEqual(self.rows(),[edited])
        self.cli('delete','--id',original['id'])
        self.assertIn('generated=1, skipped=0',self.cli('recurring','apply','--month','2024-02').stdout)
        regenerated = self.rows()[0]
        self.assertNotEqual(regenerated['id'],original['id'])
        self.assertEqual(regenerated['date'],'2024-02-29')
        self.assertEqual(regenerated['amount'],100)
        self.assertEqual(regenerated['recurring_id'],rule['id'])

    def test_B02_multiple_rules_generated_and_skipped_count(self) -> None:
        self.seed()
        first = self.add_rule(day='1')
        self.cli('recurring','apply','--month','2024-01')
        second = self.add_rule(day='15',category='transport')
        self.assertNotEqual(first['id'],second['id'])
        self.assertIn('generated=1, skipped=1',self.cli('recurring','apply','--month','2024-01').stdout)
        self.assertEqual(len(self.rows()),2)
        self.assertIn('generated=2, skipped=0',self.cli('recurring','apply','--month','2024-02').stdout)
        self.assertEqual(len(self.rows()),4)

    def test_B02_removing_rule_preserves_history_and_readd_is_new_rule(self) -> None:
        self.seed()
        rule = self.add_rule()
        self.cli('recurring','apply','--month','2024-01')
        historical = self.rows()
        self.cli('recurring','remove','--id',rule['id'])
        self.assertEqual(self.rows(),historical)
        self.assertIn(historical[0]['id'],self.cli('list').stdout)
        self.assertIn('generated=0, skipped=0',self.cli('recurring','apply','--month','2024-02').stdout)
        self.cli('recurring','remove','--id',rule['id'],expected=2)
        new = self.add_rule()
        self.assertNotEqual(new['id'],rule['id'])
        self.cli('recurring','apply','--month','2024-01')
        self.assertEqual(len(self.rows()),2)
        self.assertEqual(self.rows()[0],historical[0])

    def test_B02_category_in_rule_cannot_be_removed_even_without_transactions(self) -> None:
        self.seed()
        rule = self.add_rule()
        before = self.snapshot()
        result = self.cli('category','remove',stdin='food\n',expected=2)
        self.assertIn('1',result.stderr)
        self.assertEqual(self.snapshot(),before)
        self.cli('recurring','remove','--id',rule['id'])
        self.cli('category','remove',stdin='food\n')
        self.assertNotIn('food',[row['name'] for row in self.rows('categories.jsonl')])

    def test_B02_rule_corruption_blocks_all_reads_and_preserves_files(self) -> None:
        self.seed()
        valid = self.add_rule()
        variations = [b'\n',b'{broken}\n',b'\xff\n',
                      (json.dumps(valid)+'\n'+json.dumps(valid)+'\n').encode(),
                      (json.dumps(dict(valid,day=True))+'\n').encode(),
                      (json.dumps(dict(valid,day='1'))+'\n').encode(),
                      (json.dumps(dict(valid,amount=True))+'\n').encode(),
                      (json.dumps(dict(valid,day=32))+'\n').encode(),
                      (json.dumps(dict(valid,category='missing'))+'\n').encode(),
                      (json.dumps(dict(valid,tags=['x','x']))+'\n').encode(),
                      (json.dumps(dict(valid,extra=1))+'\n').encode(),
                      ('{"id":"'+valid['id']+'","id":"'+valid['id']+'"}\n').encode()]
        for content in variations:
            with self.subTest(content=content):
                (self.data/'recurring.jsonl').write_bytes(content)
                before = self.snapshot()
                self.cli('list',expected=3)
                self.assertEqual(self.snapshot(),before)
                self.assertFalse((self.data/'.budget_app.lock').exists())

    def test_B02_provenance_must_be_paired_valid_and_unique(self) -> None:
        self.seed()
        rule = self.add_rule()
        self.cli('recurring','apply','--month','2024-01')
        valid = self.rows()[0]
        missing_month = dict(valid); del missing_month['recurring_month']
        missing_id = dict(valid); del missing_id['recurring_id']
        variants = [[missing_month],[missing_id],
                    [dict(valid,recurring_id='invalid')],
                    [dict(valid,recurring_id=None,recurring_month=None)],
                    [dict(valid,recurring_month='2024-13')],
                    [valid,dict(valid,id='TX-'+uuid.uuid4().hex)]]
        for rows in variants:
            with self.subTest(rows=rows):
                self.write_rows('transactions.jsonl',rows)
                before = self.snapshot()
                self.cli('list',expected=3)
                self.assertEqual(self.snapshot(),before)

    def test_B02_recurring_file_export_protection_including_aliases(self) -> None:
        self.seed()
        self.add_rule()
        before = self.snapshot()
        path = self.data/'recurring.jsonl'
        alias = self.root/'rules.csv'; alias.symlink_to(path)
        hard = self.root/'hard.csv'; os.link(path,hard)
        for target in (path,alias,hard):
            self.cli('export','--out',str(target),'--month','2024-01','--overwrite',expected=2)
            self.assertEqual(self.snapshot(),before)

    def test_B02_csv_keeps_minimal_schema_without_recurring_provenance(self) -> None:
        self.seed()
        self.add_rule()
        self.cli('recurring','apply','--month','2024-01')
        source = self.root/'export.csv'
        self.cli('export','--out',str(source),'--month','2024-01')
        with source.open(encoding='utf-8',newline='') as stream:
            records = list(csv.reader(stream))
        self.assertEqual(records[0],['date','type','category','amount','memo','tags'])
        self.assertEqual(len(records),2)
        self.cli('import','--from',str(source))
        rows = self.rows()
        self.assertEqual(len(rows),2)
        self.assertIn('recurring_id',rows[0])
        self.assertNotIn('recurring_id',rows[1])
        self.assertNotIn('recurring_month',rows[1])
        self.assertIn('generated=0, skipped=1',self.cli('recurring','apply','--month','2024-01').stdout)

    def test_B03_table_visual_alignment_and_right_aligned_amount(self) -> None:
        rows = [self.transaction(type='income',category='salary',amount=123456789,memo='한글'),
                self.transaction(amount=1,memo='e\u0301 combining'),
                self.transaction(category='transport',amount=250,memo='Ａwide'),
                self.transaction(amount=25,memo='a\ufe0f variation'),
                self.transaction(amount=2000,memo='a\u20dd enclosing')]
        self.seed(rows)
        before = self.snapshot()
        for command in ('list','search'):
            output = self.cli(command).stdout
            lines = [line for line in output.splitlines() if re.match(r'TX-[0-9a-f]{32}',line)]
            self.assertEqual(len(lines),len(rows))
            positions = []
            amount_ends = []
            for line in lines:
                boundaries = list(re.finditer(r' \| ',line))
                self.assertEqual(len(boundaries),5)
                positions.append([self.display_width(line[:match.start()]) for match in boundaries])
                amount = line[boundaries[3].end():boundaries[4].start()]
                self.assertEqual(amount,amount.rstrip())
                self.assertRegex(amount,r'^\s*[0-9]+$')
                amount_ends.append(self.display_width(line[:boundaries[4].start()]))
            self.assertEqual(positions,[positions[0]]*len(rows))
            self.assertEqual(amount_ends,[amount_ends[0]]*len(rows))
            widths=[self.display_width(line) for line in lines]
            self.assertEqual(widths,[widths[0]]*len(rows))
        self.assertEqual(self.snapshot(),before)

    def test_B03_memo_controls_escape_to_one_line_without_storage_change(self) -> None:
        memo='첫줄\n둘째\t탭\r복귀\x1b[31mESC\x00NUL'
        row=self.transaction(memo=memo)
        self.seed([row])
        before=self.snapshot()
        for command in ('list','search'):
            output=self.cli(command).stdout
            lines=output.splitlines()
            self.assertEqual(len(lines),1)
            self.assertIn(row['id'],lines[0])
            self.assertIn('첫줄',lines[0]); self.assertIn('둘째',lines[0])
            self.assertNotIn('\t',output)
            self.assertNotIn('\x1b',output)
            self.assertNotIn('\x00',output)
            self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.rows()[0]['memo'],memo)


if __name__=='__main__':
    unittest.main()
