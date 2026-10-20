"""Собирает сообщения медиагруппы (альбома) в один список `album`."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message


class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.7) -> None:
        self.latency = latency
        self._albums: dict[str, list[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        gid = event.media_group_id
        if gid in self._albums:  # не первое сообщение альбома — просто копим
            self._albums[gid].append(event)
            return None

        self._albums[gid] = [event]
        await asyncio.sleep(self.latency)  # ждём остальные части альбома
        data["album"] = sorted(self._albums.pop(gid), key=lambda m: m.message_id)
        return await handler(event, data)
