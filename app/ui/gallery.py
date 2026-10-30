"""Галерея шаблонов: только картинки — Ordinary и Popup, вкладками по типу."""

from __future__ import annotations

import base64
import html as html_lib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import streamlit.components.v1 as components

from app.core import colors, images, repo, templates
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.texts import parse_tags, shorten
from app.ui.common import load_thumb

settings = get_settings()

COPY_BUTTON_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; background: transparent; }
  .wrap { display: flex; align-items: center; height: 40px; }
  button {
    width: 100%; height: 38px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 8px; background: #1A2028; color: #E6EAF0;
    cursor: pointer; transition: border-color .15s, color .15s;
  }
  button:hover { border-color: #F5A524; color: #F5A524; }
  button.ok { border-color: #46C08A; color: #46C08A; }
  button.fail { border-color: #E5573F; color: #E5573F; }
  svg { display: block; }
</style>
</head>
<body>
  <div class="wrap">
    <button id="copy" type="button" title="Скопировать ссылку в буфер"
            aria-label="Скопировать ссылку в буфер">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="2" width="6" height="4" rx="1"></rect>
        <path d="M9 4H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2"></path>
      </svg>
    </button>
  </div>
  <script>
    const url = __URL__;
    const button = document.getElementById("copy");
    const COPY_ICON = button.innerHTML;
    const DONE_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>';
    const FAIL_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"></path></svg>';

    function flash(state, icon) {
      button.classList.remove("ok", "fail");
      if (state) button.classList.add(state);
      button.innerHTML = icon;
      setTimeout(() => {
        button.classList.remove("ok", "fail");
        button.innerHTML = COPY_ICON;
      }, 1400);
    }

    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(url);
        flash("ok", DONE_ICON);
        return;
      } catch (error) { /* запасной путь */ }

      const area = document.createElement("textarea");
      area.value = url;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      let copied = false;
      try { copied = document.execCommand("copy"); } catch (error) { copied = false; }
      document.body.removeChild(area);
      flash(copied ? "ok" : "fail", copied ? DONE_ICON : FAIL_ICON);
    });
  </script>
</body>
</html>
"""

CARD_STYLES = """
<style>
  .thumb { height: 150px; display: flex; align-items: center; justify-content: center; }
  .thumb img { max-width: 100%; max-height: 150px; width: auto; height: auto;
               display: block; border-radius: 8px; }
  .thumb.tall { height: 240px; }
  .thumb.tall img { max-height: 240px; }
  .card-gap { height: 12px; }
  a.banner-link { display: block; cursor: pointer; }
  a.banner-link:hover img { filter: brightness(1.08); }
</style>
"""


def copy_link_button(url: str) -> None:
    components.html(COPY_BUTTON_TEMPLATE.replace("__URL__", json.dumps(url)), height=40)


def detect_color(url: str) -> tuple[str | None, float | None]:
    try:
        image = images.load_image(url, settings)
    except images.ImageLoadError:
        return None, None
    return colors.center_color(image)


def refresh_colors() -> None:
    with session_scope() as session:
        rows = [
            (banner_id, url)
            for banner_id, url in repo.banners_for_color_refresh(session)
            if url
        ]

    if not rows:
        st.info("Баннеров с картинками пока нет", icon="🗂️")
        return

    progress = st.progress(0.0, text="Пересчитываю цвета…")
    updated = 0
    for index, (banner_id, url) in enumerate(rows, start=1):
        color_hex, hue = detect_color(url)
        with session_scope() as session:
            repo.set_banner_color(session, banner_id, color_hex, hue)
        if color_hex:
            updated += 1
        progress.progress(index / len(rows), text=f"{index} из {len(rows)}")
    progress.empty()
    st.success(f"Цвета обновлены: {updated} из {len(rows)}")


def banner_image_html(
    data: bytes, banner_id: int | None, alt: str, tall: bool = False
) -> str:
    payload = base64.b64encode(data).decode("ascii")
    safe_alt = html_lib.escape(alt or "Баннер", quote=True)
    img = f'<img src="data:image/jpeg;base64,{payload}" alt="{safe_alt}" />'
    shelf = "thumb tall" if tall else "thumb"
    if banner_id is None:
        return f'<div class="{shelf}">{img}</div>'
    return (
        f'<div class="{shelf}"><a class="banner-link" '
        f'href="constructor?banner_id={banner_id}" target="_self" '
        f'title="Открыть в конструкторе">{img}</a></div>'
    )


def card_actions(item) -> None:
    favorite_col, copy_col, edit_col, delete_col = st.columns(
        [1.7, 0.8, 0.8, 0.8], gap="small"
    )
    checked = favorite_col.checkbox(
        "Избранное",
        value=item.is_favorite,
        key=f"favorite_{item.kind}_{item.id}",
    )
    if checked != item.is_favorite:
        with session_scope() as session:
            repo.set_banner_favorite(session, item.id, checked)
        st.rerun()
    with copy_col:
        copy_link_button(item.url or "")
    if edit_col.button(
        "",
        icon=":material/edit:",
        key=f"edit_{item.id}",
        help="Изменить баннер",
        use_container_width=True,
    ):
        st.session_state["gallery_edit"] = item.id
    if delete_col.button(
        "",
        icon=":material/delete:",
        key=f"delete_{item.id}",
        help="Удалить баннер",
        use_container_width=True,
    ):
        st.session_state["gallery_delete"] = item.id


def draw_template_form(
    prefix: str,
    *,
    kind: str,
    initial: dict,
    show_variables: bool = False,
) -> dict:
    """Поля одного типа: картинка, описание, теги."""
    values: dict = {"kind": kind}

    values["url"] = st.text_input(
        "Ссылка на картинку",
        value=initial.get("url") or "",
        placeholder="https://cdn.example.com/banner.jpg",
        key=f"{prefix}_url",
    )
    values["title"] = initial.get("title") or ""
    values["message"] = initial.get("message") or ""
    values["action_text"] = initial.get("action_text") or ""

    if show_variables:
        st.caption("Переменные: " + " ".join(templates.VARIABLES))

    values["description"] = st.text_input(
        "Описание", value=initial.get("description") or "", key=f"{prefix}_desc"
    )
    values["tags"] = st.text_input(
        "Теги через запятую", value=initial.get("tags") or "", key=f"{prefix}_tags"
    )
    return values


def save_template(
    values: dict,
    *,
    template_id: int | None,
    current_color: str | None = None,
    current_hue: float | None = None,
) -> str | None:
    """Создаёт или обновляет баннер. Возвращает текст ошибки, если что-то не так."""
    color_hex, hue = detect_color(values["url"]) if values["url"] else (None, None)
    if color_hex is None and values["url"] and template_id is not None:
        color_hex, hue = current_color, current_hue

    try:
        with session_scope() as session:
            if template_id is None:
                repo.create_banner(
                    session,
                    kind=values["kind"],
                    url=values["url"],
                    description=values["description"],
                    tags=parse_tags(values["tags"]),
                    center_color=color_hex,
                    center_hue=hue,
                )
            else:
                repo.update_banner(
                    session,
                    template_id,
                    kind=values["kind"],
                    url=values["url"],
                    title=values["title"],
                    message=values["message"],
                    action_text=values["action_text"],
                    description=values["description"],
                    tags=parse_tags(values["tags"]),
                    center_color=color_hex,
                    center_hue=hue,
                )
    except repo.ValidationError as exc:
        return str(exc)
    return None


@st.dialog("Новый баннер")
def add_dialog() -> None:
    tabs = st.tabs([templates.kind_label(kind) for kind in templates.IMAGE_KINDS])
    for tab, kind in zip(tabs, templates.IMAGE_KINDS):
        with tab:
            values = draw_template_form(f"add_{kind}", kind=kind, initial={})
            if st.button(
                "Добавить",
                type="primary",
                use_container_width=True,
                key=f"add_submit_{kind}",
            ):
                error = save_template(values, template_id=None)
                if error:
                    st.error(error)
                else:
                    st.toast("Баннер добавлен")
                    st.rerun()


@st.dialog("Изменить баннер")
def edit_dialog(template_id: int) -> None:
    with session_scope() as session:
        banner = repo.get_banner(session, template_id)
        if banner is None:
            st.error("Баннер не найден — возможно, его удалили")
            return
        initial = {
            "kind": banner.kind,
            "url": banner.url,
            "title": banner.title,
            "message": banner.message,
            "action_text": banner.action_text,
            "description": banner.description,
            "tags": ", ".join(tag.name for tag in banner.tags),
        }
        current_color = banner.center_color
        current_hue = banner.center_hue

    current_kind = templates.normalize_kind(initial["kind"])
    tabs = st.tabs([templates.kind_label(kind) for kind in templates.IMAGE_KINDS])
    for tab, kind in zip(tabs, templates.IMAGE_KINDS):
        with tab:
            values = draw_template_form(f"edit_{kind}", kind=kind, initial=initial)
            if st.button(
                "Сохранить",
                type="primary",
                use_container_width=True,
                key=f"edit_submit_{kind}",
            ):
                error = save_template(
                    values,
                    template_id=template_id,
                    current_color=current_color,
                    current_hue=current_hue,
                )
                if error:
                    st.error(error)
                else:
                    st.toast("Изменения сохранены")
                    st.rerun()
    st.caption(f"Текущий тип: {templates.kind_label(current_kind)}")


@st.dialog("Удалить баннер?")
def delete_dialog(template_id: int) -> None:
    with session_scope() as session:
        banner = repo.get_banner(session, template_id)
        if banner is None:
            st.error("Баннер не найден — возможно, его уже удалили")
            return
        description = banner.description
        kind_label = templates.kind_label(banner.kind)

    st.warning("Действие необратимо. Записи истории по этому баннеру останутся.", icon="⚠️")
    st.write(f"{kind_label}. {description}" if description else kind_label)

    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button("Удалить", type="primary", use_container_width=True):
        with session_scope() as session:
            repo.delete_banner(session, template_id)
        st.toast("Баннер удалён")
        st.rerun()
    if cancel_col.button("Отмена", use_container_width=True):
        st.rerun()


def render_grid(
    kind: str,
    *,
    search: str,
    tags,
    sort_mode: str,
    columns_count: int,
    favorites_only: bool,
) -> None:
    """Сетка карточек одного типа со своей пагинацией."""
    page_key = f"gallery_page_{kind}"
    signature = (search.strip().casefold(), tuple(sorted(tags)))
    if st.session_state.get(f"{page_key}_sig") != signature:
        st.session_state[f"{page_key}_sig"] = signature
        st.session_state[page_key] = 1

    page = int(st.session_state.get(page_key, 1) or 1)
    page_size = settings.page_size

    with session_scope() as session:
        items, total = repo.search_banners(
            session,
            search=search,
            tags=tags,
            kinds=[kind],
            favorites_only=favorites_only,
            limit=page_size,
            offset=(page - 1) * page_size,
            sort=sort_mode,
        )

    pages_total = max(1, math.ceil(total / page_size))
    if page > pages_total:
        st.session_state[page_key] = pages_total
        st.rerun()

    if total == 0:
        if favorites_only:
            st.info("В избранном по этому типу пока пусто.", icon="⭐")
        else:
            st.info("Пока пусто. Добавьте баннер кнопкой справа сверху.", icon="🔍")
        return

    columns = st.columns(columns_count, gap="medium")
    for index, item in enumerate(items):
        with columns[index % columns_count]:
            with st.container(border=True):
                data, error = load_thumb(item.url or "", settings.thumb_max_side)
                if data:
                    st.markdown(
                        banner_image_html(data, item.id, item.description or "Баннер"),
                        unsafe_allow_html=True,
                    )
                else:
                    st.warning(error or "Картинка недоступна", icon="⚠️")
                st.markdown('<div class="card-gap"></div>', unsafe_allow_html=True)
                card_actions(item)

    left, middle, right = st.columns([1, 2, 1])
    if left.button("← Назад", disabled=page <= 1, use_container_width=True, key=f"back_{kind}"):
        st.session_state[page_key] = page - 1
        st.rerun()
    middle.markdown(
        f"<div style='text-align:center;padding-top:0.5rem'>"
        f"Страница {page} из {pages_total} · баннеров: {total}</div>",
        unsafe_allow_html=True,
    )
    if right.button(
        "Вперёд →", disabled=page >= pages_total, use_container_width=True, key=f"next_{kind}"
    ):
        st.session_state[page_key] = page + 1
        st.rerun()


st.title("Галерея шаблонов")
st.markdown(CARD_STYLES, unsafe_allow_html=True)

with session_scope() as session:
    usage = repo.tag_usage(session)

counts = {name: uses for name, uses in usage}
used_tags = [name for name, uses in usage if uses > 0]

with st.sidebar:
    st.subheader("Фильтры")
    search = st.text_input(
        "Поиск по описанию", key="gallery_search", placeholder="например, скидка"
    )
    selected_tags = st.multiselect(
        "Теги (точное совпадение)",
        options=used_tags,
        format_func=lambda name: f"{name} ({counts.get(name, 0)})",
        key="gallery_tags",
    )
    st.caption(f"Тегов в каталоге: {len(used_tags)}")

    st.divider()
    columns_count = st.select_slider(
        "Карточек в ряд",
        options=[2, 3, 4, 5],
        value=min(max(settings.gallery_columns, 2), 5),
        key="gallery_columns",
        help="Подберите плотность сетки под ширину окна",
    )
    sort_mode = st.radio(
        "Сортировка",
        options=["color", "new", "old", "length"],
        format_func=lambda value: {
            "color": "по цвету баннера",
            "new": "сначала новые",
            "old": "сначала старые",
            "length": "по длине текста",
        }[value],
        key="gallery_sort",
    )
    with session_scope() as session:
        favorites_total = repo.favorite_banners_count(session)
    favorites_only = st.toggle(
        f"Только избранное ({favorites_total})",
        key="gallery_favorites_only",
        help="Показывает баннеры, отмеченные галочкой «Избранное»",
    )
    if st.button(
        "Пересчитать цвета",
        use_container_width=True,
        help="Заново берёт цвет из центра картинок баннеров",
    ):
        refresh_colors()

toolbar_spacer, toolbar_right = st.columns([5.2, 0.85])
if toolbar_right.button(
    "Добавить баннер", icon=":material/add:", use_container_width=True
):
    add_dialog()

tabs = st.tabs([templates.kind_label(kind) for kind in templates.IMAGE_KINDS])
for tab, kind in zip(tabs, templates.IMAGE_KINDS):
    with tab:
        render_grid(
            kind,
            search=search,
            tags=selected_tags,
            sort_mode=sort_mode,
            columns_count=columns_count,
            favorites_only=favorites_only,
        )

edit_id = st.session_state.pop("gallery_edit", None)
delete_id = st.session_state.pop("gallery_delete", None)

if delete_id is not None:
    delete_dialog(delete_id)
elif edit_id is not None:
    edit_dialog(edit_id)
