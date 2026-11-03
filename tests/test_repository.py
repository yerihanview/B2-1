"""Developer storage tests: rollback, publication boundaries and corruption."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import is_dataclass
from io import StringIO
import ast
import inspect
import json
import sys
from pathlib import Path
import tempfile
import typing
import unittest
from unittest.mock import patch
import uuid

from budget_app.cli import main
from budget_app.errors import DurabilityError, StorageError
from budget_app.models import Transaction
from budget_app.repository import FILES, Repository
from budget_app.service import Service


def write_text(text: str) -> typing.Callable[[typing.TextIO], None]:
    def writer(handle: typing.TextIO) -> None:
        handle.write(text)
    return writer


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Repository(self.root / 'data')
        with self.repo.session():
            service = Service(self.repo)
            service.add_category('food')
            service.add(date='2024-01-15', type='expense', category='food', amount='15')

    def snapshot(self):
        return {name: self.repo.path(name).read_bytes() for name in FILES}

    def test_T16_replace_failure_preserves_each_mutation_target(self):
        actions = [
            lambda s: s.add(date='2024-01-16', type='income', category='food', amount='3'),
            lambda s: s.update(next(s.repo.iter_transactions()).id, memo='changed'),
            lambda s: s.delete(next(s.repo.iter_transactions()).id),
            lambda s: s.add_category('other'),
            lambda s: s.remove_category('unused'),
            lambda s: s.set_budget('2024-01', '10'),
        ]
        with self.repo.session():
            Service(self.repo).add_category('unused')
        for action in actions:
            with self.subTest(action=action):
                before = self.snapshot()
                with self.repo.session(), patch('budget_app.repository.os.replace', side_effect=OSError('replace failure')):
                    with self.assertRaises(OSError):
                        action(Service(self.repo))
                self.assertEqual(before, self.snapshot())
                self.assertFalse(list(self.repo.directory.glob('.budget-*.tmp')))
                self.assertFalse(self.repo.lock_path.exists())

    def test_T26_writer_flush_fsync_failures_leave_original(self):
        with self.repo.session():
            target = self.repo.path('transactions.jsonl')
            before = target.read_bytes()
            def bad_writer(handle):
                handle.write('partial')
                raise OSError('write failure')
            with self.assertRaises(OSError):
                self.repo.atomic_write(target, bad_writer)
            self.assertEqual(target.read_bytes(), before)
            with patch('budget_app.repository.os.fsync', side_effect=OSError('fsync failure')):
                with self.assertRaises(OSError):
                    self.repo.atomic_write(target, write_text('partial'))
            self.assertEqual(target.read_bytes(), before)
            real_fdopen = __import__('os').fdopen
            class FlushFailure:
                def __init__(self, handle): self.handle = handle
                def __enter__(self): return self
                def __exit__(self, *args): return self.handle.__exit__(*args)
                def write(self, text): return self.handle.write(text)
                def flush(self): raise OSError('flush failure')
            def bad_fdopen(*args, **kwargs):
                return FlushFailure(real_fdopen(*args, **kwargs))
            with patch('budget_app.repository.os.fdopen', side_effect=bad_fdopen):
                with self.assertRaises(OSError):
                    self.repo.atomic_write(target, write_text('partial'))
            self.assertEqual(target.read_bytes(), before)
        self.assertFalse(list(self.repo.directory.glob('.budget-*.tmp')))

    def test_T26_post_replace_fsync_reports_committed_change(self):
        with self.repo.session():
            service = Service(self.repo)
            with patch.object(self.repo, '_sync_directory', side_effect=OSError('directory fsync')):
                with self.assertRaises(DurabilityError) as context:
                    service.set_budget('2024-01', 100)
            self.assertEqual(context.exception.code, 3)
            self.assertIn('반영됨', str(context.exception))
            self.assertEqual(json.loads(self.repo.path('budgets.jsonl').read_text())['amount'], 100)

    def test_T26_post_exclusive_link_cleanup_failure_is_committed(self):
        destination = self.root / 'new.csv'
        real_unlink = Path.unlink
        failed = False
        def fail_first_temp_unlink(path, *args, **kwargs):
            nonlocal failed
            if path.name.startswith('.budget-') and not failed:
                failed = True
                raise OSError('unlink after successful link')
            return real_unlink(path, *args, **kwargs)
        with self.repo.session(), patch.object(Path, 'unlink', fail_first_temp_unlink):
            with self.assertRaises(DurabilityError):
                self.repo.atomic_write(destination, write_text('published'), overwrite=False, export=True)
        self.assertEqual(destination.read_text(), 'published')
        self.assertFalse(list(self.root.glob('.budget-*.tmp')))

    def test_T22_duplicate_object_keys_extra_fields_and_nonobjects(self):
        target = self.repo.path('categories.jsonl')
        for content in ['{"name":"food","name":"food"}\n', '{"name":"food","extra":1}\n', '[]\n']:
            with self.subTest(content=content):
                target.write_text(content)
                with self.assertRaises(StorageError):
                    with self.repo.session():
                        pass
                self.assertEqual(target.read_text(), content)
                self.assertFalse(self.repo.lock_path.exists())

    def test_T23_foreign_replacement_lock_not_deleted(self):
        with self.repo.session():
            self.repo.lock_path.unlink()
            self.repo.lock_path.write_text('foreign owner')
            # Ensure a distinct inode, even on a filesystem that immediately reuses deleted inodes.
            foreign = self.repo.directory / 'foreign'
            foreign.write_text('foreign owner')
            foreign.replace(self.repo.lock_path)
        self.assertTrue(self.repo.lock_path.exists())
        self.assertEqual(self.repo.lock_path.read_text(), 'foreign owner')

    def test_T18_decorator_wraps_and_storage_errors_have_no_traceback(self):
        self.assertTrue(hasattr(main, '__wrapped__'))
        captured = StringIO()
        with redirect_stderr(captured), patch('budget_app.repository.os.open', side_effect=PermissionError('blocked')):
            result = main(['--data-dir', str(self.repo.directory), 'list'])
        self.assertEqual(result, 3)
        self.assertIn('[힌트]', captured.getvalue())
        self.assertNotIn('Traceback', captured.getvalue())

    def test_S_public_apis_have_runtime_resolvable_type_hints(self):
        self.assertTrue(is_dataclass(Transaction))
        for owner in (Repository, Transaction):
            for name, member in owner.__dict__.items():
                if name.startswith('_') or not callable(member):
                    continue
                self.assertTrue(typing.get_type_hints(member), (owner, name))

    def test_T22_excessively_nested_json_is_storage_error_without_traceback(self):
        content = '[' * 20000 + '0' + ']' * 20000
        self.repo.path('transactions.jsonl').write_text(content)
        captured = StringIO()
        with redirect_stderr(captured):
            result = main(['--data-dir', str(self.repo.directory), 'list'])
        self.assertEqual(result, 3)
        self.assertNotIn('Traceback', captured.getvalue())
        self.assertEqual(self.repo.path('transactions.jsonl').read_text(), content)

    def test_T24_export_symlink_loop_is_storage_error(self):
        target = self.root / 'loop.csv'
        target.symlink_to(target)
        captured = StringIO()
        with redirect_stderr(captured):
            result = main(['--data-dir', str(self.repo.directory), 'export', '--out',
                           str(target), '--month', '2024-01', '--overwrite'])
        self.assertEqual(result, 3)
        self.assertNotIn('Traceback', captured.getvalue())
        self.assertTrue(target.is_symlink())

    def test_T26_lock_cleanup_after_commit_reports_change(self):
        captured = StringIO()
        real_unlink = Path.unlink
        def fail_lock_cleanup(path, *args, **kwargs):
            if path.name == '.budget_app.lock':
                raise PermissionError('lock cleanup blocked')
            return real_unlink(path, *args, **kwargs)
        with redirect_stderr(captured), redirect_stdout(StringIO()), patch.object(Path, 'unlink', fail_lock_cleanup):
            result = main(['--data-dir', str(self.repo.directory), 'budget', 'set',
                           '--month', '2024-01', '--amount', '200'])
        self.assertEqual(result, 3)
        self.assertIn('반영됨', captured.getvalue())
        self.assertIn('자동 재실행하지', captured.getvalue())
        self.assertEqual(json.loads(self.repo.path('budgets.jsonl').read_text())['amount'], 200)
        self.assertTrue(self.repo.lock_path.exists())

    def test_T17_repository_is_a_real_consumable_generator(self):
        with self.repo.session():
            rows = self.repo.iter_transactions()
            self.assertTrue(inspect.isgenerator(rows))
            self.assertIsInstance(next(rows), Transaction)
            with self.assertRaises(StopIteration):
                next(rows)

    def test_S_application_imports_only_standard_library_or_relative_modules(self):
        package = Path(__file__).resolve().parents[1] / 'budget_app'
        modules = list(package.glob('*.py'))
        self.assertGreaterEqual(len(modules), 3)
        for module in modules:
            tree = ast.parse(module.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    assert node.module is not None
                    roots = [node.module.split('.')[0]]
                else:
                    continue
                for root in roots:
                    self.assertIn(root, sys.stdlib_module_names, (module.name, root))
