"""История: готовые снимки шаблонов, разложенные по каналам."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.core import repo, storage, templates
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.texts import format_scale
from app.ui.common import render_preview

settings = get_settings()


@st.cache_data(show_spinner=False, ttl=3600, max_entries=400)
def load_history_image(key: str) -> bytes | None:
    """Готовый PNG из файлового хранилища истории."""
    try:
        return storage.read_png(settings.history_dir, key)
    except storage.StorageError:
        return None


@st.dialog("Удалить из истории?")
def delete_dialog(preview_id: int) -> None:
    st.warning("Картинка и параметры макета будут удалены. Действие необратимо.", icon="⚠️")

    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button("Удалить", type="primary", use_container_width=True):
        with session_scope() as session:
            image_key = repo.delete_preview(session, preview_id)
        storage.delete_file(settings.history_dir, image_key)
        st.toast("Запись удалена из истории")
        st.rerun()
    if cancel_col.button("Отмена", use_container_width=True):
        st.rerun()


def restore_images(rows: list) -> None:
    """Дорисовывает картинки для записей, сохранённых до появления image_key."""
    progress = st.progress(0.0, text="Перерисовываю карточки…")
    restored = 0
    for index, preview in enumerate(rows, start=1):
        if preview.banner is not None:
            image, _error, _ = render_preview(
                preview.banner.url,
                preview.theme_text,
                preview.message_text,
                float(preview.theme_scale),
                float(preview.message_scale),
                float(preview.theme_pos_x),
                float(preview.theme_pos_y),
                float(preview.message_pos_x),
                float(preview.message_pos_y),
                float(preview.max_width),
                preview.align,
                preview.color,
                float(preview.stroke_width),
                settings.history_image_max_side,
                settings.max_lines,
            )
            if image:
                key = storage.save_png(settings.history_dir, image)
                with session_scope() as session:
                    repo.set_preview_image_key(session, preview.id, key)
                restored += 1
        progress.progress(index / len(rows), text=f"{index} из {len(rows)}")

    progress.empty()
    st.success(f"Восстановлено картинок: {restored} из {len(rows)}")
    st.rerun()


def render_cards(previews: list) -> None:
    columns = st.columns(3, gap="medium")
    for index, preview in enumerate(previews):
        with columns[index % 3]:
            with st.container(border=True):
                image = load_history_image(preview.image_key) if preview.image_key else None
                if image:
                    st.image(image)
                else:
                    st.warning("Картинка не сохранена", icon="🖼️")

                preview_kind = templates.normalize_kind(preview.kind)
                if preview_kind == templates.ORDINARY:
                    st.caption(
                        f"Тема {format_scale(preview.theme_scale)} · "
                        f"сообщение {format_scale(preview.message_scale)} · "
                        f"{preview.created_at:%d.%m.%Y %H:%M}"
                    )
                else:
                    st.caption(f"{preview.created_at:%d.%m.%Y %H:%M}")

                star_col, delete_col, open_col = st.columns(3, gap="small")
                if star_col.button(
                    "",
                    icon=":material/star:" if preview.is_favorite else ":material/star_border:",
                    key=f"favorite_{preview.id}",
                    help="Убрать из избранного" if preview.is_favorite else "Добавить в избранное",
                    use_container_width=True,
                ):
                    with session_scope() as session:
                        repo.set_preview_favorite(session, preview.id, not preview.is_favorite)
                    st.rerun()

                if delete_col.button(
                    "",
                    icon=":material/delete:",
                    key=f"delete_{preview.id}",
                    help="Удалить из истории",
                    use_container_width=True,
                ):
                    st.session_state["history_delete"] = preview.id

                if preview.banner_id is not None:
                    open_col.link_button(
                        "",
                        f"constructor?banner_id={preview.banner_id}",
                        icon=":material/open_in_new:",
                        help="Открыть в конструкторе",
                        use_container_width=True,
                    )


st.title("История")

with session_scope() as session:
    favorites_total = repo.favorite_count(session)
    all_previews = repo.recent_previews(
        session,
        limit=settings.history_limit * len(templates.KINDS),
        favorites_only=bool(st.session_state.get("history_favorites_only", False)),
    )

controls_left, controls_right = st.columns([2, 1], gap="medium")
with controls_left:
    order = st.radio(
        "Сортировка по дате",
        options=["new", "old"],
        format_func=lambda value: "сначала новые" if value == "new" else "сначала старые",
        horizontal=True,
        key="history_order",
    )
with controls_right:
    favorites_only = st.toggle(
        f"Только избранное ({favorites_total})",
        key="history_favorites_only",
    )

missing_images = [
    preview for preview in all_previews if not preview.image_key and preview.banner is not None
]
if missing_images:
    if st.button(
        f"Восстановить картинки ({len(missing_images)})",
        icon=":material/refresh:",
        help="Дорисовать карточки, сохранённые до появления картинок в истории",
    ):
        restore_images(missing_images)

tabs = st.tabs([templates.kind_label(kind) for kind in templates.KINDS])
for tab, kind in zip(tabs, templates.KINDS):
    with tab:
        with session_scope() as session:
            previews = repo.recent_previews(
                session,
                limit=settings.history_limit,
                favorites_only=favorites_only,
                order=order,
                kinds=[kind],
            )

        if not previews:
            if favorites_only:
                st.info("В избранном по этому каналу пока пусто.", icon="⭐")
            else:
                st.info("По этому каналу записей ещё нет.", icon="🕘")
            continue

        render_cards(previews)

delete_id = st.session_state.pop("history_delete", None)
if delete_id is not None:
    delete_dialog(delete_id)
