"""Конструктор: два поля на баннере — тема и сообщение."""

from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.core import popup, repo, storage, templates
from app.core.config import get_settings, resolve_font_path
from app.core.db import session_scope
from app.core.texts import format_scale, shorten
from app.ui.common import build_spec, render_popup_preview, render_preview

settings = get_settings()

TEXT_PREVIEW_STYLE = """
<style>
  .phone { width: 320px; margin: 0 auto; border-radius: 30px; padding: 12px 12px 18px;
           background: #0F1318; border: 1px solid rgba(255,255,255,0.14);
           box-shadow: 0 16px 40px rgba(0,0,0,0.45); }
  .bar { display: flex; justify-content: space-between; font-size: 11px; color: #7C8797;
         padding: 2px 6px 10px; }
  .screen { background: #171C23; border-radius: 20px; padding: 12px; min-height: 280px; }
  .push { display: flex; gap: 10px; background: rgba(30,37,46,0.96);
          border-radius: 16px; padding: 12px; border: 1px solid rgba(255,255,255,0.08); }
  .push-icon { width: 34px; height: 34px; border-radius: 9px; flex: 0 0 34px;
               background: linear-gradient(135deg, #F5A524, #E5573F); }
  .push-body { min-width: 0; }
  .push-title { color: #E6EAF0; font-weight: 600; font-size: 13px; }
  .push-text { color: #C3CCD8; font-size: 12px; line-height: 1.35; margin-top: 2px; }
  .push-app { color: #7C8797; font-size: 10px; margin-top: 6px; }
  .chat { display: flex; flex-direction: column; align-items: flex-start; }
  .bubble { max-width: 88%; padding: 10px 12px; border-radius: 16px 16px 16px 4px;
            background: #1F262F; color: #E6EAF0; font-size: 13px; line-height: 1.4;
            border: 1px solid rgba(255,255,255,0.06); }
  .bubble-time { font-size: 10px; color: #7C8797; margin-top: 6px; text-align: right; }
  .empty { color: #5B6675; font-size: 12px; }
</style>
"""


def variable_inputs(variables: list[str], prefix: str) -> dict[str, str]:
    """Поля подстановки: слева переменная без скобок, справа значение."""
    values: dict[str, str] = {}
    if not variables:
        return values

    st.caption("Подстановка переменных")
    for variable in variables:
        name = variable.replace("{", "").replace("}", "")
        name_col, value_col = st.columns([1, 1.8], gap="small")
        name_col.markdown(f"`{name}`")
        values[variable] = value_col.text_input(
            name,
            key=f"var_{prefix}_{name}",
            placeholder=templates.VARIABLE_HINTS.get(variable, ""),
            label_visibility="collapsed",
        )
    return values


def length_caption(kind: str, title: str, message: str) -> str:
    """Счётчики символов: без лимитов, просто длины."""
    parts = []
    if templates.has_title(kind):
        parts.append(f"Тема {len((title or '').strip())}")
    parts.append(f"Текст {len((message or '').strip())}")
    return " · ".join(parts)


def phone_preview_html(kind: str, title: str, message: str) -> str:
    """Предпросмотр так, как сообщение выглядит на телефоне."""
    normalized = templates.normalize_kind(kind)
    safe_message = html.escape(message or "").replace("\n", "<br>")
    if not safe_message:
        safe_message = '<span class="empty">текст пустой</span>'

    if normalized == templates.SMS:
        inner = (
            f'<div class="chat"><div class="bubble">{safe_message}'
            f'<div class="bubble-time">сейчас</div></div></div>'
        )
    else:
        safe_title = html.escape(title or "")
        title_html = f'<div class="push-title">{safe_title}</div>' if safe_title else ""
        inner = (
            f'<div class="push"><div class="push-icon"></div>'
            f'<div class="push-body">{title_html}'
            f'<div class="push-text">{safe_message}</div>'
            f'<div class="push-app">Приложение · сейчас</div></div></div>'
        )

    return (
        f"{TEXT_PREVIEW_STYLE}"
        f'<div class="phone"><div class="bar"><span>9:41</span>'
        f"<span>Приложение</span><span>100 %</span></div>"
        f'<div class="screen">{inner}</div></div>'
    )


def render_popup_mode(banner) -> None:
    """Конструктор Popup: тема, сообщение и кнопка на белой подложке."""
    title_key = f"pm_title_{banner.id}"
    message_key = f"pm_message_{banner.id}"
    action_key = f"pm_action_{banner.id}"
    title_scale_key = f"pm_title_scale_{banner.id}"
    message_scale_key = f"pm_message_scale_{banner.id}"

    with session_scope() as session:
        full = repo.get_banner(session, banner.id)
        if full is None:
            st.error("Шаблон не найден")
            return
        image_url = full.url or ""
        initial_title = full.title
        initial_message = full.message
        initial_action = full.action_text or popup.DEFAULT_ACTION

    st.session_state.setdefault(title_key, initial_title)
    st.session_state.setdefault(message_key, initial_message)
    st.session_state.setdefault(action_key, initial_action)
    st.session_state.setdefault(title_scale_key, popup.DEFAULT_TITLE_SCALE * 100)
    st.session_state.setdefault(message_scale_key, popup.DEFAULT_MESSAGE_SCALE * 100)

    form_col, preview_col = st.columns([1, 1.15], gap="large")

    with form_col:
        st.caption(
            "Popup · белая подложка выступает по бокам картинки: тема, сообщение и кнопка"
        )

        title = st.text_input("Тема", key=title_key)
        message = st.text_area("Сообщение", key=message_key, height=120)
        action_text = st.text_input("Текст кнопки", key=action_key)

        st.caption("Размеры шрифтов — доля ширины подложки")
        title_scale = st.slider(
            "Тема — размер, % ширины",
            min_value=2.0,
            max_value=15.0,
            step=0.5,
            key=title_scale_key,
        )
        message_max = max(1.5, title_scale - 0.5)
        if st.session_state.get(message_scale_key, 0) > message_max:
            st.session_state[message_scale_key] = message_max
        message_scale = st.slider(
            "Сообщение — размер, % ширины",
            min_value=1.0,
            max_value=message_max,
            step=0.5,
            key=message_scale_key,
            help="Всегда меньше размера темы",
        )

        if st.button(
            "Сохранить в шаблон",
            use_container_width=True,
            help="Текст уйдёт в Блокнот",
        ):
            try:
                with session_scope() as session:
                    repo.create_text_template(
                        session,
                        kind=templates.POPUP,
                        title=title,
                        message=message,
                        source_banner_id=banner.id,
                    )
            except repo.ValidationError as exc:
                st.error(str(exc))
            else:
                st.success("Текст сохранён в Блокнот")

        if st.button("Сохранить в историю", use_container_width=True):
            snapshot, snapshot_error = render_popup_preview(
                image_url,
                title,
                message,
                action_text,
                title_scale / 100,
                message_scale / 100,
                settings.history_image_max_side,
            )
            if not snapshot:
                st.warning(f"Не удалось отрисовать: {snapshot_error}", icon="⚠️")
            else:
                key = storage.save_png(settings.history_dir, snapshot)
                with session_scope() as session:
                    repo.save_template_preview(
                        session,
                        kind=templates.POPUP,
                        title=title,
                        message=message,
                        image_key=key,
                        banner_id=banner.id,
                    )
                st.success("Сохранено в историю")

    with preview_col:
        image, error = render_popup_preview(
            image_url,
            title,
            message,
            action_text,
            title_scale / 100,
            message_scale / 100,
            settings.preview_max_side,
        )
        if error:
            st.warning(error, icon="⚠️")
        elif image:
            st.image(image)


CHANNEL_STYLE = """
<style>
  .phone { width: 300px; margin: 0 auto; border-radius: 28px; padding: 10px 10px 16px;
           background: #0F1318; border: 1px solid rgba(255,255,255,0.14);
           box-shadow: 0 16px 40px rgba(0,0,0,0.45); }
  .bar { display: flex; justify-content: space-between; font-size: 10px; color: #7C8797;
         padding: 2px 6px 10px; }
  .screen { background: #171C23; border-radius: 20px; padding: 12px; min-height: 240px; }
  .push { display: flex; gap: 10px; background: rgba(30,37,46,0.96);
          border-radius: 16px; padding: 12px; border: 1px solid rgba(255,255,255,0.08); }
  .push-icon { width: 32px; height: 32px; border-radius: 9px; flex: 0 0 32px;
               background: linear-gradient(135deg, #F5A524, #E5573F); }
  .push-title { color: #E6EAF0; font-weight: 600; font-size: 12px; }
  .push-text { color: #C3CCD8; font-size: 11px; line-height: 1.35; margin-top: 2px;
               overflow-wrap: anywhere; }
  .push-app { color: #7C8797; font-size: 10px; margin-top: 6px; }
  .chat { display: flex; }
  .bubble { max-width: 92%; padding: 10px 12px; border-radius: 16px 16px 16px 4px;
            background: #1F262F; color: #E6EAF0; font-size: 12px; line-height: 1.4;
            border: 1px solid rgba(255,255,255,0.06); overflow-wrap: anywhere; }
  .time { font-size: 9px; color: #7C8797; margin-top: 6px; text-align: right; }
</style>
"""


def channel_preview_html(kind: str, title: str, message: str) -> str:
    """Как текст выглядит в канале: пуш-уведомление или СМС в чате."""
    normalized = templates.normalize_kind(kind)
    safe_message = html.escape(message or "").replace("\n", "<br>") or "текст пустой"

    if normalized == templates.SMS:
        inner = (
            f'<div class="chat"><div class="bubble">{safe_message}'
            f'<div class="time">сейчас</div></div></div>'
        )
    else:
        safe_title = html.escape(title or "")
        title_html = f'<div class="push-title">{safe_title}</div>' if safe_title else ""
        inner = (
            f'<div class="push"><div class="push-icon"></div><div>'
            f'{title_html}<div class="push-text">{safe_message}</div>'
            f'<div class="push-app">Приложение · сейчас</div></div></div>'
        )

    return (
        f"{CHANNEL_STYLE}"
        f'<div class="phone"><div class="bar"><span>9:41</span>'
        f"<span>Приложение</span><span>100 %</span></div>"
        f'<div class="screen">{inner}</div></div>'
    )


def render_channel_mode(kind: str, template) -> None:
    """Раздел конструктора для Push и СМС: текст, счётчики и предпросмотр в телефоне."""
    kind = templates.normalize_kind(kind)
    title_key = f"ch_{kind}_title"
    message_key = f"ch_{kind}_message"

    if template is not None and templates.normalize_kind(template.kind) == kind:
        applied_key = f"ch_applied_{template.id}"
        if not st.session_state.get(applied_key):
            st.session_state[title_key] = template.title
            st.session_state[message_key] = template.message
            st.session_state[applied_key] = True

    st.session_state.setdefault(title_key, "")
    st.session_state.setdefault(message_key, "")

    form_col, preview_col = st.columns([1, 1], gap="large")

    with form_col:
        st.caption(f"{templates.kind_label(kind)} · текстовый шаблон без картинки")

        title = st.text_input("Тема", key=title_key) if templates.has_title(kind) else ""
        message = st.text_area("Текст сообщения", key=message_key, height=140)

        variables = templates.extract_variables(title, message)
        variable_values = variable_inputs(variables, f"ch_{kind}")
        rendered_title = templates.substitute_variables(title, variable_values)
        rendered_message = templates.substitute_variables(message, variable_values)

        st.caption(length_caption(kind, rendered_title, rendered_message))

        if st.button("Сохранить в шаблон", type="primary", use_container_width=True):
            try:
                with session_scope() as session:
                    repo.create_text_template(session, kind=kind, title=title, message=message)
            except repo.ValidationError as exc:
                st.error(str(exc))
            else:
                st.success("Текст сохранён в Блокнот")

        st.link_button("Открыть в Блокноте", "/notepad", use_container_width=True)

    with preview_col:
        st.markdown(
            channel_preview_html(kind, rendered_title, rendered_message),
            unsafe_allow_html=True,
        )


st.title("Конструктор")

with session_scope() as session:
    briefs = repo.list_banners_brief(session)
    recent_themes = repo.recent_texts(
        session, days=settings.recent_texts_days, limit=8, kind="theme"
    )
    recent_messages = repo.recent_texts(
        session, days=settings.recent_texts_days, limit=8, kind="message"
    )

by_id = {brief.id: brief for brief in briefs}

requested_param = st.query_params.get("banner_id")
requested_id = int(requested_param) if str(requested_param).isdigit() else None

text_id_param = str(st.query_params.get("text_id", ""))
text_template = None
if text_id_param.isdigit():
    with session_scope() as session:
        text_template = repo.get_text_template(session, int(text_id_param))

kind_options = list(templates.KINDS)

if text_template is not None and not templates.has_image(text_template.kind):
    default_kind = templates.normalize_kind(text_template.kind)
elif requested_id in by_id:
    default_kind = templates.normalize_kind(by_id[requested_id].kind)
elif briefs:
    default_kind = templates.normalize_kind(briefs[0].kind)
else:
    default_kind = templates.ORDINARY

# Подстановку из истории делаем до создания виджетов: после создания Streamlit
# запрещает менять значение через session_state.
for pending_key, state_key in (
    ("pending_theme", "c_theme_text"),
    ("pending_message", "c_message_text"),
):
    pending = st.session_state.pop(pending_key, None)
    if pending is not None:
        st.session_state[state_key] = pending

# Переход из Блокнота на баннер: подставляем сохранённый текст один раз.
if text_template is not None and templates.has_image(text_template.kind):
    applied_key = f"text_applied_{text_id_param}"
    if not st.session_state.get(applied_key):
        st.session_state["c_theme_text"] = text_template.title
        st.session_state["c_message_text"] = text_template.message
        st.session_state[applied_key] = True

st.session_state.setdefault("c_theme_text", "")
st.session_state.setdefault("c_message_text", "")

# Глубокие ссылки (?banner_id=, ?text_id=) один раз переключают тип на нужный.
deep_link_key = f"deep_kind_{requested_id}_{text_id_param}"
if (requested_id is not None or text_id_param) and not st.session_state.get(deep_link_key):
    st.session_state["constructor_kind"] = default_kind
    st.session_state[deep_link_key] = True

kind_key = st.radio(
    "Тип",
    kind_options,
    index=kind_options.index(default_kind),
    format_func=templates.kind_label,
    horizontal=True,
    key="constructor_kind",
)

if not templates.has_image(kind_key):
    render_channel_mode(kind_key, text_template)
    st.stop()

kind_briefs = [
    brief for brief in briefs if templates.normalize_kind(brief.kind) == kind_key
][:3]

if requested_id in by_id and templates.normalize_kind(by_id[requested_id].kind) == kind_key:
    if requested_id not in [brief.id for brief in kind_briefs]:
        kind_briefs = ([by_id[requested_id]] + kind_briefs)[:3]

if not kind_briefs:
    st.info(
        f"Для типа «{templates.kind_label(kind_key)}» ещё нет баннеров — добавьте их в галерее.",
        icon="🖼️",
    )
    st.stop()

banner_id = st.selectbox(
    "Баннер",
    options=[brief.id for brief in kind_briefs],
    format_func=lambda banner_pk: by_id[banner_pk].label,
    key=f"constructor_banner_{kind_key}",
)
banner = by_id[banner_id]

# Отмечаем использование: дата обновления двигается один раз за сессию.
touch_key = f"touched_{banner.id}"
if not st.session_state.get(touch_key):
    with session_scope() as session:
        repo.touch_banner(session, banner.id)
    st.session_state[touch_key] = True

if templates.normalize_kind(banner.kind) == templates.POPUP:
    render_popup_mode(banner)
    st.stop()


controls, preview_area = st.columns([1, 1.1], gap="large")

with controls:
    banner = by_id[banner_id]

    theme_text = st.text_area(
        "Тема",
        key="c_theme_text",
        height=80,
        placeholder="Скидка 30% на всё",
    )
    message_text = st.text_area(
        "Сообщение",
        key="c_message_text",
        height=80,
        placeholder="Только до воскресенья",
    )

    banner_variables = templates.extract_variables(theme_text, message_text)
    variable_values = variable_inputs(banner_variables, "banner")
    render_theme = templates.substitute_variables(theme_text, variable_values)
    render_message = templates.substitute_variables(message_text, variable_values)

    with st.expander("Шрифты", expanded=True):
        theme_scale_percent = st.slider(
            "Тема — масштаб, % высоты",
            min_value=5.0,
            max_value=20.0,
            value=settings.theme_text_scale * 100,
            step=0.5,
            key="c_theme_scale",
        )

        # Сообщение всегда меньше темы на 3 п.п.: верхняя граница едет за темой.
        message_max = max(1.0, theme_scale_percent - settings.message_scale_gap * 100)
        if st.session_state.get("c_message_scale", 0) > message_max:
            st.session_state["c_message_scale"] = message_max
        st.session_state.setdefault(
            "c_message_scale", min(settings.message_text_scale * 100, message_max)
        )
        message_scale_percent = st.slider(
            "Сообщение — масштаб, % высоты",
            min_value=1.0,
            max_value=message_max,
            step=0.5,
            key="c_message_scale",
            help="Всегда меньше темы на 3 п.п. или больше",
        )

        color = st.color_picker("Цвет текста", value=settings.default_color, key="c_color")
        stroke_width = st.slider(
            "Обводка (доля кегля)",
            min_value=0.0,
            max_value=0.12,
            value=0.0,
            step=0.005,
            key="c_stroke",
            help="0 — без обводки; 0.03–0.08 помогает на пёстром фоне",
        )

    with st.expander("Выравнивание", expanded=False):
        align = st.radio(
            "Выравнивание",
            options=["left", "center", "right"],
            index=0,
            horizontal=True,
            key="c_align",
            format_func=lambda value: {
                "left": "по левому краю",
                "center": "по центру",
                "right": "по правому краю",
            }[value],
        )

        banner_width_mm = int(settings.banner_width_mm)
        left_margin_mm = st.slider(
            "Отступ текста от левой границы, мм",
            min_value=0,
            max_value=int(settings.banner_width_mm * 0.4),
            value=int(settings.left_margin_mm),
            step=5,
            key="c_left_margin_mm",
            help=f"Считается для баннера шириной {banner_width_mm} мм",
        )
        margin = left_margin_mm / settings.banner_width_mm
        st.caption(
            f"≈ {margin * 100:.1f} % ширины баннера. Тема и сообщение начинаются "
            "от одной границы."
        )

        st.caption("Положение по вертикали — центр блока, доли высоты баннера.")
        theme_pos_y = st.slider(
            "Тема — по вертикали", min_value=0.0, max_value=1.0,
            value=settings.theme_pos_y, step=0.01, key="c_theme_y",
        )
        message_pos_y = st.slider(
            "Сообщение — по вертикали", min_value=0.0, max_value=1.0,
            value=settings.message_pos_y, step=0.01, key="c_message_y",
        )
        max_width = st.slider(
            "Предел ширины блока",
            min_value=0.1,
            max_value=1.0,
            value=settings.default_max_width,
            step=0.01,
            key="c_max_width",
            help="До какой доли ширины тянется строка, прежде чем перенестись",
        )

    if recent_themes:
        with st.expander("Недавние темы"):
            for index, (recent, uses) in enumerate(recent_themes):
                if st.button(
                    f"{shorten(recent, 40)}  ·  {uses}×",
                    key=f"recent_theme_{index}",
                    use_container_width=True,
                ):
                    st.session_state["pending_theme"] = recent
                    st.rerun()

    if recent_messages:
        with st.expander("Недавние сообщения"):
            for index, (recent, uses) in enumerate(recent_messages):
                if st.button(
                    f"{shorten(recent, 40)}  ·  {uses}×",
                    key=f"recent_message_{index}",
                    use_container_width=True,
                ):
                    st.session_state["pending_message"] = recent
                    st.rerun()

# Общая левая граница: при центрировании блок стоит по центру, при выравнивании
# вправо отступ отсчитывается от правого края.
pos_x = {"left": margin, "center": 0.5, "right": 1.0 - margin}[align]

theme_scale = theme_scale_percent / 100
message_scale = message_scale_percent / 100

spec = build_spec(
    theme_text=render_theme,
    message_text=render_message,
    theme_scale=theme_scale,
    message_scale=message_scale,
    theme_pos_x=pos_x,
    theme_pos_y=theme_pos_y,
    message_pos_x=pos_x,
    message_pos_y=message_pos_y,
    max_width=max_width,
    align=align,
    color=color,
    stroke_width=stroke_width,
)

with preview_area:
    compare = st.toggle(
        "Сравнить масштабы",
        value=False,
        key="c_compare",
        help="Три превью подряд: меньше на шаг N, текущий, больше на шаг N",
    )
    step_percent = settings.compare_step * 100
    if compare:
        step_percent = st.slider(
            "Шаг сравнения, п.п.",
            min_value=0.5,
            max_value=5.0,
            value=step_percent,
            step=0.5,
            key="c_compare_step",
        )
    max_side = settings.preview_max_side

    if compare:
        for delta in (-step_percent / 100, 0.0, step_percent / 100):
            variant = spec.shifted(delta)
            image, error, _ = render_preview(
                banner.url,
                variant.theme.text,
                variant.message.text,
                variant.theme.text_scale,
                variant.message.text_scale,
                variant.theme.pos_x,
                variant.theme.pos_y,
                variant.message.pos_x,
                variant.message.pos_y,
                max_width,
                align,
                color,
                stroke_width,
                max_side,
                settings.max_lines,
            )
            if error:
                st.warning(error, icon="⚠️")
                break
            if delta < 0:
                label = f"меньше на {step_percent:g} п.п."
            elif delta > 0:
                label = f"больше на {step_percent:g} п.п."
            else:
                label = "текущий масштаб"
            st.image(
                image,
                caption=(
                    f"{label}: тема {format_scale(variant.theme.text_scale)} · "
                    f"сообщение {format_scale(variant.message.text_scale)}"
                ),
            )
    else:
        image, error, font_px = render_preview(
            banner.url,
            render_theme,
            render_message,
            theme_scale,
            message_scale,
            pos_x,
            theme_pos_y,
            pos_x,
            message_pos_y,
            max_width,
            align,
            color,
            stroke_width,
            max_side,
            settings.max_lines,
        )
        if error:
            st.warning(error, icon="⚠️")
        elif image:
            caption = (
                f"Тема {format_scale(theme_scale)} · сообщение {format_scale(message_scale)}"
            )
            if font_px:
                caption += f" · кегль темы на оригинале ≈ {font_px} px"
            st.image(image, caption=caption)

    save_col, history_col = st.columns(2, gap="medium")

    if save_col.button(
        "Сохранить в шаблон",
        disabled=spec.is_empty,
        use_container_width=True,
        help="Текст уйдёт в Блокнот",
    ):
        try:
            with session_scope() as session:
                repo.create_text_template(
                    session,
                    kind=templates.ORDINARY,
                    title=theme_text,
                    message=message_text,
                    source_banner_id=banner.id,
                )
        except repo.ValidationError as exc:
            st.error(str(exc))
        else:
            st.success("Текст сохранён в Блокнот")

    if history_col.button(
        "Сохранить в историю",
        type="primary",
        disabled=spec.is_empty,
        use_container_width=True,
    ):
        # Для истории рендерим отдельно и крупнее: картинка должна быть читаемой.
        history_image, history_error, _ = render_preview(
            banner.url,
            theme_text,
            message_text,
            theme_scale,
            message_scale,
            pos_x,
            theme_pos_y,
            pos_x,
            message_pos_y,
            max_width,
            align,
            color,
            stroke_width,
            settings.history_image_max_side,
            settings.max_lines,
        )
        image_key = None
        if history_image:
            image_key = storage.save_png(settings.history_dir, history_image)

        with session_scope() as session:
            repo.save_preview(
                session, banner_id=banner.id, spec=spec, image_key=image_key
            )

        if history_error or image_key is None:
            st.warning(
                f"Сохранено без картинки: {history_error or 'рендер не удался'}",
                icon="⚠️",
            )
        else:
            st.success("Баннер сохранён в историю")
