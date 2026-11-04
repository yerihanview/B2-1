"""전용 임시 복사본에서 교체 실패를 주입해 update/delete의 원본 보존을 시연한다."""
from contextlib import redirect_stderr
import hashlib
from io import StringIO
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

from budget_app.cli import main as cli_main


FILES = ('transactions.jsonl', 'categories.jsonl', 'budgets.jsonl')


def main() -> None:
    """실패 전후 해시와 종료 코드를 비교하고 원본 시연 데이터는 변경하지 않는다."""
    import json

    source = Path(sys.argv[1])
    with tempfile.TemporaryDirectory(prefix='b2-atomic-demo-') as temporary:
        folder = Path(temporary)
        for name in (*FILES, 'recurring.jsonl'):
            if (source / name).exists():
                shutil.copyfile(source / name, folder / name)

        records = (folder / 'transactions.jsonl').read_text(encoding='utf-8').splitlines()
        identifier = json.loads(records[0])['id']

        for action in [('update', '--id', identifier, '--memo', '반영되면 안 되는 메모'),
                       ('delete', '--id', identifier)]:
            before = {name: (folder / name).read_bytes() for name in FILES}
            errors = StringIO()
            with patch('budget_app.repository.os.replace', side_effect=OSError('시연용 교체 실패')):
                with redirect_stderr(errors):
                    code = cli_main(['--data-dir', str(folder), *action])

            print(f'명령: {action[0]} / 종료 코드: {code} (예상 3)')
            print(errors.getvalue().strip())
            assert code == 3
            assert 'Traceback' not in errors.getvalue()
            for name, original in before.items():
                current = (folder / name).read_bytes()
                assert original == current
                if name == 'transactions.jsonl':
                    print('교체 전 SHA-256:', hashlib.sha256(original).hexdigest())
                    print('실패 후 SHA-256:', hashlib.sha256(current).hexdigest())
            assert not list(folder.glob('.budget-*.tmp'))
            assert not (folder / '.budget_app.lock').exists()
            print(f'PASS: {action[0]} 교체 실패 시 원본 보존·임시 파일과 잠금 정리')

    print('주의: 이 시연은 교체 직전 실패만 검증하며 전원 장애 내구성을 보장하지 않는다.')


if __name__ == '__main__':
    main()
