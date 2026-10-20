"""Общие хелперы для хендлеров."""
from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

import config
from services.storage import clear_photos


async def reset_user(state: FSMContext, user_id: int) -> None:
    """Полный сброс: состояние FSM + сохранённые фото пользователя на диске."""
    await state.clear()
    await clear_photos(user_id)


async def edit_or_send(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    """Редактирует сообщение с кнопкой; если оно медиа (видео) или правка невозможна —
    отправляет новое сообщение, не трогая оригинал."""
    msg = call.message
    if not isinstance(msg, Message):
        return
    if msg.text is None:
        await msg.answer(text, reply_markup=kb)
        return
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        await msg.answer(text, reply_markup=kb)


def image_ref(m: Message) -> list[str] | None:
    """[file_id, suffix] для фото или картинки-документа."""
    if m.photo:
        return [m.photo[-1].file_id, ".jpg"]
    if m.document and (m.document.mime_type or "").startswith("image/"):
        suffix = Path(m.document.file_name or "").suffix.lower() or ".jpg"
        return [m.document.file_id, suffix]
    return None


async def _retry(make_call):
    for _ in range(3):
        try:
            return await make_call()
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
    return await make_call()


async def send_video(
    bot: Bot, chat_id: int, path: Path, *, caption: str, width: int, height: int, duration: int,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    """Видео (или файл без пересжатия при SEND_AS_DOCUMENT=1) с кнопками прямо под ним."""
    if config.SEND_AS_DOCUMENT:
        await _retry(lambda: bot.send_document(
            chat_id, FSInputFile(path, filename=path.name), caption=caption,
            reply_markup=reply_markup, disable_content_type_detection=True))
    else:
        await _retry(lambda: bot.send_video(
            chat_id, FSInputFile(path, filename=path.name), caption=caption, width=width,
            height=height, duration=duration, supports_streaming=True, reply_markup=reply_markup))
