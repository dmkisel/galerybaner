"""Тесты справочника типов шаблонов: поля, лимиты, переменные."""

from __future__ import annotations

from app.core import templates


def test_image_kinds() -> None:
    assert templates.has_image("ordinary") is True
    assert templates.has_image("popup") is True
    assert templates.has_image("push") is False
    assert templates.has_image("sms") is False


def test_sms_has_no_title() -> None:
    assert templates.has_title("push") is True
    assert templates.has_title("ordinary") is True
    assert templates.has_title("sms") is False


def test_lengths_are_counters_only() -> None:
    lengths = templates.text_lengths("push", "Заголовок", "Текст")

    assert lengths == {"title": 9, "message": 5}
    assert "limit" not in templates.text_lengths("sms", "", "Коротко")




def test_unknown_kind_falls_back_to_ordinary() -> None:
    assert templates.normalize_kind("нечто") == "ordinary"


def test_extract_variables_in_order_without_duplicates() -> None:
    text = "Привет, {name}! Бонус {amount} до {date}. {name}, не пропустите."

    assert templates.extract_variables(text) == ["{name}", "{amount}", "{date}"]


def test_extract_variables_from_title_and_message() -> None:
    assert templates.extract_variables("{city}: скидка", "Только для {name}") == [
        "{city}",
        "{name}",
    ]


def test_extract_variables_ignores_empty_braces() -> None:
    assert templates.extract_variables("{} { } и просто {скобки") == []


def test_substitute_variables_replaces_known_values() -> None:
    text = "Привет, {name}! Бонус {amount}."

    assert templates.substitute_variables(text, {"{name}": "Анна"}) == (
        "Привет, Анна! Бонус {amount}."
    )


def test_substitute_variables_keeps_placeholder_when_empty() -> None:
    assert templates.substitute_variables("Выигрыш {amount}", {"{amount}": ""}) == "Выигрыш {amount}"


def test_message_length_sums_title_and_text() -> None:
    assert templates.message_length("Тема", "Текст") == 9
    assert templates.message_length("", "") == 0


