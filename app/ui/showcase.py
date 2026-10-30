"""Витрина коммуникаций: примерка баннеров на экранах приложения.

Вёрстка повторяет референсы из AppToBanner: главная, кэшбэк и бонусы, история
операций, продуктовый каталог. Баннеры встают в свои посадочные места.
"""

from __future__ import annotations

import base64
import html
import io
import sys
from dataclasses import dataclass

from PIL import Image
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.core import repo, storage, templates
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.showcase import SHOWCASE_PAGES, ShowcasePage, page_by_key
from app.core.texts import shorten
from app.ui.common import load_thumb

settings = get_settings()


@dataclass
class SlotView:
    title: str
    image: str | None
    text: str
    assigned: bool


PHONE_STYLE = """
<style>
  .phone { width: 100%; max-width: 380px; margin: 0 auto; border-radius: 30px;
           background: #F4F5F7; overflow: hidden; position: relative;
           border: 1px solid rgba(255,255,255,0.16);
           box-shadow: 0 18px 44px rgba(0,0,0,0.45); font-family: "Inter", system-ui, sans-serif; }
  .phone.compact { max-width: 320px; border-radius: 24px; }
  .status { display: flex; justify-content: space-between; padding: 10px 18px 4px;
            font-size: 10px; color: #6E7480; background: transparent; }
  .page { background: #F4F5F7; padding-bottom: 46px; }

  .hero { padding: 10px 16px 26px; color: #fff;
          background: linear-gradient(140deg, #FFB25C 0%, #FF8A3D 45%, #FF5F00 100%); }
  .hero.blue { background: linear-gradient(140deg, #6FB6FF 0%, #3E8BFF 60%, #2F6FE0 100%); }
  .hero-top { display: flex; align-items: center; justify-content: space-between; }
  .avatar { width: 34px; height: 34px; border-radius: 50%; background: rgba(255,255,255,0.9);
            color: #FF5F00; display: flex; align-items: center; justify-content: center;
            font-size: 12px; font-weight: 700; }
  .hero-actions { display: flex; gap: 8px; }
  .chip { width: 30px; height: 30px; border-radius: 50%; background: rgba(255,255,255,0.9); }
  .hero-title { font-size: 13px; margin-top: 12px; opacity: .9; }
  .hero-name { font-size: 17px; font-weight: 700; }
  .hero-cap { font-size: 15px; font-weight: 700; text-align: center; padding-top: 6px; }

  .sheet { background: #F4F5F7; padding: 0 12px; margin-top: -14px; border-radius: 18px 18px 0 0; }
  .card { background: #fff; border-radius: 16px; padding: 12px 14px;
          box-shadow: 0 4px 14px rgba(16,20,26,0.06); margin-bottom: 10px; }
  .row { display: flex; gap: 10px; align-items: stretch; }
  .row > * { flex: 1 1 0; }
  .label { font-size: 11px; color: #8A8F98; }
  .value { font-size: 15px; font-weight: 700; color: #16171A; }
  .muted { font-size: 11px; color: #8A8F98; }
  .icon-tile { background: #fff; border-radius: 14px; height: 44px;
               box-shadow: 0 4px 14px rgba(16,20,26,0.06); }
  .icons { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 44%; }
  .section { display: flex; justify-content: space-between; align-items: center;
             font-size: 14px; font-weight: 700; color: #16171A; padding: 12px 4px 8px; }
  .section span { color: #B9BEC6; font-weight: 400; }

  .slot { border-radius: 16px; margin: 6px 0 12px; position: relative;
          overflow: hidden; background: #fff; }
  .slot img { width: 100%; height: auto; display: block; }
  .slot.empty { border: 1px dashed #C9CDD4; background: #EFF1F4; display: flex;
                align-items: center; justify-content: center; color: #8A8F98;
                font-size: 11px; min-height: 96px; padding: 12px; text-align: center; }
  .slot.text-only { background: #EFF1F4; padding: 14px; }
  .slot.text-only .text-only-copy { color: #16171A; font-size: 12px; font-weight: 600;
                                    line-height: 1.3; word-break: break-word; }
  .slot .close { position: absolute; right: 8px; top: 6px; width: 18px; height: 18px;
                 border-radius: 50%; background: rgba(255,255,255,0.85); color: #6E7480;
                 font-size: 12px; line-height: 18px; text-align: center; }

  .chips { display: flex; gap: 6px; padding: 6px 12px 10px; }
  .pill { background: #EDEFF2; border-radius: 10px; padding: 6px 12px; font-size: 10px; color: #3A3F47; }
  .list-row { display: flex; gap: 10px; align-items: center; padding: 8px 12px; }
  .logo { width: 30px; height: 30px; border-radius: 50%; background: #FFD9C2; flex: 0 0 30px; }
  .row-title { font-size: 12px; font-weight: 600; color: #16171A; }
  .row-sub { font-size: 10px; color: #8A8F98; }
  .row-amount { margin-left: auto; font-size: 12px; font-weight: 600; color: #16171A; }

  .btn { background: #FF6A13; color: #fff; border-radius: 14px; text-align: center;
         padding: 11px; font-size: 12px; font-weight: 600; margin: 8px 4px; }
  .tabbar { position: absolute; bottom: 0; left: 0; right: 0; height: 44px;
            background: #fff; display: flex; align-items: center; justify-content: space-around;
            font-size: 9px; color: #9AA0A8; border-top: 1px solid #E6E8EC; }
  .tabbar .active { color: #FF6A13; font-weight: 700; }
</style>
"""


def slot_html(view: SlotView) -> str:
    """Баннер в посадочном месте: креатив целиком, без обрезки и наложений."""
    title = html.escape(view.title)
    if not view.assigned:
        return f'<div class="slot empty">{title} — не задано</div>'

    if not view.image:
        if view.text:
            return (
                f'<div class="slot text-only">'
                f'<div class="text-only-copy">{html.escape(shorten(view.text, 90))}</div></div>'
            )
        return f'<div class="slot empty">{title} — баннер недоступен</div>'

    return (
        f'<div class="slot">'
        f'<img src="data:image/jpeg;base64,{view.image}" alt="{title}" />'
        f'<div class="close">×</div></div>'
    )


def phone_shell(page_title: str, body: str, *, active_tab: str, compact: bool) -> str:
    cls = "phone compact" if compact else "phone"
    tabs = "".join(
        f'<span class="{"active" if name == active_tab else ""}">{name}</span>'
        for name in ("Главная", "История", "Платежи", "Поддержка", "Ещё")
    )
    return (
        f'{PHONE_STYLE}<div class="{cls}">'
        f'<div class="status"><span>9:41</span><span>{html.escape(page_title)}</span></div>'
        f'<div class="page">{body}</div>'
        f'<div class="tabbar">{tabs}</div></div>'
    )


def main_page_body(views: dict[str, SlotView]) -> str:
    return (
        '<div class="hero">'
        '<div class="hero-top"><div class="avatar">ДВ</div>'
        '<div class="hero-actions"><div class="chip"></div><div class="chip"></div></div></div>'
        '<div class="hero-title">Здравствуйте,</div>'
        '<div class="hero-name">Дмитрий Викторович!</div>'
        "</div>"
        '<div class="sheet">'
        '<div class="card row"><div>'
        '<div class="label">В кошельке</div><div class="value">•••• ••••</div>'
        "</div><div class=\"icons\"><div class=\"icon-tile\"></div><div class=\"icon-tile\"></div>"
        '<div class="icon-tile"></div><div class="icon-tile"></div></div></div>'
        '<div class="row">'
        '<div class="card"><div class="label">Кэшбэк и бонусы</div>'
        '<div class="value">•••••</div></div>'
        '<div class="card"><div class="label">Траты за октябрь</div>'
        '<div class="value">•••••</div></div></div>'
        f"{slot_html(views['main'])}"
        '<div class="section">Карты <span>⌄</span></div>'
        f"{slot_html(views['cards'])}"
        '<div class="section">Вклады и накопления <span>⌄</span></div>'
        f"{slot_html(views['deposits'])}"
        '<div class="section">Счета <span>⌄</span></div>'
        f"{slot_html(views['accounts'])}"
        '<div class="section">Кредиты <span>⌄</span></div>'
        f"{slot_html(views['credits'])}"
        '<div class="btn">Открыть новый продукт</div>'
        "</div>"
    )


def loyalty_page_body(views: dict[str, SlotView]) -> str:
    return (
        '<div class="hero blue"><div class="hero-cap">Кэшбэк и бонусы</div></div>'
        '<div class="sheet">'
        '<div class="card"><div class="value">Копится в октябре</div>'
        '<div class="muted">Можно будет обменять 5 ноября</div>'
        '<div class="muted" style="margin-top:8px">899 ★ &nbsp;&nbsp; из 5 000 ★</div></div>'
        '<div class="row"><div class="card"><div class="value">История</div>'
        '<div class="muted">Списания и начисления</div></div>'
        '<div class="card"><div class="value">Детализация</div>'
        '<div class="muted">Начисления по месяцам</div></div></div>'
        f"{slot_html(views['top'])}"
        '<div class="card"><div class="label">CARD ТП Кошелек Gold</div>'
        '<div class="value">7,59 ₽</div><div class="muted">Стандарт-Бонус</div></div>'
        '<div class="section">Приглашайте друзей</div>'
        '<div class="row"><div class="card"><div class="row-sub">Дебетовая UnionPay</div>'
        '<div class="value">1 000 ₽</div></div>'
        '<div class="card"><div class="row-sub">Кредиты наличными</div>'
        '<div class="value">2 000 ₽</div></div></div>'
        f"{slot_html(views['bottom'])}"
        "</div>"
    )


def transactions_page_body(views: dict[str, SlotView]) -> str:
    rows = "".join(
        '<div class="list-row"><div class="logo"></div><div>'
        f'<div class="row-title">{name}</div><div class="row-sub">Покупки</div></div>'
        f'<div class="row-amount">{amount}</div></div>'
        for name, amount in (
            ("DODOPIZZABLAGOVESCHENSK", "-1 058 ₽"),
            ("DODOPIZZABLAGOVESCHENSK", "-1 463 ₽"),
            ("AZS 9", "-3 496,50 ₽"),
            ("Карта • 6803", "-4 348 ₽"),
        )
    )
    return (
        '<div style="padding:10px 14px 0;font-size:18px;font-weight:700;color:#16171A">'
        "История операций</div>"
        '<div class="chips"><div class="pill">⚙</div><div class="pill">Пополнение</div>'
        '<div class="pill">Списание</div><div class="pill">Кэшбэк</div></div>'
        '<div style="padding:0 12px">'
        '<div class="card row"><div><div class="label">Траты за октябрь</div>'
        '<div class="value">335 177,32 ₽</div></div></div>'
        f"{slot_html(views['top'])}"
        '<div class="section">Сегодня</div></div>'
        f"{rows}"
    )


def catalog_page_body(views: dict[str, SlotView]) -> str:
    rows = "".join(
        '<div class="card" style="display:flex;gap:10px;align-items:center">'
        '<div class="logo"></div><div>'
        f'<div class="row-title">{title}</div><div class="row-sub">{subtitle}</div></div></div>'
        for title, subtitle in (
            ("Взять кредит", "На любые цели"),
            ("Рефинансирование", "Снижение платежа по кредитам"),
            ("Выпустить дебетовую карту", "Цифровую или пластиковую"),
            ("Открыть вклад", "До 17% в рублях"),
        )
    )
    return (
        '<div style="padding:12px 14px;font-size:17px;font-weight:700;color:#16171A">'
        "Продуктовый каталог</div>"
        f'<div style="padding:0 12px">{slot_html(views["top"])}</div>'
        f'<div style="padding:0 12px 12px">{rows}</div>'
    )


def build_mockup(page: ShowcasePage, views: dict[str, SlotView], compact: bool = False) -> str:
    if page.kind == "home":
        body = main_page_body(views)
        tab = "Главная"
    elif page.kind == "loyalty":
        body = loyalty_page_body(views)
        tab = "Ещё"
    elif page.kind == "transactions":
        body = transactions_page_body(views)
        tab = "История"
    else:
        body = catalog_page_body(views)
        tab = "Главная"

    return phone_shell(page.title, body, active_tab=tab, compact=compact)


@st.cache_data(show_spinner=False, ttl=3600, max_entries=500)
def image_b64(url: str) -> str | None:
    data, _error = load_thumb(url, settings.thumb_max_side)
    if not data:
        return None
    return base64.b64encode(data).decode("ascii")


def views_for(page: ShowcasePage, combination: repo.ShowcaseCombination) -> dict[str, SlotView]:
    views: dict[str, SlotView] = {}
    for slot in page.slots:
        entry = combination.slot(slot.key)
        if entry is None:
            views[slot.key] = SlotView(slot.title, None, "", False)
            continue
        views[slot.key] = SlotView(
            title=slot.title,
            image=image_b64(entry.banner_url) if entry.banner_url else None,
            text=entry.text,
            assigned=True,
        )
    return views


def format_clients(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " клиентов"


def variant_label(index: int, combination: repo.ShowcaseCombination, page: ShowcasePage) -> str:
    return (
        f"№{index} · {format_clients(combination.clients_count)} · "
        f"{combination.filled_slots(page)} из {len(page.slots)} мест"
    )


@st.cache_data(show_spinner=False, ttl=3600, max_entries=300)
def favorite_image_b64(image_key: str) -> str | None:
    """Готовый снимок из истории → JPEG для подложки баннера."""
    try:
        data = storage.read_png(settings.history_dir, image_key)
    except storage.StorageError:
        return None
    if not data:
        return None

    try:
        with Image.open(io.BytesIO(data)) as img:
            thumb = img.convert("RGB")
            thumb.thumbnail((settings.thumb_max_side, settings.thumb_max_side), Image.LANCZOS)
            buffer = io.BytesIO()
            thumb.save(buffer, format="JPEG", quality=85, optimize=True)
    except Exception:  # noqa: BLE001 - битый файл не должен ронять страницу
        return None
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def favorites_for_page() -> list:
    with session_scope() as session:
        rows = repo.recent_previews(session, limit=200, favorites_only=True)
    return [row for row in rows if row.image_key]


def favorite_label(preview) -> str:
    title = (preview.theme_text or preview.message_text or "").strip()
    return f"#{preview.id} · {templates.kind_label(preview.kind)} · {shorten(title, 34)}"


def render_favorites_source() -> None:
    """Второй источник: баннеры из «Избранного» истории, примерка по местам."""
    favorites = favorites_for_page()
    if not favorites:
        st.info(
            "В истории пока нет избранных баннеров. Отметьте их звёздочкой на вкладке "
            "«История» — они появятся здесь.",
            icon="⭐",
        )
        return

    page_key = st.radio(
        "Страница",
        options=[page.key for page in SHOWCASE_PAGES],
        format_func=lambda key: page_by_key(key).title,
        horizontal=True,
        key="showcase_fav_page",
    )
    page = page_by_key(page_key)

    by_id = {preview.id: preview for preview in favorites}
    views: dict[str, SlotView] = {}
    choices: dict[str, int | None] = {}

    mockup_col, picker_col = st.columns([1.45, 1], gap="large")

    with picker_col:
        st.caption("Поставьте избранный баннер на каждое место страницы.")
        for slot in page.slots:
            options: list[int | None] = [None] + list(by_id)
            choices[slot.key] = st.selectbox(
                slot.title,
                options=options,
                format_func=lambda value: "— не задано —" if value is None else favorite_label(by_id[value]),
                key=f"showcase_fav_{page.key}_{slot.key}",
            )

    for slot in page.slots:
        chosen = choices[slot.key]
        if chosen is None:
            views[slot.key] = SlotView(slot.title, None, "", False)
            continue
        preview = by_id[chosen]
        views[slot.key] = SlotView(
            title=slot.title,
            image=favorite_image_b64(preview.image_key or ""),
            text=(preview.theme_text or preview.message_text or "").strip(),
            assigned=True,
        )

    with mockup_col:
        st.markdown(build_mockup(page, views), unsafe_allow_html=True)


st.title("Витрина коммуникаций")
st.caption(
    "Примерка баннеров на экранах приложения: главная, кэшбэк, история операций, "
    "продуктовый каталог. Данные приходят из таблицы `communication_showcase`."
)

source = st.radio(
    "Источник",
    options=["airflow", "favorites"],
    format_func=lambda value: {
        "airflow": "Комбинации из Airflow",
        "favorites": "Избранное из истории",
    }[value],
    horizontal=True,
    key="showcase_source",
)

if source == "favorites":
    render_favorites_source()
    st.stop()

with session_scope() as session:
    summary = repo.showcase_pages_summary(session)
    rows_total = repo.showcase_rows_total(session)
    unknown_pages, unknown_slots = repo.unknown_showcase_values(session)

if rows_total == 0:
    st.info(
        "Таблица витрины пока пуста. Загрузите строки в `communication_showcase`: "
        "`combination_key`, `page`, `slot`, `banner_url`, `text`, `clients_count`.",
        icon="🗂️",
    )
    st.stop()

page_key = st.radio(
    "Страница",
    options=[page.key for page in SHOWCASE_PAGES],
    format_func=lambda key: f"{page_by_key(key).title} ({summary.get(key, 0)})",
    horizontal=True,
    key="showcase_page",
)
page = page_by_key(page_key)

with session_scope() as session:
    combinations = repo.list_showcase_combinations(session, page.key)

if not combinations:
    st.info(
        f"Для страницы «{page.title}» в таблице нет строк. Проверьте значение `page`.",
        icon="🔍",
    )
    st.stop()

variant_key = f"showcase_selected_{page.key}"

toolbar_left, toolbar_right = st.columns([2, 1.2], gap="medium")
with toolbar_left:
    st.caption(f"Вариантов на странице: {len(combinations)}")
with toolbar_right:
    show_all = st.toggle(
        "Показать все варианты", value=len(combinations) > 1, key="showcase_all"
    )

labels = {
    index: variant_label(index, combination, page)
    for index, combination in enumerate(combinations, start=1)
}

if show_all and len(combinations) > 1:
    grid_columns = st.columns(2, gap="medium")
    for index, combination in enumerate(combinations):
        with grid_columns[index % 2]:
            with st.container(border=True):
                st.markdown(
                    build_mockup(page, views_for(page, combination), compact=True),
                    unsafe_allow_html=True,
                )
                st.caption(labels[index + 1])
                if st.button(
                    "Открыть этот вариант",
                    key=f"open_{page.key}_{combination.key}",
                    use_container_width=True,
                ):
                    st.session_state[variant_key] = combination.key
                    st.rerun()
    st.divider()

keys = [combination.key for combination in combinations]
current_key = st.session_state.get(variant_key)
if current_key not in keys:
    current_key = keys[0]
    st.session_state[variant_key] = current_key

selected_key = st.selectbox(
    "Вариант",
    options=keys,
    index=keys.index(current_key),
    format_func=lambda key: next(
        labels[index]
        for index, combination in enumerate(combinations, start=1)
        if combination.key == key
    ),
    key=variant_key,
)

combination = next(item for item in combinations if item.key == selected_key)

mockup_col, info_col = st.columns([1.45, 1], gap="large")

with mockup_col:
    st.markdown(build_mockup(page, views_for(page, combination)), unsafe_allow_html=True)

with info_col:
    st.metric("Клиентов с этой комбинацией", f"{combination.clients_count:,}".replace(",", " "))
    st.metric("Заполнено мест", f"{combination.filled_slots(page)} из {len(page.slots)}")
    st.caption(f"Комбинация из CRM: `{combination.key}`")

    st.divider()
    st.subheader("Посадочные места")
    for slot in page.slots:
        entry = combination.slot(slot.key)
        if entry is None:
            st.caption(f"{slot.title} — пусто")
            continue
        st.markdown(f"**{slot.title}**")
        if entry.text:
            st.caption(entry.text)
        st.caption(shorten(entry.banner_url, 70) if entry.banner_url else "ссылка не задана")

with st.expander("Диагностика выгрузки", expanded=False):
    st.caption(f"Всего строк в таблице: {rows_total}")
    if unknown_pages:
        st.warning(
            "Неизвестные значения `page`: " + ", ".join(f"«{value}»" for value in unknown_pages),
            icon="⚠️",
        )
    if unknown_slots:
        st.warning(
            "Неизвестные значения `slot`: " + ", ".join(f"«{value}»" for value in unknown_slots),
            icon="⚠️",
        )
    if not unknown_pages and not unknown_slots:
        st.caption("Все страницы и места распознаны.")
