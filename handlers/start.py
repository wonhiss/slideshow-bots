from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from handlers.common import edit_or_send, reset_user
from keyboards.inline import sponsors_kb, welcome_kb
from services.subscription import SUB_TEXT, get_unsubscribed

router = Router()

WELCOME_TEXT = (
    "👋 <b>Быстрые слайд-шоу для креативов</b>\n\n"
    f"Загрузите от {config.MIN_PHOTOS} до {config.MAX_PHOTOS} фото — я соберу из них динамичное видео: "
    "вы выберете длину, скорость смены кадров, формат (9:16, 16:9, 1:1, 4:5), фильтр и яркость.\n\n"
    "Нажмите кнопку ниже или сразу отправьте фото."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await reset_user(state, message.from_user.id)
    await message.answer(WELCOME_TEXT, reply_markup=welcome_kb())


@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    missing = await get_unsubscribed(bot, call.from_user.id, use_cache=False)
    if missing:
        await call.answer("❌ Вы подписаны не на все каналы", show_alert=True)
        await edit_or_send(call, SUB_TEXT, sponsors_kb(missing))
        return
    await call.answer("✅ Подписка подтверждена")
    await reset_user(state, call.from_user.id)
    await edit_or_send(call, WELCOME_TEXT, welcome_kb())
