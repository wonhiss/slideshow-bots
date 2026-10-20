"""Один активный job на пользователя.

Структура временных файлов:
  temp/{user_id}/photos/      — исходные фото пользователя (живут, пока он не загрузит новые / не выйдет в меню)
  temp/{user_id}/jobs/{id}/   — рабочие файлы одной сборки (кадры, списки, mp4) — удаляются сразу после отправки
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import config

_active: set[int] = set()


class JobBusy(Exception):
    pass


def user_dir(user_id: int) -> Path:
    return config.TEMP_DIR / str(user_id)


def is_active(user_id: int) -> bool:
    return user_id in _active


def _cleanup(job_dir: Path) -> None:
    shutil.rmtree(job_dir, ignore_errors=True)
    for parent in (job_dir.parent, job_dir.parent.parent):  # jobs/, затем temp/{user_id}/ — только если пусты
        try:
            parent.rmdir()
        except OSError:
            pass


def purge_temp() -> None:
    """При старте: FSM в памяти сброшен, значит старые файлы больше никому не нужны."""
    shutil.rmtree(config.TEMP_DIR, ignore_errors=True)
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def user_job(user_id: int):
    if user_id in _active:
        raise JobBusy()
    _active.add(user_id)
    job_dir = user_dir(user_id) / "jobs" / uuid.uuid4().hex[:10]
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield job_dir
    finally:
        _active.discard(user_id)
        await asyncio.to_thread(_cleanup, job_dir)
