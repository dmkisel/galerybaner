"""Рендер баннера: два текстовых блока — «Тема» и «Сообщение».

Модуль не зависит от Streamlit и БД. Правила повторяют макет заказчика:

* тема — жирным в верхней половине баннера, сообщение — обычным в нижней;
* оба блока начинаются от одной левой границы (отступ в мм переводится в долю);
* не длиннее двух строк и не шире заданной доли ширины;
* кегль подбирается под длину текста: масштаб из настроек — это максимум,
  при длинном тексте шрифт уменьшается, чтобы блок остался в двух строках
  и не вылез из своей половины баннера.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

MIN_FONT_PX = 8
LINE_SPACING_RATIO = 0.15
STROKE_COLOR = "#0B0F14"
DEFAULT_COLOR = "#FFFFFF"
VALID_ALIGNS = ("left", "center", "right")

MIN_TEXT_SCALE = 0.01
MAX_TEXT_SCALE = 0.20
# Сообщение всегда мельче темы: между ними держим зазор в 3 п.п.
SCALE_GAP = 0.03
# Сообщение не должно догнать тему после автоподбора кегля.
MESSAGE_SIZE_RATIO = 0.85

MAX_LINES = 2
ELLIPSIS = "…"

ZONE_UPPER = "upper"
ZONE_LOWER = "lower"
ZONE_ANY = "any"
# Какую долю своей половины баннера блок может занять по высоте.
ZONE_FILL = 0.92

WEIGHT_THEME = "Bold"
WEIGHT_MESSAGE = "Regular"
WEIGHT_VALUES = {"Regular": 400.0, "Medium": 500.0, "SemiBold": 600.0, "Bold": 700.0}


@dataclass(frozen=True)
class TextBlock:
    """Один текстовый блок. Координаты — доли от размера баннера."""

    text: str = ""
    text_scale: float = 0.155
    pos_x: float = 0.05
    pos_y: float = 0.50
    max_width: float = 0.78
    align: str = "left"
    color: str = DEFAULT_COLOR
    stroke_width: float = 0.0
    weight: str = WEIGHT_MESSAGE
    zone: str = ZONE_ANY


@dataclass(frozen=True)
class BannerSpec:
    """Тема + сообщение. Оба блока живут в одних правилах переноса и ширины."""

    theme: TextBlock
    message: TextBlock

    def shifted(self, delta: float) -> "BannerSpec":
        """Тот же макет, но оба масштаба сдвинуты на delta (доля высоты).

        Оба блока едут на одну величину, поэтому разница между темой
        и сообщением сохраняется.
        """
        theme_scale = min(max(self.theme.text_scale + delta, MIN_TEXT_SCALE), MAX_TEXT_SCALE)
        message_scale = min(
            max(self.message.text_scale + delta, MIN_TEXT_SCALE),
            max(MIN_TEXT_SCALE, theme_scale - SCALE_GAP),
        )
        return BannerSpec(
            theme=replace(self.theme, text_scale=theme_scale),
            message=replace(self.message, text_scale=message_scale),
        )

    @property
    def is_empty(self) -> bool:
        return not (self.theme.text.strip() or self.message.text.strip())


@dataclass(frozen=True)
class BlockLayout:
    """Результат раскладки блока: итоговый кегль, строки и размеры."""

    font_px: int
    lines: tuple[str, ...]
    spacing: int
    stroke: int
    block_w: int
    block_h: int
    left: int
    top: int
    origin_x: int
    origin_y: int
    align: str


def font_size_for(banner_height: int, text_scale: float) -> int:
    """Кегль в пикселях: доля высоты баннера, но не меньше читаемого минимума."""
    if banner_height <= 0:
        return MIN_FONT_PX
    return max(MIN_FONT_PX, int(round(text_scale * banner_height)))


def zone_bounds(image_height: int, zone: str) -> tuple[float, float]:
    """Границы полосы, в которой живёт блок."""
    if zone == ZONE_UPPER:
        return 0.0, image_height / 2
    if zone == ZONE_LOWER:
        return image_height / 2, float(image_height)
    return 0.0, float(image_height)


@lru_cache(maxsize=128)
def _load_font_cached(font_path: str, size: int, weight: str) -> ImageFont.FreeTypeFont:
    return _apply_weight(ImageFont.truetype(font_path, size=size), weight)


def load_font(font_path: Path | str, size: int, weight: str = WEIGHT_MESSAGE) -> ImageFont.FreeTypeFont:
    return _load_font_cached(str(font_path), max(1, int(size)), weight)


def _apply_weight(font: ImageFont.FreeTypeFont, weight: str) -> ImageFont.FreeTypeFont:
    """Выставляет начертание у вариативного шрифта.

    Для обычного TTF (DejaVu) обе попытки падают штатно — шрифт остаётся
    в своём единственном начертании.
    """
    try:
        font.set_variation_by_name(weight)
        return font
    except Exception:  # noqa: BLE001 - шрифт может быть не вариативным
        pass

    target = WEIGHT_VALUES.get(weight, 400.0)
    try:
        axes = font.get_variation_axes()
        values = [
            target if "wght" in str(axis.get("name", "")) else axis.get("default", 0)
            for axis in axes
        ]
        font.set_variation_by_axes(values)
    except Exception:  # noqa: BLE001 - нет поддержки вариаций в сборке FreeType
        pass
    return font


def _safe_color(value: str, fallback: str = DEFAULT_COLOR) -> str:
    try:
        ImageColor.getrgb(value)
    except (ValueError, AttributeError):
        return fallback
    return value


def _split_word(
    word: str, font: ImageFont.FreeTypeFont, max_width: float, draw: ImageDraw.ImageDraw
) -> tuple[str, str]:
    """Отрезает максимальный префикс слова, влезающий в строку.

    Гарантирует прогресс: минимум один символ уходит в `head`, поэтому
    вызывающий цикл не может зациклиться на слишком узкой колонке.
    """
    if max_width <= 0:
        return word, ""
    cut = 0
    for index in range(1, len(word) + 1):
        if draw.textlength(word[:index], font=font) <= max_width:
            cut = index
        else:
            break
    cut = max(cut, 1)
    return word[:cut], word[cut:]


def _wrap_all(
    text: str, font: ImageFont.FreeTypeFont, max_width: float, draw: ImageDraw.ImageDraw
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        current = ""
        for word in words:
            while word:
                if not current:
                    if draw.textlength(word, font=font) <= max_width:
                        current = word
                        word = ""
                    else:
                        head, word = _split_word(word, font, max_width, draw)
                        lines.append(head)
                    continue

                candidate = f"{current} {word}"
                if draw.textlength(candidate, font=font) <= max_width:
                    current = candidate
                    word = ""
                else:
                    lines.append(current)
                    current = ""

        if current:
            lines.append(current)

    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _ellipsize(
    line: str, font: ImageFont.FreeTypeFont, max_width: float, draw: ImageDraw.ImageDraw
) -> str:
    """Обрезает строку так, чтобы многоточие влезло в предел ширины."""
    trimmed = line.rstrip()
    if draw.textlength(trimmed + ELLIPSIS, font=font) <= max_width:
        return trimmed + ELLIPSIS

    while trimmed and draw.textlength(trimmed + ELLIPSIS, font=font) > max_width:
        trimmed = trimmed[:-1].rstrip()
    return f"{trimmed}{ELLIPSIS}" if trimmed else ELLIPSIS


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: float,
    draw: ImageDraw.ImageDraw,
    max_lines: int | None = None,
) -> list[str]:
    """Перенос по словам с жёстким лимитом строк и многоточием в последней."""
    lines = _wrap_all(text, font, max_width, draw)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(lines[-1], font, max_width, draw)
    return lines


def _text_height(
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    spacing: int,
    draw: ImageDraw.ImageDraw,
) -> int:
    bbox = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing)
    return bbox[3] - bbox[1]


def _fit_font_size(
    text: str,
    font_path: Path | str,
    weight: str,
    max_width: float,
    max_lines: int,
    max_height: float,
    requested: int,
    draw: ImageDraw.ImageDraw,
) -> int:
    """Наибольший кегль ≤ requested, при котором текст влезает в рамку.

    Именно это «подбирает шрифт под длину»: короткий текст рисуется в полный
    масштаб, длинный — мельче, но целиком, без многоточия.
    """

    def fits(size: int) -> bool:
        font = load_font(font_path, size, weight)
        lines = _wrap_all(text, font, max_width, draw)
        if len(lines) > max_lines or not lines:
            return False
        spacing = int(round(size * LINE_SPACING_RATIO))
        return _text_height(lines, font, spacing, draw) <= max_height

    if fits(requested):
        return requested

    low, high = MIN_FONT_PX, max(MIN_FONT_PX, requested - 1)
    best = MIN_FONT_PX
    while low <= high:
        middle = (low + high) // 2
        if fits(middle):
            best = middle
            low = middle + 1
        else:
            high = middle - 1
    return best


def layout_block(
    image: Image.Image,
    block: TextBlock,
    font_path: Path | str,
    max_lines: int = MAX_LINES,
    max_font_px: int | None = None,
) -> BlockLayout | None:
    """Раскладка блока: подбор кегля, перенос и итоговые координаты отрисовки."""
    text = (block.text or "").strip()
    if not text:
        return None

    align = block.align if block.align in VALID_ALIGNS else "left"
    scratch = ImageDraw.Draw(Image.new("L", (1, 1)))

    max_width_px = max(1.0, block.max_width * image.width)
    top, bottom = zone_bounds(image.height, block.zone)
    max_height_px = max(MIN_FONT_PX * 1.2, (bottom - top) * ZONE_FILL)

    requested = font_size_for(image.height, block.text_scale)
    if max_font_px is not None:
        requested = min(requested, max(1, max_font_px))

    size = _fit_font_size(
        text, font_path, block.weight, max_width_px, max_lines, max_height_px, requested, scratch
    )
    font = load_font(font_path, size, block.weight)
    lines = wrap_text(text, font, max_width_px, scratch, max_lines=max_lines)
    if not lines:
        return None

    spacing = int(round(size * LINE_SPACING_RATIO))
    stroke = max(0, int(round(block.stroke_width * size)))
    body = "\n".join(lines)

    bbox = scratch.multiline_textbbox(
        (0, 0), body, font=font, spacing=spacing, align=align, stroke_width=stroke
    )
    block_w = bbox[2] - bbox[0]
    block_h = bbox[3] - bbox[1]

    # pos_x — якорь блока: левый край при align=left, центр при center,
    # правый при right. Так тема и сообщение с одним отступом стоят на одном уровне.
    if align == "left":
        origin_x = block.pos_x * image.width - bbox[0]
    elif align == "right":
        origin_x = block.pos_x * image.width - block_w - bbox[0]
    else:
        origin_x = block.pos_x * image.width - block_w / 2 - bbox[0]

    # По вертикали блок центрируется в своей половине и не выходит за неё.
    center_y = block.pos_y * image.height
    half = block_h / 2
    if bottom - top > block_h:
        center_y = min(max(center_y, top + half), bottom - half)
    else:
        center_y = (top + bottom) / 2
    origin_y = center_y - half - bbox[1]

    return BlockLayout(
        font_px=size,
        lines=tuple(lines),
        spacing=spacing,
        stroke=stroke,
        block_w=int(round(block_w)),
        block_h=int(round(block_h)),
        left=int(round(origin_x + bbox[0])),
        top=int(round(origin_y + bbox[1])),
        origin_x=int(round(origin_x)),
        origin_y=int(round(origin_y)),
        align=align,
    )


def banner_layout(
    img: Image.Image,
    spec: BannerSpec,
    font_path: Path | str,
    max_lines: int = MAX_LINES,
) -> tuple[BlockLayout | None, BlockLayout | None]:
    """Раскладка обоих блоков.

    Сообщение раскладывается уже с оглядкой на итоговый кегль темы: после
    автоподбора тема может сильно уменьшиться, и сообщение не должно её догнать.
    """
    theme = layout_block(img, spec.theme, font_path, max_lines)
    limit = max(1, int(round(theme.font_px * MESSAGE_SIZE_RATIO))) if theme else None
    message = layout_block(img, spec.message, font_path, max_lines, max_font_px=limit)
    return theme, message


def _paint(
    image: Image.Image,
    block: TextBlock,
    layout: BlockLayout,
    font_path: Path | str,
) -> None:
    draw = ImageDraw.Draw(image)
    font = load_font(font_path, layout.font_px, block.weight)
    draw.multiline_text(
        (layout.origin_x, layout.origin_y),
        "\n".join(layout.lines),
        font=font,
        fill=_safe_color(block.color),
        spacing=layout.spacing,
        align=layout.align,
        stroke_width=layout.stroke,
        stroke_fill=STROKE_COLOR,
    )


def render_block(
    img: Image.Image,
    block: TextBlock,
    font_path: Path | str,
    max_lines: int = MAX_LINES,
) -> Image.Image:
    """Копия изображения с одним блоком текста."""
    base = img.convert("RGBA").copy()
    layout = layout_block(base, block, font_path, max_lines)
    if layout is not None:
        _paint(base, block, layout, font_path)
    return base


def render_banner(
    img: Image.Image,
    spec: BannerSpec,
    font_path: Path | str,
    max_lines: int = MAX_LINES,
) -> Image.Image:
    """Копия изображения с темой и сообщением."""
    base = img.convert("RGBA").copy()
    theme_layout, message_layout = banner_layout(img, spec, font_path, max_lines)
    if theme_layout is not None:
        _paint(base, spec.theme, theme_layout, font_path)
    if message_layout is not None:
        _paint(base, spec.message, message_layout, font_path)
    return base


def fit_within(img: Image.Image, max_side: int | None) -> Image.Image:
    """Пропорционально уменьшает картинку, чтобы длинная сторона влезла в лимит."""
    if not max_side or max(img.size) <= max_side:
        return img.copy()
    ratio = max_side / max(img.size)
    new_size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
    return img.resize(new_size, Image.LANCZOS)


def png_bytes(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
