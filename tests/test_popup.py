"""Тесты рендера Popup: подложка, скругления, тема, сообщение и кнопка."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core import popup


@pytest.fixture()
def banner() -> Image.Image:
    return Image.new("RGB", (600, 300), (30, 40, 60))


def render(banner: Image.Image, font_path: Path, **kwargs) -> Image.Image:
    return popup.render_popup(banner, popup.PopupSpec(**kwargs), font_path)


def test_default_scales() -> None:
    assert popup.DEFAULT_TITLE_SCALE == 0.05
    assert popup.DEFAULT_MESSAGE_SCALE == 0.03


def test_backing_is_wider_and_taller_than_image(banner: Image.Image, font_path: Path) -> None:
    """Подложка выступает по бокам и сверху на 0.5 см."""
    result = render(banner, font_path, title="Тема", message="Текст")

    expected_margin = round(banner.width * popup.SIDE_MARGIN_RATIO)
    expected_top = round(banner.width * popup.TOP_MARGIN_RATIO)

    assert result.width == banner.width + 2 * expected_margin
    assert result.height > banner.height + expected_top


def test_backing_corners_are_rounded(banner: Image.Image, font_path: Path) -> None:
    result = render(banner, font_path, message="Текст")

    # Угол прозрачный, а чуть внутри — белая подложка.
    assert result.getpixel((0, 0))[3] == 0
    radius = max(4, round(result.width * popup.BACKING_RADIUS_RATIO))
    assert result.getpixel((radius, radius))[:3] == (255, 255, 255)


def test_image_is_inset_from_edges(banner: Image.Image, font_path: Path) -> None:
    result = render(banner, font_path, message="Текст")

    margin = round(banner.width * popup.SIDE_MARGIN_RATIO)
    top = round(banner.width * popup.TOP_MARGIN_RATIO)
    radius = max(2, round(banner.width * popup.IMAGE_RADIUS_RATIO))

    assert result.getpixel((margin + 2, top - 1))[:3] == (255, 255, 255)
    assert result.getpixel((margin + radius + 2, top + radius + 2))[:3] == banner.getpixel((2, 2))


def test_text_area_is_fixed_to_ten_lines(banner: Image.Image, font_path: Path) -> None:
    """Место под текст фиксировано: короткий текст не подтягивает кнопку вверх."""
    short = render(banner, font_path, message="Коротко")
    longer = render(banner, font_path, message="Строка один\nСтрока два\nСтрока три")

    assert short.height == longer.height


def test_more_lines_than_allowed_do_not_grow_area(banner: Image.Image, font_path: Path) -> None:
    many = "\n".join(f"Строка {index}" for index in range(20))

    result = render(banner, font_path, message=many)

    assert result.height == render(banner, font_path, message="Коротко").height


def test_title_and_message_raise_footer(banner: Image.Image, font_path: Path) -> None:
    without_title = render(banner, font_path, message="Текст")
    with_title = render(banner, font_path, title="Заголовок", message="Текст")

    assert with_title.height > without_title.height


def test_button_is_saturated_orange(banner: Image.Image, font_path: Path) -> None:
    result = render(banner, font_path, message="Текст", action_text="Купить")

    top = round(banner.width * popup.TOP_MARGIN_RATIO)
    width, height = result.size
    orange = False
    for y in range(top + banner.height, height, 2):
        for x in range(0, width, 3):
            red, green, blue, _alpha = result.getpixel((x, y))
            if red > 230 and 80 < green < 140 and blue < 60:
                orange = True
                break
        if orange:
            break

    assert orange, "насыщенная оранжевая кнопка не найдена"
    assert popup.BUTTON_COLOR == "#FF6A13"


def test_message_stays_smaller_than_title(banner: Image.Image, font_path: Path) -> None:
    result = render(banner, font_path, title="Тема", message="Текст", message_scale=0.2)

    assert result.height > banner.height


def test_empty_texts_still_render_button(banner: Image.Image, font_path: Path) -> None:
    result = render(banner, font_path, message="", action_text="Ок")

    assert result.height > banner.height
