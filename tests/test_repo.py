"""Тесты репозитория на реальном Postgres.

Пропускаются, если не задан TEST_DATABASE_URL. Защита от случайного запуска
на рабочей базе: имя базы обязано содержать «test».
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from sqlalchemy.exc import IntegrityError

from app.core import repo
from app.core.models import ShowcaseEntry
from app.core.render import WEIGHT_MESSAGE, WEIGHT_THEME, BannerSpec, TextBlock

pytestmark = pytest.mark.usefixtures("test_database_url")


@pytest.fixture(scope="session")
def engine(test_database_url: str):
    database = make_url(test_database_url).database or ""
    if "test" not in database:
        pytest.skip("Тесты пишут в базу, в имени которой должно быть 'test'")
    eng = create_engine(test_database_url, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine) -> Session:
    maker = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = maker()
    db.execute(
        text(
            "TRUNCATE previews, banner_tags, banners, tags, communication_showcase "
            "RESTART IDENTITY CASCADE"
        )
    )
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def make_spec(theme: str = "Скидка 30%", message: str = "До воскресенья") -> BannerSpec:
    return BannerSpec(
        theme=TextBlock(text=theme, text_scale=0.155, pos_y=0.30, weight=WEIGHT_THEME),
        message=TextBlock(text=message, text_scale=0.09, pos_y=0.70, weight=WEIGHT_MESSAGE),
    )


def make_banner(session: Session, url: str = "https://example.com/a.jpg", **kwargs):
    kwargs.setdefault("description", "Тестовый баннер")
    return repo.create_banner(session, url=url, **kwargs)


def test_create_and_search_by_description(session: Session) -> None:
    repo.create_banner(
        session, url="https://example.com/spring.jpg", description="Весенняя распродажа", tags=["скидки"]
    )
    repo.create_banner(
        session, url="https://example.com/black.jpg", description="Чёрная пятница", tags=["промо"]
    )

    found, total = repo.search_banners(session, search="распродажа")

    assert total == 1
    assert found[0].url.endswith("spring.jpg")
    assert [tag.name for tag in found[0].tags] == ["скидки"]


def test_tag_filter_uses_and_semantics(session: Session) -> None:
    repo.create_banner(
        session, url="https://example.com/both.jpg", description="оба тега", tags=["скидки", "промо"]
    )
    repo.create_banner(
        session, url="https://example.com/one.jpg", description="один тег", tags=["скидки"]
    )

    both, total_both = repo.search_banners(session, tags=["скидки", "промо"])
    only_discount, total_discount = repo.search_banners(session, tags=["скидки"])

    assert total_both == 1
    assert both[0].description == "оба тега"
    assert total_discount == 2
    assert len(only_discount) == 2


def test_tag_filter_is_exact_match(session: Session) -> None:
    repo.create_banner(
        session, url="https://example.com/long.jpg", description="x", tags=["скидки-онлайн"]
    )

    _, total = repo.search_banners(session, tags=["скидки"])

    assert total == 0


def test_tag_usage_counts_banners(session: Session) -> None:
    repo.create_banner(session, url="https://example.com/1.jpg", tags=["скидки"])
    repo.create_banner(session, url="https://example.com/2.jpg", tags=["скидки", "промо"])

    usage = dict(repo.tag_usage(session))

    assert usage["скидки"] == 2
    assert usage["промо"] == 1


def test_pagination_slices_results(session: Session) -> None:
    for index in range(5):
        repo.create_banner(session, url=f"https://example.com/{index}.jpg", description=f"# {index}")

    page_one, total = repo.search_banners(session, limit=2, offset=0)
    page_two, _ = repo.search_banners(session, limit=2, offset=2)

    assert total == 5
    assert len(page_one) == 2
    assert {banner.id for banner in page_one}.isdisjoint({banner.id for banner in page_two})


def test_update_replaces_tags(session: Session) -> None:
    banner = repo.create_banner(
        session, url="https://example.com/u.jpg", description="старое", tags=["скидки"]
    )

    repo.update_banner(
        session, banner.id, url="https://example.com/u2.jpg", description="новое", tags=["промо"]
    )
    session.expire_all()
    updated = repo.get_banner(session, banner.id)

    assert updated is not None
    assert updated.description == "новое"
    assert updated.url.endswith("u2.jpg")
    assert [tag.name for tag in updated.tags] == ["промо"]


def test_preview_stores_both_blocks(session: Session) -> None:
    banner = make_banner(session)

    saved = repo.save_preview(session, banner_id=banner.id, spec=make_spec())

    assert saved.theme_text == "Скидка 30%"
    assert saved.message_text == "До воскресенья"
    assert float(saved.theme_scale) == pytest.approx(0.155, abs=1e-4)
    assert float(saved.message_scale) == pytest.approx(0.09, abs=1e-4)
    assert float(saved.theme_pos_y) == pytest.approx(0.30, abs=1e-4)
    assert float(saved.message_pos_y) == pytest.approx(0.70, abs=1e-4)


def test_delete_keeps_history_row(session: Session) -> None:
    banner = make_banner(session)
    repo.save_preview(session, banner_id=banner.id, spec=make_spec())
    session.commit()

    assert repo.delete_banner(session, banner.id) is True
    session.commit()

    previews = repo.recent_previews(session)
    assert len(previews) == 1
    assert previews[0].banner_id is None
    assert previews[0].theme_text == "Скидка 30%"


def test_recent_texts_counts_both_kinds(session: Session) -> None:
    banner = make_banner(session)

    for _ in range(2):
        repo.save_preview(session, banner_id=banner.id, spec=make_spec("Повтор", "Коротко"))
    repo.save_preview(session, banner_id=banner.id, spec=make_spec("Другая тема", "Другое сообщение"))

    texts = dict(repo.recent_texts(session, days=30))

    assert texts["Повтор"] == 2
    assert texts["Коротко"] == 2
    assert texts["Другая тема"] == 1
    assert texts["Другое сообщение"] == 1


def test_recent_texts_can_filter_by_kind(session: Session) -> None:
    banner = make_banner(session)
    repo.save_preview(session, banner_id=banner.id, spec=make_spec("Только тема", "Только сообщение"))

    themes = dict(repo.recent_texts(session, kind="theme"))
    messages = dict(repo.recent_texts(session, kind="message"))

    assert "Только тема" in themes
    assert "Только сообщение" not in themes
    assert "Только сообщение" in messages
    assert "Только тема" not in messages


def test_empty_preview_is_rejected(session: Session) -> None:
    banner = make_banner(session)

    with pytest.raises(repo.ValidationError):
        repo.save_preview(session, banner_id=banner.id, spec=make_spec(theme="  ", message=" "))


def test_invalid_url_is_rejected(session: Session) -> None:
    with pytest.raises(repo.ValidationError):
        repo.create_banner(session, url="ftp://example.com/a.jpg")


def test_duplicate_url_is_rejected(session: Session) -> None:
    repo.create_banner(session, url="https://example.com/same.jpg", description="первый")

    with pytest.raises(repo.ValidationError):
        repo.create_banner(session, url="https://example.com/same.jpg", description="второй")


def test_update_to_taken_url_is_rejected(session: Session) -> None:
    repo.create_banner(session, url="https://example.com/a.jpg")
    second = repo.create_banner(session, url="https://example.com/b.jpg")

    with pytest.raises(repo.ValidationError):
        repo.update_banner(
            session, second.id, url="https://example.com/a.jpg", description="", tags=[]
        )


def test_update_keeps_own_url(session: Session) -> None:
    banner = repo.create_banner(session, url="https://example.com/c.jpg", description="старое")

    updated = repo.update_banner(
        session, banner.id, url=banner.url, description="новое", tags=[]
    )

    assert updated.description == "новое"


def test_banner_color_is_saved(session: Session) -> None:
    banner = repo.create_banner(
        session, url="https://example.com/col.jpg", center_color="#123456", center_hue=210.0
    )

    session.expire_all()
    saved = repo.get_banner(session, banner.id)

    assert saved is not None
    assert saved.center_color == "#123456"
    assert float(saved.center_hue) == pytest.approx(210.0, abs=0.01)


def test_set_banner_color_updates_row(session: Session) -> None:
    banner = repo.create_banner(session, url="https://example.com/set.jpg")

    repo.set_banner_color(session, banner.id, "#00FF00", 120.0)
    session.expire_all()
    saved = repo.get_banner(session, banner.id)

    assert saved is not None
    assert saved.center_color == "#00FF00"
    assert float(saved.center_hue) == pytest.approx(120.0, abs=0.01)


def test_sort_by_color_follows_hue(session: Session) -> None:
    repo.create_banner(
        session, url="https://example.com/blue.jpg", center_color="#0000FF", center_hue=240.0
    )
    repo.create_banner(
        session, url="https://example.com/red.jpg", center_color="#FF0000", center_hue=0.0
    )
    repo.create_banner(
        session, url="https://example.com/gray.jpg", center_color="#808080", center_hue=None
    )

    found, total = repo.search_banners(session, sort="color")

    assert total == 3
    assert [banner.center_hue for banner in found] == [0.0, 240.0, None]


def test_sort_new_puts_latest_first(session: Session) -> None:
    repo.create_banner(session, url="https://example.com/first.jpg")
    second = repo.create_banner(session, url="https://example.com/second.jpg")

    found, _ = repo.search_banners(session, sort="new")

    assert found[0].id == second.id


def test_preview_stores_image_key(session: Session) -> None:
    banner = make_banner(session)
    image_key = "a" * 32 + ".png"

    saved = repo.save_preview(
        session, banner_id=banner.id, spec=make_spec(), image_key=image_key
    )

    assert saved.image_key == image_key
    assert saved.is_favorite is False


def test_favorite_toggle(session: Session) -> None:
    banner = make_banner(session)
    preview = repo.save_preview(session, banner_id=banner.id, spec=make_spec())

    assert repo.set_preview_favorite(session, preview.id, True) is True
    session.expire_all()

    assert repo.recent_previews(session)[0].is_favorite is True
    assert repo.favorite_count(session) == 1


def test_favorites_only_filter(session: Session) -> None:
    banner = make_banner(session)
    first = repo.save_preview(session, banner_id=banner.id, spec=make_spec("Первая", "А"))
    repo.save_preview(session, banner_id=banner.id, spec=make_spec("Вторая", "Б"))
    repo.set_preview_favorite(session, first.id, True)

    favorites = repo.recent_previews(session, favorites_only=True)

    assert len(favorites) == 1
    assert favorites[0].theme_text == "Первая"


def test_delete_preview_returns_image_key(session: Session) -> None:
    banner = make_banner(session)
    image_key = "b" * 32 + ".png"
    preview = repo.save_preview(
        session, banner_id=banner.id, spec=make_spec(), image_key=image_key
    )

    removed = repo.delete_preview(session, preview.id)

    assert removed == image_key
    assert repo.recent_previews(session) == []
    assert repo.delete_preview(session, preview.id) is None


def test_history_order_by_date(session: Session) -> None:
    banner = make_banner(session)
    first = repo.save_preview(session, banner_id=banner.id, spec=make_spec("Один", ""))
    second = repo.save_preview(session, banner_id=banner.id, spec=make_spec("Два", ""))
    third = repo.save_preview(session, banner_id=banner.id, spec=make_spec("Три", ""))

    newest = [p.id for p in repo.recent_previews(session, order="new")]
    oldest = [p.id for p in repo.recent_previews(session, order="old")]

    assert newest == [third.id, second.id, first.id]
    assert oldest == [first.id, second.id, third.id]


def add_showcase_row(
    session: Session,
    *,
    key: str,
    page: str,
    slot: str,
    url: str = "https://example.com/b.jpg",
    text: str = "",
    clients: int = 0,
) -> None:
    session.add(
        ShowcaseEntry(
            combination_key=key,
            page=page,
            slot=slot,
            banner_url=url,
            text=text,
            clients_count=clients,
        )
    )
    session.flush()


def test_showcase_groups_rows_by_combination(session: Session) -> None:
    add_showcase_row(session, key="A", page="home", slot="main", clients=1000)
    add_showcase_row(session, key="A", page="home", slot="deposits", clients=1000)
    add_showcase_row(session, key="B", page="home", slot="main", clients=50)

    combinations = repo.list_showcase_combinations(session, "home")

    assert [combination.key for combination in combinations] == ["A", "B"]
    assert combinations[0].clients_count == 1000
    assert set(combinations[0].rows) == {"main", "deposits"}


def test_showcase_accepts_russian_names(session: Session) -> None:
    add_showcase_row(session, key="A", page="Главный", slot="Основной баннер")
    add_showcase_row(session, key="A", page="Главный", slot="Под вкладами")

    combinations = repo.list_showcase_combinations(session, "home")

    assert len(combinations) == 1
    assert set(combinations[0].rows) == {"main", "deposits"}


def test_showcase_ignores_unknown_slots(session: Session) -> None:
    add_showcase_row(session, key="A", page="home", slot="неведомое место")

    assert repo.list_showcase_combinations(session, "home") == []

    _pages, slots = repo.unknown_showcase_values(session)
    assert slots == ["неведомое место"]


def test_showcase_summary_counts_combinations(session: Session) -> None:
    add_showcase_row(session, key="A", page="home", slot="main")
    add_showcase_row(session, key="B", page="home", slot="main")
    add_showcase_row(session, key="C", page="loyalty", slot="top")

    summary = repo.showcase_pages_summary(session)

    assert summary["home"] == 2
    assert summary["loyalty"] == 1
    assert summary["catalog"] == 0
    assert repo.showcase_rows_total(session) == 3


def test_showcase_slot_is_unique_within_combination(session: Session) -> None:
    add_showcase_row(session, key="A", page="home", slot="main")

    with pytest.raises(IntegrityError):
        add_showcase_row(session, key="A", page="home", slot="main")


def test_showcase_same_slot_in_different_combinations(session: Session) -> None:
    add_showcase_row(session, key="A", page="home", slot="main")
    add_showcase_row(session, key="B", page="home", slot="main")

    combinations = repo.list_showcase_combinations(session, "home")

    assert len(combinations) == 2
    assert all("main" in combination.rows for combination in combinations)


def test_push_needs_no_image(session: Session) -> None:
    push = repo.create_banner(
        session, kind="push", url="", title="Заголовок", message="Текст", description="Пуш"
    )

    assert push.url is None
    assert push.kind == "push"
    assert push.title == "Заголовок"


def test_sms_needs_neither_image_nor_title(session: Session) -> None:
    sms = repo.create_banner(session, kind="sms", url="", message="Код 1234", description="СМС")

    assert sms.url is None
    assert sms.kind == "sms"
    assert sms.title == ""


def test_banner_kinds_require_image(session: Session) -> None:
    for kind in ("ordinary", "popup"):
        with pytest.raises(repo.ValidationError):
            repo.create_banner(session, kind=kind, url="", description="без картинки")


def test_empty_urls_do_not_conflict(session: Session) -> None:
    repo.create_banner(session, kind="push", url="", message="Первый", description="раз")
    repo.create_banner(session, kind="push", url="", message="Второй", description="два")
    repo.create_banner(session, kind="sms", url="", message="Третий", description="три")

    assert len(repo.list_banners_brief(session, kind="push")) == 2


def test_search_filters_by_kinds(session: Session) -> None:
    repo.create_banner(session, url="https://example.com/k1.jpg", description="баннер")
    repo.create_banner(session, kind="popup", url="https://example.com/k2.jpg", description="попуп")
    repo.create_banner(session, kind="push", url="", message="пуш", description="пуш")

    found, total = repo.search_banners(session, kinds=["push"])

    assert total == 1
    assert found[0].description == "пуш"


def test_list_brief_filters_by_kind(session: Session) -> None:
    repo.create_banner(session, url="https://example.com/b1.jpg", description="баннер")
    repo.create_banner(session, kind="sms", url="", message="смс", description="смс")

    briefs = repo.list_banners_brief(session, kind="ordinary")

    assert [brief.description for brief in briefs] == ["баннер"]


def test_sort_by_length_puts_short_first(session: Session) -> None:
    repo.create_banner(
        session, kind="push", url="", message="длинный текст сообщения", description="длинный"
    )
    repo.create_banner(session, kind="push", url="", message="коротко", description="короткий")

    found, _ = repo.search_banners(session, kinds=["push"], sort="length")

    assert [banner.description for banner in found] == ["короткий", "длинный"]


def test_popup_action_text_is_saved(session: Session) -> None:
    banner = repo.create_banner(
        session,
        kind="popup",
        url="https://example.com/popup.jpg",
        action_text="Купить",
        description="попуп",
    )

    session.expire_all()
    saved = repo.get_banner(session, banner.id)

    assert saved is not None
    assert saved.action_text == "Купить"


def test_touch_banner_moves_updated_at(session: Session) -> None:
    from datetime import datetime, timedelta, timezone

    banner = repo.create_banner(session, url="https://example.com/touch.jpg", description="тач")
    session.flush()

    past = datetime.now(timezone.utc) - timedelta(days=10)
    banner.updated_at = past
    session.flush()
    session.expire_all()

    repo.touch_banner(session, banner.id)
    session.expire_all()

    fresh = repo.get_banner(session, banner.id)
    assert fresh is not None
    assert fresh.updated_at > past


def test_sort_old_puts_least_recent_first(session: Session) -> None:
    from datetime import datetime, timedelta, timezone

    old_one = repo.create_banner(session, url="https://example.com/o1.jpg", description="старый")
    new_one = repo.create_banner(session, url="https://example.com/o2.jpg", description="новый")
    session.flush()

    now = datetime.now(timezone.utc)
    old_one.updated_at = now - timedelta(days=30)
    new_one.updated_at = now
    session.flush()

    found, _ = repo.search_banners(session, sort="old")

    assert [banner.id for banner in found][:2] == [old_one.id, new_one.id]


def test_text_template_created_and_listed(session: Session) -> None:
    template = repo.create_text_template(
        session, title="Заголовок", message="Текст сообщения", tags=["промо"]
    )

    items, total = repo.list_text_templates(session)

    assert total == 1
    assert items[0].id == template.id
    assert items[0].title == "Заголовок"
    assert [tag.name for tag in items[0].tags] == ["промо"]


def test_text_template_requires_text(session: Session) -> None:
    with pytest.raises(repo.ValidationError):
        repo.create_text_template(session, title="  ", message=" ")


def test_text_templates_filter_by_tag_and_search(session: Session) -> None:
    repo.create_text_template(session, title="Скидка", message="Только сегодня", tags=["промо"])
    repo.create_text_template(session, title="Доставка", message="Бесплатно", tags=["логистика"])

    by_tag, total_tag = repo.list_text_templates(session, tags=["промо"])
    by_search, total_search = repo.list_text_templates(session, search="Бесплатно")

    assert total_tag == 1
    assert by_tag[0].title == "Скидка"
    assert total_search == 1
    assert by_search[0].title == "Доставка"


def test_text_templates_sort_by_length(session: Session) -> None:
    repo.create_text_template(session, title="", message="Длинный текст сообщения")
    repo.create_text_template(session, title="", message="Коротко")

    items, _ = repo.list_text_templates(session, sort="length")

    assert [item.message for item in items] == ["Коротко", "Длинный текст сообщения"]


def test_text_template_delete(session: Session) -> None:
    template = repo.create_text_template(session, message="Удалить меня")

    assert repo.delete_text_template(session, template.id) is True
    assert repo.list_text_templates(session)[1] == 0
    assert repo.delete_text_template(session, template.id) is False


def test_text_templates_filter_by_kind(session: Session) -> None:
    repo.create_text_template(session, kind="push", title="Пуш", message="Текст пуша")
    repo.create_text_template(session, kind="sms", message="Текст смс")

    pushes, total_push = repo.list_text_templates(session, kinds=["push"])
    sms, total_sms = repo.list_text_templates(session, kinds=["sms"])

    assert total_push == 1
    assert pushes[0].title == "Пуш"
    assert total_sms == 1
    assert sms[0].message == "Текст смс"


def test_text_template_kind_is_updated(session: Session) -> None:
    template = repo.create_text_template(session, kind="sms", message="Текст")

    assert repo.update_text_template(
        session, template.id, kind="popup", title="Новая тема", message="Новый текст", tags=[]
    )
    session.expire_all()

    fresh = repo.get_text_template(session, template.id)
    assert fresh is not None
    assert fresh.kind == "popup"
    assert fresh.title == "Новая тема"
