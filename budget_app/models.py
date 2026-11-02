"""Transaction schema and input validation, shared by storage and services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date as Date
from typing import Any

from .errors import InputError

_NAME = re.compile(r"[A-Za-z0-9_-]{1,50}")
_TAG = re.compile(r"[A-Za-z0-9_-]{1,30}")
_ID = re.compile(r"TX-[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}")


def parse_date(value: str) -> Date:
    """Parse an exact ASCII ISO date, including calendar validity."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise InputError("날짜 형식이 올바르지 않습니다.", "YYYY-MM-DD 형식으로 입력하세요.")
    try:
        return Date.fromisoformat(value)
    except ValueError as exc:
        raise InputError("존재하지 않는 날짜입니다.", "유효한 날짜(예: 2024-01-15)를 입력하세요.") from exc


def parse_month(value: str) -> str:
    """Validate a fixed-width year-month."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise InputError("월 형식이 올바르지 않습니다.", "YYYY-MM 형식으로 입력하세요.")
    parse_date(value + "-01")
    return value


def parse_amount(value: str | int) -> int:
    """Accept positive integer values or ASCII decimal input without whitespace."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InputError("금액은 양의 정수여야 합니다.")
    if isinstance(value, str) and not re.fullmatch(r"[0-9]+", value):
        raise InputError("금액은 공백 없는 양의 십진 정수여야 합니다.")
    try:
        result = int(value)
    except ValueError as exc:
        raise InputError("금액을 정수로 처리할 수 없습니다.", "처리 가능한 길이의 양의 정수를 입력하세요.") from exc
    if result <= 0:
        raise InputError("금액은 0보다 커야 합니다.")
    return result


def parse_name(value: str, tag: bool = False) -> str:
    """Normalize input category/tag names, not persisted values."""
    label = "태그" if tag else "카테고리"
    if not isinstance(value, str):
        raise InputError(f"{label}는 문자열이어야 합니다.")
    result = value.strip()
    if not (_TAG if tag else _NAME).fullmatch(result):
        maximum = 30 if tag else 50
        raise InputError(f"{label} 형식이 올바르지 않습니다.", f"영문·숫자·밑줄·하이픈 {maximum}자 이내로 입력하세요.")
    return result


def parse_tags(value: str) -> tuple[str, ...]:
    """Parse comma-separated tags; preserve first occurrence order."""
    if not isinstance(value, str):
        raise InputError("태그 입력은 문자열이어야 합니다.")
    if value == "":
        return ()
    return tuple(dict.fromkeys(parse_name(token, tag=True) for token in value.split(",")))


def validate_memo(value: str) -> str:
    """Preserve memo whitespace and reject non-text or more than 500 characters."""
    if not isinstance(value, str) or len(value) > 500:
        raise InputError("메모는 500자 이하 문자열이어야 합니다.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InputError("메모를 UTF-8로 표현할 수 없습니다.") from exc
    return value


@dataclass(frozen=True)
class Transaction:
    """One validated immutable transaction, independent of storage format."""

    id: str
    type: str
    date: Date
    category: str
    amount: int
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise InputError("거래 id는 TX-와 UUID4 소문자 hex 32자리여야 합니다.")
        if self.type not in ("income", "expense"):
            raise InputError("거래 타입은 income 또는 expense여야 합니다.")
        if type(self.date) is not Date:
            raise InputError("거래 날짜는 유효한 date여야 합니다.")
        if parse_name(self.category) != self.category:
            raise InputError("저장 카테고리의 앞뒤 공백은 허용하지 않습니다.")
        if type(self.amount) is not int:
            raise InputError("거래 금액은 정수여야 합니다.")
        parse_amount(self.amount)
        validate_memo(self.memo)
        if not isinstance(self.tags, tuple):
            raise InputError("모델의 태그는 tuple이어야 합니다.")
        seen: set[str] = set()
        for tag in self.tags:
            if parse_name(tag, tag=True) != tag or tag in seen:
                raise InputError("저장 태그는 공백과 중복 없는 정규형이어야 합니다.")
            seen.add(tag)

    @classmethod
    def from_dict(cls, record: dict[str, Any], stored: bool = False) -> Transaction:
        """Convert raw input or strict persisted JSON to a validated model."""
        required = {"id", "type", "date", "category", "amount"}
        allowed = required | {"memo", "tags"}
        if not isinstance(record, dict) or not required <= record.keys() or record.keys() - allowed:
            raise InputError("거래 필수 필드가 없거나 미정의 필드가 있습니다.")
        category = parse_name(record["category"])
        if stored and category != record["category"]:
            raise InputError("저장 카테고리가 정규형이 아닙니다.")
        raw_tags = record.get("tags", [])
        if isinstance(raw_tags, str) and not stored:
            tags = parse_tags(raw_tags)
        elif isinstance(raw_tags, list):
            parsed_tags = tuple(parse_name(tag, tag=True) for tag in raw_tags)
            tags = tuple(dict.fromkeys(parsed_tags))
            if stored and (tuple(raw_tags) != parsed_tags or parsed_tags != tags):
                raise InputError("저장 태그가 정규형이 아닙니다.")
        else:
            raise InputError("태그는 문자열 목록이어야 합니다.")
        if stored and type(record["amount"]) is not int:
            raise InputError("저장 금액은 정수여야 합니다.")
        return cls(
            id=record["id"], type=record["type"], date=parse_date(record["date"]),
            category=category, amount=parse_amount(record["amount"]),
            memo=validate_memo(record.get("memo", "")), tags=tags,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the documented JSONL record schema."""
        return {
            "id": self.id, "type": self.type, "date": self.date.isoformat(),
            "category": self.category, "amount": self.amount,
            "memo": self.memo, "tags": list(self.tags),
        }
