"""Developer CSV atomicity and strict record tests."""
import csv
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from budget_app.csv_io import HEADER, export_csv, import_csv
from budget_app.errors import InputError, StorageError
from budget_app.repository import Repository
from budget_app.service import Service


class CSVTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root / 'data')
        with self.repo.session():
            service = Service(self.repo)
            service.add_category('food')
            service.add(date='2024-01-15', type='expense', category='food', amount='1')

    def test_T26_import_replace_failure_keeps_original_and_cleans_stage(self):
        source = self.root / 'input.csv'
        source.write_text(','.join(HEADER) + '\n2024-01-16,expense,food,20,가상,m\n')
        before = self.repo.path('transactions.jsonl').read_bytes()
        with self.repo.session(), patch('budget_app.repository.os.replace', side_effect=OSError('replace failure')):
            with self.assertRaises(OSError):
                import_csv(self.repo, source)
        self.assertEqual(before, self.repo.path('transactions.jsonl').read_bytes())
        self.assertFalse(list(self.repo.directory.glob('.budget-*.tmp')))

    def test_T26_export_replace_failure_keeps_existing_csv(self):
        target = self.root / 'output.csv'
        target.write_bytes(b'original')
        with self.repo.session(), patch('budget_app.repository.os.replace', side_effect=OSError('replace failure')):
            with self.assertRaises(OSError):
                export_csv(self.repo, target, from_date='2024-01-01', to_date='2024-01-31', overwrite=True)
        self.assertEqual(b'original', target.read_bytes())
        self.assertFalse(list(self.root.glob('.budget-*.tmp')))

    def test_T24_race_created_destination_is_never_clobbered(self):
        target = self.root / 'race.csv'
        with self.repo.session():
            def writer(handle):
                handle.write('new output')
                target.write_text('race-created')
            with self.assertRaises(InputError):
                self.repo.atomic_write(target, writer, overwrite=False, export=True)
        self.assertEqual(target.read_text(), 'race-created')

    def test_T25_invalid_quote_rolls_back_and_header_only_no_replace(self):
        source = self.root / 'input.csv'
        source.write_text(','.join(HEADER) + '\n2024-01-15,expense,food,1,"unclosed\n')
        before = self.repo.path('transactions.jsonl').read_bytes()
        with self.repo.session():
            with self.assertRaises(InputError):
                import_csv(self.repo, source)
            self.assertEqual(before, self.repo.path('transactions.jsonl').read_bytes())
            source.write_text(','.join(HEADER) + '\n')
            with patch('budget_app.repository.os.replace', side_effect=AssertionError('must not rewrite')):
                self.assertEqual(import_csv(self.repo, source), 0)

    def test_T09_import_ids_avoid_existing_and_within_batch_collisions(self):
        source = self.root / 'input.csv'
        source.write_text(','.join(HEADER) + '\n2024-01-16,expense,food,20,a,m\n2024-01-17,expense,food,30,b,m\n')
        first = uuid.uuid4()
        second = uuid.uuid4()
        with self.repo.session():
            existing = uuid.UUID(next(self.repo.iter_transactions()).id[3:])
            with patch('budget_app.service.uuid4', side_effect=[existing, first, first, second]):
                self.assertEqual(import_csv(self.repo, source), 2)
            ids = [row.id for row in self.repo.iter_transactions()]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(ids[-2:], ['TX-' + first.hex, 'TX-' + second.hex])

    def test_T09_import_collision_exhaustion_preserves_original(self):
        source = self.root / 'input.csv'
        source.write_text(','.join(HEADER) + '\n2024-01-16,expense,food,20,a,m\n')
        before = self.repo.path('transactions.jsonl').read_bytes()
        with self.repo.session():
            existing = uuid.UUID(next(self.repo.iter_transactions()).id[3:])
            with patch('budget_app.service.uuid4', return_value=existing):
                with self.assertRaises(StorageError):
                    import_csv(self.repo, source)
        self.assertEqual(before, self.repo.path('transactions.jsonl').read_bytes())

    def test_T25_reader_field_limit_is_restored(self):
        source = self.root / 'input.csv'
        source.write_text(','.join(HEADER) + '\n2024-01-16,expense,food,20,a,m\n')
        previous = csv.field_size_limit()
        with self.repo.session():
            self.assertEqual(import_csv(self.repo, source), 1)
        self.assertEqual(csv.field_size_limit(), previous)
