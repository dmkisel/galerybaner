"""Рендер Popup-баннера для конструктора.

Белая подложка с закруглёнными углами выступает по бокам и сверху на 0.5 см.
Внутри: картинка с закруглёнными углами, тема (жирная), сообщение и кнопка.
Под текст отведено ровно 10 строк — если текст короче, место до кнопки остаётся
пустым, поэтому кнопка всегда стоит на одном месте.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.render import WEIGHT_MESSAGE, WEIGHT_THEME, load_font, wrap_text

WHITE = "#FFFFFF"
TITLE_COLOR = "#16171A"
MESSAGE_COLOR = "#3A3F47"
BUTTON_COLOR = "#FF6A13"
BUTTON_TEXT_COLOR = "#FFFFFF"
DEFAULT_ACTION = "Подробнее"

PADDING_RATIO = 0.05
BUTTON_HEIGHT_RATIO = 0.12
LINE_GAP_RATIO = 0.38
# Отступ тема → сообщение больше, чем сообщение → кнопка.
TITLE_GAP_RATIO = 0.9
BLOCK_GAP_RATIO = 0.45

# Подложка выступает по бокам и сверху на 0.5 см (при ширине popup 100 мм).
SIDE_MARGIN_RATIO = 0.05
TOP_MARGIN_RATIO = 0.05

# Закругления подложки и картинки.
BACKING_RADIUS_RATIO = 0.035
IMAGE_RADIUS_RATIO = 0.02

# Сколько строк текста гарантированно помещается до кнопки.
TEXT_AREA_LINES = 10

DEFAULT_TITLE_SCALE = 0.05
DEFAULT_MESSAGE_SCALE = 0.03
MIN_MESSAGE_RATIO = 0.75


@dataclass(frozen=True)
class PopupSpec:
    title: str = ""
    message: str = ""
    action_text: str = DEFAULT_ACTION
    title_scale: float = DEFAULT_TITLE_SCALE
    message_scale: float = DEFAULT_MESSAGE_SCALE


def _scratch() -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new("RGB", (1, 1)))


def _wrap_block(
    text: str, font, max_width: int, spacing: int, max_lines: int | None = None
) -> tuple[list[str], int]:
    """Строки текста и высота блока."""
    if not (text or "").strip():
        return [], 0

    draw = _scratch()
    lines = wrap_text(text.strip(), font, max_width, draw, max_lines=max_lines)
    if not lines:
        return [], 0

    bbox = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing)
    return lines, bbox[3] - bbox[1]


def _area_height(font, spacing: int, lines: int) -> int:
    """Высота блока ровно на `lines` строк — под фиксированное место под текст."""
    draw = _scratch()
    sample = "\n".join(["Ag"] * max(1, lines))
    bbox = draw.multiline_textbbox((0, 0), sample, font=font, spacing=spacing)
    return bbox[3] - bbox[1]


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255
    )
    return mask


def render_popup(img: Image.Image, spec: PopupSpec, font_path: Path | str) -> Image.Image:
    base = img.convert("RGB")
    width, height = base.size

    margin = max(1, round(width * SIDE_MARGIN_RATIO))
    top_margin = max(1, round(width * TOP_MARGIN_RATIO))
    canvas_width = width + 2 * margin

    padding = max(10, round(canvas_width * PADDING_RATIO))
    max_text_width = max(1, canvas_width - 2 * padding)

    title_size = max(8, round(canvas_width * spec.title_scale))
    message_size = max(8, round(canvas_width * spec.message_scale))
    # Сообщение всегда мельче темы.
    message_size = min(message_size, max(8, int(title_size * MIN_MESSAGE_RATIO)))
    title_size = max(title_size, message_size + 1)

    title_font = load_font(font_path, title_size, WEIGHT_THEME)
    message_font = load_font(font_path, message_size, WEIGHT_MESSAGE)

    title_line_gap = int(title_size * LINE_GAP_RATIO)
    message_line_gap = int(message_size * LINE_GAP_RATIO)

    title_lines, title_height = _wrap_block(
        spec.title, title_font, max_text_width, title_line_gap
    )
    message_lines, _ = _wrap_block(
        spec.message,
        message_font,
        max_text_width,
        message_line_gap,
        max_lines=TEXT_AREA_LINES,
    )

    # Место под сообщение фиксировано: 10 строк.
    text_area_height = _area_height(message_font, message_line_gap, TEXT_AREA_LINES)

    title_gap = round(padding * TITLE_GAP_RATIO) if title_lines else 0
    block_gap = round(padding * BLOCK_GAP_RATIO)
    button_height = max(34, round(canvas_width * BUTTON_HEIGHT_RATIO))

    footer_height = (
        padding + title_height + title_gap + text_area_height + block_gap + button_height + padding
    )

    canvas = Image.new(
        "RGBA", (canvas_width, top_margin + height + footer_height), (0, 0, 0, 0)
    )
    backing_radius = max(4, round(canvas_width * BACKING_RADIUS_RATIO))
    ImageDraw.Draw(canvas).rounded_rectangle(
        [0, 0, canvas_width - 1, canvas.height - 1], radius=backing_radius, fill=WHITE
    )

    image_radius = max(2, round(width * IMAGE_RADIUS_RATIO))
    canvas.paste(base, (margin, top_margin), _rounded_mask(base.size, image_radius))

    draw = ImageDraw.Draw(canvas)
    y = top_margin + height + padding

    if title_lines:
        draw.multiline_text(
            (padding, y),
            "\n".join(title_lines),
            font=title_font,
            fill=TITLE_COLOR,
            spacing=title_line_gap,
        )
        y += title_height + title_gap
    else:
        y += title_gap

    if message_lines:
        draw.multiline_text(
            (padding, y),
            "\n".join(message_lines),
            font=message_font,
            fill=MESSAGE_COLOR,
            spacing=message_line_gap,
        )

    button_y = y + text_area_height + block_gap
    draw.rounded_rectangle(
        [padding, button_y, canvas_width - padding, button_y + button_height],
        radius=round(button_height * 0.32),
        fill=BUTTON_COLOR,
    )
    button_font = load_font(font_path, max(10, round(button_height * 0.38)), WEIGHT_THEME)
    draw.text(
        (canvas_width / 2, button_y + button_height / 2),
        (spec.action_text or DEFAULT_ACTION).strip(),
        font=button_font,
        fill=BUTTON_TEXT_COLOR,
        anchor="mm",
    )
    return canvas


def popup_png(img: Image.Image, spec: PopupSpec, font_path: Path | str) -> bytes:
    buffer = io.BytesIO()
    render_popup(img, spec, font_path).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
