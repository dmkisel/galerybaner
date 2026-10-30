"""Хелперы для текста и тегов: нормализация, парсинг ввода, форматирование."""

from __future__ import annotations

import re
from collections.abc import Iterable

MARKDOWN_CHARS = re.compile(r"([\\`*_{}\[\]()#+\-.!|>~])")


def normalize_tag_key(name: str) -> str:
    """Ключ тега для точного сравнения: без лишних пробелов, в нижнем регистре."""
    return " ".join((name or "").split()).casefold()


def parse_tags(raw: str | Iterable[str]) -> list[str]:
    """Разбирает «скидки, Промо, скидки» -> ['скидки', 'Промо'] с сохранением регистра."""
    if isinstance(raw, str):
        parts = raw.replace(";", ",").split(",")
    else:
        parts = list(raw)

    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        name = " ".join((part or "").split())
        if not name:
            continue
        key = normalize_tag_key(name)
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def format_scale(value: float) -> str:
    """0.075 -> '7,5 %' (для подписи в интерфейсе)."""
    percent = round(float(value) * 100, 1)
    text = f"{percent:g}"
    return f"{text} %"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def shorten(text: str, limit: int = 80) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def escape_markdown(text: str) -> str:
    """Экранирует служебные символы Markdown в пользовательском тексте."""
    return MARKDOWN_CHARS.sub(r"\\\1", text or "")
