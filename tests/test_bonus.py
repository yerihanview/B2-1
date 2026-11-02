"""Bonus developer tests: ZIP snapshots and new atomic publication paths."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile

from budget_app.errors import DurabilityError, InputError, StorageError
from budget_app.repository import FILES, Repository
from budget_app.service import Service


class BonusStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root / 'data')
        with self.repo.session():
            service = Service(self.repo)
            service.add_category('salary')
            service.add(date='2024-01-01', type='income', category='salary', amount='100', memo='가상')

    def snapshot(self):
        return {name: self.repo.path(name).read_bytes() for name in self.repo.storage_filenames()}

    def test_B01_zip_contains_exact_raw_bytes_hash_manifest_and_no_extras(self):
        # Preserve deliberate whitespace to prove a byte snapshot, not JSON reserialization.
        category = self.repo.path('categories.jsonl')
        category.write_text('{ "name" : "salary" }\n', encoding='utf-8')
        self.repo.path('private-note.txt').write_text('not a ledger file')
        with self.repo.session():
            before = self.snapshot()
            backup = Service(self.repo).backup()
            self.assertRegex(backup.name, r'^backup-[0-9]{8}T[0-9]{12}Z-[a-f0-9]{32}\.zip$')
            with zipfile.ZipFile(backup) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), set(FILES) | {'manifest.json'})
                manifest = json.loads(archive.read('manifest.json'))
                self.assertEqual(manifest['format'], 'budget_app_backup')
                self.assertEqual(manifest['version'], 1)
                self.assertTrue(manifest['created_at'].endswith('Z'))
                self.assertEqual(set(manifest['files']), set(FILES))
                for name, expected in before.items():
                    self.assertEqual(archive.read(name), expected)
                    self.assertEqual(manifest['files'][name], {'size': len(expected), 'sha256': hashlib.sha256(expected).hexdigest()})
            self.assertEqual(self.snapshot(), before)

    def test_B01_existing_archive_is_never_overwritten(self):
        now = datetime(2024, 1, 15, 1, 2, 3, 456789, tzinfo=timezone.utc)
        with self.repo.session(), patch('budget_app.backup.datetime') as clock, patch('budget_app.backup.uuid.uuid4', return_value=uuid.UUID('12345678123442348234123456781234')):
            clock.now.return_value = now
            service = Service(self.repo)
            destination = service.backup(self.root / 'out')
            original = destination.read_bytes()
            with self.assertRaises(InputError):
                service.backup(self.root / 'out')
            self.assertEqual(destination.read_bytes(), original)

    def test_B01_backup_prepublication_failures_leave_no_completed_zip(self):
        out = self.root / 'out'
        with self.repo.session():
            before = self.snapshot()
            injections = [
                patch('budget_app.backup.zipfile.ZipFile.writestr', side_effect=OSError('manifest write')),
                patch('budget_app.repository.os.fsync', side_effect=OSError('file fsync')),
                patch('budget_app.repository.os.link', side_effect=OSError('exclusive publication')),
            ]
            for injection in injections:
                with self.subTest(injection=injection), injection:
                    with self.assertRaises(OSError):
                        Service(self.repo).backup(out)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(list(out.glob('*.zip')))
                self.assertFalse(list(out.glob('.budget-*.tmp')))

    def test_B01_postpublication_failure_preserves_valid_archive(self):
        with self.repo.session():
            before = self.snapshot()
            with patch.object(self.repo, '_sync_directory', side_effect=OSError('directory fsync')):
                with self.assertRaises(DurabilityError) as context:
                    Service(self.repo).backup(self.root / 'out')
            self.assertIn('반영됨', str(context.exception))
            archive_path, = (self.root / 'out').glob('*.zip')
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                for name, expected in before.items():
                    self.assertEqual(archive.read(name), expected)
            self.assertEqual(self.snapshot(), before)

    def test_B02_rule_and_apply_replace_failures_preserve_all_files(self):
        with self.repo.session():
            service = Service(self.repo)
            with patch('budget_app.repository.os.replace', side_effect=OSError('rule replace')):
                with self.assertRaises(OSError):
                    service.add_recurring(31, 'income', 'salary', '100')
            self.assertFalse(self.repo.path('recurring.jsonl').exists())
            service.add_recurring(31, 'income', 'salary', '100')
            before = self.snapshot()
            with patch('budget_app.repository.os.replace', side_effect=OSError('apply replace')):
                with self.assertRaises(OSError):
                    service.apply_recurring('2024-02')
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(list(self.repo.directory.glob('.budget-*.tmp')))

    def test_B02_optional_storage_backup_restore_and_noop_apply(self):
        with self.repo.session():
            service = Service(self.repo)
            self.assertFalse(self.repo.path('recurring.jsonl').exists())
            with patch('budget_app.repository.os.replace', side_effect=AssertionError('no rules no rewrite')):
                self.assertEqual(service.apply_recurring('2024-01'), (0, 0))
            service.add_recurring(31, 'income', 'salary', '100')
            self.assertEqual(service.apply_recurring('2024-02'), (1, 0))
            with patch('budget_app.repository.os.replace', side_effect=AssertionError('all skip no rewrite')):
                self.assertEqual(service.apply_recurring('2024-02'), (0, 1))
            destination = service.backup()
        restored = self.root / 'restored'
        restored.mkdir()
        with zipfile.ZipFile(destination) as archive:
            for name in FILES + ('recurring.jsonl',):
                (restored / name).write_bytes(archive.read(name))
        with Repository(restored).session() as repository:
            self.assertEqual(Service(repository).apply_recurring('2024-02'), (0, 1))
            self.assertEqual(len(repository.recurring), 1)

    def test_B02_duplicate_source_and_partial_source_are_corrupt(self):
        with self.repo.session():
            service = Service(self.repo)
            service.add_recurring(31, 'income', 'salary', '100')
            service.apply_recurring('2024-02')
        target = self.repo.path('transactions.jsonl')
        records = [json.loads(line) for line in target.read_text().splitlines()]
        generated = records[-1]
        duplicate = dict(generated, id='TX-' + uuid.uuid4().hex)
        target.write_text(''.join(json.dumps(row) + '\n' for row in records + [duplicate]))
        with self.assertRaises(StorageError):
            with self.repo.session():
                pass
        del generated['recurring_month']
        target.write_text(json.dumps(generated) + '\n')
        with self.assertRaises(StorageError):
            with self.repo.session():
                pass
