"""Подхватывает всё, что не обработали остальные роутеры (подключается последним)."""
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.common import edit_or_send
from handlers.start import WELCOME_TEXT
from keyboards.inline import welcome_kb

router = Router()


@router.message(StateFilter(None))
async def idle_message(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=welcome_kb())


@router.message()
async def unexpected_message(message: Message) -> None:
    await message.answer("Не понял 🤔 Используйте кнопки под сообщением или /start, чтобы начать заново.")


@router.callback_query()
async def stale_callback(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer("Это действие сейчас недоступно.")
    if await state.get_state() is None:
        await edit_or_send(call, WELCOME_TEXT, welcome_kb())
