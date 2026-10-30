"""Тесты определения цвета по центру баннера."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.colors import center_average_rgb, center_color, rgb_hue, rgb_to_hex


def test_center_average_ignores_edges() -> None:
    img = Image.new("RGB", (100, 100), (0, 0, 255))
    for x in range(40, 60):
        for y in range(40, 60):
            img.putpixel((x, y), (255, 0, 0))

    assert center_average_rgb(img, ratio=0.2) == (255, 0, 0)


def test_center_color_of_solid_banner() -> None:
    img = Image.new("RGB", (200, 200), (255, 0, 0))

    hex_value, hue = center_color(img)

    assert hex_value == "#FF0000"
    assert hue == pytest.approx(0.0, abs=0.5)


def test_gray_banner_has_no_hue() -> None:
    img = Image.new("RGB", (120, 120), (128, 128, 128))

    hex_value, hue = center_color(img)

    assert hex_value == "#808080"
    assert hue is None


def test_hue_of_green_is_120() -> None:
    assert rgb_hue((0, 255, 0)) == pytest.approx(120.0, abs=0.5)


def test_hue_of_blue_is_240() -> None:
    assert rgb_hue((0, 0, 255)) == pytest.approx(240.0, abs=0.5)


def test_rgb_to_hex_pads_short_values() -> None:
    assert rgb_to_hex((1, 2, 3)) == "#010203"
    assert rgb_to_hex((255, 255, 255)) == "#FFFFFF"


def test_average_of_two_halves_is_middle_color() -> None:
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    for x in range(50, 100):
        for y in range(100):
            img.putpixel((x, y), (255, 255, 255))

    red, green, blue = center_average_rgb(img, ratio=0.2)

    assert 120 <= red <= 135
    assert red == green == blue
