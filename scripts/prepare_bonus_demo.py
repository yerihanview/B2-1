"""기존 데이터를 건드리지 않고 보너스 시연용 가상 데이터를 새 폴더에 준비한다."""
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """매번 고유한 시연 폴더를 만들고 복사 가능한 절대 경로를 출력한다."""
    parent = ROOT / 'data'
    parent.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix='bonus-demo-', dir=parent))

    for source in (ROOT / 'demos' / 'mission' / 'data').glob('*.jsonl'):
        shutil.copyfile(source, destination / source.name)

    print(destination)


if __name__ == '__main__':
    main()
