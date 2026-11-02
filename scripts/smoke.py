"""Run a real multi-process CLI demonstration with disposable synthetic data."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print('Python:', sys.version.replace('\n', ' '))
    print('SHA:', subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    print('Synthetic data only; <TEMP> paths are ephemeral.')
    with tempfile.TemporaryDirectory(prefix='b2-smoke-') as temporary:
        folder = Path(temporary)
        data = folder / 'data'

        def run(*args: str, text: str = '', expected: int = 0) -> str:
            argv = [sys.executable, '-m', 'budget_app', '--data-dir', str(data), *args]
            completed = subprocess.run(argv, input=text, text=True, encoding='utf-8',
                                       capture_output=True, cwd=ROOT, timeout=30)
            print('$ python -m budget_app --data-dir <TEMP>/data',
                  ' '.join(args).replace(temporary, '<TEMP>'))
            if text:
                print('stdin:', repr(text))
            print('exit:', completed.returncode)
            if completed.stdout:
                print(completed.stdout.replace(temporary, '<TEMP>').rstrip())
            if completed.stderr:
                print('stderr:', completed.stderr.replace(temporary, '<TEMP>').rstrip())
            assert completed.returncode == expected, completed.stderr
            assert 'Traceback' not in completed.stderr
            return completed.stdout

        for name in ('food', 'salary', 'unused'):
            run('category', 'add', text=name + '\n')
        run('category', 'list')
        run('category', 'remove', text='unused\n')
        income = run('add', text='2024-01-01\nincome\nsalary\n100000\n가상 수입\n\n')
        expense = run('add', text='2024-01-15\nexpense\nfood\n15000\n점심\nmeal,weekday\n')
        income_id = re.search(r'TX-[0-9a-f]{32}', income).group()
        expense_id = re.search(r'TX-[0-9a-f]{32}', expense).group()
        listed = run('list', '--limit', '20')
        assert listed.index(expense_id) < listed.index(income_id)
        searched = run('search', '--from', '2024-01-15', '--to', '2024-01-15', '--tag', 'meal')
        assert expense_id in searched and income_id not in searched
        run('budget', 'set', '--month', '2024-01', '--amount', '10000')
        summary = run('summary', '--month', '2024-01')
        assert '150.0%' in summary and '경고' in summary
        run('update', '--id', expense_id, '--memo', '수정된 가상 점심', '--tags', '')
        exported = folder / 'export.csv'
        run('export', '--out', str(exported), '--month', '2024-01')
        with exported.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.reader(stream))
        assert rows[0] == ['date', 'type', 'category', 'amount', 'memo', 'tags']
        assert len(rows) == 3
        run('import', '--from', str(exported))
        transaction_file = data / 'transactions.jsonl'
        assert len(transaction_file.read_text(encoding='utf-8').splitlines()) == 4
        before = hashlib.sha256(transaction_file.read_bytes()).hexdigest()
        broken = folder / 'broken.csv'
        broken.write_text('date,type,category,amount,memo,tags\n'
                          '2024-01-01,expense,food,10,정상,\n'
                          '2024-01-01,expense,food,-1,오류,\n', encoding='utf-8')
        run('import', '--from', str(broken), expected=2)
        assert hashlib.sha256(transaction_file.read_bytes()).hexdigest() == before
        print('PASS: mixed CSV rollback preserves original SHA-256')
        run('category', 'remove', text='food\n', expected=2)
        run('delete', '--id', expense_id)
        run('delete', '--id', expense_id, expected=2)
        assert all((data / name).exists() for name in
                   ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl'))
        for path in sorted(data.glob('*.jsonl')):
            records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            print('PERSISTENCE:', path.name, 'records=', len(records))
        # Every invocation above is a fresh process; state survives all restarts.
        final = run('summary', '--month', '2024-01')
        assert '150.0%' in final
        print('PASS: CLI flow, CSV, errors, rollback, three-file persistence across fresh processes')


if __name__ == '__main__':
    main()
