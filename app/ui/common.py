"""Общие кэшированные обёртки для страниц.

Streamlit перезапускает скрипт на каждый чих виджета, поэтому скачивание и
рендер обязательно кэшируются — иначе слайдер масштаба будет ходить в сеть.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # запуск как скрипта Streamlit
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.core import images, popup
from app.core.config import get_settings, resolve_font_path
from app.core.render import (
    WEIGHT_MESSAGE,
    WEIGHT_THEME,
    ZONE_LOWER,
    ZONE_UPPER,
    BannerSpec,
    TextBlock,
    fit_within,
    layout_block,
    png_bytes,
    render_banner,
)


@st.cache_data(show_spinner=False, ttl=3600, max_entries=800)
def load_thumb(url: str, max_side: int) -> tuple[bytes | None, str | None]:
    """Миниатюра для сетки каталога. Возвращает (jpeg, текст ошибки)."""
    settings = get_settings()
    try:
        img = images.load_image(url, settings)
        return images.thumbnail_jpeg(img, max_side), None
    except images.ImageLoadError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 - картинка не должна ронять страницу
        return None, f"Не удалось обработать картинку: {exc}"


def build_spec(
    *,
    theme_text: str,
    message_text: str,
    theme_scale: float,
    message_scale: float,
    theme_pos_x: float,
    theme_pos_y: float,
    message_pos_x: float,
    message_pos_y: float,
    max_width: float,
    align: str,
    color: str,
    stroke_width: float,
) -> BannerSpec:
    return BannerSpec(
        theme=TextBlock(
            text=theme_text,
            text_scale=theme_scale,
            pos_x=theme_pos_x,
            pos_y=theme_pos_y,
            max_width=max_width,
            align=align,
            color=color,
            stroke_width=stroke_width,
            weight=WEIGHT_THEME,
            zone=ZONE_UPPER,
        ),
        message=TextBlock(
            text=message_text,
            text_scale=message_scale,
            pos_x=message_pos_x,
            pos_y=message_pos_y,
            max_width=max_width,
            align=align,
            color=color,
            stroke_width=stroke_width,
            weight=WEIGHT_MESSAGE,
            zone=ZONE_LOWER,
        ),
    )


@st.cache_data(show_spinner=False, ttl=3600, max_entries=200)
def render_popup_preview(
    url: str,
    title: str,
    message: str,
    action_text: str,
    title_scale: float,
    message_scale: float,
    max_side: int,
) -> tuple[bytes | None, str | None]:
    """Popup целиком: подложка, картинка, тема, сообщение и кнопка."""
    settings = get_settings()
    try:
        img = images.load_image(url, settings)
    except images.ImageLoadError as exc:
        return None, str(exc)

    img = fit_within(img, max_side or None)
    composed = popup.render_popup(
        img,
        popup.PopupSpec(
            title=title,
            message=message,
            action_text=action_text,
            title_scale=title_scale,
            message_scale=message_scale,
        ),
        resolve_font_path(settings),
    )
    return png_bytes(composed), None


@st.cache_data(show_spinner=False, ttl=3600, max_entries=300)
def render_preview(
    url: str,
    theme_text: str,
    message_text: str,
    theme_scale: float,
    message_scale: float,
    theme_pos_x: float,
    theme_pos_y: float,
    message_pos_x: float,
    message_pos_y: float,
    max_width: float,
    align: str,
    color: str,
    stroke_width: float,
    max_side: int,
    max_lines: int = 2,
) -> tuple[bytes | None, str | None, int | None]:
    """Превью с темой и сообщением: (png, ошибка, кегль темы на оригинале)."""
    settings = get_settings()
    try:
        img = images.load_image(url, settings)
    except images.ImageLoadError as exc:
        return None, str(exc), None

    spec = build_spec(
        theme_text=theme_text,
        message_text=message_text,
        theme_scale=theme_scale,
        message_scale=message_scale,
        theme_pos_x=theme_pos_x,
        theme_pos_y=theme_pos_y,
        message_pos_x=message_pos_x,
        message_pos_y=message_pos_y,
        max_width=max_width,
        align=align,
        color=color,
        stroke_width=stroke_width,
    )

    # Кегль берём с полного размера: после автоподбора он зависит от длины текста.
    font_px = None
    layout = layout_block(img, spec.theme, resolve_font_path(settings), max_lines)
    if layout is not None:
        font_px = layout.font_px

    img = fit_within(img, max_side or None)
    rendered = render_banner(img, spec, resolve_font_path(settings), max_lines=max_lines)
    return png_bytes(rendered), None, font_px
