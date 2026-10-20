"""Хранение исходных фото пользователя в temp/{user_id}/photos/."""
from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import config
from services.jobs import is_active, user_dir

if TYPE_CHECKING:
    from aiogram import Bot


def photos_dir(user_id: int) -> Path:
    return user_dir(user_id) / "photos"


def _clear_photos_sync(user_id: int) -> None:
    shutil.rmtree(photos_dir(user_id), ignore_errors=True)
    try:
        user_dir(user_id).rmdir()  # удалится, только если пуст (нет активной сборки)
    except OSError:
        pass


async def clear_photos(user_id: int) -> None:
    await asyncio.to_thread(_clear_photos_sync, user_id)


async def save_photos(bot: "Bot", user_id: int, refs: list[list[str]]) -> list[Path]:
    """refs: [[file_id, suffix], ...] → скачивает в temp/{user_id}/photos/, возвращает пути."""
    d = photos_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    paths = [d / f"{uuid.uuid4().hex[:8]}{suffix}" for _, suffix in refs]
    await asyncio.gather(*(bot.download(fid, destination=p) for (fid, _), p in zip(refs, paths)))
    return paths


def _latest_mtime(path: Path) -> float:
    latest = path.stat().st_mtime
    for root, _, files in os.walk(path):
        for f in files:
            try:
                latest = max(latest, os.stat(os.path.join(root, f)).st_mtime)
            except OSError:
                pass
    return latest


def purge_stale(max_age_sec: float) -> int:
    """Удаляет папки брошенных пользователей (без активной сборки и давно не трогавшиеся)."""
    removed = 0
    if not config.TEMP_DIR.exists():
        return 0
    now = time.time()
    for d in config.TEMP_DIR.iterdir():
        if not d.is_dir() or not d.name.isdigit() or is_active(int(d.name)):
            continue
        try:
            if now - _latest_mtime(d) > max_age_sec:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except OSError:
            pass
    return removed
