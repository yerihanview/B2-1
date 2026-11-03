"""거래·반복 규칙 모델과 공통 입력 검증을 정의한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date as Date
from typing import Any

from .errors import InputError

_NAME = re.compile(r"[가-힣A-Za-z0-9_-]{1,50}")
_TAG = re.compile(r"[가-힣A-Za-z0-9_-]{1,30}")
_ID = re.compile(r"TX-[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}")
_RECURRING_ID = re.compile(r"RR-[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}")


def parse_date(value: str) -> Date:
    """실제 달력에 존재하는 YYYY-MM-DD 날짜인지 검증한다."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise InputError("날짜 형식이 올바르지 않습니다.", "YYYY-MM-DD 형식으로 입력하세요.")

    try:
        return Date.fromisoformat(value)
    except ValueError as exc:
        raise InputError("존재하지 않는 날짜입니다.", "유효한 날짜(예: 2024-01-15)를 입력하세요.") from exc


def parse_month(value: object) -> str:
    """입력의 문자열 여부와 YYYY-MM 형식을 검증한다."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise InputError("월 형식이 올바르지 않습니다.", "YYYY-MM 형식으로 입력하세요.")

    parse_date(value + "-01")

    return value


def parse_amount(value: str | int) -> int:
    """공백 없는 십진 문자열이나 정수에서 양의 정수 금액을 얻는다."""
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
    """카테고리·태그 입력의 공백을 정리하고 문자와 길이를 검증한다."""
    label = "태그" if tag else "카테고리"

    if not isinstance(value, str):
        raise InputError(f"{label}는 문자열이어야 합니다.")

    result = value.strip()

    if not (_TAG if tag else _NAME).fullmatch(result):
        maximum = 30 if tag else 50
        raise InputError(f"{label} 형식이 올바르지 않습니다.", f"한글(가-힣)·영문·숫자·밑줄·하이픈 1~{maximum}자로 입력하세요.")

    return result


def parse_tags(value: str) -> tuple[str, ...]:
    """쉼표로 구분한 태그를 검증하고 최초 순서를 유지하며 중복을 제거한다."""
    if not isinstance(value, str):
        raise InputError("태그 입력은 문자열이어야 합니다.")

    if value == "":
        return ()

    return tuple(dict.fromkeys(parse_name(token, tag=True) for token in value.split(",")))


def validate_memo(value: str) -> str:
    """메모의 공백은 보존하고 UTF-8 인코딩과 500자 제한을 검증한다."""
    if not isinstance(value, str) or len(value) > 500:
        raise InputError("메모는 500자 이하 문자열이어야 합니다.")

    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InputError("메모를 UTF-8로 표현할 수 없습니다.") from exc

    return value


def _record_tags(record: dict[str, Any], stored: bool) -> tuple[str, ...]:
    """입력 태그를 변환하고 저장된 태그는 정규형인지 엄격히 검증한다."""
    raw_tags = record.get("tags", [])

    if isinstance(raw_tags, str) and not stored:
        return parse_tags(raw_tags)

    if not isinstance(raw_tags, list):
        raise InputError("태그는 문자열 목록이어야 합니다.")

    parsed_tags = tuple(parse_name(tag, tag=True) for tag in raw_tags)
    tags = tuple(dict.fromkeys(parsed_tags))

    if stored and (tuple(raw_tags) != parsed_tags or parsed_tags != tags):
        raise InputError("저장 태그가 정규형이 아닙니다.")

    return tags


def _validate_values(type: str, category: str, amount: int,
                     memo: str, tags: tuple[str, ...]) -> None:
    """거래와 반복 규칙이 공유하는 필드의 유효성을 검증한다."""
    if type not in ("income", "expense"):
        raise InputError("거래 타입은 income 또는 expense여야 합니다.")

    if parse_name(category) != category:
        raise InputError("저장 카테고리의 앞뒤 공백은 허용하지 않습니다.")

    if isinstance(amount, bool) or not isinstance(amount, int):
        raise InputError("거래 금액은 정수여야 합니다.")

    parse_amount(amount)
    validate_memo(memo)

    if not isinstance(tags, tuple):
        raise InputError("모델의 태그는 tuple이어야 합니다.")

    seen: set[str] = set()

    for tag in tags:
        if parse_name(tag, tag=True) != tag or tag in seen:
            raise InputError("저장 태그는 공백과 중복 없는 정규형이어야 합니다.")

        seen.add(tag)


@dataclass(frozen=True)
class Transaction:
    """저장 형식과 독립적인 불변 거래 모델."""

    id: str
    type: str
    date: Date
    category: str
    amount: int
    memo: str = ""
    tags: tuple[str, ...] = ()
    recurring_id: str | None = None
    recurring_month: str | None = None

    def __post_init__(self) -> None:
        """모델 생성 시 식별자와 필드 값의 유효성을 검증한다."""
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise InputError("거래 id는 TX-와 UUID4 소문자 hex 32자리여야 합니다.")

        if type(self.date) is not Date:
            raise InputError("거래 날짜는 유효한 date여야 합니다.")

        _validate_values(self.type, self.category, self.amount, self.memo, self.tags)

        if self.recurring_id is None and self.recurring_month is None:
            return

        if not isinstance(self.recurring_id, str) or not _RECURRING_ID.fullmatch(self.recurring_id):
            raise InputError("반복 출처는 유효한 RR UUID4 id여야 합니다.")

        parse_month(self.recurring_month)

    @classmethod
    def from_dict(cls, record: dict[str, Any], stored: bool = False) -> Transaction:
        """필수·허용 필드를 확인하고 입력 또는 저장 데이터를 모델로 변환한다."""
        required = {"id", "type", "date", "category", "amount"}
        allowed = required | {"memo", "tags", "recurring_id", "recurring_month"}

        if not isinstance(record, dict) or not required <= record.keys() or record.keys() - allowed:
            raise InputError("거래 필수 필드가 없거나 미정의 필드가 있습니다.")

        category = parse_name(record["category"])

        if stored and category != record["category"]:
            raise InputError("저장 카테고리가 정규형이 아닙니다.")

        tags = _record_tags(record, stored)
        provenance = {"recurring_id", "recurring_month"} & record.keys()

        if provenance and (len(provenance) != 2 or
                           not isinstance(record["recurring_id"], str) or
                           not isinstance(record["recurring_month"], str)):
            raise InputError("반복 출처 id와 month는 유효한 문자열 쌍이어야 합니다.")

        if stored and type(record["amount"]) is not int:
            raise InputError("저장 금액은 정수여야 합니다.")

        return cls(
            id=record["id"], type=record["type"], date=parse_date(record["date"]),
            category=category, amount=parse_amount(record["amount"]),
            memo=validate_memo(record.get("memo", "")), tags=tags,
            recurring_id=record.get("recurring_id"), recurring_month=record.get("recurring_month"),
        )

    def to_dict(self) -> dict[str, Any]:
        """모델을 JSONL 저장 스키마에 맞는 사전으로 변환한다."""
        result = {
            "id": self.id, "type": self.type, "date": self.date.isoformat(),
            "category": self.category, "amount": self.amount,
            "memo": self.memo, "tags": list(self.tags),
        }

        if self.recurring_id is not None:
            result["recurring_id"] = self.recurring_id
            result["recurring_month"] = self.recurring_month

        return result


@dataclass(frozen=True)
class RecurringRule:
    """지정 월에 적용할 거래의 원형을 보관하는 불변 반복 규칙."""

    id: str
    day: int
    type: str
    category: str
    amount: int
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """모델 생성 시 식별자와 필드 값의 유효성을 검증한다."""
        if not isinstance(self.id, str) or not _RECURRING_ID.fullmatch(self.id):
            raise InputError("반복 규칙 id는 RR-와 UUID4 소문자 hex 32자리여야 합니다.")

        if isinstance(self.day, bool) or not isinstance(self.day, int) or not 1 <= self.day <= 31:
            raise InputError("반복 날짜 day는 1~31 정수여야 합니다.")

        _validate_values(self.type, self.category, self.amount, self.memo, self.tags)

    @classmethod
    def from_dict(cls, record: dict[str, Any], stored: bool = False) -> RecurringRule:
        """필수·허용 필드를 확인하고 입력 또는 저장 데이터를 모델로 변환한다."""
        required = {"id", "day", "type", "category", "amount"}
        allowed = required | {"memo", "tags"}

        if not isinstance(record, dict) or not required <= record.keys() or record.keys() - allowed:
            raise InputError("반복 규칙 필수 필드가 없거나 미정의 필드가 있습니다.")

        category = parse_name(record["category"])

        if stored and category != record["category"]:
            raise InputError("저장 카테고리가 정규형이 아닙니다.")

        if stored and (type(record["amount"]) is not int or type(record["day"]) is not int):
            raise InputError("저장된 반복 금액과 day는 정수여야 합니다.")

        return cls(
            id=record["id"], day=parse_amount(record["day"]), type=record["type"],
            category=category, amount=parse_amount(record["amount"]),
            memo=validate_memo(record.get("memo", "")), tags=_record_tags(record, stored),
        )

    def to_dict(self) -> dict[str, Any]:
        """모델을 JSONL 저장 스키마에 맞는 사전으로 변환한다."""
        return {
            "id": self.id, "day": self.day, "type": self.type,
            "category": self.category, "amount": self.amount,
            "memo": self.memo, "tags": list(self.tags),
        }
