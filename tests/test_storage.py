"""Тесты файлового хранилища истории."""

from __future__ import annotations

import pytest

from app.core import storage

VALID_KEY = "0" * 32 + ".png"


def test_save_and_read_roundtrip(tmp_path) -> None:
    data = b"\x89PNG\r\n\x1a\n fake image"

    key = storage.save_png(tmp_path, data)

    assert storage.read_png(tmp_path, key) == data


def test_keys_are_unique(tmp_path) -> None:
    first = storage.save_png(tmp_path, b"a")
    second = storage.save_png(tmp_path, b"b")

    assert first != second


def test_missing_file_returns_none(tmp_path) -> None:
    assert storage.read_png(tmp_path, VALID_KEY) is None


def test_foreign_key_is_rejected(tmp_path) -> None:
    with pytest.raises(storage.StorageError):
        storage.read_png(tmp_path, "../secret.png")
    with pytest.raises(storage.StorageError):
        storage.read_png(tmp_path, "")


def test_delete_removes_file(tmp_path) -> None:
    key = storage.save_png(tmp_path, b"data")

    storage.delete_file(tmp_path, key)

    assert storage.read_png(tmp_path, key) is None


def test_delete_is_idempotent(tmp_path) -> None:
    storage.delete_file(tmp_path, VALID_KEY)
    storage.delete_file(tmp_path, None)


def test_no_temp_files_left(tmp_path) -> None:
    storage.save_png(tmp_path, b"x")

    assert not list(tmp_path.glob("*.tmp"))
