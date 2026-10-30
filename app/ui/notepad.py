"""Блокнот: текстовые шаблоны, собранные в конструкторе или добавленные вручную."""

from __future__ import annotations

import html as html_lib
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.core import repo, templates
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.texts import escape_markdown, parse_tags

settings = get_settings()

CARD_STYLES = """
<style>
  .badge { display: inline-block; font-size: 10px; letter-spacing: .04em;
           text-transform: uppercase; padding: 2px 8px; border-radius: 999px;
           background: #262E38; color: #A8B3C1; margin-bottom: 6px; }
  .badge.ordinary { background: #3A2E12; color: #F5A524; }
  .badge.popup { background: #12303A; color: #4FC3D9; }
  .badge.push { background: #2A1F3A; color: #B48CF2; }
  .badge.sms { background: #1C3324; color: #5FD08A; }
  .tpl-text { white-space: pre-wrap; color: #E6EAF0; font-size: 14px;
              line-height: 1.45; }
</style>
"""


def badge_html(kind: str) -> str:
    normalized = templates.normalize_kind(kind)
    return f'<span class="badge {normalized}">{templates.kind_short(normalized)}</span>'


def length_caption(kind: str, title: str, message: str) -> str:
    parts = []
    if templates.has_title(kind):
        parts.append(f"Тема {len((title or '').strip())}")
    parts.append(f"Текст {len((message or '').strip())}")
    return " · ".join(parts)


def text_form(prefix: str, *, kind: str, initial: dict) -> dict:
    """Поля текста: тема (кроме СМС), сообщение и теги. Тип задаёт вкладка."""
    kind_value = templates.normalize_kind(kind)

    title = ""
    if templates.has_title(kind_value):
        title = st.text_input(
            "Тема", value=initial.get("title") or "", key=f"{prefix}_title"
        )

    message = st.text_area(
        "Текст",
        value=initial.get("message") or "",
        height=140,
        key=f"{prefix}_message",
    )

    st.caption(length_caption(kind_value, title, message))
    variables = templates.extract_variables(title, message)
    if variables:
        st.caption("Переменные: " + " ".join(variables))

    tags = st.text_input(
        "Теги через запятую", value=initial.get("tags") or "", key=f"{prefix}_tags"
    )

    return {"kind": kind_value, "title": title, "message": message, "tags": tags}


@st.dialog("Новый текст")
def add_dialog() -> None:
    tabs = st.tabs([templates.kind_label(kind) for kind in templates.KINDS])
    for tab, kind in zip(tabs, templates.KINDS):
        with tab:
            values = text_form(f"note_add_{kind}", kind=kind, initial={})
            if st.button(
                "Добавить",
                type="primary",
                use_container_width=True,
                key=f"note_add_submit_{kind}",
            ):
                try:
                    with session_scope() as session:
                        repo.create_text_template(
                            session,
                            kind=kind,
                            title=values["title"],
                            message=values["message"],
                            tags=parse_tags(values["tags"]),
                        )
                except repo.ValidationError as exc:
                    st.error(str(exc))
                else:
                    st.toast("Текст добавлен в Блокнот")
                    st.rerun()


@st.dialog("Изменить текст")
def edit_dialog(template_id: int) -> None:
    with session_scope() as session:
        template = repo.get_text_template(session, template_id)
        if template is None:
            st.error("Текст не найден — возможно, его удалили")
            return
        initial = {
            "title": template.title,
            "message": template.message,
            "kind": template.kind,
            "tags": ", ".join(tag.name for tag in template.tags),
        }

    tabs = st.tabs([templates.kind_label(kind) for kind in templates.KINDS])
    for tab, kind in zip(tabs, templates.KINDS):
        with tab:
            values = text_form(f"note_edit_{kind}", kind=kind, initial=initial)
            if st.button(
                "Сохранить",
                type="primary",
                use_container_width=True,
                key=f"note_edit_submit_{kind}",
            ):
                try:
                    with session_scope() as session:
                        repo.update_text_template(
                            session,
                            template_id,
                            kind=kind,
                            title=values["title"],
                            message=values["message"],
                            tags=parse_tags(values["tags"]),
                        )
                except repo.ValidationError as exc:
                    st.error(str(exc))
                else:
                    st.toast("Изменения сохранены")
                    st.rerun()


@st.dialog("Удалить текст?")
def delete_dialog(template_id: int) -> None:
    st.warning("Текст будет удалён из Блокнота. Действие необратимо.", icon="⚠️")

    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button("Удалить", type="primary", use_container_width=True):
        with session_scope() as session:
            repo.delete_text_template(session, template_id)
        st.toast("Текст удалён")
        st.rerun()
    if cancel_col.button("Отмена", use_container_width=True):
        st.rerun()


st.title("Блокнот")
st.markdown(CARD_STYLES, unsafe_allow_html=True)

with session_scope() as session:
    usage = repo.text_tag_usage(session)

counts = {name: uses for name, uses in usage}
used_tags = [name for name, uses in usage if uses > 0]

with st.sidebar:
    st.subheader("Фильтры")
    selected_kinds = st.multiselect(
        "Тип коммуникации",
        options=list(templates.KINDS),
        format_func=templates.kind_label,
        key="notepad_kinds",
        placeholder="все типы",
    )
    search = st.text_input(
        "Поиск по тексту", key="notepad_search", placeholder="например, скидка"
    )
    selected_tags = st.multiselect(
        "Теги (точное совпадение)",
        options=used_tags,
        format_func=lambda name: f"{name} ({counts.get(name, 0)})",
        key="notepad_tags",
    )
    st.divider()
    with session_scope() as session:
        favorites_total = repo.favorite_texts_count(session)
    favorites_only = st.toggle(
        f"Только избранное ({favorites_total})",
        key="notepad_favorites_only",
        help="Показывает тексты, отмеченные галочкой «Избранное»",
    )
    sort_mode = st.radio(
        "Сортировка",
        options=["new", "old", "length"],
        format_func=lambda value: {
            "new": "сначала новые",
            "old": "сначала старые",
            "length": "по длине текста",
        }[value],
        key="notepad_sort",
    )

signature = (
    search.strip().casefold(),
    tuple(sorted(selected_tags)),
    tuple(sorted(selected_kinds)),
)
if st.session_state.get("notepad_signature") != signature:
    st.session_state["notepad_signature"] = signature
    st.session_state["notepad_page"] = 1

page = int(st.session_state.get("notepad_page", 1) or 1)
page_size = settings.page_size

with session_scope() as session:
    items, total = repo.list_text_templates(
        session,
        search=search,
        tags=selected_tags,
        kinds=selected_kinds,
        favorites_only=favorites_only,
        limit=page_size,
        offset=(page - 1) * page_size,
        sort=sort_mode,
    )

pages_total = max(1, math.ceil(total / page_size))
if page > pages_total:
    st.session_state["notepad_page"] = pages_total
    st.rerun()

_spacer, add_col = st.columns([5.2, 0.85])
if add_col.button("Добавить текст", icon=":material/add:", use_container_width=True):
    add_dialog()

if total == 0:
    st.info(
        "В Блокноте пока пусто. Добавьте текст кнопкой выше или сохраните его "
        "из конструктора.",
        icon="📝",
    )
else:
    for item in items:
        with st.container(border=True):
            content_col, meta_col, actions_col = st.columns([3.4, 0.95, 1.35], gap="medium")

            with content_col:
                st.markdown(badge_html(item.kind), unsafe_allow_html=True)
                if item.title:
                    st.markdown(f"**{escape_markdown(item.title)}**")
                st.markdown(
                    f'<div class="tpl-text">{html_lib.escape(item.message)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            with meta_col:
                st.caption(length_caption(item.kind, item.title, item.message))
                if item.tags:
                    st.caption(" · ".join(tag.name for tag in item.tags))
                variables = templates.extract_variables(item.title, item.message)
                if variables:
                    st.caption("Переменные: " + " ".join(variables))
                st.caption(f"{item.updated_at:%d.%m.%Y}")

            with actions_col:
                open_col, edit_col, delete_col = st.columns(3, gap="small")
                open_col.link_button(
                    "",
                    f"constructor?text_id={item.id}",
                    icon=":material/edit_note:",
                    help="Посмотреть текст на баннере",
                    use_container_width=True,
                )
                if edit_col.button(
                    "",
                    icon=":material/edit:",
                    key=f"notepad_edit_{item.id}",
                    help="Изменить текст",
                    use_container_width=True,
                ):
                    st.session_state["notepad_edit"] = item.id
                if delete_col.button(
                    "",
                    icon=":material/delete:",
                    key=f"notepad_delete_{item.id}",
                    help="Удалить текст",
                    use_container_width=True,
                ):
                    st.session_state["notepad_delete"] = item.id
                checked = st.checkbox(
                    "Избранное",
                    value=item.is_favorite,
                    key=f"favorite_text_{item.id}",
                )
                if checked != item.is_favorite:
                    with session_scope() as session:
                        repo.set_text_favorite(session, item.id, checked)
                    st.rerun()

    left, middle, right = st.columns([1, 2, 1])
    if left.button("← Назад", disabled=page <= 1, use_container_width=True):
        st.session_state["notepad_page"] = page - 1
        st.rerun()
    middle.markdown(
        f"<div style='text-align:center;padding-top:0.5rem'>"
        f"Страница {page} из {pages_total} · текстов: {total}</div>",
        unsafe_allow_html=True,
    )
    if right.button("Вперёд →", disabled=page >= pages_total, use_container_width=True):
        st.session_state["notepad_page"] = page + 1
        st.rerun()

edit_id = st.session_state.pop("notepad_edit", None)
delete_id = st.session_state.pop("notepad_delete", None)

if delete_id is not None:
    delete_dialog(delete_id)
elif edit_id is not None:
    edit_dialog(edit_id)
