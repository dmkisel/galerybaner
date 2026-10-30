"""Загрузка изображений по внешнему URL с дисковым кэшем.

Картинки не хранятся в БД — там только ссылка. Скачанные байты кэшируются на
диске с TTL, чтобы галерея не ходила в сеть на каждый ре-ран Streamlit и не
зависела от доступности чужого CDN.
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageOps

from app.core.config import Settings

USER_AGENT = "GaleryBaner/1.0 (+internal)"
ALLOWED_SCHEMES = {"http", "https"}


class ImageLoadError(RuntimeError):
    """Понятная пользователю ошибка загрузки картинки."""


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _cache_paths(cache_dir: Path, url: str) -> tuple[Path, Path]:
    key = _digest(url)
    return cache_dir / f"{key}.bin", cache_dir / f"{key}.json"


def _host_is_private(host: str) -> bool:
    if not host:
        return True
    if host.lower() in {"localhost", "localhost.localdomain", "ip6-localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _validate_url(url: str, allow_private_hosts: bool) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ImageLoadError("Ссылка должна начинаться с http:// или https://")
    if not parsed.netloc:
        raise ImageLoadError("В ссылке нет имени хоста")
    if not allow_private_hosts and _host_is_private(parsed.hostname or ""):
        raise ImageLoadError("Ссылки на локальные адреса запрещены настройками")
    return url


def _read_cache(cache_bin: Path, cache_meta: Path, ttl_hours: int) -> bytes | None:
    if not (cache_bin.exists() and cache_meta.exists()):
        return None
    age_seconds = time.time() - cache_bin.stat().st_mtime
    if age_seconds > ttl_hours * 3600:
        return None
    try:
        return cache_bin.read_bytes()
    except OSError:
        return None


def _write_cache(cache_bin: Path, cache_meta: Path, url: str, data: bytes, content_type: str) -> None:
    cache_bin.parent.mkdir(parents=True, exist_ok=True)
    tmp_bin = cache_bin.with_suffix(".bin.tmp")
    tmp_meta = cache_meta.with_suffix(".json.tmp")
    tmp_bin.write_bytes(data)
    tmp_meta.write_text(
        json.dumps({"url": url, "content_type": content_type, "fetched_at": time.time()}),
        encoding="utf-8",
    )
    os.replace(tmp_bin, cache_bin)
    os.replace(tmp_meta, cache_meta)


def fetch_bytes(url: str, settings: Settings, force_refresh: bool = False) -> bytes:
    """Байты картинки: из кэша, если свежие, иначе по сети."""
    url = _validate_url(url, settings.allow_private_hosts)
    cache_bin, cache_meta = _cache_paths(settings.cache_dir, url)

    if not force_refresh:
        cached = _read_cache(cache_bin, cache_meta, settings.cache_ttl_hours)
        if cached is not None:
            return cached

    try:
        response = requests.get(
            url,
            timeout=settings.http_timeout,
            stream=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise ImageLoadError(f"Сервер не ответил за {settings.http_timeout} с") from exc
    except requests.HTTPError as exc:
        raise ImageLoadError(f"Сервер вернул ошибку {exc.response.status_code}") from exc
    except requests.RequestException as exc:
        raise ImageLoadError(f"Не удалось скачать картинку: {exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > settings.max_image_bytes:
                raise ImageLoadError(
                    f"Картинка больше {settings.max_image_bytes // (1024 * 1024)} МБ"
                )
            chunks.append(chunk)
    except requests.RequestException as exc:
        raise ImageLoadError(f"Обрыв при скачивании: {exc}") from exc
    finally:
        response.close()

    data = b"".join(chunks)
    if not data:
        raise ImageLoadError("Сервер вернул пустой ответ")

    _assert_decodable(data)
    _write_cache(cache_bin, cache_meta, url, data, content_type)
    return data


def _assert_decodable(data: bytes) -> None:
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
    except Exception as exc:  # Pillow кидает разные типы
        raise ImageLoadError("По ссылке не изображение или файл повреждён") from exc


def load_image(url: str, settings: Settings, force_refresh: bool = False) -> Image.Image:
    """Скачанная картинка в RGBA с учётом EXIF-ориентации."""
    data = fetch_bytes(url, settings, force_refresh=force_refresh)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ImageLoadError("Не удалось открыть изображение") from exc
    return ImageOps.exif_transpose(img).convert("RGBA")


def thumbnail_jpeg(img: Image.Image, max_side: int, quality: int = 85) -> bytes:
    """Компактный JPEG для сетки каталога: 50+ картинок не должны весить десятки МБ."""
    thumb = img.copy()
    thumb.thumbnail((max_side, max_side), Image.LANCZOS)

    if thumb.mode in {"RGBA", "LA", "P"}:
        rgba = thumb.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (18, 22, 28))
        flat.paste(rgba, mask=rgba.split()[-1])
    else:
        flat = thumb.convert("RGB")

    buffer = io.BytesIO()
    flat.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()
