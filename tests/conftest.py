"""Общие фикстуры: путь к шрифту и подключение к тестовой БД."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings, resolve_font_path


@pytest.fixture(scope="session")
def font_path() -> Path:
    try:
        return resolve_font_path(get_settings())
    except FileNotFoundError:
        pytest.skip("Не найден файл шрифта для рендера")


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TEST_DATABASE_URL не задан")
    return url
