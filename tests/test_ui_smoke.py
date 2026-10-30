"""Смоук-тесты страниц Streamlit: страница должна рендериться без исключений."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from app.core import repo, storage
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.models import ShowcaseEntry
from app.core.render import WEIGHT_MESSAGE, WEIGHT_THEME, BannerSpec, TextBlock

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PAGES = (
    "app/ui/gallery.py",
    "app/ui/notepad.py",
    "app/ui/constructor.py",
    "app/ui/showcase.py",
    "app/ui/history.py",
)


@pytest.fixture(scope="module")
def seeded(test_database_url: str) -> None:
    with session_scope() as session:
        repo.create_banner(
            session,
            url="https://example.invalid/banner-1.jpg",
            description="Смоук-баннер для тестов",
            tags=["промо", "сезон"],
        )
        repo.create_banner(
            session,
            url="https://example.invalid/banner-2.jpg",
            description="Второй смоук-баннер",
            tags=["промо"],
        )


@pytest.fixture(scope="module")
def history_entry(seeded: None):
    """Запись истории с настоящей картинкой — проверяем карточку, а не пустой экран."""
    settings = get_settings()
    buffer = io.BytesIO()
    Image.new("RGB", (320, 200), (200, 60, 60)).save(buffer, format="PNG")
    key = storage.save_png(settings.history_dir, buffer.getvalue())

    spec = BannerSpec(
        theme=TextBlock(text="Смоук", text_scale=0.155, weight=WEIGHT_THEME),
        message=TextBlock(text="Проверка истории", text_scale=0.125, weight=WEIGHT_MESSAGE),
    )
    with session_scope() as session:
        banner = repo.search_banners(session, limit=1)[0][0]
        repo.save_preview(session, banner_id=banner.id, spec=spec, image_key=key)

    yield key
    storage.delete_file(settings.history_dir, key)


@pytest.fixture(scope="module")
def showcases(seeded: None) -> None:
    """Две комбинации в таблице витрины — страница должна показать оба варианта."""
    with session_scope() as session:
        session.add_all(
            [
                ShowcaseEntry(
                    combination_key="home-A",
                    page="home",
                    slot="main",
                    banner_url="https://example.invalid/banner-1.jpg",
                    text="Первый вариант",
                    clients_count=1500,
                ),
                ShowcaseEntry(
                    combination_key="home-B",
                    page="home",
                    slot="main",
                    banner_url="https://example.invalid/banner-2.jpg",
                    text="Второй вариант",
                    clients_count=300,
                ),
            ]
        )


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page: str, seeded: None) -> None:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / page), default_timeout=60)
    app.run()

    assert not app.exception, f"{page}: {app.exception}"


def test_notepad_renders_text_template(seeded: None) -> None:
    with session_scope() as session:
        repo.create_text_template(
            session,
            title="Смоук-заголовок",
            message="Текст из блокнота",
            tags=["промо"],
        )

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "app/ui/notepad.py"), default_timeout=60)
    app.run()

    assert not app.exception, app.exception
    page_text = " ".join(str(element.value) for element in app.markdown)
    assert "Текст из блокнота" in page_text


def test_history_renders_saved_entry(history_entry: str) -> None:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "app/ui/history.py"), default_timeout=60)
    app.run()

    assert not app.exception, app.exception
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "Тема" in captions


def test_showcase_lists_all_variants(showcases: None) -> None:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "app/ui/showcase.py"), default_timeout=60)
    app.run()

    assert not app.exception, app.exception
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "Вариантов на странице: 2" in captions
    assert "№1" in captions and "№2" in captions


def test_gallery_favorites_empty_state(seeded: None) -> None:
    """Пустое избранное не должно ронять страницу (иконка-звёздочка)."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "app/ui/gallery.py"), default_timeout=60)
    app.session_state["gallery_favorites_only"] = True
    app.run()

    assert not app.exception, app.exception


def test_history_favorites_empty_state(history_entry: str) -> None:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "app/ui/history.py"), default_timeout=60)
    app.session_state["history_favorites_only"] = True
    app.run()

    assert not app.exception, app.exception
