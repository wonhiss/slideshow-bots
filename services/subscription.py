from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

import config
from config import Sponsor

log = logging.getLogger(__name__)

SUB_TEXT = (
    "🔒 <b>Для доступа к боту подпишитесь на каналы спонсоров</b>\n\n"
    "После подписки нажмите «✅ Проверить подписку»."
)

_cache: dict[int, float] = {}


async def _is_member(bot: Bot, sponsor: Sponsor, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(sponsor.chat_id, user_id)
    except TelegramAPIError as e:
        # Бот не админ в канале / неверный ID — не блокируем людей из-за ошибки конфигурации
        log.warning("Не удалось проверить %s (%s): %s", sponsor.title, sponsor.chat_id, e)
        return True
    if m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return True
    if m.status == ChatMemberStatus.RESTRICTED:
        return bool(getattr(m, "is_member", False))
    return False


async def get_unsubscribed(bot: Bot, user_id: int, use_cache: bool = True) -> list[Sponsor]:
    if not config.SPONSORS or user_id in config.ADMIN_IDS:
        return []
    now = time.monotonic()
    if use_cache and now - _cache.get(user_id, -1e9) < config.SUB_CACHE_TTL:
        return []
    results = await asyncio.gather(*(_is_member(bot, s, user_id) for s in config.SPONSORS))
    missing = [s for s, ok in zip(config.SPONSORS, results) if not ok]
    if missing:
        _cache.pop(user_id, None)
    else:
        _cache[user_id] = now
    return missing
