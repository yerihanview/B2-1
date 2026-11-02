"""Terminal tables with explicit Unicode display-width and control escaping."""
from __future__ import annotations

import unicodedata

from .models import Transaction


def display_width(text: str) -> int:
    """Count combining marks as zero and East Asian wide/fullwidth as two."""
    return sum(0 if unicodedata.category(char) in ('Mn', 'Me') or unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def escape_text(text: str) -> str:
    """Keep memo contents on one terminal line without emitting control codes."""
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
    padding = ' ' * (width - display_width(text))
    return padding + text if right else text + padding


def format_transactions(rows: list[Transaction]) -> list[str]:
    """Render the existing six columns, preserving supplied sort order."""
    if not rows:
        return ['[데이터 없음]']
    cells = [[row.id, row.date.isoformat(), row.type, row.category,
              str(row.amount), escape_text(row.memo)] for row in rows]
    widths = [max(display_width(row[column]) for row in cells) for column in range(6)]
    return [' | '.join(_pad(text, widths[index], right=index == 4)
                       for index, text in enumerate(row)) for row in cells]
