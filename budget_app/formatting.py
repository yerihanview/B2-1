"""한글 표시 폭과 제어문자를 고려해 터미널 표를 만든다."""
from __future__ import annotations

import unicodedata

from .models import Transaction


def display_width(text: str) -> int:
    """결합문자는 0칸, 동아시아 전각·광폭 문자는 2칸으로 계산한다."""
    return sum(0 if unicodedata.category(char) in ('Mn', 'Me') or unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def escape_text(text: str) -> str:
    """제어문자를 이스케이프해 메모가 터미널의 한 행에 표시되게 한다."""
    escapes = {'\n': r'\n', '\r': r'\r', '\t': r'\t', '\b': r'\b', '\f': r'\f', '\v': r'\v'}
    parts: list[str] = []

    for char in text:
        if char in escapes:
            parts.append(escapes[char])
        elif unicodedata.category(char) in ('Cc', 'Cf', 'Zl', 'Zp'):
            number = ord(char)

            if number <= 0xff:
                parts.append(f'\\x{number:02x}')
            elif number <= 0xffff:
                parts.append(f'\\u{number:04x}')
            else:
                parts.append(f'\\U{number:08x}')
        else:
            parts.append(char)

    return ''.join(parts)


def _pad(text: str, width: int, *, right: bool = False) -> str:
    """표시 폭을 기준으로 공백을 채워 왼쪽 또는 오른쪽 정렬한다."""
    padding = ' ' * (width - display_width(text))

    return padding + text if right else text + padding


def format_transactions(rows: list[Transaction]) -> list[str]:
    """전달받은 순서를 유지하며 거래를 여섯 열의 표로 만든다."""
    if not rows:
        return ['[데이터 없음]']

    cells = [[row.id, row.date.isoformat(), row.type, row.category,
              str(row.amount), escape_text(row.memo)] for row in rows]
    widths = [max(display_width(row[column]) for row in cells) for column in range(6)]

    return [' | '.join(_pad(text, widths[index], right=index == 4)
                       for index, text in enumerate(row)) for row in cells]
