"""Доступ к данным. Все запросы к Postgres собраны здесь.

Функции принимают открытую сессию — транзакцией управляет вызывающий код
(в UI это `session_scope`, в тестах — фикстура).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import and_, func, select, union_all
from sqlalchemy.orm import Session

from app.core.models import (
    Banner,
    Preview,
    ShowcaseEntry,
    Tag,
    TextTemplate,
    banner_tags,
    text_template_tags,
)
from app.core.render import (
    WEIGHT_MESSAGE,
    WEIGHT_THEME,
    ZONE_LOWER,
    ZONE_UPPER,
    BannerSpec,
    TextBlock,
)
from app.core.showcase import SHOWCASE_PAGES, ShowcasePage, normalize_page, normalize_slot, raw_page_values
from app.core.templates import has_image, kind_label, kind_short, normalize_kind
from app.core.texts import normalize_tag_key


class ValidationError(ValueError):
    """Ошибка ввода, которую нужно показать пользователю."""


@dataclass(frozen=True)
class BannerBrief:
    """Минимум данных для выпадающих списков и селектора шаблона."""

    id: int
    url: str | None
    description: str
    kind: str = "ordinary"
    title: str = ""
    message: str = ""
    action_text: str = ""
    is_favorite: bool = False

    @property
    def label(self) -> str:
        base = f"#{self.id} · {kind_short(self.kind)}"
        if self.description.strip():
            base += f" · {self.description.strip()}"
        if self.title.strip():
            base += f" · {self.title.strip()}"
        return base


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Ссылка должна быть вида https://example.com/banner.jpg")
    return url


def _find_by_url(session: Session, url: str, exclude_id: int | None = None) -> Banner | None:
    if not url:
        return None
    stmt = select(Banner).where(Banner.url == url)
    if exclude_id is not None:
        stmt = stmt.where(Banner.id != exclude_id)
    return session.scalar(stmt)


def upsert_tags(session: Session, names: list[str]) -> list[Tag]:
    """Находит или создаёт теги. Первое написание определяет отображаемый регистр."""
    tags: list[Tag] = []
    seen: set[str] = set()
    for raw in names:
        key = normalize_tag_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        tag = session.scalar(select(Tag).where(Tag.name_key == key))
        if tag is None:
            tag = Tag(name=" ".join(raw.split()), name_key=key)
            session.add(tag)
            session.flush()
        tags.append(tag)
    return tags


def _validate_template(kind: str, url: str) -> tuple[str, str | None]:
    """Проверяет тип и ссылку: картинка нужна только баннерам."""
    normalized = normalize_kind(kind)
    if not has_image(normalized):
        return normalized, None

    if not (url or "").strip():
        raise ValidationError(f"Для {kind_label(normalized)} нужна ссылка на картинку")
    return normalized, _validate_url(url)


def create_banner(
    session: Session,
    *,
    kind: str = "ordinary",
    url: str = "",
    description: str = "",
    tags: list[str] | None = None,
    title: str = "",
    message: str = "",
    action_text: str = "",
    created_by: str | None = None,
    center_color: str | None = None,
    center_hue: float | None = None,
) -> Banner:
    normalized, image_url = _validate_template(kind, url)
    if _find_by_url(session, image_url or "") is not None:
        raise ValidationError("Шаблон с такой ссылкой уже есть в каталоге")

    banner = Banner(
        kind=normalized,
        url=image_url,
        title=(title or "").strip(),
        message=(message or "").strip(),
        action_text=(action_text or "").strip(),
        description=(description or "").strip(),
        created_by=created_by,
        center_color=center_color if image_url else None,
        center_hue=center_hue if image_url else None,
    )
    banner.tags = upsert_tags(session, tags or [])
    session.add(banner)
    session.flush()
    return banner


def update_banner(
    session: Session,
    banner_id: int,
    *,
    kind: str = "ordinary",
    url: str = "",
    description: str = "",
    tags: list[str] | None = None,
    title: str = "",
    message: str = "",
    action_text: str = "",
    center_color: str | None = None,
    center_hue: float | None = None,
) -> Banner:
    banner = session.get(Banner, banner_id)
    if banner is None:
        raise ValidationError("Шаблон не найден")

    normalized, image_url = _validate_template(kind, url)
    if _find_by_url(session, image_url or "", exclude_id=banner_id) is not None:
        raise ValidationError("Шаблон с такой ссылкой уже есть в каталоге")

    banner.kind = normalized
    banner.url = image_url
    banner.title = (title or "").strip()
    banner.message = (message or "").strip()
    banner.action_text = (action_text or "").strip()
    banner.description = (description or "").strip()
    banner.center_color = center_color if image_url else None
    banner.center_hue = center_hue if image_url else None
    banner.tags = upsert_tags(session, tags or [])
    session.flush()
    return banner


def set_banner_color(
    session: Session, banner_id: int, color: str | None, hue: float | None
) -> None:
    banner = session.get(Banner, banner_id)
    if banner is None:
        return
    banner.center_color = color
    banner.center_hue = hue
    session.flush()


def banners_for_color_refresh(session: Session) -> list[tuple[int, str]]:
    """Шаблоны с картинкой и их ссылки — для пересчёта цвета."""
    rows = session.execute(
        select(Banner.id, Banner.url)
        .where(Banner.url.is_not(None), Banner.url != "")
        .order_by(Banner.id)
    ).all()
    return [(banner_id, url) for banner_id, url in rows]


def delete_banner(session: Session, banner_id: int) -> bool:
    banner = session.get(Banner, banner_id)
    if banner is None:
        return False
    session.delete(banner)
    session.flush()
    return True


def get_banner(session: Session, banner_id: int) -> Banner | None:
    return session.get(Banner, banner_id)


def list_banners_brief(session: Session, kind: str | None = None) -> list[BannerBrief]:
    """Шаблоны для выпадающих списков; kind ограничивает выборку одним типом."""
    stmt = select(
        Banner.id,
        Banner.url,
        Banner.description,
        Banner.kind,
        Banner.title,
        Banner.message,
        Banner.action_text,
        Banner.is_favorite,
    )
    if kind is not None:
        stmt = stmt.where(Banner.kind == normalize_kind(kind))

    rows = session.execute(stmt.order_by(Banner.created_at.desc(), Banner.id.desc())).all()
    return [
        BannerBrief(
            id=row.id,
            url=row.url,
            description=row.description,
            kind=row.kind,
            title=row.title,
            message=row.message,
            action_text=row.action_text,
            is_favorite=row.is_favorite,
        )
        for row in rows
    ]


def tag_usage(session: Session) -> list[tuple[str, int]]:
    """Все теги с числом баннеров — для сайдбара фильтра."""
    stmt = (
        select(Tag.name, func.count(banner_tags.c.banner_id).label("uses"))
        .select_from(Tag)
        .outerjoin(banner_tags, banner_tags.c.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(banner_tags.c.banner_id).desc(), Tag.name)
    )
    return [(name, uses) for name, uses in session.execute(stmt).all()]


def search_banners(
    session: Session,
    *,
    search: str = "",
    tags: tuple[str, ...] | list[str] = (),
    kinds: tuple[str, ...] | list[str] = (),
    favorites_only: bool = False,
    limit: int = 12,
    offset: int = 0,
    sort: str = "color",
) -> tuple[list[Banner], int]:
    """Поиск по описанию + фильтр по тегам (AND) и типам шаблонов.

    sort="color" — по оттенку центра баннера (текстовые — в конце),
    sort="new" — сначала новые,
    sort="old" — сначала давно не использованные (по дате обновления),
    sort="length" — от коротких текстов к длинным.
    """
    conditions = []

    text = (search or "").strip()
    if text:
        conditions.append(Banner.description.ilike(f"%{text}%"))

    kind_values = [normalize_kind(kind) for kind in kinds]
    if kind_values:
        conditions.append(Banner.kind.in_(kind_values))

    if favorites_only:
        conditions.append(Banner.is_favorite.is_(True))

    for raw in tags:
        key = normalize_tag_key(raw)
        if key:
            conditions.append(Banner.tags.any(Tag.name_key == key))

    base = select(Banner)
    counter = select(func.count(Banner.id))
    if conditions:
        base = base.where(and_(*conditions))
        counter = counter.where(and_(*conditions))

    total = int(session.scalar(counter) or 0)
    if sort == "old":
        # Давно не использовались: сначала самый старый updated_at.
        ordering = (Banner.updated_at.asc(), Banner.id.asc())
    elif sort == "new":
        ordering = (Banner.created_at.desc(), Banner.id.desc())
    elif sort == "length":
        ordering = (func.length(Banner.title) + func.length(Banner.message), Banner.id.asc())
    else:
        ordering = (Banner.center_hue.asc().nulls_last(), Banner.id.asc())

    stmt = base.order_by(*ordering).limit(max(1, limit)).offset(max(0, offset))
    return list(session.scalars(stmt).all()), total


def save_preview(
    session: Session,
    *,
    banner_id: int,
    spec: BannerSpec,
    image_key: str | None = None,
) -> Preview:
    if spec.is_empty:
        raise ValidationError("Нечего сохранять: оба поля пустые")
    if session.get(Banner, banner_id) is None:
        raise ValidationError("Баннер не найден")

    preview = Preview(
        banner_id=banner_id,
        image_key=image_key,
        theme_text=spec.theme.text.strip(),
        message_text=spec.message.text.strip(),
        theme_scale=float(spec.theme.text_scale),
        message_scale=float(spec.message.text_scale),
        theme_pos_x=float(spec.theme.pos_x),
        theme_pos_y=float(spec.theme.pos_y),
        message_pos_x=float(spec.message.pos_x),
        message_pos_y=float(spec.message.pos_y),
        max_width=float(spec.theme.max_width),
        stroke_width=float(spec.theme.stroke_width),
        align=spec.theme.align,
        color=spec.theme.color,
    )
    session.add(preview)
    session.flush()
    return preview


def recent_previews(
    session: Session,
    *,
    limit: int = 24,
    favorites_only: bool = False,
    order: str = "new",
    kinds: tuple[str, ...] | list[str] = (),
) -> list[Preview]:
    """История по дате: order="new" — сначала новые, "old" — сначала старые.

    kinds ограничивает выборку каналами (ordinary | popup | push | sms).
    """
    stmt = select(Preview)
    if favorites_only:
        stmt = stmt.where(Preview.is_favorite.is_(True))

    kind_values = [normalize_kind(kind) for kind in kinds]
    if kind_values:
        stmt = stmt.where(Preview.kind.in_(kind_values))

    if order == "old":
        stmt = stmt.order_by(Preview.created_at.asc(), Preview.id.asc())
    else:
        stmt = stmt.order_by(Preview.created_at.desc(), Preview.id.desc())

    return list(session.scalars(stmt.limit(max(1, limit))).all())


def set_preview_favorite(session: Session, preview_id: int, value: bool) -> bool:
    preview = session.get(Preview, preview_id)
    if preview is None:
        return False
    preview.is_favorite = value
    session.flush()
    return True


def delete_preview(session: Session, preview_id: int) -> str | None:
    """Удаляет запись и возвращает ключ файла, чтобы вызывающий удалил картинку."""
    preview = session.get(Preview, preview_id)
    if preview is None:
        return None

    image_key = preview.image_key
    session.delete(preview)
    session.flush()
    return image_key


def favorite_count(session: Session) -> int:
    return int(session.scalar(select(func.count(Preview.id)).where(Preview.is_favorite.is_(True))) or 0)


def set_preview_image_key(session: Session, preview_id: int, image_key: str | None) -> bool:
    preview = session.get(Preview, preview_id)
    if preview is None:
        return False
    preview.image_key = image_key
    session.flush()
    return True


@dataclass(frozen=True)
class ShowcaseCombination:
    """Комбинация из витрины: строки по местам и число клиентов."""

    key: str
    page: str
    clients_count: int
    rows: dict[str, ShowcaseEntry]

    def slot(self, slot_key: str) -> ShowcaseEntry | None:
        return self.rows.get(slot_key)

    def filled_slots(self, page: ShowcasePage) -> int:
        return sum(1 for slot in page.slots if slot.key in self.rows)


def list_showcase_combinations(session: Session, page: str) -> list[ShowcaseCombination]:
    """Читает строки витрины и собирает их в комбинации по `combination_key`."""
    stmt = (
        select(ShowcaseEntry)
        .where(func.lower(func.btrim(ShowcaseEntry.page)).in_(raw_page_values(page)))
        .order_by(
            ShowcaseEntry.clients_count.desc(),
            ShowcaseEntry.combination_key,
            ShowcaseEntry.slot,
        )
    )

    grouped: dict[str, ShowcaseCombination] = {}
    for row in session.scalars(stmt).all():
        slot_key = normalize_slot(row.slot)
        if slot_key is None:
            continue

        bucket = grouped.get(row.combination_key)
        if bucket is None:
            bucket = ShowcaseCombination(
                key=row.combination_key,
                page=page,
                clients_count=row.clients_count,
                rows={},
            )
            grouped[row.combination_key] = bucket
        bucket.rows.setdefault(slot_key, row)

    return list(grouped.values())


def showcase_pages_summary(session: Session) -> dict[str, int]:
    """Сколько комбинаций в таблице по каждой странице."""
    result = {page.key: 0 for page in SHOWCASE_PAGES}
    seen: set[tuple[str, str]] = set()

    rows = session.execute(select(ShowcaseEntry.page, ShowcaseEntry.combination_key)).all()
    for raw_page, combination_key in rows:
        page_key = normalize_page(raw_page)
        if page_key is None or (page_key, combination_key) in seen:
            continue
        seen.add((page_key, combination_key))
        result[page_key] += 1
    return result


def unknown_showcase_values(session: Session) -> tuple[list[str], list[str]]:
    """Значения страниц и мест, которые приложение не знает — подсказка для ETL."""
    rows = session.execute(select(ShowcaseEntry.page, ShowcaseEntry.slot).distinct()).all()
    pages = sorted({raw for raw, _slot in rows if normalize_page(raw) is None})
    slots = sorted({raw for _page, raw in rows if normalize_slot(raw) is None})
    return pages, slots


def showcase_rows_total(session: Session) -> int:
    return int(session.scalar(select(func.count(ShowcaseEntry.id))) or 0)


def preview_to_spec(preview: Preview) -> BannerSpec:
    """Параметры записи истории в модель рендера — для перерисовки картинки."""
    return BannerSpec(
        theme=TextBlock(
            text=preview.theme_text,
            text_scale=float(preview.theme_scale),
            pos_x=float(preview.theme_pos_x),
            pos_y=float(preview.theme_pos_y),
            max_width=float(preview.max_width),
            align=preview.align,
            color=preview.color,
            stroke_width=float(preview.stroke_width),
            weight=WEIGHT_THEME,
            zone=ZONE_UPPER,
        ),
        message=TextBlock(
            text=preview.message_text,
            text_scale=float(preview.message_scale),
            pos_x=float(preview.message_pos_x),
            pos_y=float(preview.message_pos_y),
            max_width=float(preview.max_width),
            align=preview.align,
            color=preview.color,
            stroke_width=float(preview.stroke_width),
            weight=WEIGHT_MESSAGE,
            zone=ZONE_LOWER,
        ),
    )


def recent_texts(
    session: Session,
    *,
    days: int = 30,
    limit: int = 30,
    kind: str = "any",
) -> list[tuple[str, int]]:
    """Тексты за последние N дней по убыванию частоты.

    kind: "theme" — только темы, "message" — только сообщения, "any" — оба.
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=max(1, days))

    theme_rows = select(Preview.theme_text.label("txt"), Preview.created_at.label("ts")).where(
        func.btrim(Preview.theme_text) != ""
    )
    message_rows = select(
        Preview.message_text.label("txt"), Preview.created_at.label("ts")
    ).where(func.btrim(Preview.message_text) != "")

    if kind == "theme":
        rows = theme_rows
    elif kind == "message":
        rows = message_rows
    else:
        rows = union_all(theme_rows, message_rows)

    merged = rows.subquery()
    stmt = (
        select(merged.c.txt, func.count().label("uses"))
        .where(merged.c.ts >= threshold)
        .group_by(merged.c.txt)
        .order_by(func.count().desc(), func.max(merged.c.ts).desc())
        .limit(max(1, limit))
    )
    return [(text, uses) for text, uses in session.execute(stmt).all()]


def save_template_preview(
    session: Session,
    *,
    kind: str,
    title: str = "",
    message: str = "",
    image_key: str | None = None,
    banner_id: int | None = None,
) -> Preview:
    """Сохраняет в историю готовый снимок popup/push/смс.

    Раскладочные поля баннера (масштабы, позиции) для этих типов не имеют
    смысла — пишем нейтральные значения, чтобы история оставалась единой.
    """
    preview = Preview(
        banner_id=banner_id,
        kind=normalize_kind(kind),
        image_key=image_key,
        theme_text=(title or "").strip(),
        message_text=(message or "").strip(),
        theme_scale=0.0,
        message_scale=0.0,
        theme_pos_x=0.5,
        theme_pos_y=0.5,
        message_pos_x=0.5,
        message_pos_y=0.5,
        max_width=0.5,
        stroke_width=0.0,
        align="left",
        color="#000000",
    )
    session.add(preview)
    session.flush()
    return preview


def touch_banner(session: Session, banner_id: int) -> None:
    """Отмечает шаблон использованным: обновляет дату изменения."""
    banner = session.get(Banner, banner_id)
    if banner is None:
        return
    banner.updated_at = func.now()
    session.flush()


def create_text_template(
    session: Session,
    *,
    kind: str = "ordinary",
    title: str = "",
    message: str = "",
    tags: list[str] | None = None,
    source_banner_id: int | None = None,
) -> TextTemplate:
    """Сохраняет текст из конструктора или из Блокнота."""
    if not (title or "").strip() and not (message or "").strip():
        raise ValidationError("Нечего сохранять: текст пустой")

    template = TextTemplate(
        kind=normalize_kind(kind),
        title=(title or "").strip(),
        message=(message or "").strip(),
        source_banner_id=source_banner_id,
    )
    template.tags = upsert_tags(session, tags or [])
    session.add(template)
    session.flush()
    return template


def get_text_template(session: Session, template_id: int) -> TextTemplate | None:
    return session.get(TextTemplate, template_id)


def update_text_template(
    session: Session,
    template_id: int,
    *,
    kind: str,
    title: str = "",
    message: str = "",
    tags: list[str] | None = None,
) -> bool:
    template = session.get(TextTemplate, template_id)
    if template is None:
        return False
    if not (title or "").strip() and not (message or "").strip():
        raise ValidationError("Нечего сохранять: текст пустой")

    template.kind = normalize_kind(kind)
    template.title = (title or "").strip()
    template.message = (message or "").strip()
    template.tags = upsert_tags(session, tags or [])
    session.flush()
    return True


def delete_text_template(session: Session, template_id: int) -> bool:
    template = session.get(TextTemplate, template_id)
    if template is None:
        return False
    session.delete(template)
    session.flush()
    return True


def list_text_templates(
    session: Session,
    *,
    search: str = "",
    tags: tuple[str, ...] | list[str] = (),
    kinds: tuple[str, ...] | list[str] = (),
    favorites_only: bool = False,
    limit: int = 12,
    offset: int = 0,
    sort: str = "new",
) -> tuple[list[TextTemplate], int]:
    """Текстовые шаблоны Блокнота: тип, поиск, теги, сортировка."""
    conditions = []

    kind_values = [normalize_kind(kind) for kind in kinds]
    if kind_values:
        conditions.append(TextTemplate.kind.in_(kind_values))

    if favorites_only:
        conditions.append(TextTemplate.is_favorite.is_(True))

    text = (search or "").strip()
    if text:
        conditions.append(TextTemplate.message.ilike(f"%{text}%"))

    for raw in tags:
        key = normalize_tag_key(raw)
        if key:
            conditions.append(TextTemplate.tags.any(Tag.name_key == key))

    base = select(TextTemplate)
    counter = select(func.count(TextTemplate.id))
    if conditions:
        base = base.where(and_(*conditions))
        counter = counter.where(and_(*conditions))

    total = int(session.scalar(counter) or 0)

    if sort == "length":
        ordering = (
            func.length(TextTemplate.title) + func.length(TextTemplate.message),
            TextTemplate.id.asc(),
        )
    elif sort == "old":
        ordering = (TextTemplate.created_at.asc(), TextTemplate.id.asc())
    else:
        ordering = (TextTemplate.created_at.desc(), TextTemplate.id.desc())

    stmt = base.order_by(*ordering).limit(max(1, limit)).offset(max(0, offset))
    return list(session.scalars(stmt).all()), total


def text_tag_usage(session: Session) -> list[tuple[str, int]]:
    """Теги, которые реально используются в Блокноте."""
    stmt = (
        select(Tag.name, func.count(text_template_tags.c.template_id).label("uses"))
        .select_from(Tag)
        .outerjoin(text_template_tags, text_template_tags.c.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(text_template_tags.c.template_id).desc(), Tag.name)
    )
    return [(name, uses) for name, uses in session.execute(stmt).all()]


def set_banner_favorite(session: Session, banner_id: int, value: bool) -> bool:
    banner = session.get(Banner, banner_id)
    if banner is None:
        return False
    banner.is_favorite = value
    session.flush()
    return True


def set_text_favorite(session: Session, template_id: int, value: bool) -> bool:
    template = session.get(TextTemplate, template_id)
    if template is None:
        return False
    template.is_favorite = value
    session.flush()
    return True


def favorite_banners_count(session: Session, kinds: tuple[str, ...] | list[str] = ()) -> int:
    stmt = select(func.count(Banner.id)).where(Banner.is_favorite.is_(True))
    if kinds:
        stmt = stmt.where(Banner.kind.in_([normalize_kind(kind) for kind in kinds]))
    return int(session.scalar(stmt) or 0)


def favorite_texts_count(session: Session) -> int:
    stmt = select(func.count(TextTemplate.id)).where(TextTemplate.is_favorite.is_(True))
    return int(session.scalar(stmt) or 0)
