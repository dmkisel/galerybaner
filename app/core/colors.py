"""Цвет баннера по центральным пикселям — для сортировки каталога.

Считаем средний цвет центрального квадрата (20 % от меньшей стороны), а для
сортировки используем оттенок: так баннеры выстраиваются по спектру, а не по
яркости. Почти серые баннеры оттенка не имеют — они уезжают в конец списка.
"""

from __future__ import annotations

import colorsys

from PIL import Image

CENTER_RATIO = 0.2
# Ниже этой насыщенности цвет считаем серым: оттенок у него случайный.
NEUTRAL_SATURATION = 0.06


def center_average_rgb(img: Image.Image, ratio: float = CENTER_RATIO) -> tuple[int, int, int]:
    """Средний RGB центрального прямоугольника."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    box_w = max(1, round(width * ratio))
    box_h = max(1, round(height * ratio))
    left = (width - box_w) // 2
    top = (height - box_h) // 2

    patch = rgb.crop((left, top, left + box_w, top + box_h))
    # Сжатие в один пиксель усредняет область — быстрее ручного перебора.
    return patch.resize((1, 1), Image.BOX).getpixel((0, 0))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def rgb_hue(rgb: tuple[int, int, int]) -> float | None:
    """Оттенок 0–360. Для серых и почти серых — None."""
    red, green, blue = (channel / 255 for channel in rgb)
    hue, saturation, _ = colorsys.rgb_to_hsv(red, green, blue)
    if saturation < NEUTRAL_SATURATION:
        return None
    return round(hue * 360, 2)


def center_color(img: Image.Image, ratio: float = CENTER_RATIO) -> tuple[str, float | None]:
    """Пара (hex, оттенок) для баннера."""
    rgb = center_average_rgb(img, ratio)
    return rgb_to_hex(rgb), rgb_hue(rgb)
