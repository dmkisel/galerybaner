"""Файловое хранилище готовых картинок истории.

В БД лежит только ключ файла, сами PNG — в каталоге `data/history` за томом
Docker. Так история не раздувает базу и переживает удаление баннера.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.png$")


class StorageError(RuntimeError):
    """Файл истории недоступен или ключ неверного формата."""


def save_png(directory: Path, data: bytes) -> str:
    """Пишет PNG и возвращает ключ. Запись атомарная: tmp → rename."""
    directory.mkdir(parents=True, exist_ok=True)
    key = f"{uuid.uuid4().hex}.png"
    tmp_path = directory / f"{key}.tmp"

    tmp_path.write_bytes(data)
    os.replace(tmp_path, directory / key)
    return key


def _resolve(directory: Path, key: str) -> Path:
    # Ключ приходит из БД, но проверяем формат: так исключаем выход за каталог.
    if not KEY_PATTERN.match(key or ""):
        raise StorageError("Некорректный ключ файла истории")
    return directory / key


def read_png(directory: Path, key: str) -> bytes | None:
    """Байты картинки или None, если файла нет."""
    path = _resolve(directory, key)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StorageError(f"Не удалось прочитать файл истории: {exc}") from exc


def delete_file(directory: Path, key: str | None) -> None:
    """Удаляет файл; отсутствие файла ошибкой не считается."""
    if not key:
        return
    try:
        _resolve(directory, key).unlink(missing_ok=True)
    except StorageError:
        # Битый ключ в БД не должен мешать удалению записи.
        return
    except OSError:
        return
