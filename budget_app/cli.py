"""Argument parsing and terminal presentation, with no direct data-file access."""
from __future__ import annotations

import argparse
import calendar
from decimal import Decimal
from typing import Sequence

from .decorators import user_errors
from .errors import InputError
from .formatting import escape_text, format_transactions
from .models import Transaction, parse_amount, parse_date, parse_month, parse_name, parse_tags, validate_memo
from .repository import Repository
from .service import Service


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault('allow_abbrev', False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise InputError(message, '명령과 필수 옵션을 확인하세요. --help로 사용법을 볼 수 있습니다.')


def _day(value: str) -> str:
    return parse_date(value).isoformat()


def _amount(value: str) -> str:
    parse_amount(value)
    return value


def _memo(value: str) -> str:
    return validate_memo(value)


def _tags(value: str) -> str:
    parse_tags(value)
    return value


def _limit(value: str) -> int:
    number = parse_amount(value)
    if number > 1000:
        raise InputError('limit은 1~1000이어야 합니다.')
    return number


def _top(value: str) -> int:
    number = parse_amount(value)
    if number > 100:
        raise InputError('top은 1~100이어야 합니다.')
    return number


def _day_of_month(value: str) -> int:
    day = parse_amount(value)
    if day > 31:
        raise InputError('day는 1~31이어야 합니다.')
    return day


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(prog='python -m budget_app', description='파일 기반 용돈 기입장')
    parser.add_argument('--data-dir', default='./data', help='저장 폴더 (하위 명령 앞에 지정)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('add', help='대화형 거래 추가')
    listing = commands.add_parser('list', help='최근 거래 조회')
    listing.add_argument('--limit', type=_limit, default=20)
    search = commands.add_parser('search', help='거래 검색 (모든 조건 AND)')
    search.add_argument('--from', dest='from_date', type=_day)
    search.add_argument('--to', dest='to_date', type=_day)
    search.add_argument('--category', type=parse_name)
    search.add_argument('--type', choices=('income', 'expense'))
    search.add_argument('--q')
    search.add_argument('--tag', type=lambda text: parse_name(text, tag=True))
    search.add_argument('--limit', type=_limit, default=20)
    summary = commands.add_parser('summary', help='월 수입·지출·예산 요약')
    summary.add_argument('--month', type=parse_month, required=True)
    summary.add_argument('--top', type=_top, default=3)
    budget = commands.add_parser('budget', help='월 예산 관리')
    budget_commands = budget.add_subparsers(dest='action', required=True)
    setting = budget_commands.add_parser('set', help='월 예산 저장')
    setting.add_argument('--month', type=parse_month, required=True)
    setting.add_argument('--amount', type=_amount, required=True)
    category = commands.add_parser('category', help='카테고리 관리')
    category_commands = category.add_subparsers(dest='action', required=True)
    for name in ('add', 'list', 'remove'):
        category_commands.add_parser(name)
    update = commands.add_parser('update', help='ID에 해당하는 거래 수정')
    update.add_argument('--id', required=True)
    update.add_argument('--date', type=_day)
    update.add_argument('--type', choices=('income', 'expense'))
    update.add_argument('--category', type=parse_name)
    update.add_argument('--amount', type=_amount)
    update.add_argument('--memo', type=_memo)
    update.add_argument('--tags', type=_tags)
    delete = commands.add_parser('delete', help='거래 삭제 (확인 없이 실행, 자동 복구 없음)')
    delete.add_argument('--id', required=True)
    exporting = commands.add_parser('export', help='CSV 내보내기 (파일 순서)')
    exporting.add_argument('--out', required=True)
    exporting.add_argument('--month', type=parse_month)
    exporting.add_argument('--from', dest='from_date', type=_day)
    exporting.add_argument('--to', dest='to_date', type=_day)
    exporting.add_argument('--overwrite', action='store_true')
    importing = commands.add_parser('import', help='CSV 가져오기 (같은 파일 재실행 시 중복 추가)')
    importing.add_argument('--from', dest='source', required=True)
    backup = commands.add_parser('backup', help='원본 바이트와 해시 manifest를 ZIP으로 백업')
    backup.add_argument('--out-dir', help='백업 저장 폴더 (기본: data-dir/backups)')
    recurring = commands.add_parser('recurring', help='월별 반복 거래 규칙 관리')
    recurring_commands = recurring.add_subparsers(dest='action', required=True)
    recurring_add = recurring_commands.add_parser('add', help='반복 규칙 추가')
    recurring_add.add_argument('--day', type=_day_of_month, required=True)
    recurring_add.add_argument('--type', choices=('income', 'expense'), required=True)
    recurring_add.add_argument('--category', type=parse_name, required=True)
    recurring_add.add_argument('--amount', type=_amount, required=True)
    recurring_add.add_argument('--memo', type=_memo, default='')
    recurring_add.add_argument('--tags', type=_tags, default='')
    recurring_commands.add_parser('list', help='반복 규칙 ID순 조회')
    recurring_remove = recurring_commands.add_parser('remove', help='규칙만 삭제 (생성된 거래 보존)')
    recurring_remove.add_argument('--id', required=True)
    recurring_apply = recurring_commands.add_parser('apply', help='지정 월의 미생성 반복 거래만 생성')
    recurring_apply.add_argument('--month', type=parse_month, required=True)
    return parser


def _range(args: argparse.Namespace) -> tuple[str, str]:
    if args.month:
        if args.from_date or args.to_date:
            raise InputError('--month와 --from/--to를 섞을 수 없습니다.')
        year, month = map(int, args.month.split('-'))
        return args.month + '-01', args.month + f'-{calendar.monthrange(year, month)[1]:02d}'
    if not args.from_date or not args.to_date:
        raise InputError('export에는 --month 또는 --from/--to 쌍이 필요합니다.')
    if args.from_date > args.to_date:
        raise InputError('시작 날짜가 끝 날짜보다 늦습니다.')
    return args.from_date, args.to_date


def _show_transactions(transactions: list[Transaction]) -> None:
    for line in format_transactions(transactions):
        print(line)


@user_errors
def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    changes = {}
    if args.command == 'update':
        changes = {name: getattr(args, name) for name in
                   ('date', 'type', 'category', 'amount', 'memo', 'tags')
                   if getattr(args, name) is not None}
        if not changes:
            raise InputError('변경 필드를 한 개 이상 지정하세요.')
    interval = _range(args) if args.command == 'export' else None
    if args.command == 'search' and args.from_date and args.to_date and args.from_date > args.to_date:
        raise InputError('시작 날짜가 끝 날짜보다 늦습니다.')
    repository = Repository(args.data_dir)
    with repository.session():
        service = Service(repository)
        if args.command == 'add':
            fields = dict(zip(('date', 'type', 'category', 'amount', 'memo', 'tags'),
                              (input(prompt) for prompt in ('날짜(YYYY-MM-DD): ', '타입(income/expense): ',
                               '카테고리: ', '금액(양수 정수): ', '메모(선택): ', '태그(쉼표 구분): '))))
            transaction = service.add(**fields)
            print(f'[저장 완료] id={transaction.id}')
        elif args.command in ('list', 'search'):
            filters = {name: getattr(args, name) for name in
                       ('from_date', 'to_date', 'category', 'type', 'q', 'tag')} if args.command == 'search' else {}
            _show_transactions(service.select(limit=args.limit, **filters))
        elif args.command == 'summary':
            result = service.summary(args.month, args.top)
            if not result['count']:
                print(f'[데이터 없음] {args.month}')
            print(f"총 수입: {Decimal(result['income']):f}원\n총 지출: {Decimal(result['expense']):f}원\n잔액: {Decimal(result['balance']):f}원")
            if result['budget'] is not None:
                print(f"예산: {Decimal(result['budget']):f}원 (사용률 {result['usage']}%)")
                if result['exceeded']:
                    print('[경고] 예산 초과')
            print(f'지출 TOP {args.top}')
            for index, (name, amount) in enumerate(result['top'], 1):
                print(f'{index}) {name} {Decimal(amount):f}원')
        elif args.command == 'budget':
            service.set_budget(args.month, args.amount)
            print(f'[저장 완료] {args.month} 예산 {args.amount}원')
        elif args.command == 'category':
            if args.action == 'list':
                if not repository.categories:
                    print('[데이터 없음] category add로 등록하세요.')
                for name in sorted(repository.categories):
                    print(f'- {name}')
            else:
                name = input('카테고리명: ')
                if args.action == 'add':
                    name = service.add_category(name)
                    print(f'[저장 완료] category={name}')
                else:
                    service.remove_category(name)
                    print(f'[삭제 완료] category={name.strip()}')
        elif args.command == 'update':
            transaction = service.update(args.id, **changes)
            print(f'[수정 완료] id={transaction.id}')
        elif args.command == 'delete':
            service.delete(args.id)
            print(f'[삭제 완료] id={args.id}')
        elif args.command == 'backup':
            destination = service.backup(args.out_dir)
            print(f'[백업 완료] {destination}')
        elif args.command == 'recurring':
            if args.action == 'add':
                rule = service.add_recurring(args.day, args.type, args.category, args.amount,
                                             memo=args.memo, tags=args.tags)
                print(f'[저장 완료] id={rule.id}')
            elif args.action == 'list':
                rules = service.list_recurring()
                if not rules:
                    print('[데이터 없음]')
                for rule in rules:
                    print(f'{rule.id} | {rule.day} | {rule.type} | {rule.category} | '
                          f'{rule.amount} | {escape_text(rule.memo)} | {",".join(rule.tags)}')
            elif args.action == 'remove':
                service.remove_recurring(args.id)
                print(f'[삭제 완료] id={args.id}')
            else:
                generated, skipped = service.apply_recurring(args.month)
                print(f'[완료] generated={generated}, skipped={skipped}')
        elif args.command == 'import':
            count = service.import_csv(args.source)
            print(f'[완료] imported={count}, skipped=0')
        elif args.command == 'export':
            count = service.export_csv(args.out, from_date=interval[0], to_date=interval[1],
                               overwrite=args.overwrite)
            print(f'[완료] exported={count} {args.out}')
    return 0
