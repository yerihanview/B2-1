"""Demonstrate all four bonus missions with disposable synthetic data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print('Python:', sys.version.replace('\n', ' '))
    print('SHA:', subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    print('Synthetic data only; <TEMP> paths are ephemeral.')
    with tempfile.TemporaryDirectory(prefix='b2-bonus-demo-') as temporary:
        folder = Path(temporary)
        data = folder / 'data'

        def run(*arguments: str, stdin: str = '', directory: Path = data) -> str:
            argv = [sys.executable, '-m', 'budget_app', '--data-dir', str(directory), *arguments]
            completed = subprocess.run(argv, input=stdin, text=True, encoding='utf-8',
                                       capture_output=True, cwd=ROOT, timeout=30)
            print('$ python -m budget_app --data-dir', str(directory).replace(temporary, '<TEMP>'),
                  ' '.join(arguments).replace(temporary, '<TEMP>'))
            if stdin:
                print('stdin:', repr(stdin))
            print('exit:', completed.returncode)
            print((completed.stdout + completed.stderr).replace(temporary, '<TEMP>').rstrip())
            assert completed.returncode == 0, completed.stderr
            assert 'Traceback' not in completed.stderr
            return completed.stdout

        run('category', 'add', stdin='salary\n')
        run('category', 'add', stdin='food\n')
        registered = run('recurring', 'add', '--day', '31', '--type', 'income',
                         '--category', 'salary', '--amount', '3000000',
                         '--memo', '가상 월급', '--tags', 'monthly')
        rule_id_match = re.search(r'RR-[0-9a-f]{32}', registered)
        assert rule_id_match is not None
        rule_id = rule_id_match.group()
        run('recurring', 'list')
        assert 'generated=1' in run('recurring', 'apply', '--month', '2024-02')
        transactions = data / 'transactions.jsonl'
        before = transactions.read_bytes()
        assert 'generated=0' in run('recurring', 'apply', '--month', '2024-02')
        assert transactions.read_bytes() == before
        row = json.loads(before)
        assert row['date'] == '2024-02-29'
        assert row['recurring_id'] == rule_id and row['recurring_month'] == '2024-02'
        print('PASS: leap-month clipping and repeat-apply idempotence')
        run('add', stdin='2024-02-29\nexpense\nfood\n15000\n한글 점심\nmeal\n')
        run('list')
        run('search', '--from', '2024-02-01', '--to', '2024-02-29')
        run('backup')
        archives = list((data / 'backups').glob('*.zip'))
        assert len(archives) == 1
        restored = folder / 'restored'
        restored.mkdir()
        with zipfile.ZipFile(archives[0]) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            assert manifest['format'] == 'budget_app_backup' and manifest['version'] == 1
            assert set(archive.namelist()) == set(manifest['files']) | {'manifest.json'}
            for name, information in manifest['files'].items():
                assert name in ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl', 'recurring.jsonl')
                payload = archive.read(name)
                assert payload == (data / name).read_bytes()
                assert hashlib.sha256(payload).hexdigest() == information['sha256']
                assert len(payload) == information['size']
                (restored / name).write_bytes(payload)
        print('PASS: backup original bytes, SHA-256 manifest, no locks/previous archives')
        assert rule_id in run('recurring', 'list', directory=restored)
        assert row['id'] in run('list', directory=restored)
        assert 'generated=0' in run('recurring', 'apply', '--month', '2024-02', directory=restored)
        run('recurring', 'remove', '--id', rule_id)
        assert row['id'] in run('list')
        print('PASS: restored CLI state and rule removal preserves past transactions')
        run('backup')
        assert len(list((data / 'backups').glob('*.zip'))) == 2
        print('PASS: repeated backup preserves prior archive')
        print('B04 atomic failure boundaries: see full test logs for injected failure assertions.')


if __name__ == '__main__':
    main()
