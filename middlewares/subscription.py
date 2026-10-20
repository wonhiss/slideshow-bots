"""ОП: пока пользователь не подписан на всех спонсоров — дальше /start он не пройдёт."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from keyboards.inline import sponsors_kb
from services.subscription import SUB_TEXT, get_unsubscribed


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or (isinstance(event, CallbackQuery) and event.data == "check_sub"):
            return await handler(event, data)

        missing = await get_unsubscribed(data["bot"], user.id)
        if not missing:
            return await handler(event, data)

        kb = sponsors_kb(missing)
        if isinstance(event, Message):
            await event.answer(SUB_TEXT, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.answer("Сначала подпишитесь на каналы спонсоров", show_alert=True)
            if isinstance(event.message, Message):
                await event.message.answer(SUB_TEXT, reply_markup=kb)
        return None
