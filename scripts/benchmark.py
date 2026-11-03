"""Reproducible synthetic-data measurements; no personal data or third-party tools."""
from __future__ import annotations

import argparse
import contextlib
from datetime import date, timedelta
import io
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import tempfile
import time
import tracemalloc
import uuid

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261102


def fixture(folder: Path, count: int) -> str:
    """Write bounded-size synthetic rows one at a time, outside the checkout."""
    rng = random.Random(SEED)
    (folder / 'categories.jsonl').write_text('{"name":"food"}\n', encoding='utf-8')
    (folder / 'budgets.jsonl').write_text('', encoding='utf-8')
    first_id = ''
    with (folder / 'transactions.jsonl').open('w', encoding='utf-8') as stream:
        for i in range(count):
            transaction_id = 'TX-' + uuid.UUID(int=i + 1, version=4).hex
            first_id = first_id or transaction_id
            row = dict(id=transaction_id, type='expense',
                       date=(date(2024, 1, 1) + timedelta(days=rng.randrange(366))).isoformat(),
                       category='food', amount=rng.randrange(1, 100001),
                       memo='가상 거래', tags=['meal'])
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    return first_id


def worker(arguments: list[str], input_text: str) -> None:
    sys.path.insert(0, str(ROOT))
    from budget_app.cli import main

    sys.stdin = io.StringIO(input_text)
    tracemalloc.start()
    start = time.perf_counter()
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = main(arguments)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if code:
        raise SystemExit(code)
    command = arguments[2]
    output_rows = None
    if command in ('list', 'search'):
        output_rows = sum(line.startswith('TX-') for line in captured.getvalue().splitlines())
        assert output_rows == int(arguments[arguments.index('--limit') + 1])
    else:
        target = Path(arguments[1]) / 'transactions.jsonl'
        with target.open(encoding='utf-8') as stream:
            if command == 'update':
                assert json.loads(next(stream))['memo'] == '가상 수정'
            else:
                last = None
                for line in stream:
                    last = line
                assert last is not None
                assert json.loads(last)['memo'] == '가상 추가'
    print(json.dumps(dict(seconds=round(elapsed, 6), peak_bytes=peak, exit_code=code,
                          output_rows=output_rows, functional_check=True)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--input', default='', help=argparse.SUPPRESS)
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.worker:
        arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
        worker(arguments, args.input)
        return
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    print(json.dumps(dict(python=sys.version, platform=platform.platform(), sha=sha,
                          seed=SEED, repeat=args.repeat,
                          measurement='CLI main after import; tracemalloc enabled; synthetic data; '
                          'fixture generation excluded; wall time includes fsync'), ensure_ascii=False))
    cases = [(10000, 20, 'list'), (100000, 20, 'list'),
             (100000, 1000, 'list'), (100000, 20, 'search'),
             (100000, None, 'add'), (100000, None, 'update')]
    for count, limit, command in cases:
        for iteration in range(1, args.repeat + 1):
            with tempfile.TemporaryDirectory(prefix='b2-benchmark-') as temporary:
                folder = Path(temporary)
                first_id = fixture(folder, count)
                argv = ['--data-dir', str(folder), command]
                input_text = ''
                if command in ('list', 'search'):
                    argv += ['--limit', str(limit)]
                    if command == 'search':
                        argv += ['--tag', 'meal', '--from', '2024-01-01', '--to', '2024-12-31']
                elif command == 'add':
                    input_text = '2024-01-15\nexpense\nfood\n100\n가상 추가\nmeal\n'
                else:
                    argv += ['--id', first_id, '--memo', '가상 수정']
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), '--worker',
                     '--input', input_text, '--', *argv],
                    cwd=ROOT, text=True, capture_output=True, timeout=300, check=True)
                result = json.loads(completed.stdout)
                result.update(N=count, K=limit, command=command, iteration=iteration)
                print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
