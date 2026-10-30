"""Настройки приложения.

Модуль намеренно не зависит от Streamlit: его импортируют и скрипты, и тесты,
и Alembic. Все значения читаются из переменных окружения, у каждого есть
безопасное значение по умолчанию для локального docker compose.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
DEFAULT_FONT = APP_DIR / "assets" / "fonts" / "Inter-Variable.ttf"

FONT_FALLBACKS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_database_url() -> str:
    """DATABASE_URL в приоритете, иначе собираем из POSTGRES_* переменных."""
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    user = quote_plus(_env_str("POSTGRES_USER", "app"))
    password = quote_plus(_env_str("POSTGRES_PASSWORD", "app"))
    host = _env_str("POSTGRES_HOST", "db")
    port = _env_str("POSTGRES_PORT", "5432")
    database = quote_plus(_env_str("POSTGRES_DB", "galerybaner"))
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


@dataclass(frozen=True)
class Settings:
    database_url: str

    font_path: Path = DEFAULT_FONT

    cache_dir: Path = PROJECT_ROOT / "data" / "cache"
    # Готовые картинки истории лежат отдельно от кэша: кэш можно чистить целиком.
    history_dir: Path = PROJECT_ROOT / "data" / "history"
    cache_ttl_hours: int = 24
    http_timeout: int = 10
    max_image_bytes: int = 20 * 1024 * 1024
    allow_private_hosts: bool = True

    gallery_page_size: int = 12
    gallery_columns: int = 4
    history_limit: int = 48
    recent_texts_days: int = 30
    recent_texts_limit: int = 30

    preview_max_side: int = 560
    thumb_max_side: int = 480
    history_image_max_side: int = 1280

    # Макет по умолчанию: тема над центром, сообщение — под ним.
    theme_text_scale: float = 0.155
    message_text_scale: float = 0.125
    theme_pos_y: float = 0.35
    message_pos_y: float = 0.65
    default_max_width: float = 0.70
    default_align: str = "left"
    default_color: str = "#000000"
    max_lines: int = 2

    # Физические размеры: отступ задаётся в мм и переводится в долю ширины.
    banner_width_mm: float = 1000.0
    left_margin_mm: float = 50.0
    message_scale_gap: float = 0.03

    min_text_scale: float = 0.01
    max_text_scale: float = 0.20
    compare_step: float = 0.02

    @property
    def page_size(self) -> int:
        return max(1, self.gallery_page_size)


def resolve_font_path(settings: Settings) -> Path:
    """Первый существующий шрифт: сначала настроенный, затем системные запасные."""
    candidates = (settings.font_path, *FONT_FALLBACKS)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Не найден файл шрифта. Положите TTF в app/assets/fonts/ "
        "или задайте переменную окружения FONT_PATH."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=build_database_url(),
        font_path=Path(_env_str("FONT_PATH", str(DEFAULT_FONT))),
        cache_dir=Path(_env_str("CACHE_DIR", str(PROJECT_ROOT / "data" / "cache"))),
        history_dir=Path(_env_str("HISTORY_DIR", str(PROJECT_ROOT / "data" / "history"))),
        cache_ttl_hours=_env_int("CACHE_TTL_HOURS", 24),
        http_timeout=_env_int("HTTP_TIMEOUT", 10),
        max_image_bytes=_env_int("MAX_IMAGE_BYTES", 20 * 1024 * 1024),
        allow_private_hosts=_env_bool("IMAGES_ALLOW_PRIVATE_HOSTS", True),
        gallery_page_size=_env_int("GALLERY_PAGE_SIZE", 12),
        gallery_columns=_env_int("GALLERY_COLUMNS", 4),
        history_limit=_env_int("HISTORY_LIMIT", 24),
        recent_texts_days=_env_int("RECENT_TEXTS_DAYS", 30),
        recent_texts_limit=_env_int("RECENT_TEXTS_LIMIT", 30),
        preview_max_side=_env_int("PREVIEW_MAX_SIDE", 560),
        thumb_max_side=_env_int("THUMB_MAX_SIDE", 480),
        theme_text_scale=_env_float("THEME_TEXT_SCALE", 0.155),
        message_text_scale=_env_float("MESSAGE_TEXT_SCALE", 0.125),
        min_text_scale=_env_float("MIN_TEXT_SCALE", 0.01),
        max_text_scale=_env_float("MAX_TEXT_SCALE", 0.20),
        compare_step=_env_float("COMPARE_STEP", 0.02),
    )
