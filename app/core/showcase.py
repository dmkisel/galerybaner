"""Структура витрины: страницы приложения и их посадочные места.

Ключи (`page`, `slot`) пишутся в БД, подписи (`title`) — только для интерфейса.
Порядок слотов задаёт порядок блоков в мокапе страницы.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    key: str
    title: str


@dataclass(frozen=True)
class ShowcasePage:
    key: str
    title: str
    slots: tuple[Slot, ...]
    kind: str


SHOWCASE_PAGES: tuple[ShowcasePage, ...] = (
    ShowcasePage(
        key="home",
        title="Главный",
        kind="home",
        # Порядок как на экране: баннер → Карты → Вклады → Счета → Кредиты
        slots=(
            Slot("main", "Основной баннер"),
            Slot("cards", "Под картами"),
            Slot("deposits", "Под вкладами"),
            Slot("accounts", "Под счетами"),
            Slot("credits", "Под кредитами"),
        ),
    ),
    ShowcasePage(
        key="loyalty",
        title="Лояльность",
        kind="loyalty",
        slots=(Slot("top", "Сверху"), Slot("bottom", "Снизу")),
    ),
    ShowcasePage(
        key="transactions",
        title="История транзакций",
        kind="transactions",
        slots=(Slot("top", "Сверху"),),
    ),
    ShowcasePage(
        key="catalog",
        title="Продуктовый каталог",
        kind="catalog",
        slots=(Slot("top", "Сверху"),),
    ),
)

PAGES_BY_KEY = {page.key: page for page in SHOWCASE_PAGES}


# CRM может писать как ключи, так и человеческие названия — принимаем оба.
PAGE_ALIASES: dict[str, str] = {
    "home": "home",
    "main": "home",
    "главный": "home",
    "главная": "home",
    "главная страница": "home",
    "главная старница": "home",
    "loyalty": "loyalty",
    "лояльность": "loyalty",
    "transactions": "transactions",
    "транзакции": "transactions",
    "история транзакций": "transactions",
    "catalog": "catalog",
    "каталог": "catalog",
    "продуктовый каталог": "catalog",
}

SLOT_ALIASES: dict[str, str] = {
    "main": "main",
    "основной баннер": "main",
    "основной банер": "main",
    "deposits": "deposits",
    "под вкладами": "deposits",
    "credits": "credits",
    "под кредитами": "credits",
    "cards": "cards",
    "под картами": "cards",
    "accounts": "accounts",
    "под счетами": "accounts",
    "top": "top",
    "сверху": "top",
    "bottom": "bottom",
    "снизу": "bottom",
}


def _key(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def normalize_page(value: str) -> str | None:
    """Ключ страницы из того, что написала CRM. None — значение не знакомо."""
    return PAGE_ALIASES.get(_key(value))


def normalize_slot(value: str) -> str | None:
    return SLOT_ALIASES.get(_key(value))


def raw_page_values(page_key: str) -> tuple[str, ...]:
    """Все написания, которые соответствуют странице — для запроса в БД."""
    return tuple(alias for alias, key in PAGE_ALIASES.items() if key == page_key)


def page_by_key(key: str) -> ShowcasePage:
    return PAGES_BY_KEY.get(key, SHOWCASE_PAGES[0])


def slot_titles(page: ShowcasePage) -> dict[str, str]:
    return {slot.key: slot.title for slot in page.slots}
