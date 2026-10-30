"""Тесты рендера: геометрия, лимит строк, автоподбор кегля и начертания."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from app.core.render import (
    MAX_LINES,
    MIN_FONT_PX,
    MIN_TEXT_SCALE,
    WEIGHT_MESSAGE,
    WEIGHT_THEME,
    ZONE_ANY,
    ZONE_LOWER,
    ZONE_UPPER,
    BannerSpec,
    TextBlock,
    banner_layout,
    font_size_for,
    layout_block,
    load_font,
    render_banner,
    render_block,
    wrap_text,
)


@pytest.fixture()
def banner() -> Image.Image:
    return Image.new("RGB", (1200, 628), (40, 48, 60))


def make_block(text: str, scale: float = 0.155, **kwargs) -> TextBlock:
    base = {
        "text": text,
        "text_scale": scale,
        "pos_x": 0.05,
        "pos_y": 0.25,
        "zone": ZONE_UPPER,
    }
    base.update(kwargs)
    return TextBlock(**base)


def make_spec(
    theme: str = "Скидка 30%",
    message: str = "Только до воскресенья",
    theme_scale: float = 0.155,
    message_scale: float = 0.125,
) -> BannerSpec:
    return BannerSpec(
        theme=make_block(
            theme, theme_scale, pos_y=0.25, zone=ZONE_UPPER, weight=WEIGHT_THEME
        ),
        message=make_block(
            message, message_scale, pos_y=0.75, zone=ZONE_LOWER, weight=WEIGHT_MESSAGE
        ),
    )


def ink(image: Image.Image, background: Image.Image) -> int:
    return sum(
        1
        for a, b in zip(image.convert("RGB").tobytes(), background.convert("RGB").tobytes())
        if a != b
    )


def ink_bbox(image: Image.Image, background: Image.Image) -> tuple[int, int, int, int] | None:
    """Границы нарисованного текста в пикселях."""
    return ImageChops.difference(image.convert("RGB"), background.convert("RGB")).getbbox()


def test_font_size_is_share_of_height() -> None:
    assert font_size_for(1000, 0.155) == 155
    assert font_size_for(628, 0.125) == 78
    assert font_size_for(1080, 0.155) == 167


def test_font_size_never_below_readable_minimum() -> None:
    assert font_size_for(100, 0.01) == MIN_FONT_PX
    assert font_size_for(0, 0.10) == MIN_FONT_PX


def test_wrap_respects_max_width(font_path: Path) -> None:
    canvas = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_path, 40)

    lines = wrap_text("Скидка тридцать процентов только до воскресенья", font, 300, draw)

    assert len(lines) > 1
    for line in lines:
        assert draw.textlength(line, font=font) <= 300


def test_wrap_breaks_word_longer_than_line(font_path: Path) -> None:
    canvas = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_path, 40)
    word = "ы" * 120

    lines = wrap_text(word, font, 200, draw)

    assert len(lines) > 1
    assert "".join(lines) == word
    for line in lines:
        assert draw.textlength(line, font=font) <= 200


def test_max_lines_caps_with_ellipsis(font_path: Path) -> None:
    canvas = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_path, 36)
    long_text = "Очень длинный текст баннера, который точно не влезет в две строки целиком"

    lines = wrap_text(long_text, font, 260, draw, max_lines=2)

    assert len(lines) == 2
    assert lines[-1].endswith("…")
    assert draw.textlength(lines[-1], font=font) <= 260


def test_short_text_has_no_ellipsis(font_path: Path) -> None:
    canvas = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_path, 30)

    lines = wrap_text("Коротко", font, 400, draw, max_lines=MAX_LINES)

    assert len(lines) == 1
    assert not lines[-1].endswith("…")


def test_theme_is_bolder_than_message(banner: Image.Image, font_path: Path) -> None:
    """Вариативный шрифт должен давать разные начертания для темы и сообщения."""
    regular = make_block("Скидка", weight=WEIGHT_MESSAGE, zone=ZONE_ANY)
    bold = make_block("Скидка", weight=WEIGHT_THEME, zone=ZONE_ANY)

    heavy = ink(render_block(banner, bold, font_path), banner)
    light = ink(render_block(banner, regular, font_path), banner)

    assert heavy > light, "жирное начертание должно закрашивать больше пикселей"


def test_render_banner_returns_new_image_of_same_size(banner: Image.Image, font_path: Path) -> None:
    before = banner.tobytes()

    rendered = render_banner(banner, make_spec(), font_path)

    assert rendered.size == banner.size
    assert rendered is not banner
    assert banner.tobytes() == before, "входное изображение не должно меняться"


def test_render_banner_draws_both_blocks(banner: Image.Image, font_path: Path) -> None:
    only_theme = render_banner(banner, make_spec(message=""), font_path)
    both = render_banner(banner, make_spec(), font_path)

    assert ink(both, banner) > ink(only_theme, banner)


def test_empty_spec_returns_untouched_copy(banner: Image.Image, font_path: Path) -> None:
    spec = make_spec(theme="", message="")

    rendered = render_banner(banner, spec, font_path)

    assert spec.is_empty
    assert rendered.size == banner.size
    assert ink(rendered, banner) == 0


def test_render_is_deterministic(banner: Image.Image, font_path: Path) -> None:
    spec = make_spec()

    first = render_banner(banner, spec, font_path).tobytes()
    second = render_banner(banner, spec, font_path).tobytes()

    assert first == second


def test_short_text_keeps_requested_size(banner: Image.Image, font_path: Path) -> None:
    layout = layout_block(banner, make_block("Скидка"), font_path)

    assert layout is not None
    assert layout.font_px == 97  # 0.155 * 628


def test_long_text_autofits_into_two_lines(banner: Image.Image, font_path: Path) -> None:
    """Длинный текст ужимается шрифтом, а не обрезается многоточием."""
    text = "Скидка тридцать процентов на весь ассортимент до воскресенья"
    layout = layout_block(banner, make_block(text), font_path)

    assert layout is not None
    assert layout.font_px < 97
    assert len(layout.lines) <= MAX_LINES
    assert not layout.lines[-1].endswith("…")


def test_left_alignment_places_blocks_on_one_line(banner: Image.Image, font_path: Path) -> None:
    """Тема и сообщение с одним отступом начинаются на одном уровне."""
    theme = make_block("СКИДКА", 0.155, pos_x=0.05, zone=ZONE_UPPER)
    message = make_block("Только до воскресенья", 0.125, pos_x=0.05, zone=ZONE_LOWER)

    theme_layout = layout_block(banner, theme, font_path)
    message_layout = layout_block(banner, message, font_path)

    assert theme_layout is not None and message_layout is not None
    assert theme_layout.left == pytest.approx(round(0.05 * banner.width), abs=2)
    assert theme_layout.left == message_layout.left


def test_right_alignment_counts_from_right_edge(banner: Image.Image, font_path: Path) -> None:
    block = make_block("СКИДКА", 0.155, pos_x=0.95, align="right")

    layout = layout_block(banner, block, font_path)

    assert layout is not None
    assert layout.left + layout.block_w == pytest.approx(round(0.95 * banner.width), abs=2)


def test_block_is_centered_in_its_half(banner: Image.Image, font_path: Path) -> None:
    block = make_block("СКИДКА", 0.155, pos_y=0.25, zone=ZONE_UPPER)

    layout = layout_block(banner, block, font_path)

    assert layout is not None
    center = layout.top + layout.block_h / 2
    assert center == pytest.approx(banner.height * 0.25, abs=2)


def test_theme_never_crosses_middle(banner: Image.Image, font_path: Path) -> None:
    block = make_block("Скидка тридцать процентов на всё", 0.2, pos_y=0.5, zone=ZONE_UPPER)

    layout = layout_block(banner, block, font_path)

    assert layout is not None
    assert layout.top + layout.block_h <= banner.height / 2 + 1


def test_message_never_crosses_middle(banner: Image.Image, font_path: Path) -> None:
    block = make_block(
        "Только до воскресенья", 0.2, pos_y=0.5, zone=ZONE_LOWER, weight=WEIGHT_MESSAGE
    )

    layout = layout_block(banner, block, font_path)

    assert layout is not None
    assert layout.top >= banner.height / 2 - 1


def test_message_stays_smaller_after_autofit(banner: Image.Image, font_path: Path) -> None:
    spec = BannerSpec(
        theme=make_block(
            "Очень длинная тема, которая занимает почти всю верхнюю половину баннера",
            0.20,
            pos_y=0.25,
            zone=ZONE_UPPER,
            weight=WEIGHT_THEME,
        ),
        message=make_block(
            "Коротко", 0.17, pos_y=0.75, zone=ZONE_LOWER, weight=WEIGHT_MESSAGE
        ),
    )

    theme_layout, message_layout = banner_layout(banner, spec, font_path)

    assert theme_layout is not None and message_layout is not None
    assert message_layout.font_px < theme_layout.font_px


def test_shift_keeps_message_smaller_than_theme() -> None:
    spec = make_spec(theme_scale=0.20, message_scale=0.19)

    bigger = spec.shifted(0.05)

    assert bigger.theme.text_scale <= 0.20
    assert bigger.theme.text_scale - bigger.message.text_scale >= 0.03 - 1e-9


def test_shift_never_drops_below_minimum() -> None:
    spec = make_spec(theme_scale=0.04, message_scale=0.01)

    smaller = spec.shifted(-0.5)

    assert smaller.theme.text_scale == pytest.approx(MIN_TEXT_SCALE)
    assert smaller.message.text_scale >= MIN_TEXT_SCALE
