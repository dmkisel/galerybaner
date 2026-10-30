"""Тесты нормализации тегов и текстовых хелперов."""

from __future__ import annotations

from app.core.texts import escape_markdown, format_scale, normalize_tag_key, parse_tags, shorten


def test_parse_tags_trims_and_dedupes() -> None:
    assert parse_tags(" скидки ,  Промо ,скидки ") == ["скидки", "Промо"]


def test_parse_tags_accepts_semicolons_and_empty() -> None:
    assert parse_tags("промо; сезон;;") == ["промо", "сезон"]
    assert parse_tags("") == []


def test_parse_tags_accepts_list() -> None:
    assert parse_tags(["Новинки", "новинки "]) == ["Новинки"]


def test_tag_key_is_case_and_space_insensitive() -> None:
    assert normalize_tag_key("  Чёрная   Пятница ") == "чёрная пятница"
    assert normalize_tag_key("СКИДКИ") == "скидки"


def test_format_scale() -> None:
    assert format_scale(0.08) == "8 %"
    assert format_scale(0.075) == "7.5 %"


def test_shorten_keeps_short_text() -> None:
    assert shorten("короткий", 20) == "короткий"


def test_shorten_adds_ellipsis() -> None:
    result = shorten("очень длинный текст для карточки", 10)
    assert len(result) <= 10
    assert result.endswith("…")


def test_escape_markdown_neutralises_specials() -> None:
    assert escape_markdown("*жирный* _курсив_") == r"\*жирный\* \_курсив\_"
