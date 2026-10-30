"""Типы шаблонов: какие поля нужны и какие ограничения по длине.

Ordinary и Popup — баннеры с картинкой; Push и СМС — текстовые. У СМС нет
заголовка (темы), у Push он есть. Ограничения взяты по типовым лимитам каналов.
"""

from __future__ import annotations

import re

ORDINARY = "ordinary"
POPUP = "popup"
PUSH = "push"
SMS = "sms"

KINDS: tuple[str, ...] = (ORDINARY, POPUP, PUSH, SMS)

KIND_LABELS: dict[str, str] = {
    ORDINARY: "Ordinary баннер",
    POPUP: "Popup баннер",
    PUSH: "Push",
    SMS: "СМС",
}

KIND_SHORT: dict[str, str] = {
    ORDINARY: "Ordinary",
    POPUP: "Popup",
    PUSH: "Push",
    SMS: "СМС",
}

IMAGE_KINDS: tuple[str, ...] = (ORDINARY, POPUP)
TEXT_KINDS: tuple[str, ...] = (PUSH, SMS)

VARIABLES: tuple[str, ...] = ("{name}", "{amount}", "{date}", "{city}", "{card}")

VARIABLE_PATTERN = re.compile(r"\{[A-Za-zА-Яа-я0-9_]+\}")

VARIABLE_HINTS: dict[str, str] = {
    "{name}": "имя клиента",
    "{amount}": "сумма",
    "{date}": "дата",
    "{city}": "город",
    "{card}": "карта",
}


def normalize_kind(value: str) -> str:
    """Приводит значение к известному типу; неизвестное считаем Ordinary."""
    key = (value or "").strip().casefold()
    return key if key in KINDS else ORDINARY


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(normalize_kind(kind), KIND_LABELS[ORDINARY])


def kind_short(kind: str) -> str:
    return KIND_SHORT.get(normalize_kind(kind), KIND_SHORT[ORDINARY])


def has_image(kind: str) -> bool:
    return normalize_kind(kind) in IMAGE_KINDS


def has_title(kind: str) -> bool:
    """У СМС темы нет — только текст сообщения."""
    return normalize_kind(kind) != SMS


def text_lengths(kind: str, title: str, message: str) -> dict[str, int]:
    """Длины полей шаблона — только счётчики, без ограничений."""
    result = {"message": len((message or "").strip())}
    if has_title(kind):
        result["title"] = len((title or "").strip())
    return result


def extract_variables(*texts: str) -> list[str]:
    """Переменные, которые реально есть в тексте шаблона.

    Возвращает в порядке первого появления, без повторов: `{name}`, `{amount}` и т.д.
    """
    found: list[str] = []
    for text in texts:
        for match in VARIABLE_PATTERN.findall(text or ""):
            if match not in found:
                found.append(match)
    return found


def message_length(title: str, message: str) -> int:
    """Длина текста шаблона — для сортировки и счётчиков."""
    return len((title or "").strip()) + len((message or "").strip())


def substitute_variables(text: str, values: dict[str, str]) -> str:
    """Подставляет значения вместо переменных. Пустое значение оставляет `{name}`."""
    result = text or ""
    for name, value in values.items():
        if value:
            result = result.replace(name, value)
    return result
